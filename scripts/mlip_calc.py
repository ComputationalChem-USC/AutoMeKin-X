#!/usr/bin/env python3
"""
MLIP calculator for AutoMeKin HL calculations.

Single mode:
  mlip_calc.py tsopt|minopt <xyzfile> <model> <models_dir> <charge> <mult>

Batch mode (loads model once, processes all entries in inputs.db):
  mlip_calc.py batch tsopt|minopt|irc <dir> <model> <models_dir> <charge> <mult>

Name-based calctype dispatch in batch mode:
  min*  → minopt   (min0, minf_*, minr_*)
  ircf* → ircf     (IRC forward)
  ircr* → ircr     (IRC reverse)
  ts*   → tsopt (or whatever calctype is given on the command line)

Supported models: uma, mace
"""
import os
import re
import sys
import sqlite3
import traceback
from pathlib import Path

from ase.io import read
from ase.units import Hartree, kcal, mol

import torch
torch.set_num_threads(1)

# IRC parameters
IRC_DX    = 0.1    # amu^0.5 * Å, step size along IRC
IRC_ETA   = 1e-4
IRC_GAMMA = 0.4
IRC_FMAX  = 0.01   # eV/Å — looser than TS opt to walk the full IRC path
IRC_STEPS = 1000


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
            model_paths=str(model_path), device=device, default_dtype='float64'
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


def run_frequencies(atoms, vib_name):
    from ase.vibrations import Vibrations
    print("  Computing vibrational frequencies...", flush=True)
    vib = Vibrations(atoms, name=vib_name)
    vib.run()
    freqs  = vib.get_frequencies()
    zpe_eV = vib.get_zero_point_energy()
    return freqs, zpe_eV, vib  # caller must call vib.clean() after Molden writing


def write_molden_file(atoms, vib, log_path):
    """Write Molden file with geometry and normal modes alongside the log."""
    atobohr   = 1.889726
    molden_path = log_path.replace('.log', '.molden')
    freqs     = vib.get_frequencies()
    symbols   = atoms.get_chemical_symbols()
    positions = atoms.get_positions()
    nfreq     = len(freqs)

    with open(molden_path, 'w') as f:
        f.write('[Molden Format]\n')
        f.write('[FREQ]\n')
        for freq in freqs:
            if hasattr(freq, 'imag') and freq.imag > 1e-3:
                f_cm = -freq.imag
            else:
                f_cm = freq.real if hasattr(freq, 'real') else float(freq)
            f.write(f'{f_cm:6.1f}\n')
        f.write('       \n')
        f.write('[FR-COORD]\n')
        for sym, pos in zip(symbols, positions):
            f.write(f'{sym} {pos[0]*atobohr:.6f} {pos[1]*atobohr:.6f} {pos[2]*atobohr:.6f}\n')
        f.write('\n')
        f.write('[FR-NORM-COORD]\n')
        for i in range(6, nfreq):
            f.write(f'Vibration {i - 5}\n')
            mode = vib.get_mode(i)
            for disp in mode:
                f.write(f'{disp[0]*atobohr:.6f} {disp[1]*atobohr:.6f} {disp[2]*atobohr:.6f}\n')


def write_log(log_path, model_name, calctype, atoms, freqs, zpe_eV, energy_eV, converged):
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
        for i, freq in enumerate(freqs):
            # ASE returns complex numbers: imaginary modes have freq.imag > 0, freq.real ≈ 0
            # Store imaginary modes as negative values (standard QC convention)
            if hasattr(freq, 'imag') and freq.imag > 1e-3:
                f_cm = -freq.imag
            else:
                f_cm = freq.real if hasattr(freq, 'real') else float(freq)
            f.write(f"{i+1:6d}  {f_cm:12.4f} cm**-1\n")
        f.write("\n")

        f.write(f"Zero point energy {zpe_kcal:.6f} kcal/mol\n")
        f.write(f"FINAL SINGLE POINT ENERGY   {energy_Ha:20.9f}\n\n")
        f.write("AMK_TERMINATED_NORMALLY\n")


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
                freqs, zpe_eV, vib = run_frequencies(atoms, f"{name}_vib")
                write_log(log_path, model_name, calctype, atoms, freqs, zpe_eV, energy_eV,
                          converged)
                write_molden_file(atoms, vib, log_path)
                vib.clean()

        elif calctype == 'minopt':
            if len(atoms) == 1:
                # Single atom: Sella requires ≥2 atoms; just do a single-point energy
                energy_eV = atoms.get_potential_energy()
                write_log(log_path, model_name, calctype, atoms, [], 0.0, energy_eV, True)
            else:
                converged          = run_minopt(atoms, name)
                energy_eV          = atoms.get_potential_energy()
                freqs, zpe_eV, vib = run_frequencies(atoms, f"{name}_vib")
                write_log(log_path, model_name, calctype, atoms, freqs, zpe_eV, energy_eV,
                          converged)
                write_molden_file(atoms, vib, log_path)
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


def _batch_worker(args):
    """Worker function: processes a subset of entries on one GPU."""
    gpu_id, rows, calctype, workdir, model_name, models_dir, charge, mult = args
    # Set GPU visibility before any CUDA initialization
    os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)
    calc = load_calculator(model_name, models_dir)
    print(f"  [GPU {gpu_id}] model loaded, {len(rows)} entries", flush=True)
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
    """Process all entries from inputs.db; distributes across all available GPUs."""
    import multiprocessing as mp

    print(f"AMK_MLIP batch: {calctype} | model={model_name} | charge={charge} | mult={mult}",
          flush=True)

    db_path = os.path.join(workdir, 'inputs.db')
    con = sqlite3.connect(db_path)
    rows = con.execute("SELECT name, input FROM gaussian ORDER BY id").fetchall()
    con.close()

    ngpus = torch.cuda.device_count() if torch.cuda.is_available() else 0

    if ngpus <= 1:
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
    else:
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

    print("\nBatch complete.", flush=True)


def run_single(calctype, xyzfile, model_name, models_dir, charge, mult):
    """Single-structure mode."""
    name     = Path(xyzfile).stem
    log_path = f"{name}.log"

    print(f"AMK_MLIP: {calctype} | model={model_name} | charge={charge} | mult={mult}",
          flush=True)

    try:
        calc  = load_calculator(model_name, models_dir)
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
                freqs, zpe_eV, vib = run_frequencies(atoms, f"{name}_vib")
                write_log(log_path, model_name, calctype, atoms, freqs, zpe_eV, energy_eV,
                          converged)
                write_molden_file(atoms, vib, log_path)
                vib.clean()

        elif calctype == 'minopt':
            if len(atoms) == 1:
                energy_eV = atoms.get_potential_energy()
                write_log(log_path, model_name, calctype, atoms, [], 0.0, energy_eV, True)
            else:
                converged          = run_minopt(atoms, name)
                energy_eV          = atoms.get_potential_energy()
                freqs, zpe_eV, vib = run_frequencies(atoms, f"{name}_vib")
                write_log(log_path, model_name, calctype, atoms, freqs, zpe_eV, energy_eV,
                          converged)
                write_molden_file(atoms, vib, log_path)
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
        sys.exit(1)


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

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
