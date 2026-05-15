# Automated Mechanisms and Kinetics (AutoMeKin)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/emartineznunez/AutoMeKin/blob/main/notebooks/AutoMeKin.ipynb) [![Sylabs - AutoMeKin](https://img.shields.io/badge/Sylabs-AutoMeKin-2ea44f)](https://cloud.sylabs.io/library/emartineznunez/default/automekin) [![DOI](https://zenodo.org/badge/476189550.svg)](https://zenodo.org/doi/10.5281/zenodo.10674957) [![AutoMeKin - SOURCEFORGE](https://img.shields.io/badge/AutoMeKin-SOURCEFORGE-2ea44f?logo=%23FF6600)](https://sourceforge.net/projects/automekin-rev1140/)

### This is the official repository of the automated reaction discovery program **AutoMeKin**.

<p align="left">
   <img src="logo.png" alt="AutoMeKin logo" width="200" height="100">
</p>

**AutoMeKin** (formerly `tsscds`) discovers reaction mechanisms automatically. Transition states are located using MD simulations and Graph Theory algorithms; Monte Carlo simulations provide kinetic results. The only required input is a starting molecular structure in XYZ format. The method is described in [Rodriguez et al. (2015)](https://onlinelibrary.wiley.com/doi/abs/10.1002/jcc.23790) and [Martinez-Nunez (2015)](https://pubs.rsc.org/en/content/articlelanding/2015/cp/c5cp02175h).

---

## Content
- [Supported quantum/ML engines](#engines)
- [Installation and documentation](#inst)
- [Simple examples in Colab](#colab)
- [Web interface](#web)

---

## Supported quantum/ML engines <a name="engines"></a>

AutoMeKin can use several backends for high-level (HL) single-point energies, optimizations, frequency calculations, and IRC integrations:

| Backend | Keyword | Notes |
|---|---|---|
| **MOPAC** (built-in) | `mopac` | Default low-level engine, bundled with the package |
| **Gaussian 09/16** | `g09` / `g16` | Standard QM backend |
| **ORCA** | `orca` | Full HL support; `$(which orca)` is used for SLURM-safe execution; variables `SLURM_JOBID`, `PMI_FD`, `PMI_PORT`, `PMIX_*` are unset before each ORCA call to avoid MPI conflicts |
| **Entos Qcore** | `qcore` | |
| **MLIP** (new) | `mlip` | Machine-learning interatomic potentials via [ASE](https://wiki.fysik.dtu.dk/ase/); supports **UMA** (Meta FAIR) and **MACE-OFF23** (large) models |

### MLIP details

When `HighLevel mlip <model>` is set in the input file (with `<model>` = `uma` or `mace`), AutoMeKin uses `mlip_calc.py` to drive geometry optimizations, TS optimizations, IRC integration, and frequency calculations entirely with the chosen MLIP. This avoids the need for a QM code for HL refinement.

**Supported MLIP models:**
- `uma` — Meta FAIR UMA-M model (`uma-m-1p1.pt`)
- `mace` — MACE-OFF23 large model (`MACE-OFF23_large.model`)

Model files are **not** bundled in this repository and must be provided separately in a `models/` directory (or the path set via `models_dir`).

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

## Citation

If you use AutoMeKin in your work, please cite the original papers and the Zenodo release:

> E. Martínez-Núñez et al., *J. Comput. Chem.* **2015**, 36, 222–234.  
> E. Martínez-Núñez, *Phys. Chem. Chem. Phys.* **2015**, 17, 14912–14921.  
> [![DOI](https://zenodo.org/badge/476189550.svg)](https://zenodo.org/doi/10.5281/zenodo.10674957)
