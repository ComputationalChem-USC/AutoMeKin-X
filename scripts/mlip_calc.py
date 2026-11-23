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
  mlip_calc.py md <xyzfile> <model> <models_dir> <charge> <mult> <temp_K> <duration_fs> [timestep_fs] [mdc]
      NVE trajectory from Maxwell-Boltzmann initial velocities at temp_K,
      written as a plain multi-frame XYZ (<name>_traj.xyz, ~1 frame/fs) so it
      can be piped through snapshots_mopac.sh into bbfs.exe unchanged.
      mdc>=1 (bond-break/form-constrained MD) skips the H dynamical-mass
      override, matching AMK's mopac branch.

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
read from a fifo -- used by amk.sh and tors.sh for both uma and mace: for uma
model loading is ~80% of a single call's wall time; for mace the checkpoint
itself loads fast, but every direct call still pays the python/torch/mace
start-up):
  mlip_calc.py serve <req_fifo> <resp_fifo> <model> <models_dir> <charge> <mult>
      Each line read from req_fifo is "<calctype> <args...>", the same tail
      normally passed on the command line for
      md/partial_opt/tsopt/minopt/dihedral_scan.
      Writes "DONE" or "ERROR: <msg>" to resp_fifo after each job. A "QUIT"
      line ends the loop.
      For uma/uma-s on GPU the server uses faster inference settings (see
      _uma_settings; UMA Nitro for uma-s); set AMK_MLIP_FAST=0 to disable them,
      AMK_MLIP_NITRO=1 to run uma-s with UMA Nitro (TF32; see NITRO_DEFAULT).

Product energies (called by rxn_network.sh after irc_analysis.sh when IRC is mlip):
  mlip_calc.py prodfrag <prod.db> <model> <models_dir> <charge>
      Multi-fragment products get the sum of their separated fragments' energies
      (each in its lowest spin state) instead of the supermolecule energy; the
      latter is kept in prod.energy_super. See fragment_energy().

Supported models: uma (UMA-M 1.1), uma-s (UMA-S 1.2.1; optional UMA Nitro on GPU
with fairchem-core >= 2.24), mace (MACE-OMOL-0); see MLIP_MODELS
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
# e3nn/mace call torch.jit.script/torch.jit.load when the model is loaded; recent
# torch flags them as deprecated (FutureWarning), which only clutters the logs.
warnings.filterwarnings('ignore', category=FutureWarning, message=r"`torch\.jit\.\w+` is deprecated")

# IRC parameters
IRC_DX    = 0.08   # amu^0.5 * Å, step size along IRC
IRC_ETA   = 1e-4
IRC_GAMMA = 0.4
IRC_FMAX  = 0.01   # eV/Å — looser than TS opt to walk the full IRC path
IRC_STEPS = 1000
# Minimum displacement (Ang) / energy drop (kcal/mol) for an IRC endpoint to
# count as having left the TS.
IRC_MIN_DISP   = 0.10
IRC_MIN_DROP   = 0.5

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


# MLIP models selectable as "LowLevel mlip <name>" / "HighLevel mlip <name>":
# name -> (checkpoint, optional atom-reference file) in $AMK/models.
#   uma    UMA-M 1.1 (Meta FAIR): the most accurate UMA; atom refs from the yaml
#   uma-s  UMA-S 1.2.1: smaller and much faster (UMA Nitro, see _uma_settings);
#          its checkpoint already carries the isolated-atom references
#   mace   MACE-OMOL-0 extra large
MLIP_MODELS = {
    'uma':   ('uma-m-1p1.pt', 'uma-m-1p1_atom_refs.yaml'),
    'uma-s': ('uma-s-1p2p1.pt', None),
    'mace':  ('MACE-omol-0-extra-large-1024.model', None),
}

# UMA Nitro (fairchem-core >= 2.24, UMA-S 1.2.1 only, CUDA capability >= 8):
# fused kernels + CUDA graphs, one system per call -- ~2 ms per call on 9 atoms
# instead of ~14 ms (FP32 fast path, fairchem 2.26). Opt-in (AMK_MLIP_NITRO=1)
# because it computes in TF32: on the disilanol benchmark (10 DFT TSs displaced
# 0.05 A, Sella fmax 0.005, cost_benchmark/piece9_nitro) only 5/10 TS
# optimizations converged, against 9-10/10 with the FP32 settings -- the same
# problem as fairchem's TF32 "turbo" on FA.
NITRO_DEFAULT = '0'


def _uma_settings(model_name, device, fast):
    """fairchem InferenceSettings for an UMA model, built explicitly so that
    they mean the same on every fairchem version (since 2.24 the preset called
    "default" is Nitro, with a TF32 fallback for any other checkpoint, and
    "turbo" no longer exists):
      default  FP32, unmerged, not compiled (fairchem <= 2.23 "default",
               >= 2.24 "batch"); valid for any composition
      fast     FP32, MoLE merged for the first composition + torch.compile
               (fairchem "turbo" with tf32 off; >= 2.24 "high-precision").
               Benchmarked on the full FA network (28 TSs + 11 MINs,
               PROJECTS_Low_Level/uma_benchmark_FA): same energies, geometries
               and frequencies as the default settings, ~1.9x faster Sella
               opt+freq. TF32 (stock turbo) is NOT used: its noisier forces left
               7/28 TSs unconverged at fmax 0.005. The first call pays ~40-115 s
               of compilation and the merged model raises on any other
               composition, so the caller needs a default calc to fall back on.
      nitro    uma-s with fast=True on CUDA, when fairchem has it and
               AMK_MLIP_NITRO=1 (opt-in, see NITRO_DEFAULT).
    torch.compile (fast) builds Triton kernels, which link against libcuda.so:
    on a machine with only libcuda.so.1, point TRITON_LIBCUDA_PATH to a
    directory with a libcuda.so symlink."""
    from fairchem.core.units.mlip_unit.api.inference import InferenceSettings
    if not (fast and device == 'cuda'):
        return InferenceSettings(tf32=False, activation_checkpointing=True, merge_mole=False,
                                 compile=False, external_graph_gen=False, internal_graph_gen_version=2)
    if (model_name == 'uma-s' and os.environ.get('AMK_MLIP_NITRO', NITRO_DEFAULT) != '0'
            and 'nitro' in InferenceSettings.__dataclass_fields__):
        major, _ = torch.cuda.get_device_capability()
        if major >= 8:
            return InferenceSettings(tf32=True, activation_checkpointing=False, merge_mole=True,
                                     compile=True, external_graph_gen=False,
                                     internal_graph_gen_version=2, nitro=True)
    return InferenceSettings(tf32=False, activation_checkpointing=False, merge_mole=True,
                             compile=True, external_graph_gen=False, internal_graph_gen_version=2)


