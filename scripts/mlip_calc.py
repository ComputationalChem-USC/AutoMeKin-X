#!/usr/bin/env python3
"""
MLIP calculator for AutoMeKin HL and LL calculations.

Single mode:
  mlip_calc.py tsopt|minopt <xyzfile> <model> <models_dir> <charge> <mult>

Batch mode (loads model once, processes all entries in inputs.db):
  mlip_calc.py batch tsopt|minopt|irc <dir> <model> <models_dir> <charge> <mult>

Name-based calctype dispatch in batch mode:
  min*  → minopt   (min0, minf_*, minr_*)
  ircf* → ircf     (IRC forward)
  ircr* → ircr     (IRC reverse)
  ts*   → tsopt (or whatever calctype is given on the command line)

LL reactive-sampling modes (used by amk.sh when LowLevel is mlip):
  mlip_calc.py md <xyzfile> <model> <models_dir> <charge> <mult> <temp_K> <duration_fs> [timestep_fs]
      NVE trajectory from Maxwell-Boltzmann initial velocities at temp_K,
      written as a plain multi-frame XYZ (<name>_traj.xyz, ~1 frame/fs) so it
      can be piped through snapshots_mopac.sh into bbfs.exe unchanged.

  mlip_calc.py partial_opt <xyzfile> <frozen_csv> <model> <models_dir> <charge> <mult>
      Relaxes every atom NOT listed in <frozen_csv> (comma-separated, 1-based,
      matching the fort.NNN convention bbfs.exe/amk.sh already use for other
      programs) while holding the listed ones fixed. Writes <name>_popt.xyz.
      This is a plain constrained minimization (FIRE), not a saddle search;
      feed the result to "tsopt" to actually locate the TS.

  mlip_calc.py dihedral_scan <xyzfile> <a1,a2,a3,a4> <dihed0_deg> <model> <models_dir> <charge> <mult> [npoints] [step_deg]
      Relaxed torsional scan (used by tors.sh's mlip branch): npoints steps
      of step_deg starting at dihed0_deg, each relaxed with that one dihedral
      fixed. Writes tors.out in the same text format tors.sh's qcore branch
      already produces, so the shared local-maximum finder there is unchanged.

Persistent-server mode (loads model once, then services jobs one at a time
read from a fifo -- used by amk.sh for the UMA path, where model loading is
~80% of a single call's wall time; not wired up for mace, whose checkpoint
loads in under a second so there is nothing to amortize):
  mlip_calc.py serve <req_fifo> <resp_fifo> <model> <models_dir> <charge> <mult>
      Each line read from req_fifo is "<calctype> <args...>", the same
      tail normally passed on the command line for md/partial_opt/tsopt/minopt.
      Writes "DONE" or "ERROR: <msg>" to resp_fifo after each job. A "QUIT"
      line ends the loop.

Supported models: uma, mace
"""
import os

# Set before any ML library is imported (jaxlib/absl read these at load time).
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')  # silence XLA/absl C++ logs (cpu_aot_loader, etc.)
os.environ.setdefault('JAX_PLATFORMS', 'cpu')        # skip GPU probing; jax is only an indirect dep here, unused for compute

import re
import sys
import sqlite3
import traceback
import warnings
import logging
from pathlib import Path

import numpy as np
from ase.io import read
from ase.units import Hartree, kcal, mol

import torch
torch.set_num_threads(1)

logging.getLogger().setLevel(logging.ERROR)
warnings.filterwarnings('ignore', message="Can't initialize NVML")
warnings.filterwarnings('ignore', category=FutureWarning, module='ase.optimize.optimize')
warnings.filterwarnings('ignore', message=r".*weights_only.*")

# IRC parameters
IRC_DX    = 0.08   # amu^0.5 * Å, step size along IRC
IRC_ETA   = 1e-4
IRC_GAMMA = 0.4
IRC_FMAX  = 0.01   # eV/Å — looser than TS opt to walk the full IRC path
IRC_STEPS = 1000

# Post-minopt imaginary-frequency check. Below this magnitude, a negative
# frequency is treated as Eckart-projection numerical noise (e.g. extra
# near-zero directions left over when a "product" is actually several
# weakly-interacting dissociated fragments, for which the 6 global T+R modes
# removed by _project_trans_rot aren't the full story) rather than a genuine
# unstable mode. Above it, the structure is not accepted as a true minimum.
MIN_IMAG_NOISE_CM   = 50.0
MIN_IMAG_MAX_RETRY  = 3
MIN_IMAG_DISPLACE_A = 0.3  # Å, step along the imaginary mode before re-relaxing


def get_device():
    if not torch.cuda.is_available():
        return 'cpu'
    props = torch.cuda.get_device_properties(0)
    # PyTorch 2.7+ requires compute capability >= 7.0 (sm_70)
    if props.major < 7:
        print(
            f"WARNING: GPU {props.name} has compute capability sm_{props.major}{props.minor}, "
            f"which is below the minimum sm_70 required by this PyTorch version. "
            f"Falling back to CPU.",
            flush=True
        )
        return 'cpu'
    return 'cuda'


def load_calculator(model_name, models_dir):
    device = get_device()
    models_path = Path(models_dir)

    if model_name == 'uma':
        from fairchem.core import FAIRChemCalculator, pretrained_mlip
        from omegaconf import OmegaConf
        model_path = models_path / 'uma-m-1p1.pt'
        refs_path  = models_path / 'uma-m-1p1_atom_refs.yaml'
        if not model_path.exists():
            raise FileNotFoundError(f"UMA model not found: {model_path}")
        atom_refs = OmegaConf.load(refs_path) if refs_path.exists() else None
        pred_unit = pretrained_mlip.load_predict_unit(str(model_path), device=device,
                                                      atom_refs=atom_refs)
        return FAIRChemCalculator(pred_unit, task_name='omol')

    elif model_name == 'mace':
        from mace.calculators import MACECalculator
        model_path = models_path / 'MACE-omol-0-extra-large-1024.model'
        if not model_path.exists():
            raise FileNotFoundError(f"MACE model not found: {model_path}")
        return MACECalculator(
            model_paths=str(model_path), device=device, default_dtype='float32'
        )

    else:
        raise ValueError(f"Unknown model '{model_name}'. Supported: uma, mace")


