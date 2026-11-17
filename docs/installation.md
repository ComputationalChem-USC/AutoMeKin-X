---
title: Installation
layout: home
nav_order: 2
---

# Installation

AutoMeKin-X is compiled from its source code with the standard GNU toolchain
(`autoreconf` → `configure` → `make` → `make install`).

{: .highlight }
New to AutoMeKin or to Linux? The [Installation from zero](beginners_install.html)
page of the beginners tutorial walks through every command below on a clean
Ubuntu machine, including the Python environment and the high-level engines.

## Contents
- [Requirements](#requirements)
- [Building AutoMeKin-X](#build)
- [Electronic structure and ML engines](#engines)
- [Installing `amk_tools`](#amktools)

## Requirements <a name="requirements"></a>

{: .highlight }
The following **packages** are required beforehand:
[GNU Autoconf](https://www.gnu.org/software/autoconf/), [GNU Bash](https://www.gnu.org/software/bash/), [GNU bc](https://www.gnu.org/software/bc/), [GNU Awk, gawk](https://www.gnu.org/software/gawk/), [GNU C Compiler, gcc](https://gcc.gnu.org/), [GNU Fortran Compiler, gfortran](https://gcc.gnu.org/wiki/GFortran), [GNU Parallel](https://www.gnu.org/software/parallel/), [SQLite\>= 3](https://www.sqlite.org/index.html) and, optionally, [environment-modules](https://github.com/cea-hpc/modules).
The installation of [molden](https://www.theochem.ru.nl/molden/linux.html) is highly recommended to analyze the results.

{: .highlight }
The following **Python 3 libraries** are needed:
[ASE](https://wiki.fysik.dtu.dk/ase/install.html), [Matplotlib](https://matplotlib.org/stable/users/installing/index.html), [NetworkX](https://networkx.org/documentation/stable/install.html), [NumPy](https://numpy.org/install/), [SciPy](https://scipy.org/install/) and [joblib](https://joblib.readthedocs.io/).

{: .highlight }
If you plan to use the **MLIP** engine (`mlip uma` or `mlip mace`; see [Using ML potentials](mlip.html)), you additionally need:
[PyTorch](https://pytorch.org/get-started/locally/) (2.7 or newer recommended), [Sella](https://github.com/zadorlab/sella), [MACE](https://github.com/ACEsuit/mace) (`mace-torch` on PyPI), [fairchem-core](https://github.com/facebookresearch/fairchem) (for UMA) and [OmegaConf](https://omegaconf.readthedocs.io/).

## Building AutoMeKin-X <a name="build"></a>

```bash
git clone https://github.com/ComputationalChem-USC/AutoMeKin-X.git
cd AutoMeKin-X
autoreconf -i
./configure --prefix=path_to_program
make
make install
```

`path_to_program` is the folder where AutoMeKin-X will be installed, _e.g._,
`$HOME/automekin/install`{: .language-bash .highlight}.

To make the commands available in every new terminal, either add the
installation folders to your `PATH` in `~/.bashrc`:

```bash
export AMK=path_to_program
export PATH=$AMK/bin:$AMK/bin/HLscripts:$AMK/bin/MOPAC_DEV:$PATH
export LIBRARY_PATH=$AMK/lib:$AMK/bin/MOPAC_DEV
```

or, if you use Environment Modules, add `module use path_to_program/modules`
to `~/.bashrc` and load the program with `module load amk/2021`.

## Electronic structure and ML engines <a name="engines"></a>

MOPAC comes with the distribution, so low-level calculations work right after
the build. The high-level engines are installed separately, and only the ones
you plan to use are needed. See [Engines](engines.html) for what each one can do.

| Engine | Keyword | How to get it |
|---|---|---|
| ORCA | `orca` | Free for academic use. Step-by-step instructions in the [beginners tutorial](beginners_install.html#step-7). |
| MLIP (UMA / MACE) | `mlip uma`, `mlip mace` | Python libraries above plus the model files in `$AMK/models/`. See [Using ML potentials](mlip.html) and the [beginners tutorial](beginners_install.html#73-mlip). |
| Gaussian 09/16 | `g09`, `g16` | Commercial license from [Gaussian, Inc.](https://gaussian.com/) |
| Entos Qcore | `qcore` | Free for academia. Conda package `qcore` from the `entos` channel; the tested version (0.8.14) is pinned in the repository's `automekin.yml`. Accept the license once with `qcore --academic-license`. |

{: .note }
The beginners tutorial covers ORCA and the MLIP models only, but **Gaussian and
Entos Qcore remain fully supported**: once `g09`/`g16` or `qcore` are reachable
from your `PATH`, you can use them in the input file exactly as described in the
[General section](general.html).

{: .important }
If you install Qcore in its own conda environment, do not leave that
environment activated while running AutoMeKin: its Python would shadow the one
AutoMeKin needs. Instead, call Qcore through a small wrapper on your `PATH`
(_e.g._, `$AMK/bin/qcore` containing
`exec /path/to/envs/qcore-0.8.14-env/bin/qcore "$@"`).

## Installing `amk_tools` <a name="amktools"></a>

[`amk_tools`](https://github.com/dgarayr/amk_tools) is strongly recommended
for analyzing the results (interactive reaction networks and network
statistics). Install it following the instructions in its repository, or see
[Visualization and analysis with amk_tools](beginners_amktools.html).