def load_calculator(model_name, models_dir, fast=False):
    """Calculator of an MLIP_MODELS entry. fast=True only matters for the UMA
    models on GPU (see _uma_settings)."""
    device = get_device()
    models_path = Path(models_dir)
    if model_name not in MLIP_MODELS:
        raise ValueError(f"Unknown model '{model_name}'. Supported: {', '.join(MLIP_MODELS)}")
    ckpt, refs = MLIP_MODELS[model_name]
    model_path = models_path / ckpt
    if not model_path.exists():
        raise FileNotFoundError(f"MLIP model not found: {model_path}")

    if model_name.startswith('uma'):
        from fairchem.core import FAIRChemCalculator, pretrained_mlip
        from omegaconf import OmegaConf
        refs_path = models_path / refs if refs else None
        atom_refs = OmegaConf.load(refs_path) if refs_path and refs_path.exists() else None
        pred_unit = pretrained_mlip.load_predict_unit(str(model_path), device=device,
                                                      inference_settings=_uma_settings(model_name, device, fast),
                                                      atom_refs=atom_refs)
        return FAIRChemCalculator(pred_unit, task_name='omol')

    from mace.calculators import MACECalculator
    return MACECalculator(model_paths=str(model_path), device=device, default_dtype='float32')


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


_IRC_HESS_CACHE = {}   # ts_key -> (TS positions, finite-difference Hessian); see run_irc


def run_irc(atoms, name, direction, dx=IRC_DX, eta=IRC_ETA, gamma=IRC_GAMMA,
            fmax=IRC_FMAX, steps=IRC_STEPS):
    from sella import IRC

    # Sella IRC checks gradient_converged() before taking any step, so a
    # well-converged TS (forces < fmax) would stop immediately at step 0.
    # Force at least one kick along the imaginary mode before allowing
    # convergence to be declared.
    # Since ASE 3.23, Optimizer.irun() calls gradient_converged() and never
    # Sella's IRC.converged(), so a TS whose residual forces are already
    # < fmax after the first kick is "converged" on the saddle point itself,
    # and minopt then drops both endpoints into the same basin. Only allow
    # convergence once the walk has actually left the TS. (Sella's own
    # positive-curvature condition is not used: its Hessian is not projected
    # for translations/rotations, so on loose fragment complexes, e.g. H...HOCO,
    # it never holds and the walk overshoots into a different product.)
    x0 = atoms.get_positions().copy()
    e0 = atoms.get_potential_energy()

    def _left_ts():
        disp = np.linalg.norm(atoms.get_positions() - x0)
        drop = (e0 - atoms.get_potential_energy()) * mol / kcal
        return disp >= IRC_MIN_DISP and drop >= IRC_MIN_DROP

    class _IRC(IRC):
        def gradient_converged(self, gradient):
            if self.nsteps == 0 or not _left_ts():
                return False
            return super().gradient_converged(gradient)

    print(f"  IRC {direction} with Sella (dx={dx}, fmax={fmax} eV/Ang, max_steps={steps})",
          flush=True)
    # Exact (finite-difference) Hessian for the initial diagonalization:
    # Sella's default iterative estimate (Davidson, tolerance gamma) can miss
    # the imaginary mode altogether (all eigenvalues > 0), and then the first
    # kick goes along a stiff mode and falls back onto the TS.
    calc = atoms.calc
    # ircf_X and ircr_X start from the same TS geometry, so its Hessian is
    # computed once and reused by the second direction (run_batch hands both
    # directions of a TS to the same worker, one after the other).
    ts_key = name[4:] if name[:4] in ('ircf', 'ircr') else name

    def _exact_hessian(at):
        from ase.vibrations import Vibrations
        cached = _IRC_HESS_CACHE.get(ts_key)
        if cached is not None and np.allclose(cached[0], at.get_positions(), atol=1e-8):
            print(f"  Reusing the TS Hessian of {ts_key} (computed for the other IRC direction)",
                  flush=True)
            return cached[1].copy()
        work = at.copy()
        work.info.update(atoms.info)
        work.calc = calc
        vib = Vibrations(work, name=f'{name}_irchess')
        vib.run()
        h = vib.get_vibrations().get_hessian_2d()
        vib.clean()
        _IRC_HESS_CACHE.clear()          # keep only the TS being processed
        _IRC_HESS_CACHE[ts_key] = (at.get_positions().copy(), h.copy())
        return h

    dyn = _IRC(atoms, trajectory=f'{name}.traj', dx=dx, eta=eta, gamma=gamma,
               keep_going=True, hessian_function=_exact_hessian)
    # Sella warns whenever the inner loop misses on any single outer step,
    # even if the walk (keep_going=True) later still reaches the final
    # convergence check successfully -- confirmed on the FA 5-iter validation
    # run that every surviving ircf_/ircr_ log ended up Converged: True
    # despite this warning firing 3 times. Silenced as log noise; the
    # `converged` flag returned below is still recorded in the log by
    # write_irc_log (as "Converged: ...") for anyone auditing results later.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="IRC inner loop failed to converge.*")
        converged = dyn.run(fmax=fmax, steps=steps, direction=direction)
    print(f"  Steps: {dyn.nsteps}, Converged: {converged}", flush=True)

    # Safety net: an endpoint that has not left the TS region would give a
    # spurious MINn<->MINn connection; report it as not converged.
    disp = np.linalg.norm(atoms.get_positions() - x0)
    drop = (e0 - atoms.get_potential_energy()) * mol / kcal
    if disp < IRC_MIN_DISP or drop < IRC_MIN_DROP:
        print(f"  WARNING: IRC {direction} did not leave the TS (disp={disp:.3f} Ang, "
              f"drop={drop:.2f} kcal/mol)", flush=True)
        converged = False
    return converged