def run_tsopt(atoms, name, fmax=0.005, steps=500):
    from sella import Sella
    print(f"  TS opt with Sella (fmax={fmax} eV/Ang, max_steps={steps})", flush=True)
    dyn = Sella(atoms, order=1, logfile=f'{name}_sella.log', trajectory=f'{name}.traj')
    converged = dyn.run(fmax=fmax, steps=steps)
    print(f"  Steps: {dyn.nsteps}, Converged: {converged}", flush=True)
    return converged


def run_minopt(atoms, name, fmax=0.005, steps=500):
    from sella import Sella
    print(f"  Min opt with Sella (fmax={fmax} eV/Ang, max_steps={steps})", flush=True)
    dyn = Sella(atoms, order=0, logfile=f'{name}_sella.log', trajectory=f'{name}.traj')
    converged = dyn.run(fmax=fmax, steps=steps)
    print(f"  Steps: {dyn.nsteps}, Converged: {converged}", flush=True)
    return converged


def run_minopt_verified(atoms, name, fmax=0.005, steps=500):
    """Optimize to a minimum, then check via frequency analysis that no real
    (non-noise) imaginary mode remains. A minimum with a genuine imaginary
    frequency isn't actually a minimum -- if one shows up, displace the
    geometry along that mode and re-relax, up to MIN_IMAG_MAX_RETRY times,
    before giving up.

    Returns (converged, freqs_cm, modes, zpe_eV, vib, is_true_min)."""
    converged = run_minopt(atoms, name, fmax=fmax, steps=steps)
    freqs_cm, modes, zpe_eV, vib = compute_frequencies(atoms, f"{name}_vib")

    attempt = 0
    while freqs_cm.size and freqs_cm[0] < -MIN_IMAG_NOISE_CM and attempt < MIN_IMAG_MAX_RETRY:
        attempt += 1
        print(f"  Real imaginary mode ({freqs_cm[0]:.1f} cm^-1) after min opt -- "
              f"displacing along it and re-relaxing (retry {attempt}/{MIN_IMAG_MAX_RETRY})",
              flush=True)
        disp = np.asarray(modes[0])
        disp = disp / np.linalg.norm(disp)
        vib.clean()
        atoms.positions = atoms.positions + MIN_IMAG_DISPLACE_A * disp
        converged = run_minopt(atoms, name, fmax=fmax, steps=steps)
        freqs_cm, modes, zpe_eV, vib = compute_frequencies(atoms, f"{name}_vib")

    is_true_min = not (freqs_cm.size and freqs_cm[0] < -MIN_IMAG_NOISE_CM)
    if not is_true_min:
        print(f"  WARNING: {name} still has an imaginary mode ({freqs_cm[0]:.1f} cm^-1) "
              f"after {MIN_IMAG_MAX_RETRY} retries; not accepting as a converged minimum",
              flush=True)
    return converged, freqs_cm, modes, zpe_eV, vib, is_true_min


def run_irc(atoms, name, direction, dx=IRC_DX, eta=IRC_ETA, gamma=IRC_GAMMA,
            fmax=IRC_FMAX, steps=IRC_STEPS):
    from sella import IRC

    # Sella IRC checks gradient_converged() before taking any step, so a
    # well-converged TS (forces < fmax) would stop immediately at step 0.
    # Force at least one kick along the imaginary mode before allowing
    # convergence to be declared.
    class _IRC(IRC):
        def gradient_converged(self, gradient):
            if self.nsteps == 0:
                return False
            return super().gradient_converged(gradient)

    print(f"  IRC {direction} with Sella (dx={dx}, fmax={fmax} eV/Ang, max_steps={steps})",
          flush=True)
    dyn = _IRC(atoms, trajectory=f'{name}.traj', dx=dx, eta=eta, gamma=gamma,
               keep_going=True)
    converged = dyn.run(fmax=fmax, steps=steps, direction=direction)
    print(f"  Steps: {dyn.nsteps}, Converged: {converged}", flush=True)
    return converged


def run_md(atoms, name, temp_K, duration_fs, timestep_fs=0.5):
    """NVE trajectory from Maxwell-Boltzmann initial velocities.

    Writes a plain multi-frame XYZ (element x y z, no extra columns) at
    ~1 frame/fs, matching the frame-per-fs convention the rest of AMK's LL
    pipeline (irange, nfs, snapshots_mopac.sh, bbfs.exe) already assumes.

    The input geometry is already relaxed (opt_start/sel_mol.sh optimize it
    before amk.sh ever calls this), so at t=0 all of the assigned thermal
    energy is kinetic and none is potential. Under NVE that energy
    equilibrates between the two over the first several vibrational periods,
    so the time-averaged temperature the trajectory actually samples ends up
    well below temp_K -- roughly half, in the harmonic-oscillator limit
    (virial theorem). FAIR's own UMA MD example initializes at 2x the target
    temperature for exactly this reason; the same factor is used here so
    temp_K (which callers set from amk.dat's `temp`) matches the intended
    excitation instead of silently under-driving the reactive sampling."""
    from ase.md.velocitydistribution import MaxwellBoltzmannDistribution, Stationary, ZeroRotation
    from ase.md.verlet import VelocityVerlet
    from ase import units as ase_units

    EQUIPARTITION_FACTOR = 2.0
    MaxwellBoltzmannDistribution(atoms, temperature_K=temp_K * EQUIPARTITION_FACTOR)
    Stationary(atoms)
    if len(atoms) > 2:
        ZeroRotation(atoms)

    dyn = VelocityVerlet(atoms, timestep=timestep_fs * ase_units.fs)
    dump_every = max(1, round(1.0 / timestep_fs))   # ~1 frame per fs
    nsteps = max(1, round(duration_fs / timestep_fs))

    traj_path = f"{name}_traj.xyz"

    def dump(f):
        symbols = atoms.get_chemical_symbols()
        positions = atoms.get_positions()
        f.write(f"{len(atoms)}\n\n")
        for sym, pos in zip(symbols, positions):
            f.write(f"{sym} {pos[0]:14.8f} {pos[1]:14.8f} {pos[2]:14.8f}\n")

    with open(traj_path, 'w') as f:
        dump(f)
        for step in range(nsteps):
            dyn.run(1)
            if (step + 1) % dump_every == 0:
                dump(f)

    return traj_path


