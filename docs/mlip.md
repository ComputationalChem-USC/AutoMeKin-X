---
title: Using ML potentials (MLIP)
layout: home
nav_order: 3.5
---

# Using ML potentials (MLIP)

## Contents
- [Supported quantum/ML engines](#engines)
- [MLIP details](#details)
- [Using MLIP in the input file](#howto)
- [Notes and limitations](#notes)

## Supported quantum/ML engines<a name="engines"></a>

AutoMeKin can use several backends for high-level (HL) single-point energies, optimizations, frequency calculations, and IRC integrations:

| Backend | Keyword | Notes |
|---|---|---|
| **MOPAC** (built-in) | `mopac` | Default low-level engine, bundled with the package |
| **Gaussian 09/16** | `g09` / `g16` | Standard QM backend |
| **ORCA** | `orca` | Full HL support; `$(which orca)` is used for SLURM-safe execution; variables `SLURM_JOBID`, `PMI_FD`, `PMI_PORT`, `PMIX_*` are unset before each ORCA call to avoid MPI conflicts |
| **Entos Qcore** | `qcore` | |
| **MLIP** (new) | `mlip` | Machine-learning interatomic potentials via [ASE](https://wiki.fysik.dtu.dk/ase/) + [Sella](https://github.com/zadorlab/sella); supports **UMA** (Meta FAIR) and **MACE** (OMol-trained) models |

## MLIP details<a name="details"></a>

When `HighLevel mlip <model>` is set in the input file (with `<model>` = `uma` or `mace`), AutoMeKin uses `scripts/mlip_calc.py` to drive geometry optimizations, TS optimizations, IRC integration, and frequency calculations entirely with the chosen MLIP. This avoids the need for a QM code for HL refinement, and automatically uses the GPU (with multi-GPU batch parallelization) when one is available, falling back to CPU otherwise.

**Supported MLIP models:**
- `uma` — Meta FAIR UMA-M model (`uma-m-1p1.pt`, optionally paired with `uma-m-1p1_atom_refs.yaml` for atomic reference energies)
- `mace` — MACE-omol-0-extra-large-1024 model (`MACE-omol-0-extra-large-1024.model`)
- `delta` — delta-ML correction on top of ORCA r2SCAN-3c HL energies (`HighLevel orca r2scan-3c delta`), per [Rodriguez-Lopez et al., Small Structures 2026, 7, e70504](https://onlinelibrary.wiley.com/doi/10.1002/sstr.70504). For more information on how to use it, see [AMK-ML-corrections-BH](https://github.com/ComputationalChem-USC/AMK-ML-corrections-BH).

Model files are **not** bundled in this repository. They must be placed in `$AMK/models/` (the `models` subdirectory of your AutoMeKin installation prefix, `$AMK`) — this path is fixed and is not configurable from the input file. See [Using MLIP in the input file](#howto) below for the exact steps.

## Using MLIP in the input file<a name="howto"></a>

AutoMeKin input files (see `examples/*.dat`) are plain-text keyword files split into sections such as `--General--`, `--Method--`, `--Screening--` and `--Kinetics--`. The `HighLevel` keyword in `--General--` selects the engine used for HL refinement (post-processing of the low-level transition states: optimization, IRC, and frequencies). To use an MLIP instead of a QM code, set it to `mlip` followed by the model name:

```
--General--
molecule  FA
LowLevel  mopac pm7
HighLevel mlip uma
HL_rxn_network complete
charge 0
mult   1

--Method--
sampling MD
ntraj   10

--Screening--
imagmin 200
MAPEmax 0.008
BAPEmax 2.5
eigLmax 0.1

--Kinetics--
Energy 150
```

Swap `uma` for `mace` to use MACE instead:

```
HighLevel mlip mace
```

That's it — no other keyword changes are needed. Everything else (`LowLevel`, `sampling`, screening thresholds, `Kinetics`) works exactly as with a QM `HighLevel` backend such as `g09` or `orca`.

**Steps to enable it:**

1. **Get the model weights.** They are not shipped with AutoMeKin:
   - UMA: `uma-m-1p1.pt` (+ optional `uma-m-1p1_atom_refs.yaml`) from Meta FAIR's [`fairchem`](https://github.com/facebookresearch/fairchem) releases / Hugging Face.
   - MACE: `MACE-omol-0-extra-large-1024.model` from the [MACE](https://github.com/ACEsuit/mace) model releases.
2. **Place them in `$AMK/models/`**, where `$AMK` is your AutoMeKin installation directory:
   ```bash
   mkdir -p "$AMK/models"
   cp uma-m-1p1.pt uma-m-1p1_atom_refs.yaml "$AMK/models/"          # for uma
   cp MACE-omol-0-extra-large-1024.model "$AMK/models/"             # for mace
   ```
   AutoMeKin checks for the exact filenames above; if the file is missing it aborts the run with `MLIP model file not found: ...` before submitting any jobs.
3. **Set `HighLevel mlip <model>`** in the input file, with `<model>` being `uma` or `mace` (case-insensitive).
4. **Set `charge` and `mult`** in `--General--` as usual — `mlip_calc.py` reads them from the input (they can also be overridden per-structure via a `charge=... mult=...` comment line in an XYZ file).
5. **Run AutoMeKin as normal.** Internally, each HL step (`TS.sh`, `IRC.sh`, `MIN.sh`, `PRODs.sh`, barrierless location) calls `mlip_calc.py`, which:
   - loads the chosen model once and batch-processes all pending structures (`batch` mode) for efficiency;
   - runs TS optimizations and IRC integration with Sella, and minima optimizations + frequencies with ASE;
   - automatically detects available GPUs (`torch.cuda.device_count()`) and splits the batch across them; with 0 or 1 GPU it runs on a single device (GPU if usable, otherwise CPU — GPUs with compute capability below `sm_70` are skipped with a warning).

**Installing/using UMA and MACE:** AutoMeKin only calls into these models through `mlip_calc.py`; it does not document their own installation or usage. For specifications on installing and using UMA and MACE themselves, visit their respective repositories: [UMA (fairchem)](https://github.com/facebookresearch/fairchem) and [MACE](https://github.com/ACEsuit/mace).

## Notes and limitations<a name="notes"></a>

- MLIP does not provide a Gibbs free energy correction, so AutoMeKin automatically switches HL Boltzmann/microcanonical sorting to use E+ZPE instead when `HighLevel mlip` is set — set `Energy <value>` under `--Kinetics--` (not `Temperature`) as in the example above.
- `HighLevel mlip` only accepts a single model name — the two-level `method1//method2` HL string supported for `g09`/`g16` does not apply here.
- `IRCpoints` defaults to 100 for `mlip` if not set explicitly.
- For UMA, the optional `uma-m-1p1_atom_refs.yaml` is recommended alongside `uma-m-1p1.pt`: it supplies atomic reference energies used for isolated-atom/single-atom-fragment energies (e.g. barrierless dissociation products); without it those energies can be inaccurate.
- Final results are collected in `FINAL_ML_<molecule>/` instead of the `FINAL_HL_<molecule>/` used by QM backends.
- GPU selection has no dedicated AutoMeKin keyword; to restrict which GPU(s) are visible, `export CUDA_VISIBLE_DEVICES=...` in the shell/job script before launching the run.
- `HL_rxn_network` and the other screening/kinetics keywords behave the same as with QM backends; only the HL refinement engine changes.