def run_md(atoms, name, temp_K, duration_fs, timestep_fs=0.5, mdc=0):
    """NVE trajectory from Maxwell-Boltzmann initial velocities.

    Writes a plain multi-frame XYZ (element x y z, no extra columns) at
    ~1 frame/fs, matching the frame-per-fs convention the rest of AMK's LL
    pipeline (irange, nfs, snapshots_mopac.sh, bbfs.exe) already assumes.

    The input geometry is already relaxed (opt_start/sel_mol.sh optimize it
    before amk.sh ever calls this), so at t=0 all of the assigned thermal
    energy is kinetic and none is potential; under NVE that energy then
    equilibrates between the two. EQUIPARTITION_FACTOR is kept at 1 (no
    initial-temperature boost) to match AMK's MOPAC path, which samples
    momenta directly at the target temperature (see termo.f90) rather than
    compensating for the kinetic/potential equilibration up front."""
    from ase.md.velocitydistribution import MaxwellBoltzmannDistribution, Stationary, ZeroRotation
    from ase.md.verlet import VelocityVerlet
    from ase import units as ase_units

    # Give H its usual dynamical mass override (real mass ~1.008 amu -> 4.0),
    # same as AMK's MOPAC path (amk.sh's `sed 's/H /H4.0/g'` on the .mop
    # geometry block): H's fast, low-mass motion is what makes classical
    # trajectories stiff, so slowing it down like this keeps the reactive
    # sampling stable at the same timestep MOPAC uses. This only affects the
    # velocities/dynamics below -- it does not change the written geometry.
    # Skipped when mdc>=1 (bond-break/form-constrained MD, AMK's
    # nbondsbreak/nbondsform), matching amk.sh's mopac branch (utils.sh:97-102)
    # which keeps real H mass there so the constraint's physics isn't distorted.
    if mdc < 1:
        H_DYNAMICAL_MASS = 4.0
        masses = atoms.get_masses().copy()
        is_h = [sym == 'H' for sym in atoms.get_chemical_symbols()]
        masses[is_h] = H_DYNAMICAL_MASS
        atoms.set_masses(masses)
        print("masses:", list(zip(atoms.get_chemical_symbols(), atoms.get_masses())), flush=True)

    EQUIPARTITION_FACTOR = 1.0
    MaxwellBoltzmannDistribution(atoms, temperature_K=temp_K * EQUIPARTITION_FACTOR)
    Stationary(atoms)
    if len(atoms) > 2:
        ZeroRotation(atoms)

    dyn = VelocityVerlet(atoms, timestep=timestep_fs * ase_units.fs)
    dump_every = max(1, round(1.0 / timestep_fs))   # ~1 frame per fs
    nsteps = max(1, round(duration_fs / timestep_fs))

    # Fragmentation stopping criterion, matching AMK's MOPAC path: stop the
    # trajectory once any initially-bonded pair has stretched past 5x its
    # starting distance, checked every 10 MD steps (not every step/frame).
    # Initial bonds are perceived once, up front, from covalent radii (ASE's
    # natural_cutoffs) -- this only decides which pairs to watch, it doesn't
    # change the dynamics itself.
    FRAGMENT_RATIO = 5.0
    FRAGMENT_CHECK_EVERY = 10
    from ase.neighborlist import natural_cutoffs, neighbor_list
    # mult=1.2: the default (1.0, bare covalent-radii sum) misses some real
    # equilibrium bonds by a hair (e.g. a typical C-H distance ~1.09 Ang vs a
    # C+H covalent-radii-sum cutoff of ~1.07 Ang) -- 1.2 was verified to catch
    # all 4 bonds in the formic-acid test geometry with no spurious ones.
    i_idx, j_idx = neighbor_list('ij', atoms, natural_cutoffs(atoms, mult=1.2))
    bonded_pairs = sorted({tuple(sorted((int(i), int(j)))) for i, j in zip(i_idx, j_idx)})
    r0 = {pair: atoms.get_distance(*pair) for pair in bonded_pairs}
    print(f"Fragmentation watch: {len(bonded_pairs)} initial bond(s), "
          f"stop if r > {FRAGMENT_RATIO}x r0, checked every {FRAGMENT_CHECK_EVERY} steps",
          flush=True)

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
            dumped = False
            if (step + 1) % dump_every == 0:
                dump(f)
                dumped = True
            if (step + 1) % FRAGMENT_CHECK_EVERY == 0:
                for pair, r0_ab in r0.items():
                    r_ab = atoms.get_distance(*pair)
                    if r_ab > FRAGMENT_RATIO * r0_ab:
                        print(f"Fragmentation stopping criterion met at step {step + 1}: "
                              f"bond {pair} r={r_ab:.2f} Ang > {FRAGMENT_RATIO}x r0={r0_ab:.2f} Ang",
                              flush=True)
                        if not dumped:
                            dump(f)
                        return traj_path

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
    targets = [dihed0 + i * step_deg for i in range(npoints)]

    def relax_point(at, i):
        """Relax one scan point in place; returns its energy (kcal/mol) or None."""
        target = targets[i]
        at.set_constraint()
        at.set_positions(ref_positions)
        at.set_dihedral(a1, a2, a3, a4, target)
        try:
            at.set_constraint(FixInternals(dihedrals_deg=[[target, [a1, a2, a3, a4]]]))
            dyn = FIRE(at, logfile=None)
            dyn.run(fmax=fmax, steps=steps)
            return at.get_potential_energy() * eV_to_kcalmol
        except Exception as e:
            print(f"  Point {i+1} ({target:.1f} deg): failed ({e})", flush=True)
            return None
        finally:
            at.set_constraint()

    # The points are independent, so with MACE they are relaxed side by side
    # with their model calls batched into one forward pass (see
    # _run_batched); same FIRE runs, same results up to float32 round-off.
    # Not with UMA: fairchem's turbo mode recompiles the model for every new
    # batch size and the 36-structure batches ran the GPU out of memory, so
    # most points failed. AMK_MLIP_BATCH=0 restores the one-point-at-a-time
    # loop for MACE as well.
    if (os.environ.get('AMK_MLIP_BATCH', '1') != '0' and npoints > 1
            and type(atoms.calc).__name__ == 'MACECalculator'):
        point_atoms = [atoms.copy() for _ in range(npoints)]
        energies = _run_batched(atoms.calc, point_atoms, relax_point)
    else:
        point_atoms, energies = [], []
        for i in range(npoints):
            energies.append(relax_point(atoms, i))
            point_atoms.append(atoms.copy())

    lines = ["POTENTIAL ENERGY SURFACE SCAN\n"]
    for target, at, energy_kcal in zip(targets, point_atoms, energies):
        if energy_kcal is None:
            continue
        lines.append("  VARIABLE        FUNCTION\n")
        lines.append(f"{target:10.1f}  -  {energy_kcal:13.3f}\n")
        lines.append("\n\n\n")
        for sym, pos in zip(symbols, at.get_positions()):
            lines.append(f"{sym} {pos[0]:14.8f} {pos[1]:14.8f} {pos[2]:14.8f}\n")

    with open("tors.out", "w") as f:
        f.writelines(lines)
    nfailed = sum(e is None for e in energies)
    if nfailed:
        print(f"  WARNING: {nfailed}/{npoints} scan points failed", flush=True)