def run_partial_opt(atoms, name, frozen_indices, fmax=0.05, steps=300):
    """Relax everything except frozen_indices (0-based). Not a saddle search
    -- this only gives a better-conditioned starting point for a subsequent
    TS search, mirroring what the mopac/qcore partial-opt step already does."""
    from ase.constraints import FixAtoms
    from ase.optimize import FIRE
    if frozen_indices:
        atoms.set_constraint(FixAtoms(indices=frozen_indices))
    dyn = FIRE(atoms, logfile=f'{name}_popt.log')
    converged = dyn.run(fmax=fmax, steps=steps)
    return converged


def run_dihedral_scan(atoms, dihedral_indices, dihed0, npoints=36, step_deg=10.0,
                       fmax=0.05, steps=300):
    """Relaxed dihedral scan used by tors.sh to locate torsional TSs.

    For each target angle, starts fresh from the input geometry (matching
    the qcore branch's own "cp mingeom min.xyz" reset every point, not a
    propagated/sequential scan), fixes that one dihedral there with
    FixInternals and relaxes everything else. Writes tors.out in the same
    "POTENTIAL ENERGY SURFACE SCAN" text block format the qcore branch
    already produces (see tors.sh), so tors.sh's shared local-maximum finder
    (plain awk, untouched) works on it without any format-specific change."""
    from ase.constraints import FixInternals
    from ase.optimize import FIRE

    a1, a2, a3, a4 = dihedral_indices
    ref_positions = atoms.get_positions().copy()
    symbols = atoms.get_chemical_symbols()
    eV_to_kcalmol = mol / kcal

    lines = ["POTENTIAL ENERGY SURFACE SCAN\n"]
    for i in range(npoints):
        target = dihed0 + i * step_deg
        atoms.set_constraint()
        atoms.set_positions(ref_positions)
        atoms.set_dihedral(a1, a2, a3, a4, target)
        try:
            atoms.set_constraint(FixInternals(dihedrals_deg=[[target, [a1, a2, a3, a4]]]))
            dyn = FIRE(atoms, logfile=None)
            dyn.run(fmax=fmax, steps=steps)
            energy_kcal = atoms.get_potential_energy() * eV_to_kcalmol
        except Exception as e:
            print(f"  Point {i+1} ({target:.1f} deg): failed ({e})", flush=True)
            continue
        finally:
            atoms.set_constraint()

        lines.append("  VARIABLE        FUNCTION\n")
        lines.append(f"{target:10.1f}  -  {energy_kcal:13.3f}\n")
        lines.append("\n\n\n")
        for sym, pos in zip(symbols, atoms.get_positions()):
            lines.append(f"{sym} {pos[0]:14.8f} {pos[1]:14.8f} {pos[2]:14.8f}\n")

    with open("tors.out", "w") as f:
        f.writelines(lines)


def _project_trans_rot(atoms, hessian_2d):
    """Return (hessian, n_rt): the Cartesian Hessian with translation and
    rotation projected out via the Eckart conditions, and the number of
    modes removed (5 for a linear molecule, 6 otherwise).

    A raw finite-difference Hessian's 6 lowest-|eigenvalue| modes are not a
    reliable stand-in for "translation+rotation": they mix with genuine
    low-frequency (or imaginary, for a TS) vibrations whenever the geometry
    has residual forces, which is common with ML potentials (noisier than
    DFT). Explicitly building the mass-weighted translation/rotation basis
    from the geometry+masses and projecting it out of the Hessian before
    diagonalizing removes that ambiguity -- this is what QC codes such as
    Gaussian/ORCA do internally before reporting frequencies."""
    natoms  = len(atoms)
    masses  = atoms.get_masses()
    pos_c   = atoms.get_positions() - atoms.get_center_of_mass()
    sqrt_m  = np.sqrt(np.repeat(masses, 3))
    Hmw     = hessian_2d / np.outer(sqrt_m, sqrt_m)

    D = np.zeros((6, 3 * natoms))
    for a in range(3):
        v = np.zeros((natoms, 3))
        v[:, a] = 1.0
        D[a] = (v * np.sqrt(masses)[:, None]).flatten()
    for a in range(3):
        e = np.zeros(3)
        e[a] = 1.0
        v = np.cross(e, pos_c)
        D[3 + a] = (v * np.sqrt(masses)[:, None]).flatten()

    _, S, Vt = np.linalg.svd(D, full_matrices=False)
    n_rt = int(np.sum(S > 1e-8 * S.max()))  # 5 for linear molecules, else 6
    Vr = Vt[:n_rt]
    P = np.eye(3 * natoms) - Vr.T @ Vr
    Hmw_proj = P @ Hmw @ P
    return Hmw_proj * np.outer(sqrt_m, sqrt_m), n_rt


