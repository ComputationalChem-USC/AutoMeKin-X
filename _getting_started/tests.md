---
title: Running the tests
layout: home
nav_order: 2
permalink: /docs/tests.html
---
# Running the tests

AutoMeKin-X ships with a set of tests that check the installation and show
the main types of calculation. The input files are installed in
`$AMK/examples`, and the `run_test.sh` script copies each one to its own
folder, runs it, and leaves the results there.

## How to run them <a name="run"></a>

1. Make sure AutoMeKin-X is on your `PATH` and `AMK` points to the
   installation folder, as described in [Installation](installation.html#build).
   If you added these lines to `~/.bashrc`, they are already set:
   ```bash
   export AMK=path_to_program
   export PATH=$AMK/bin:$AMK/bin/HLscripts:$AMK/bin/MOPAC_DEV:$PATH
   export LIBRARY_PATH=$AMK/lib:$AMK/bin/MOPAC_DEV
   ```
   You can check it with `which run_test.sh`.
2. Create an empty folder for the results and run the script from it:
   ```bash
   mkdir amk_tests && cd amk_tests
   run_test.sh
   ```
   Without arguments, all the tests are run one after the other.

3. To run only some of them, list their names after `--tests`, separated by
   commas:
   ```bash
   run_test.sh --tests=FA,FAthermo
   ```

{: .warning }
Each test takes from a few seconds to several minutes, and running all of
them can take a few hours. A folder with the name of each test is created
in the current directory, **replacing any previous folder with the same
name**.

Low-level tests run 2 iterations with 10 tasks each (`FA_ck` runs 10
iterations with 50 tasks). At the end, `run_test.sh` prints a short
description of every test.

## Available tests <a name="list"></a>

Most tests only need MOPAC, which is included in AutoMeKin-X. The ones
marked with Gaussian or Qcore need that program to be installed and on your
`PATH` (see [Engines](engines.html)); without it, they stop at the first
step that calls it.

| Test | What it does | Sampling | Needs |
|---|---|---|---|
| `FA` | Formic acid decomposition: low level, then coarse-grained network, removal of a TS, all-states network, and one- and two-level HL refinement | MD | Gaussian (for the HL part) |
| `FAthermo` | Formic acid, with thermal rate coefficients at 300 K, recomputed at 5000 K with `kinetics.sh` | MD | — |
| `FA_bxde` | Formic acid with BXDE sampling | BXDE | — |
| `FA_singletraj` | One trajectory with a fixed random seed, which finds two TSs | MD-micro | — |
| `FA_biasH2` | H<sub>2</sub> elimination from formic acid, with a biased potential | MD | — |
| `FA_biasH2O` | H<sub>2</sub>O elimination from formic acid, with a biased potential | MD | — |
| `FA_ck` | Formic acid with external forces (ChemKnow) | ChemKnow | — |
| `FA_programopt` | Low-level TSs optimized with Gaussian (`LowLevel_TSopt`), followed by HL refinement | MD | Gaussian |
| `FA_qcore` | Formic acid with Qcore (xtb) at the low and high level | MD | Qcore |
| `FA_bxde_qcore` | BXDE sampling with Qcore (xtb) | BXDE | Qcore |
| `rdiels_bias` | Retro Diels–Alder mechanism, with a biased potential | MD | — |
| `diels_bias` | Diels–Alder mechanism, with a biased potential | MD | — |
| `ttors` | Torsional transition states | MD | — |
| `assoc` | Structures of Bz–N<sub>2</sub> complexes | association | — |
| `assoc_qcore` | Structures of Bz–N<sub>2</sub> complexes with Qcore (xtb) | association | Qcore |
| `vdW` | van der Waals complexes and TSs of Bz–N<sub>2</sub> | vdW | Qcore |

## What to look at <a name="results"></a>

Each folder contains the input file, the log of the workflow
(`llcalcs.log`, `hlcalcs.log`, or `<test>.log`) and, when the test
finishes, the final folders described in [Output files](results.html):
`FINAL_LL_<molecule>` for the low level and `FINAL_HL_<molecule>` for the
high level. They can be visualized with
[amk_tools_X](analysis.html#amktools).

{: .note }
The tests do not cover ORCA or the machine-learning potentials (UMA and
MACE). The [beginners tutorial](beginners.html) runs formic acid with both,
step by step.

{: .highlight}
Some tests can also be run in Google Colab, without installing anything,
[with this notebook](https://colab.research.google.com/github/ComputationalChem-USC/AutoMeKin-X/blob/main/notebooks/AutoMeKin2.ipynb).
