# AutoMeKin-X: Next-Generation Development Version of AutoMeKin 2026.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/emartineznunez/AutoMeKin/blob/main/notebooks/AutoMeKin.ipynb) [![Sylabs - AutoMeKin](https://img.shields.io/badge/Sylabs-AutoMeKin-2ea44f)](https://cloud.sylabs.io/library/emartineznunez/default/automekin) [![DOI](https://zenodo.org/badge/476189550.svg)](https://zenodo.org/badge/latestdoi/476189550) [![AutoMeKin - SOURCEFORGE](https://img.shields.io/badge/AutoMeKin-SOURCEFORGE-2ea44f?logo=%23FF6600)](https://sourceforge.net/projects/automekin-rev1140/)

### This is the official repository of the automated reaction discovery program **AutoMeKin**.

<p align="left">
   <img src="banner.png" alt="AutoMeKin-X banner" width="700">
</p>

**AutoMeKin** (formerly `tsscds`) discovers reaction mechanisms automatically. Transition states are located using MD simulations and Graph Theory algorithms; Monte Carlo simulations provide kinetic results. The only required input is a starting molecular structure in XYZ format. The method is described in [Rodriguez et al. (2015)](https://onlinelibrary.wiley.com/doi/abs/10.1002/jcc.23790) and [Martinez-Nunez (2015)](https://pubs.rsc.org/en/content/articlelanding/2015/cp/c5cp02175h).

---

## Content
- [Supported quantum/ML engines](#engines)
- [Using ML potentials (MLIP) in the input file](#mlip-howto)
- [Installation and documentation](#inst)
- [Simple examples in Colab](#colab)
- [Web interface](#web)
- [ML methods comparison — MEA gallery](#gallery)

---

## Supported quantum/ML engines <a name="engines"></a>

AutoMeKin can use several backends for high-level (HL) single-point energies, optimizations, frequency calculations, and IRC integrations:

| Backend | Keyword | Notes |
|---|---|---|
| **MOPAC** (built-in) | `mopac` | Default low-level engine, bundled with the package |
| **Gaussian 09/16** | `g09` / `g16` | Standard QM backend |
| **ORCA** | `orca` | Full HL support; `$(which orca)` is used for SLURM-safe execution; variables `SLURM_JOBID`, `PMI_FD`, `PMI_PORT`, `PMIX_*` are unset before each ORCA call to avoid MPI conflicts |
| **Entos Qcore** | `qcore` | |
| **MLIP** (new) | `mlip` | Machine-learning interatomic potentials via [ASE](https://wiki.fysik.dtu.dk/ase/) + [Sella](https://github.com/zadorlab/sella); supports **UMA** (Meta FAIR) and **MACE** (OMol-trained) models |

### MLIP details

When `HighLevel mlip <model>` is set in the input file (with `<model>` = `uma` or `mace`), AutoMeKin uses `scripts/mlip_calc.py` to drive geometry optimizations, TS optimizations, IRC integration, and frequency calculations entirely with the chosen MLIP. This avoids the need for a QM code for HL refinement, and automatically uses the GPU (with multi-GPU batch parallelization) when one is available, falling back to CPU otherwise.

**Supported MLIP models:**
- `uma` — Meta FAIR UMA-M model (`uma-m-1p1.pt`, optionally paired with `uma-m-1p1_atom_refs.yaml` for atomic reference energies)
- `mace` — MACE-omol-0-extra-large-1024 model (`MACE-omol-0-extra-large-1024.model`)

Model files are **not** bundled in this repository. They must be placed in `$AMK/models/` (the `models` subdirectory of your AutoMeKin installation prefix, `$AMK`) — this path is fixed and is not configurable from the input file. See [Using ML potentials](#mlip-howto) below for the exact steps.

---

## Using ML potentials (MLIP) in the input file <a name="mlip-howto"></a>

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

**Notes / limitations:**
- MLIP does not provide a Gibbs free energy correction, so AutoMeKin automatically switches HL Boltzmann/microcanonical sorting to use E+ZPE instead when `HighLevel mlip` is set — set `Energy <value>` under `--Kinetics--` (not `Temperature`) as in the example above.
- `HighLevel mlip` only accepts a single model name — the two-level `method1//method2` HL string supported for `g09`/`g16` does not apply here.
- `IRCpoints` defaults to 100 for `mlip` if not set explicitly (vs. 500 for `qcore`, 100 for `g09`/`g16`, 20 for `orca`).
- For UMA, the optional `uma-m-1p1_atom_refs.yaml` is recommended alongside `uma-m-1p1.pt`: it supplies atomic reference energies used for isolated-atom/single-atom-fragment energies (e.g. barrierless dissociation products); without it those energies can be inaccurate.
- Final results are collected in `FINAL_ML_<molecule>/` instead of the `FINAL_HL_<molecule>/` used by QM backends.
- GPU selection has no dedicated AutoMeKin keyword; to restrict which GPU(s) are visible, `export CUDA_VISIBLE_DEVICES=...` in the shell/job script before launching the run.
- `HL_rxn_network` and the other screening/kinetics keywords behave the same as with QM backends; only the HL refinement engine changes.
- To compare MLIP results against a QM reference, see the [MEA gallery](#gallery) below, which benchmarks UMA and MACE against DFT and CCSD(T)-F12 on a full reaction network.

---

## Installation and documentation <a name="inst"></a>

Verify if your version is up to date [here](https://github.com/emartineznunez/AutoMeKin/blob/main/ChangeLog.md).  
Full installation instructions and documentation are [detailed here](https://emartineznunez.github.io/AutoMeKin).

Build scripts for common platforms are included:

```bash
bash Build_Ubuntu.sh      # Ubuntu/Debian
bash Build_Centos.sh      # CentOS/RHEL
bash Build_micromamba.sh  # any platform via micromamba
```

A ready-to-use conda environment file is also provided:

```bash
conda env create -f automekin.yml
```

---

## Simple examples in Colab <a name="colab"></a>

- [Notebook 1](https://colab.research.google.com/github/emartineznunez/AutoMeKin/blob/main/notebooks/AutoMeKin.ipynb) — install, run a basic example, explore results.
- [Notebook 2](https://colab.research.google.com/github/emartineznunez/AutoMeKin/blob/main/notebooks/AutoMeKin2.ipynb) — further tests and advanced options.

---

## Web interface <a name="web"></a>

Submit simple examples directly at [https://rxnkin.usc.es/amk/](https://rxnkin.usc.es/amk/).

---

## ML methods comparison — MEA gallery <a name="gallery"></a>

An interactive gallery comparing four levels of theory on the full reaction network of monoethanolamine (MEA, C₂H₇NO) — 980 Tier-1 matched transition states across four tabs:

| Tab | Description |
|---|---|
| **HL ↔ UMA** | DFT (wB97X-D3/def2-TZVP) vs. Meta FAIR UMA |
| **HL ↔ MACE** | DFT vs. MACE-OFF23 |
| **HL ↔ DELTA** | DFT vs. r²SCAN-3c corrected with a delta-ML model |
| **HL ∩ UMA ∩ MACE ∩ DELTA** | 174 Tier-1 reactions identified at all four levels |

Each card shows a side-by-side 3D rendering of the left endpoint, transition state, and right endpoint for every method. Clicking a card opens an interactive viewer (drag to rotate, scroll to zoom) with forward/reverse barriers and reaction enthalpies vs. CCSD(T)-F12.

### 👉 [Open MEA gallery](https://htmlpreview.github.io/?https://raw.githubusercontent.com/OmarRodriguezLopez1398/AutoMeKin-X/main/ML_IMP_EXAMPLES/mea_gallery.html)

> The gallery is a fully self-contained HTML file (no external dependencies). It can also be downloaded from [`ML_IMP_EXAMPLES/mea_gallery.html`](ML_IMP_EXAMPLES/mea_gallery.html) and opened locally.

---

## Citation

If you use AutoMeKin in your work, please cite the original papers and the Zenodo release:

> E. Martínez-Núñez et al., *J. Comput. Chem.* **2015**, 36, 222–234.  
> E. Martínez-Núñez, *Phys. Chem. Chem. Phys.* **2015**, 17, 14912–14921.  
> [![DOI](https://zenodo.org/badge/476189550.svg)](https://zenodo.org/badge/latestdoi/476189550)