def compute_frequencies(atoms, vib_name):
    """Finite-difference Hessian -> Eckart-projected frequencies.

    Translation and rotation are removed *exactly* via _project_trans_rot,
    not by discarding whatever falls below an arbitrary |freq| cutoff. ASE's
    raw, unprojected spectrum can leave several cm^-1 of rotational noise --
    common with the noisier gradients of an ML potential -- that a cutoff
    around 10 cm^-1 does not reliably catch. Left unprojected, that residual
    mode is indistinguishable from a second reaction-coordinate frequency and
    causes AMK's "exactly one imaginary frequency" TS check to reject
    perfectly good saddle points.

    Returns (freqs_cm, modes, zpe_eV, vib): freqs_cm is a real array ordered
    imaginary/most-negative first (negative = imaginary, matching MOPAC/QC
    convention) with the n_rt translation/rotation modes already excluded;
    modes are the matching Cartesian displacement arrays (for Molden only).
    Caller must call vib.clean() once done with vib."""
    from ase.vibrations import Vibrations
    from ase.vibrations.data import VibrationsData
    from ase.units import invcm

    print("  Computing vibrational frequencies...", flush=True)
    vib = Vibrations(atoms, name=vib_name)
    vib.run()

    hessian_2d         = vib.get_vibrations().get_hessian_2d()
    hessian_proj, n_rt  = _project_trans_rot(atoms, hessian_2d)
    vib_data            = VibrationsData.from_2d(atoms, hessian_proj)
    energies, modes      = vib_data.get_energies_and_modes()

    freqs_cm_all = np.where(np.abs(energies.imag) > 1e-6,
                             -energies.imag, energies.real) / invcm
    order = np.argsort(np.abs(freqs_cm_all))
    # drop the n_rt modes closest to zero (now cleanly the trans/rot ones),
    # then order what's left with imaginary/most-negative first
    keep = sorted(order[n_rt:], key=lambda i: freqs_cm_all[i])

    freqs_cm    = freqs_cm_all[keep]
    real_energy = energies.real[keep]
    zpe_eV      = 0.5 * float(np.sum(real_energy[real_energy > 0]))

    return freqs_cm, [modes[i] for i in keep], zpe_eV, vib


def write_molden_file(atoms, freqs_cm, modes, log_path):
    """Write Molden file with geometry and normal modes alongside the log,
    using the same Eckart-projected frequencies/modes written to the log
    (see compute_frequencies) so the two always agree exactly."""
    atobohr     = 1.889726
    molden_path = log_path.replace('.log', '.molden')
    symbols     = atoms.get_chemical_symbols()
    positions   = atoms.get_positions()

    with open(molden_path, 'w') as f:
        f.write('[Molden Format]\n')
        f.write('[FREQ]\n')
        for f_cm in freqs_cm:
            f.write(f'{f_cm:6.1f}\n')
        f.write('       \n')
        f.write('[FR-COORD]\n')
        for sym, pos in zip(symbols, positions):
            f.write(f'{sym} {pos[0]*atobohr:.6f} {pos[1]*atobohr:.6f} {pos[2]*atobohr:.6f}\n')
        f.write('\n')
        f.write('[FR-NORM-COORD]\n')
        for vib_num, mode in enumerate(modes, start=1):
            f.write(f'Vibration {vib_num}\n')
            for disp in mode:
                f.write(f'{disp[0]*atobohr:.6f} {disp[1]*atobohr:.6f} {disp[2]*atobohr:.6f}\n')


def write_log(log_path, model_name, calctype, atoms, freqs, zpe_eV, energy_eV, converged,
              terminated_normally=True):
    eV_to_Ha      = 1.0 / Hartree
    eV_to_kcalmol = mol / kcal

    energy_Ha = energy_eV * eV_to_Ha
    zpe_kcal  = zpe_eV   * eV_to_kcalmol

    positions = atoms.get_positions()
    symbols   = atoms.get_chemical_symbols()
    natom     = len(atoms)

    with open(log_path, 'w') as f:
        f.write("AMK_MLIP LOG\n")
        f.write(f"Model: {model_name}\n")
        f.write(f"Calc: {calctype}\n")
        f.write(f"Converged: {converged}\n\n")

        f.write("FINAL GEOMETRY\n")
        f.write(f"{natom}\n")
        f.write(f"Energy= {energy_Ha:.9f} Ha\n")
        for sym, pos in zip(symbols, positions):
            f.write(f"{sym:<4s} {pos[0]:14.8f} {pos[1]:14.8f} {pos[2]:14.8f}\n")
        f.write("\n")

        f.write("VIBRATIONAL FREQUENCIES (cm^-1)\n")
        for i, f_cm in enumerate(freqs):
            f.write(f"{i+1:6d}  {f_cm:12.4f} cm**-1\n")
        f.write("\n")

        f.write(f"Zero point energy {zpe_kcal:.6f} kcal/mol\n")
        f.write(f"FINAL SINGLE POINT ENERGY   {energy_Ha:20.9f}\n\n")
        if terminated_normally:
            f.write("AMK_TERMINATED_NORMALLY\n")
        else:
            f.write("AMK_FAILED: imaginary frequency persists after retries; not a true minimum\n")


def write_irc_log(log_path, endpoint_xyz_path, model_name, direction, atoms, energy_eV,
                  converged):
    """Write IRC endpoint log (no frequencies — those come in MIN.sh)."""
    eV_to_Ha  = 1.0 / Hartree
    energy_Ha = energy_eV * eV_to_Ha

    positions = atoms.get_positions()
    symbols   = atoms.get_chemical_symbols()
    natom     = len(atoms)

    with open(log_path, 'w') as f:
        f.write("AMK_MLIP LOG\n")
        f.write(f"Model: {model_name}\n")
        f.write(f"Calc: {direction}\n")
        f.write(f"Converged: {converged}\n\n")

        f.write("IRC ENDPOINT GEOMETRY\n")
        f.write(f"{natom}\n")
        f.write(f"Energy= {energy_Ha:.9f} Ha\n")
        for sym, pos in zip(symbols, positions):
            f.write(f"{sym:<4s} {pos[0]:14.8f} {pos[1]:14.8f} {pos[2]:14.8f}\n")
        f.write("\n")

        f.write(f"FINAL SINGLE POINT ENERGY   {energy_Ha:20.9f}\n\n")
        f.write("AMK_TERMINATED_NORMALLY\n")

    # Plain XYZ for get_geom_irc in utils.sh (awk 'NR>2{print}')
    with open(endpoint_xyz_path, 'w') as f:
        f.write(f"{natom}\n")
        f.write(f"Energy= {energy_Ha:.9f} Ha\n")
        for sym, pos in zip(symbols, positions):
            f.write(f"{sym:<4s} {pos[0]:14.8f} {pos[1]:14.8f} {pos[2]:14.8f}\n")


