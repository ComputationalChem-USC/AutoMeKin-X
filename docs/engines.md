---
title: Engines
layout: home
nav_order: 3
---

# Engines

AutoMeKin-X delegates the electronic structure (or machine-learning)
calculations to external engines. Each keyword of the `--General--` section
selects the engine for one stage of the workflow:

| Keyword | Stage | Accepted engines |
|---|---|---|
| `LowLevel` | Low-level MD sampling | `mopac` (default), `qcore` |
| `LowLevel_TSopt` | Low-level TS optimization | `mopac`, `qcore`, `g09`, `g16`, `orca`, `mlip <model>` (defaults to the `LowLevel` engine) |
| `LowLevel_IRC` | Low-level IRC and minima optimization | `mlip <model>` (defaults to the `LowLevel_TSopt` engine) |
| `HighLevel` | High-level TS/minima optimization, IRC and frequencies | `g09`, `g16`, `orca`, `qcore`, `mlip <model>` |

## Overview

| Engine | Keyword | Notes |
|---|---|---|
| **MOPAC** | `mopac` | Bundled with the distribution. Default low-level engine; any MOPAC semiempirical method (_e.g._, `pm7`) and MOPAC keywords can be used. |
| **Entos Qcore** | `qcore` | Free for academia. At the low level only the `xtb` method is available; at the high level the method is read from a `qcore_template` file (see the `FA_qcore` example). |
| **Gaussian 09/16** | `g09` / `g16` | Supports HF, MP2 and DFT for optimizations, plus CCSD(T) for single points through the dual-level syntax `method1//method2`. |
| **ORCA** | `orca` | Full high-level support. See [ORCA notes](#orca) below. |
| **MLIP** | `mlip uma` / `mlip mace` | Machine-learning interatomic potentials (Meta FAIR UMA, MACE-OMol) driven through ASE and Sella. See [Using ML potentials](mlip.html). |

## Default number of IRC points

The default value of `IRCpoints` depends on the high-level engine:

| Engine | Default `IRCpoints` |
|---|---|
| `g09` / `g16` | 100 |
| `qcore` | 500 |
| `orca` | 20 |
| `mlip` | 100 |

## ORCA notes <a name="orca"></a>

- AutoMeKin-X calls ORCA through its full path (`$(which orca)`) and unsets
  `SLURM_JOBID`, `PMI_FD`, `PMI_PORT` and `PMIX_*` before each call, so ORCA's
  own MPI parallelization works inside Slurm jobs.
- The method is given with Gaussian-like syntax, _e.g._,
  `HighLevel orca wb97x-d3/def2-tzvp`, and translated to ORCA's syntax.
- **Numerical frequencies are selected automatically** when no analytic
  Hessian is available in ORCA: for MP2 and CCSD(T), and for VV10 functionals,
  _i.e._, functionals whose name ends in `-V` (such as `wB97M-V`). For VV10
  functionals the TS and IRC inputs also include `NumHess true`.

### Delta-ML correction for r2SCAN-3c <a name="delta"></a>

With ORCA at the r2SCAN-3c level, a fourth value activates a delta-machine-learning
correction of the final energies:

```
HighLevel orca r2scan-3c delta
```

After the high-level workflow finishes, a MACE model predicts the difference
between CCSD(T)-F12a/cc-pVDZ-F12 and r2SCAN-3c for every TS, minimum and
product, and adds it to the r2SCAN-3c energies. The model file
(`r2scan_compiled.model`) must be placed in `$AMK/models/`. This option is only
available with `orca` and `r2scan-3c`. The method is described in
[Rodriguez-Lopez et al., Small Structures 2026, 7, e70504](https://onlinelibrary.wiley.com/doi/10.1002/sstr.70504);
see also [AMK-ML-corrections-BH](https://github.com/ComputationalChem-USC/AMK-ML-corrections-BH).