def batch_energy_forces(calc, atoms_list):
    """Energies (eV) and forces (eV/Ang) for several structures in one model
    forward pass -- same graphs and same model call the ASE calculators
    (MACECalculator / FAIRChemCalculator) build for a single structure, just
    batched. Falls back to one calculator call per structure for anything
    else."""
    if type(calc).__name__ == 'MACECalculator' and calc.num_models == 1:
        from mace import data as mace_data
        from mace.tools import torch_geometric, torch_tools
        keyspec = mace_data.KeySpecification(info_keys=calc.info_keys,
                                             arrays_keys=calc.arrays_keys)
        with torch_tools.default_dtype(calc.default_dtype):
            graphs = [mace_data.AtomicData.from_config(
                          mace_data.config_from_atoms(a, key_specification=keyspec,
                                                      head_name=calc.head),
                          z_table=calc.z_table, cutoff=calc.r_max, heads=calc.available_heads)
                      for a in atoms_list]
        batch = torch_geometric.Batch.from_data_list(graphs).to(calc.device)
        model = calc.models[0]
        model_dtype = next(model.parameters()).dtype
        for key in batch.keys:
            value = batch[key]
            if torch.is_tensor(value) and torch.is_floating_point(value):
                batch[key] = value.to(dtype=model_dtype)
        out = model(batch.to_dict(), compute_stress=False, training=False)
        energies = out['energy'].detach().cpu().numpy() * calc.energy_units_to_eV
        forces = (out['forces'].detach().cpu().numpy()
                  * calc.energy_units_to_eV / calc.length_units_to_A)
    elif type(calc).__name__ == 'FAIRChemCalculator':
        from fairchem.core.datasets.atomic_data import atomicdata_list_to_batch
        for a in atoms_list:
            calc.predictor.validate_atoms_data(a, calc.task_name)
        batch = atomicdata_list_to_batch([calc.a2g(a) for a in atoms_list])
        pred = calc.predictor.predict(batch)
        energies = pred['energy'].detach().cpu().numpy()
        forces = pred['forces'].detach().cpu().numpy()
    else:
        results = []
        for a in atoms_list:
            a = a.copy()
            a.calc = calc
            results.append((a.get_potential_energy(), a.get_forces(apply_constraint=False)))
        return results
    splits = np.cumsum([len(a) for a in atoms_list])[:-1]
    return [(float(e), f) for e, f in zip(energies, np.split(forces, splits))]