def already_done(log_path, need_molden=False):
    if not os.path.exists(log_path):
        return False
    with open(log_path) as f:
        if 'AMK_TERMINATED_NORMALLY' not in f.read():
            return False
    if need_molden and not os.path.exists(log_path.replace('.log', '.molden')):
        return False
    return True


def _dispatch_calctype(name, default_calctype):
    """Infer calctype from entry name; fall back to default_calctype."""
    if name.startswith('min'):
        return 'minopt'
    if name.startswith('ircf'):
        return 'ircf'
    if name.startswith('ircr'):
        return 'ircr'
    return default_calctype


def process_one(name, xyz_content, calc, calctype, model_name, charge=0, mult=1):
    """Process one structure. Must be called from within the working directory."""
    log_path = f"{name}.log"

    need_molden = calctype in ('tsopt', 'minopt')
    if already_done(log_path, need_molden=need_molden):
        print(f"  {name}: already done, skipping", flush=True)
        return

    # Override charge/mult if encoded in XYZ comment line (e.g. "charge=0 mult=1")
    lines = xyz_content.strip().split('\n')
    if len(lines) >= 2:
        comment = lines[1]
        m_charge = re.search(r'charge=(-?\d+)', comment)
        m_mult   = re.search(r'mult=(\d+)', comment)
        if m_charge:
            charge = int(m_charge.group(1))
        if m_mult:
            mult = int(m_mult.group(1))

    print(f"\n--- {name} (charge={charge}, mult={mult}) ---", flush=True)

    xyz_path = f"{name}.xyz"
    with open(xyz_path, 'w') as f:
        f.write(xyz_content)

    try:
        atoms = read(xyz_path)
        atoms.info['charge'] = charge
        atoms.info['spin']   = mult  # spin multiplicity (2S+1)
        atoms.calc = calc

        if calctype == 'tsopt':
            if len(atoms) == 1:
                # Single atom: no optimization or frequencies needed
                energy_eV = atoms.get_potential_energy()
                write_log(log_path, model_name, calctype, atoms, [], 0.0, energy_eV, True)
            else:
                converged          = run_tsopt(atoms, name)
                energy_eV          = atoms.get_potential_energy()
                freqs_cm, modes, zpe_eV, vib = compute_frequencies(atoms, f"{name}_vib")
                write_log(log_path, model_name, calctype, atoms, freqs_cm, zpe_eV, energy_eV,
                          converged)
                write_molden_file(atoms, freqs_cm, modes, log_path)
                vib.clean()

        elif calctype == 'minopt':
            if len(atoms) == 1:
                # Single atom: Sella requires ≥2 atoms; just do a single-point energy
                energy_eV = atoms.get_potential_energy()
                write_log(log_path, model_name, calctype, atoms, [], 0.0, energy_eV, True)
            else:
                converged, freqs_cm, modes, zpe_eV, vib, is_true_min = run_minopt_verified(atoms, name)
                energy_eV          = atoms.get_potential_energy()
                write_log(log_path, model_name, calctype, atoms, freqs_cm, zpe_eV, energy_eV,
                          converged, terminated_normally=is_true_min)
                write_molden_file(atoms, freqs_cm, modes, log_path)
                vib.clean()

        elif calctype in ('ircf', 'ircr'):
            direction = 'forward' if calctype == 'ircf' else 'reverse'
            converged = run_irc(atoms, name, direction)
            energy_eV = atoms.get_potential_energy()
            # endpoint XYZ: name convention matches get_geom_irc in utils.sh
            endpoint_xyz = f"{name}_last.xyz"
            write_irc_log(log_path, endpoint_xyz, model_name, direction, atoms, energy_eV,
                          converged)

        else:
            raise ValueError(f"Unknown calctype '{calctype}'")

        print(f"  {name}: done", flush=True)

    except Exception as e:
        with open(log_path, 'w') as f:
            f.write("AMK_MLIP LOG\n")
            f.write(f"Model: {model_name}\n")
            f.write(f"Calc: {calctype}\n\n")
            f.write(f"AMK_ERROR: {e}\n")
            f.write(traceback.format_exc())
        print(f"  {name}: ERROR - {e}", flush=True)


# Empirical PEAK RAM footprint (GB) of one CPU worker, measured via
# VmHWM/ru_maxrss (the high-water mark, not steady-state VmRSS -- the peak
# happens transiently while the checkpoint is loaded/converted, and that peak
# is what the OS must be able to satisfy, even though usage drops afterward).
_CPU_WORKER_RAM_GB = {'uma': 24.0, 'mace': 2.0}
_CPU_WORKER_RAM_GB_DEFAULT = 24.0  # conservative fallback for unlisted models


