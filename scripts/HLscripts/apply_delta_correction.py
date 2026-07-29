#!/usr/bin/env python3
"""
apply_delta_correction.py <FINAL_dir> <models_dir>

Applies a delta-ML correction to the ts.db, min.db, and prod.db energies
stored in a FINAL_HL_<molecule> directory produced with
`HighLevel orca r2scan-3c delta`.

E_delta = E_r2SCAN-3c + model(geometry)   [Hartree]

The model (<models_dir>/r2scan_compiled.model) is a MACE TorchScript model
predicting the delta(CCSD(T)-F12a/cc-pVDZ-F12 - r2SCAN-3c) correction, in eV,
as described in Rodriguez-Lopez et al., Small Structures 2026, 7, e70504.

For prod.db, geometries holding dissociated fragment pairs are split by
connectivity (bond cutoff 2.0 Angstrom) and the correction is applied to
and summed over each fragment separately, to avoid the model seeing
artificial interactions between far-separated fragments.
"""
import sqlite3
import sys
from pathlib import Path
from collections import deque

import numpy as np
import ase

EV_TO_HA = 1.0 / 27.211386245988
BOND_CUTOFF = 2.0  # Angstrom -- fragment split cutoff for prod.db

MODEL_FILENAME = "r2scan_compiled.model"


def parse_geom(geom_str):
    symbols, positions = [], []
    for line in geom_str.strip().split('\n'):
        parts = line.split()
        if len(parts) == 4:
            symbols.append(parts[0])
            positions.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return symbols, np.array(positions)


def split_fragments(symbols, positions, cutoff=BOND_CUTOFF):
    """Return a list of (symbols, positions) per connected component."""
    n = len(symbols)
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if np.linalg.norm(positions[i] - positions[j]) < cutoff:
                adj[i].append(j)
                adj[j].append(i)

    visited = [False] * n
    fragments = []
    for start in range(n):
        if visited[start]:
            continue
        queue = deque([start])
        component = []
        while queue:
            node = queue.popleft()
            if visited[node]:
                continue
            visited[node] = True
            component.append(node)
            queue.extend(adj[node])
        fragments.append(component)

    return [([symbols[i] for i in frag], positions[frag]) for frag in fragments]


def load_calculator(model_path):
    from mace.calculators import MACECalculator
    return MACECalculator(model_paths=str(model_path), device='cpu', default_dtype='float64')


def predict_delta(calc, symbols, positions):
    atoms = ase.Atoms(symbols=symbols, positions=positions)
    atoms.calc = calc
    return atoms.get_potential_energy() * EV_TO_HA


def apply_to_db(db_path, table, calc, fragment_mode=False):
    if not db_path.exists():
        return
    con = sqlite3.connect(db_path)
    rows = con.execute(f'SELECT id, energy, geom FROM {table}').fetchall()
    mode_label = ' [per-fragment]' if fragment_mode else ''
    print(f'  {db_path.name} ({table}){mode_label}: {len(rows)} entries', flush=True)

    updates = []
    for i, (row_id, e_baseline, geom) in enumerate(rows):
        symbols, positions = parse_geom(geom)

        if fragment_mode:
            frags = split_fragments(symbols, positions)
            delta = sum(predict_delta(calc, s, p) for s, p in frags)
        else:
            delta = predict_delta(calc, symbols, positions)

        e_delta = e_baseline + delta
        updates.append((e_delta, row_id))

        if (i + 1) % 50 == 0 or i + 1 == len(rows):
            print(f'    {i + 1}/{len(rows)} processed', flush=True)

    con.executemany(f'UPDATE {table} SET energy=? WHERE id=?', updates)
    con.commit()
    con.close()
    if updates:
        print(f'    Done. Example: E_orig={rows[0][1]:.6f} -> E_delta={updates[0][0]:.6f} Ha', flush=True)


def main():
    if len(sys.argv) != 3:
        print(f'Usage: {Path(sys.argv[0]).name} <FINAL_dir> <models_dir>')
        sys.exit(1)

    final_dir = Path(sys.argv[1])
    model_path = Path(sys.argv[2]) / MODEL_FILENAME
    if not model_path.is_file():
        print(f'Delta correction model not found: {model_path}')
        sys.exit(1)

    print('Loading MACE delta-correction calculator...', flush=True)
    calc = load_calculator(model_path)
    print('Calculator ready.\n', flush=True)

    for db_file, table, frag_mode in [
        (final_dir / 'ts.db',   'ts',   False),
        (final_dir / 'min.db',  'min',  False),
        (final_dir / 'prod.db', 'prod', True),
    ]:
        print(f'Processing {db_file.name}...', flush=True)
        apply_to_db(db_file, table, calc, fragment_mode=frag_mode)
        print()

    print(f'Delta correction applied to all energy databases in {final_dir}.')


if __name__ == '__main__':
    main()