class _BatchBroker:
    """Collects the model calls of several optimizations running side by
    side (one thread each) and serves them with one batched forward pass
    once every still-running optimization is waiting for its forces."""

    def __init__(self, calc, nactive):
        import threading
        self.calc = calc
        self.nactive = nactive
        self.pending = []
        self.cv = threading.Condition()

    def request(self, atoms):
        slot = {'atoms': atoms, 'result': None}
        with self.cv:
            self.pending.append(slot)
            self._flush_if_ready()
            while slot['result'] is None:
                self.cv.wait()
        if isinstance(slot['result'], Exception):
            raise slot['result']
        return slot['result']

    def leave(self):
        with self.cv:
            self.nactive -= 1
            self._flush_if_ready()

    def _flush_if_ready(self):
        if not self.pending or len(self.pending) < self.nactive:
            return
        slots, self.pending = self.pending, []
        # Split into forward passes of at most AMK_MLIP_MAX_BATCH_ATOMS atoms
        # (GPU memory grows with it: ~3.4 GiB for 36 x 18 atoms with MACE).
        max_atoms = int(os.environ.get('AMK_MLIP_MAX_BATCH_ATOMS', '1000'))
        chunks, chunk, natoms = [], [], 0
        for s in slots:
            if chunk and natoms + len(s['atoms']) > max_atoms:
                chunks.append(chunk)
                chunk, natoms = [], 0
            chunk.append(s)
            natoms += len(s['atoms'])
        chunks.append(chunk)
        results = []
        for chunk in chunks:
            try:
                results.extend(batch_energy_forces(self.calc, [s['atoms'] for s in chunk]))
            except Exception:
                # e.g. out of GPU memory: retry one structure at a time so that
                # a failed pass doesn't fail every point in it
                for s in chunk:
                    try:
                        results.extend(batch_energy_forces(self.calc, [s['atoms']]))
                    except Exception as e:
                        results.append(e)
        for s, r in zip(slots, results):
            s['result'] = r
        self.cv.notify_all()