def _cpu_worker_count(model_name):
    """Number of CPU worker processes to use for MLIP batch calculations
    when no GPU is available. Reuses the `runningtasks` value AutoMeKin's
    shell scripts already export for this run (the same knob that controls
    how many parallel ORCA/Gaussian/qcore jobs `doparallel` launches), so
    no new keyword or CLI argument is needed. Falls back to 1 (current
    sequential behavior) if unset, and never exceeds the CPU count.

    Also caps the result so total RAM usage stays within what's actually
    available: each CPU worker loads its own full copy of the model (e.g.
    ~6 GB for UMA), so naively honoring a large `runningtasks` can OOM the
    machine -- this only happened to go unnoticed during development
    because that machine had hundreds of GB of RAM."""
    try:
        n = int(os.environ.get('runningtasks', '1'))
    except ValueError:
        n = 1
    ncpus = os.cpu_count() or 1
    n = max(1, min(n, ncpus))

    ram_per_worker_gb = _CPU_WORKER_RAM_GB.get(model_name, _CPU_WORKER_RAM_GB_DEFAULT)
    try:
        with open('/proc/meminfo') as f:
            mem_available_gb = next(
                (int(line.split()[1]) / 1024 / 1024
                 for line in f if line.startswith('MemAvailable:')),
                None
            )
    except OSError:
        mem_available_gb = None

    if mem_available_gb is not None:
        usable_gb = max(0.0, mem_available_gb - 2.0)  # headroom for OS + main process
        mem_cap = max(1, int(usable_gb // ram_per_worker_gb))
        if mem_cap < n:
            print(f"Limiting CPU workers to {mem_cap} (requested {n}) to fit "
                  f"available RAM (~{mem_available_gb:.1f} GB available, "
                  f"~{ram_per_worker_gb:.1f} GB/worker estimated for '{model_name}')",
                  flush=True)
        n = min(n, mem_cap)

    return max(1, n)


def _batch_worker(args):
    """Worker function: processes a subset of entries on one GPU, or on CPU
    (gpu_id=None) as one of several CPU worker processes."""
    gpu_id, rows, calctype, workdir, model_name, models_dir, charge, mult = args
    if gpu_id is not None:
        # Set GPU visibility before any CUDA initialization
        os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)
    else:
        # Force this worker onto CPU even if CUDA is technically visible,
        # and keep it single-threaded: parallelism here comes from running
        # several worker *processes*, matching how `doparallel` runs several
        # single-core ORCA/Gaussian jobs -- not from multi-threading one process.
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
        torch.set_num_threads(1)
    calc = load_calculator(model_name, models_dir)
    tag = f"GPU {gpu_id}" if gpu_id is not None else f"CPU worker (pid {os.getpid()})"
    print(f"  [{tag}] model loaded, {len(rows)} entries", flush=True)
    old_cwd = os.getcwd()
    os.chdir(workdir)
    try:
        for name, xyz_content in rows:
            if xyz_content == 'salir':
                continue
            entry_calctype = _dispatch_calctype(name, calctype)
            process_one(name, xyz_content, calc, entry_calctype, model_name, charge, mult)
    finally:
        os.chdir(old_cwd)


def run_batch(calctype, workdir, model_name, models_dir, charge, mult):
    """Process all entries from inputs.db; distributes across all available
    GPUs, or across `runningtasks` CPU worker processes if no GPU is
    available and `runningtasks` > 1."""
    import multiprocessing as mp

    print(f"AMK_MLIP batch: {calctype} | model={model_name} | charge={charge} | mult={mult}",
          flush=True)

    db_path = os.path.join(workdir, 'inputs.db')
    con = sqlite3.connect(db_path)
    rows = con.execute("SELECT name, input FROM gaussian ORDER BY id").fetchall()
    con.close()

    ngpus = torch.cuda.device_count() if torch.cuda.is_available() else 0

    if ngpus == 1:
        calc = load_calculator(model_name, models_dir)
        print(f"Model loaded on {get_device().upper()}", flush=True)
        old_cwd = os.getcwd()
        os.chdir(workdir)
        try:
            for name, xyz_content in rows:
                if xyz_content == 'salir':
                    continue
                entry_calctype = _dispatch_calctype(name, calctype)
                process_one(name, xyz_content, calc, entry_calctype, model_name, charge, mult)
        finally:
            os.chdir(old_cwd)
    elif ngpus >= 2:
        print(f"Using {ngpus} GPUs in parallel", flush=True)
        # Interleaved split for better load balancing
        chunks = [rows[i::ngpus] for i in range(ngpus)]
        args_list = [
            (i, chunks[i], calctype, workdir, model_name, models_dir, charge, mult)
            for i in range(ngpus)
        ]
        ctx = mp.get_context('spawn')
        with ctx.Pool(processes=ngpus) as pool:
            pool.map(_batch_worker, args_list)
    else:
        # No GPU: parallelize across CPU worker processes if `runningtasks` > 1
        nworkers = _cpu_worker_count(model_name)
        if nworkers > 1:
            print(f"No GPU available -- using {nworkers} CPU worker processes "
                  f"in parallel (from runningtasks)", flush=True)
            chunks = [rows[i::nworkers] for i in range(nworkers)]
            args_list = [
                (None, chunks[i], calctype, workdir, model_name, models_dir, charge, mult)
                for i in range(nworkers)
            ]
            ctx = mp.get_context('spawn')
            with ctx.Pool(processes=nworkers) as pool:
                pool.map(_batch_worker, args_list)
        else:
            calc = load_calculator(model_name, models_dir)
            print(f"Model loaded on {get_device().upper()}", flush=True)
            old_cwd = os.getcwd()
            os.chdir(workdir)
            try:
                for name, xyz_content in rows:
                    if xyz_content == 'salir':
                        continue
                    entry_calctype = _dispatch_calctype(name, calctype)
                    process_one(name, xyz_content, calc, entry_calctype, model_name, charge, mult)
            finally:
                os.chdir(old_cwd)

    print("\nBatch complete.", flush=True)


def run_single(calctype, xyzfile, model_name, models_dir, charge, mult, calc=None):
    """Single-structure mode. If calc is given (persistent-server reuse via
    run_serve), skips loading the model and re-raises on error instead of
    exiting the process -- the caller reports the failure over the response
    fifo and keeps serving the next job."""
    name     = Path(xyzfile).stem
    log_path = f"{name}.log"
    reuse    = calc is not None

    if not reuse:
        print(f"AMK_MLIP: {calctype} | model={model_name} | charge={charge} | mult={mult}",
              flush=True)

    try:
        if calc is None:
            calc = load_calculator(model_name, models_dir)
        atoms = read(xyzfile)
        atoms.info['charge'] = charge
        atoms.info['spin']   = mult
        atoms.calc = calc

        if calctype == 'tsopt':
            if len(atoms) == 1:
                energy_eV = atoms.get_potential_energy()
                write_log(log_path, model_name, calctype, atoms, [], 0.0, energy_eV, True)
            else:
                converged          = run_tsopt(atoms, name)
                energy_eV          = atoms.get_potential_energy()
                freqs_cm, modes, zpe_eV, vib = compute_frequencies(atoms, f"{name}_vib")
                write_log(log_path, model_name, calctype, atoms, freqs_cm, zpe_eV, energy_eV,
                          converged)
                write_molden_file(atoms, freqs_cm, modes, log_path)
                vib.clean()

        elif calctype == 'minopt':
            if len(atoms) == 1:
                energy_eV = atoms.get_potential_energy()
                write_log(log_path, model_name, calctype, atoms, [], 0.0, energy_eV, True)
            else:
                converged, freqs_cm, modes, zpe_eV, vib, is_true_min = run_minopt_verified(atoms, name)
                energy_eV          = atoms.get_potential_energy()
                write_log(log_path, model_name, calctype, atoms, freqs_cm, zpe_eV, energy_eV,
                          converged, terminated_normally=is_true_min)
                write_molden_file(atoms, freqs_cm, modes, log_path)
                vib.clean()

        else:
            raise ValueError(f"Unknown calctype '{calctype}'")

        print(f"Done. Log: {log_path}", flush=True)

    except Exception as e:
        with open(log_path, 'w') as f:
            f.write("AMK_MLIP LOG\n")
            f.write(f"Model: {model_name}\n")
            f.write(f"Calc: {calctype}\n\n")
            f.write(f"AMK_ERROR: {e}\n")
            f.write(traceback.format_exc())
        print(f"ERROR: {e}", file=sys.stderr)
        if reuse:
            raise
        sys.exit(1)


def run_md_single(xyzfile, model_name, models_dir, charge, mult, temp_K, duration_fs,
                   timestep_fs=0.5, calc=None):
    """Single reactive-MD trajectory. On failure, simply does not write
    <name>_traj.xyz -- amk.sh already treats a missing trajectory file as
    "this attempt produced nothing" for every other program too.

    If calc is given (persistent-server reuse via run_serve), skips loading
    the model and re-raises on error instead of exiting the process."""
    name = Path(xyzfile).stem
    reuse = calc is not None
    print(f"AMK_MLIP: md | model={model_name} | T={temp_K} K | {duration_fs} fs", flush=True)
    try:
        if calc is None:
            calc = load_calculator(model_name, models_dir)
        atoms = read(xyzfile)
        atoms.info['charge'] = charge
        atoms.info['spin']   = mult
        atoms.calc = calc
        traj_path = run_md(atoms, name, temp_K, duration_fs, timestep_fs)
        print(f"Done. Trajectory: {traj_path}", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        traceback.print_exc()
        if reuse:
            raise
        sys.exit(1)


def run_partial_opt_single(xyzfile, frozen_csv, model_name, models_dir, charge, mult, calc=None):
    """Constrained relaxation seeding a subsequent TS search. On failure,
    <name>_popt.xyz is simply not written.

    If calc is given (persistent-server reuse via run_serve), skips loading
    the model and re-raises on error instead of exiting the process."""
    name = Path(xyzfile).stem
    reuse = calc is not None
    frozen_indices = [int(i) - 1 for i in frozen_csv.split(',') if i != '']
    print(f"AMK_MLIP: partial_opt | model={model_name} | frozen(1-based)={frozen_csv}",
          flush=True)
    try:
        if calc is None:
            calc = load_calculator(model_name, models_dir)
        atoms = read(xyzfile)
        atoms.info['charge'] = charge
        atoms.info['spin']   = mult
        atoms.calc = calc
        converged = run_partial_opt(atoms, name, frozen_indices)
        popt_path = f"{name}_popt.xyz"
        symbols   = atoms.get_chemical_symbols()
        positions = atoms.get_positions()
        with open(popt_path, 'w') as f:
            f.write(f"{len(atoms)}\n\n")
            for sym, pos in zip(symbols, positions):
                f.write(f"{sym} {pos[0]:14.8f} {pos[1]:14.8f} {pos[2]:14.8f}\n")
        print(f"Done. Converged: {converged}. Geometry: {popt_path}", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        traceback.print_exc()
        if reuse:
            raise
        sys.exit(1)


def run_dihedral_scan_single(xyzfile, dihedral_csv, dihed0, model_name, models_dir, charge,
                              mult, npoints=36, step_deg=10.0):
    """Relaxed torsional scan (see run_dihedral_scan). Writes tors.out in the
    cwd; on failure tors.out is simply not written, same as qcore's branch
    leaving no usable tors.out when entos.py fails outright."""
    dihedral_indices = [int(i) - 1 for i in dihedral_csv.split(',')]
    print(f"AMK_MLIP: dihedral_scan | model={model_name} | atoms(1-based)={dihedral_csv} | "
          f"dihed0={dihed0}", flush=True)
    try:
        calc  = load_calculator(model_name, models_dir)
        atoms = read(xyzfile)
        atoms.info['charge'] = charge
        atoms.info['spin']   = mult
        atoms.calc = calc
        run_dihedral_scan(atoms, dihedral_indices, dihed0, npoints=npoints, step_deg=step_deg)
        print("Done. Scan: tors.out", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


def run_serve(req_fifo, resp_fifo, model_name, models_dir, charge, mult):
    """Persistent worker for one amk.sh batch. Loading the UMA checkpoint
    dominates the cost of every single mlip_calc.py call (~30s of a ~40s
    call); amk.sh's trajectory loop makes many such calls (one MD run plus
    one partial_opt+tsopt pair per bond-change event it detects), each
    currently paying that cost again. This loads the model once and then
    services one job at a time, read as a single line from req_fifo ("md
    <xyzfile> <temp_K> <duration_fs> [timestep_fs]" / "partial_opt <xyzfile>
    <frozen_csv>" / "tsopt|minopt <xyzfile>" -- the same tail already passed
    on the command line for each mode), dispatching to the *_single functions
    with the reused calculator. Writes DONE/ERROR <msg> to resp_fifo after
    each job purely as a completion signal for the bash caller (mlip_request
    in utils.sh) to block on; the existing output-file / AMK_TERMINATED_NORMALLY
    checks in amk.sh are still what decides success, unchanged. Exits on a
    QUIT line (or the request fifo's writer going away for good)."""
    print(f"AMK_MLIP serve: loading {model_name}...", flush=True)
    calc = load_calculator(model_name, models_dir)
    print("AMK_MLIP serve: model loaded, ready for jobs", flush=True)

    while True:
        with open(req_fifo) as rf:
            line = rf.readline().strip()
        if not line or line == 'QUIT':
            break

        parts = line.split()
        calctype, args = parts[0], parts[1:]
        print(f"\n--- serve: {calctype} {' '.join(args)} ---", flush=True)
        status = 'DONE'
        try:
            if calctype == 'md':
                xyzfile, temp_K, duration_fs = args[0], float(args[1]), float(args[2])
                timestep_fs = float(args[3]) if len(args) > 3 else 0.5
                run_md_single(xyzfile, model_name, models_dir, charge, mult,
                              temp_K, duration_fs, timestep_fs, calc=calc)
            elif calctype == 'partial_opt':
                xyzfile, frozen_csv = args[0], args[1]
                if frozen_csv == 'NONE':
                    frozen_csv = ''
                run_partial_opt_single(xyzfile, frozen_csv, model_name, models_dir,
                                       charge, mult, calc=calc)
            elif calctype in ('tsopt', 'minopt'):
                xyzfile = args[0]
                run_single(calctype, xyzfile, model_name, models_dir, charge, mult, calc=calc)
            else:
                raise ValueError(f"serve: unknown calctype '{calctype}'")
        except Exception as e:
            status = f'ERROR: {e}'

        with open(resp_fifo, 'w') as wf:
            wf.write(status + '\n')

    print("AMK_MLIP serve: exiting", flush=True)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]

    if mode == 'batch':
        if len(sys.argv) != 8:
            print("Usage: mlip_calc.py batch tsopt|minopt|irc <dir> <model> <models_dir> <charge> <mult>")
            sys.exit(1)
        calctype   = sys.argv[2]
        workdir    = sys.argv[3]
        model      = sys.argv[4].lower()
        models_dir = sys.argv[5]
        charge     = int(sys.argv[6])
        mult       = int(sys.argv[7])
        run_batch(calctype, workdir, model, models_dir, charge, mult)

    elif mode in ('tsopt', 'minopt'):
        if len(sys.argv) != 7:
            print("Usage: mlip_calc.py tsopt|minopt <xyzfile> <model> <models_dir> <charge> <mult>")
            sys.exit(1)
        calctype   = sys.argv[1]
        xyzfile    = sys.argv[2]
        model      = sys.argv[3].lower()
        models_dir = sys.argv[4]
        charge     = int(sys.argv[5])
        mult       = int(sys.argv[6])
        run_single(calctype, xyzfile, model, models_dir, charge, mult)

    elif mode == 'md':
        if len(sys.argv) not in (9, 10):
            print("Usage: mlip_calc.py md <xyzfile> <model> <models_dir> <charge> <mult> <temp_K> <duration_fs> [timestep_fs]")
            sys.exit(1)
        xyzfile     = sys.argv[2]
        model       = sys.argv[3].lower()
        models_dir  = sys.argv[4]
        charge      = int(sys.argv[5])
        mult        = int(sys.argv[6])
        temp_K      = float(sys.argv[7])
        duration_fs = float(sys.argv[8])
        timestep_fs = float(sys.argv[9]) if len(sys.argv) > 9 else 0.5
        run_md_single(xyzfile, model, models_dir, charge, mult, temp_K, duration_fs, timestep_fs)

    elif mode == 'partial_opt':
        if len(sys.argv) != 8:
            print("Usage: mlip_calc.py partial_opt <xyzfile> <frozen_csv> <model> <models_dir> <charge> <mult>")
            sys.exit(1)
        xyzfile    = sys.argv[2]
        frozen_csv = sys.argv[3]
        model      = sys.argv[4].lower()
        models_dir = sys.argv[5]
        charge     = int(sys.argv[6])
        mult       = int(sys.argv[7])
        run_partial_opt_single(xyzfile, frozen_csv, model, models_dir, charge, mult)

    elif mode == 'serve':
        if len(sys.argv) != 8:
            print("Usage: mlip_calc.py serve <req_fifo> <resp_fifo> <model> <models_dir> <charge> <mult>")
            sys.exit(1)
        req_fifo   = sys.argv[2]
        resp_fifo  = sys.argv[3]
        model      = sys.argv[4].lower()
        models_dir = sys.argv[5]
        charge     = int(sys.argv[6])
        mult       = int(sys.argv[7])
        run_serve(req_fifo, resp_fifo, model, models_dir, charge, mult)

    elif mode == 'dihedral_scan':
        if len(sys.argv) not in (9, 10, 11):
            print("Usage: mlip_calc.py dihedral_scan <xyzfile> <a1,a2,a3,a4> <dihed0_deg> "
                  "<model> <models_dir> <charge> <mult> [npoints] [step_deg]")
            sys.exit(1)
        xyzfile      = sys.argv[2]
        dihedral_csv = sys.argv[3]
        dihed0       = float(sys.argv[4])
        model        = sys.argv[5].lower()
        models_dir   = sys.argv[6]
        charge       = int(sys.argv[7])
        mult         = int(sys.argv[8])
        npoints      = int(sys.argv[9]) if len(sys.argv) > 9 else 36
        step_deg     = float(sys.argv[10]) if len(sys.argv) > 10 else 10.0
        run_dihedral_scan_single(xyzfile, dihedral_csv, dihed0, model, models_dir, charge,
                                  mult, npoints, step_deg)

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