def _run_batched(calc, atoms_list, func):
    """Runs func(atoms_list[i], i) for every i, one thread each, with every
    model call routed through a shared _BatchBroker. Returns the list of
    func's return values."""
    import threading
    from ase.calculators.calculator import Calculator, all_changes

    class _BrokerCalc(Calculator):
        implemented_properties = ['energy', 'free_energy', 'forces']

        def __init__(self, broker):
            super().__init__()
            self.broker = broker

        def calculate(self, atoms=None, properties=('energy',), system_changes=all_changes):
            super().calculate(atoms, properties, system_changes)
            energy, forces = self.broker.request(self.atoms)
            self.results = {'energy': energy, 'free_energy': energy, 'forces': forces}

    broker = _BatchBroker(calc, len(atoms_list))
    results = [None] * len(atoms_list)

    def work(i):
        try:
            atoms_list[i].calc = _BrokerCalc(broker)
            results[i] = func(atoms_list[i], i)
        finally:
            broker.leave()

    threads = [threading.Thread(target=work, args=(i,)) for i in range(len(atoms_list))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


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
_CPU_WORKER_RAM_GB = {'uma': 24.0, 'uma-s': 8.0, 'mace': 2.0}
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


_GPU_WORKER = {}

# uma on GPU: batch steps (IRC, minima) use the fast calculator (see
# load_calculator) when each worker gets at least this many entries, so that
# the ~40 s torch.compile of its first call pays off (fast is ~3x cheaper per
# call than the default settings). AMK_MLIP_FAST=0 disables it, as in run_serve.
BATCH_FAST_MIN_JOBS = 4


def _group_jobs(jobs):
    """Groups the batch entries into work units: both IRC directions of a TS
    (ircf_X, ircr_X) go together, so one worker runs them back to back and the
    second reuses the TS Hessian of the first (see run_irc); any other entry is
    its own unit. Keeps the database order."""
    units, where = [], {}
    for name, xyz in jobs:
        key = name[4:] if name[:4] in ('ircf', 'ircr') else None
        if key is not None and key in where:
            units[where[key]].append((name, xyz))
            continue
        if key is not None:
            where[key] = len(units)
        units.append([(name, xyz)])
    return units


class _CalcPicker:
    """Fast uma calculator for the composition of the first entry, default one
    (loaded lazily) for any other, same policy as run_serve."""

    def __init__(self, model_name, models_dir, use_fast):
        self.model_name, self.models_dir = model_name, models_dir
        self.use_fast = use_fast and model_name.startswith('uma') and get_device() == 'cuda'
        self.main = load_calculator(model_name, models_dir, fast=self.use_fast)
        self.formula, self.default = None, (None if self.use_fast else self.main)

    def __call__(self, xyz_content):
        if not self.use_fast:
            return self.main
        from ase import Atoms
        lines = xyz_content.strip().split('\n')
        formula = Atoms([l.split()[0] for l in lines[2:] if len(l.split()) >= 4]).get_chemical_formula()
        if self.formula is None:
            self.formula = formula
        if formula == self.formula:
            return self.main
        if self.default is None:
            print(f"  composition {formula} != {self.formula}, loading default {self.model_name} calculator",
                  flush=True)
            self.default = load_calculator(self.model_name, self.models_dir)
        return self.default


def _use_batch_fast(njobs, nworkers):
    return (os.environ.get('AMK_MLIP_FAST', '1') != '0'
            and njobs / max(1, nworkers) >= BATCH_FAST_MIN_JOBS)


def _gpu_worker_init(device_queue, calctype, workdir, model_name, models_dir, charge, mult, use_fast=False):
    """Pool initializer for run_batch on GPU: pins this worker process to one
    device (taken from device_queue, before any CUDA initialization) and
    loads the model once for all the entries it will be handed."""
    device = device_queue.get()
    os.environ['CUDA_VISIBLE_DEVICES'] = device
    _GPU_WORKER.update(pick=_CalcPicker(model_name, models_dir, use_fast), calctype=calctype,
                       model_name=model_name, charge=charge, mult=mult)
    print(f"  [GPU {device}, pid {os.getpid()}] model loaded (fast={_GPU_WORKER['pick'].use_fast})", flush=True)
    os.chdir(workdir)


def _gpu_worker_task(unit):
    w = _GPU_WORKER
    for name, xyz_content in unit:
        process_one(name, xyz_content, w['pick'](xyz_content), _dispatch_calctype(name, w['calctype']),
                    w['model_name'], w['charge'], w['mult'])


def _batch_worker(args):
    """Worker function: processes a subset of entries as one of several CPU
    worker processes."""
    gpu_id, rows, calctype, workdir, model_name, models_dir, charge, mult = args
    # Force this worker onto CPU even if CUDA is technically visible,
    # and keep it single-threaded: parallelism here comes from running
    # several worker *processes*, matching how `doparallel` runs several
    # single-core ORCA/Gaussian jobs -- not from multi-threading one process.
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    torch.set_num_threads(1)
    calc = load_calculator(model_name, models_dir)
    print(f"  [CPU worker (pid {os.getpid()})] model loaded, {len(rows)} entries", flush=True)
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
    jobs = [r for r in rows if r[1] != 'salir']

    if ngpus >= 1:
        # A single small-molecule calculation is bound by kernel-launch
        # latency and leaves the GPU mostly idle (MACE on FA: ~10 ms of GPU
        # work in a ~40 ms call), so run several worker processes per GPU
        # (AMK_MLIP_WORKERS_PER_GPU, default 4: one GPU saturates at ~4).
        # Entries are handed out one at a time as workers free up.
        visible = os.environ.get('CUDA_VISIBLE_DEVICES')
        devices = ([d.strip() for d in visible.split(',')] if visible
                   else [str(i) for i in range(ngpus)])[:ngpus]
        try:
            per_gpu = max(1, int(os.environ.get('AMK_MLIP_WORKERS_PER_GPU', '4')))
        except ValueError:
            per_gpu = 4
        units = _group_jobs(jobs)
        nworkers = min(len(devices) * per_gpu, len(units))
        use_fast = _use_batch_fast(len(jobs), nworkers)
        if nworkers <= 1:
            pick = _CalcPicker(model_name, models_dir, use_fast)
            print(f"Model loaded on {get_device().upper()} (fast={pick.use_fast})", flush=True)
            old_cwd = os.getcwd()
            os.chdir(workdir)
            try:
                for name, xyz_content in (row for u in units for row in u):   # both IRC directions together
                    entry_calctype = _dispatch_calctype(name, calctype)
                    process_one(name, xyz_content, pick(xyz_content), entry_calctype, model_name, charge, mult)
            finally:
                os.chdir(old_cwd)
        else:
            print(f"Using {len(devices)} GPU(s) x {per_gpu} workers ({nworkers} processes)",
                  flush=True)
            ctx = mp.get_context('spawn')
            device_queue = ctx.Queue()
            for k in range(nworkers):
                device_queue.put(devices[k % len(devices)])
            with ctx.Pool(processes=nworkers, initializer=_gpu_worker_init,
                          initargs=(device_queue, calctype, workdir, model_name,
                                    models_dir, charge, mult, use_fast)) as pool:
                for _ in pool.imap_unordered(_gpu_worker_task, units, chunksize=1):
                    pass
    else:
        # No GPU: parallelize across CPU worker processes if `runningtasks` > 1
        nworkers = _cpu_worker_count(model_name)
        if nworkers > 1:
            print(f"No GPU available -- using {nworkers} CPU worker processes "
                  f"in parallel (from runningtasks)", flush=True)
            # whole units (both IRC directions of a TS together, see _group_jobs)
            units = _group_jobs([r for r in rows if r[1] != 'salir'])
            chunks = [[row for u in units[i::nworkers] for row in u] for i in range(nworkers)]
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
                units = _group_jobs([r for r in rows if r[1] != 'salir'])   # both IRC directions together
                for name, xyz_content in (row for u in units for row in u):
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
                   timestep_fs=0.5, mdc=0, calc=None):
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
        traj_path = run_md(atoms, name, temp_K, duration_fs, timestep_fs, mdc)
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
                              mult, npoints=36, step_deg=10.0, calc=None):
    """Relaxed torsional scan (see run_dihedral_scan). Writes tors.out in the
    cwd; on failure tors.out is simply not written, same as qcore's branch
    leaving no usable tors.out when entos.py fails outright.

    If calc is given (persistent-server reuse via run_serve), skips loading
    the model and re-raises on error instead of exiting the process."""
    reuse = calc is not None
    dihedral_indices = [int(i) - 1 for i in dihedral_csv.split(',')]
    print(f"AMK_MLIP: dihedral_scan | model={model_name} | atoms(1-based)={dihedral_csv} | "
          f"dihed0={dihed0}", flush=True)
    try:
        if calc is None:
            calc = load_calculator(model_name, models_dir)
        atoms = read(xyzfile)
        atoms.info['charge'] = charge
        atoms.info['spin']   = mult
        atoms.calc = calc
        run_dihedral_scan(atoms, dihedral_indices, dihed0, npoints=npoints, step_deg=step_deg)
        print("Done. Scan: tors.out", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        traceback.print_exc()
        if reuse:
            raise
        sys.exit(1)


def fragment_energy(atoms, calc, charge=0, expected=None, spin_rule='lowest'):
    """Energy (eV) of a multi-fragment structure as the sum of its fragments,
    each evaluated on its own (same geometry). spin_rule 'lowest': lowest spin
    state, singlet or triplet for even-electron fragments, doublet for odd ones
    (UMA). 'closed': singlet for even-electron polyatomic fragments, triplet for
    bare even-electron atoms, doublet for odd ones -- MACE-omol puts triplet H2
    1.6 kcal/mol below singlet H2 at 0.74 A (and triplet H2O below singlet), so
    the lowest-energy choice is not usable with it.

    Why: the MLIPs are not trained on bare, unsaturated atoms sitting inside the
    cutoff of another molecule. For Si2OH6, UMA put "Si + H2 + H4OSi" (PR186)
    at -56 kcal/mol from the reactant when the separated fragments sum to +109
    -- wB97M-V gives +115 (supermolecule) / +109 (fragments). The isolated
    fragments themselves are right (within 0.2 kcal/mol of DFT), and the
    isolated-atom energies equal the atom_refs (ground-state triplet for Si).
    Returns (energy_eV, [(formula, mult, energy_eV), ...]), or (None, []) when the
    structure is a single fragment, the system is charged (no unique way to place
    the charge) or no bond criterion reproduces `expected` (AutoMeKin's own
    fragment formulas, "H2 + H4OSi2") and there is no bare heavy atom: the caller
    then keeps the supermolecule. If nothing matches but there are bare heavy
    atoms, those are taken out and the rest is evaluated as a single block.
    Bonds: covalent radii x 1.25 (1.1-1.4 tried if needed to match `expected`),
    H-H up to 1.0 A (natural_cutoffs puts the H-H cut at 0.74 A and splits
    slightly stretched H2 into two H atoms)."""
    from ase.data import covalent_radii
    from ase.neighborlist import neighbor_list
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    def energy(a, m):
        a = a.copy()
        a.info['charge'] = 0
        a.info['spin'] = m
        a.calc = calc
        return a.get_potential_energy()

    if charge != 0:
        return None, []
    els = sorted(set(atoms.get_chemical_symbols()))
    zs = {e: atoms.numbers[atoms.get_chemical_symbols().index(e)] for e in els}
    exp = sorted(x.strip() for x in expected.split('+')) if expected else None

    def split(f):
        cut = {(a, b): f * (covalent_radii[zs[a]] + covalent_radii[zs[b]])
               for a in els for b in els}
        if ('H', 'H') in cut:
            cut[('H', 'H')] = 1.0
        i, j = neighbor_list('ij', atoms, cut)
        n, lab = connected_components(coo_matrix((np.ones(len(i)), (i, j)),
                                                 shape=(len(atoms), len(atoms))))
        return [atoms[[k for k in range(len(atoms)) if lab[k] == c]] for c in range(n)]

    # 1.25 first; the other factors only to reproduce AutoMeKin's own partition
    for f in (1.25, 1.2, 1.15, 1.1, 1.3, 1.35, 1.4):
        frags = split(f)
        if exp is None or sorted(fr.get_chemical_formula() for fr in frags) == exp:
            break
    else:
        # no match: still take out bare heavy atoms (the artifact this guards
        # against) and keep everything else together as one block
        frags = split(1.25)
        bare = [fr for fr in frags if len(fr) == 1 and fr.numbers[0] > 1]
        if not bare:
            return None, []
        rest = [k for k in range(len(atoms))
                if not any(np.allclose(atoms.positions[k], b.positions[0]) for b in bare)]
        frags = bare + [atoms[rest]]
    if len(frags) == 1:
        return None, []
    parts = []
    for frag in frags:
        if sum(frag.numbers) % 2:
            mults = (2,)
        elif spin_rule == 'closed':
            mults = (3,) if len(frag) == 1 else (1,)
        else:
            mults = (1, 3)
        # ties (bare atoms: the atom_refs carry no spin dependence) -> higher mult
        e, _, m = min((round(energy(frag, m), 6), -m, m) for m in mults)
        parts.append((frag.get_chemical_formula(), m, e))
    return sum(p[2] for p in parts), parts


def run_prodfrag(prod_db, model_name, models_dir, charge):
    """Replace the energy of every multi-fragment product in prod.db (LL, kcal/mol,
    same E_Ha*627.51 convention as irc_analysis.sh) by the sum of its separated
    fragments (fragment_energy). The supermolecule energy is kept in a new
    column energy_super. Barrierless entries (min_diss) already hold fragment
    energies and are skipped. The fragments must match AutoMeKin's partition:
    prod.formula is still empty when rxn_network.sh calls this (identifyprod.sh
    fills it later), so it is computed here with FormulaPROD.sh, the same way
    identifyprod.sh does."""
    import subprocess

    def amk_formula(natom, geom):
        r = subprocess.run(['FormulaPROD.sh'], input=f'{natom}\n\n{geom}\n',
                           capture_output=True, text=True)
        return r.stdout.strip() or None

    calc = load_calculator(model_name, models_dir)
    # MACE-omol's spin dependence is unreliable (see fragment_energy)
    spin_rule = 'lowest' if model_name.startswith('uma') else 'closed'
    con = sqlite3.connect(prod_db)
    cols = [r[1] for r in con.execute('pragma table_info(prod)')]
    if 'energy_super' not in cols:
        con.execute('alter table prod add column energy_super REAL')
    rows = con.execute("select id,name,energy,energy_super,geom,formula,natom from prod "
                       "where name not like '%min_diss%'").fetchall()
    print(f"AMK_MLIP prodfrag: {len(rows)} products in {prod_db}", flush=True)
    for pid, name, e, esup, geom, formula, natom in rows:
        formula = formula or amk_formula(natom, geom)
        lines = [l.split() for l in geom.strip().splitlines() if len(l.split()) == 4]
        from ase import Atoms
        atoms = Atoms([l[0] for l in lines], positions=[[float(x) for x in l[1:]] for l in lines])
        efr, parts = fragment_energy(atoms, calc, charge, formula, spin_rule)
        if efr is None:
            print(f"  {name:40s} kept supermolecule energy (fragments do not match "
                  f"'{formula}', no bare heavy atom)", flush=True)
            continue
        esup = e if esup is None else esup
        enew = round(efr / Hartree * 627.51, 2)
        con.execute('update prod set energy=?, energy_super=? where id=?', (enew, esup, pid))
        frs = ' + '.join(f'{f}(m={m})' for f, m, _ in parts)
        print(f"  {name:40s} super {esup:12.2f}  fragments {enew:12.2f}  "
              f"diff {enew - esup:8.2f}  {frs}", flush=True)
    con.commit()
    con.close()


def run_serve(req_fifo, resp_fifo, model_name, models_dir, charge, mult):
    """Persistent worker for one amk.sh batch or tors.sh task. Loading the
    UMA checkpoint dominates the cost of every single mlip_calc.py call
    (~30s of a ~40s call), and even for mace each direct call pays the
    python/torch start-up; amk.sh's trajectory loop and tors.sh's scan loop
    make many such calls, each currently paying that cost again. This loads
    the model once and then services one job at a time, read as a single line
    from req_fifo ("md <xyzfile> <temp_K> <duration_fs> [timestep_fs]" /
    "partial_opt <xyzfile> <frozen_csv>" / "tsopt|minopt <xyzfile>" /
    "dihedral_scan <xyzfile> <a1,a2,a3,a4> <dihed0>" -- the same tail already
    passed on the command line for each mode), dispatching to the *_single
    functions with the reused calculator. Writes DONE/ERROR <msg> to
    resp_fifo after each job purely as a completion signal for the bash
    caller (mlip_request in utils.sh) to block on; the existing output-file /
    AMK_TERMINATED_NORMALLY checks in amk.sh/tors.sh are still what decides
    success, unchanged. Exits on a QUIT line (or the request fifo's writer
    going away for good).

    uma on GPU: the fast calculator (load_calculator(fast=True)) is used for
    every job whose composition matches the first one served; a default
    calculator is loaded lazily for any other composition, since the merged
    model can't handle it. AMK_MLIP_FAST=0 disables the fast path."""
    use_fast = model_name.startswith('uma') and os.environ.get('AMK_MLIP_FAST', '1') != '0'
    print(f"AMK_MLIP serve: loading {model_name} (fast={use_fast})...", flush=True)
    fast_calc = load_calculator(model_name, models_dir, fast=use_fast)
    fast_formula = None
    default_calc = None if use_fast else fast_calc
    print("AMK_MLIP serve: model loaded, ready for jobs", flush=True)

    def pick_calc(xyzfile):
        nonlocal fast_formula, default_calc
        if not use_fast:
            return fast_calc
        formula = read(xyzfile).get_chemical_formula()
        if fast_formula is None:
            fast_formula = formula
        if formula == fast_formula:
            return fast_calc
        if default_calc is None:
            print(f"AMK_MLIP serve: composition {formula} != {fast_formula}, "
                  f"loading default {model_name} calculator", flush=True)
            default_calc = load_calculator(model_name, models_dir)
        return default_calc

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
            calc = pick_calc(args[0])
            if calctype == 'md':
                xyzfile, temp_K, duration_fs = args[0], float(args[1]), float(args[2])
                timestep_fs = float(args[3]) if len(args) > 3 else 0.5
                mdc = int(args[4]) if len(args) > 4 else 0
                run_md_single(xyzfile, model_name, models_dir, charge, mult,
                              temp_K, duration_fs, timestep_fs, mdc, calc=calc)
            elif calctype == 'partial_opt':
                xyzfile, frozen_csv = args[0], args[1]
                if frozen_csv == 'NONE':
                    frozen_csv = ''
                run_partial_opt_single(xyzfile, frozen_csv, model_name, models_dir,
                                       charge, mult, calc=calc)
            elif calctype in ('tsopt', 'minopt'):
                xyzfile = args[0]
                run_single(calctype, xyzfile, model_name, models_dir, charge, mult, calc=calc)
            elif calctype == 'dihedral_scan':
                xyzfile, dihedral_csv, dihed0 = args[0], args[1], float(args[2])
                run_dihedral_scan_single(xyzfile, dihedral_csv, dihed0, model_name, models_dir,
                                         charge, mult, calc=calc)
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
        if len(sys.argv) not in (9, 10, 11):
            print("Usage: mlip_calc.py md <xyzfile> <model> <models_dir> <charge> <mult> <temp_K> <duration_fs> [timestep_fs] [mdc]")
            sys.exit(1)
        xyzfile     = sys.argv[2]
        model       = sys.argv[3].lower()
        models_dir  = sys.argv[4]
        charge      = int(sys.argv[5])
        mult        = int(sys.argv[6])
        temp_K      = float(sys.argv[7])
        duration_fs = float(sys.argv[8])
        timestep_fs = float(sys.argv[9]) if len(sys.argv) > 9 else 0.5
        mdc         = int(sys.argv[10]) if len(sys.argv) > 10 else 0
        run_md_single(xyzfile, model, models_dir, charge, mult, temp_K, duration_fs, timestep_fs, mdc)

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

    elif mode == 'prodfrag':
        if len(sys.argv) != 6:
            print("Usage: mlip_calc.py prodfrag <prod.db> <model> <models_dir> <charge>")
            sys.exit(1)
        run_prodfrag(sys.argv[2], sys.argv[3].lower(), sys.argv[4], int(sys.argv[5]))

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
