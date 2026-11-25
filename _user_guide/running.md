---
title: Automated workflows
layout: home
nav_order: 4
permalink: /docs/running.html
---
# Automated workflows

{: .highlight}
A complete study needs only two commands: `llcalcs.sh` runs the
low-level (LL) exploration and `hlcalcs.sh` refines the result at the
high level (HL). Both read the same input file, described in
[Input files](input.html).

Before running them, make sure AutoMeKin-X is on your `PATH`, with the
variables described in [Installation](installation.html#build):
```bash
export AMK=path_to_program
export PATH=$AMK/bin:$AMK/bin/HLscripts:$AMK/bin/MOPAC_DEV:$PATH
export LIBRARY_PATH=$AMK/lib:$AMK/bin/MOPAC_DEV
```
If you use ORCA, Gaussian, Qcore or the MLIP models, they must also be
available in the same shell (see [Engines](engines.html)).

## Low level: `llcalcs.sh` <a name="ll"></a>

```bash
nohup llcalcs.sh molecule.dat ntasks niter runningtasks >llcalcs.log 2>&1 &
```

| Argument | Meaning |
|---|---|
| `molecule.dat` | The input file, in the current folder |
| `ntasks` | Number of tasks (batches of trajectories) per iteration |
| `niter` | Maximum number of iterations |
| `runningtasks` | Number of tasks running at the same time (usually the number of cores) |

Each iteration runs these steps:

1. **TS search.** `ntasks` batches of trajectories (or the sampling chosen
   in the input) look for reactive events and optimize the transition
   states.
2. **IRC.** Each new TS is connected with its reactant and products.
3. **Minima.** The new minima are optimized.
4. **Network and kinetics.** The reaction network is built and the
   kinetics is solved with kinetic Monte Carlo. The product branching
   ratios of every iteration are kept in `tsdirLL_<molecule>/branching_convergence`.

The next iteration starts from the minima found so far. The exploration
stops after `niter` iterations, or earlier when **no new TSs are found in
three consecutive iterations** (with ChemKnow sampling, also when all the
minima have been used). Then, if `barrierless yes` is set in the input,
barrierless channels are searched, and the results are collected in
`FINAL_LL_<molecule>`.

The progress is printed in `llcalcs.log`: the iteration, the time of each
step and the number of new TSs found.

{: .note }
For molecules with many rotatable bonds, the torsional scan of each
iteration can be split among several tasks with the keyword
[`ntorstasks`](dihedral.html).

## High level: `hlcalcs.sh` <a name="hl"></a>

When the low level has finished, run in the same folder:
```bash
nohup hlcalcs.sh molecule.dat runningtasks >hlcalcs.log 2>&1 &
```

It uses the program given in `HighLevel` (Gaussian, ORCA, Qcore or an MLIP)
and runs, in this order:

1. **TS optimization** of the low-level transition states.
2. **IRC** calculations from each optimized TS.
3. **Minima** optimization.
4. **Reaction network** and **kinetics**.
5. **Barrierless channels**, if `barrierless yes` is set (with Gaussian,
   ORCA or an MLIP).
6. **Products**: optimization of the fragments.

The results are collected in `FINAL_HL_<molecule>`, or in
`FINAL_ML_<molecule>` when the high level is an MLIP (UMA or MACE).

## Running under Slurm <a name="slurm"></a>

Both scripts can be submitted to Slurm. In that case, leave out the last
argument (`runningtasks` in `llcalcs.sh`, and the only number in
`hlcalcs.sh`): the number of simultaneous tasks is taken from the `-n`
option of `sbatch`. Submit them from a shell where the `AMK`, `PATH` and
`LIBRARY_PATH` variables above are set: `sbatch` passes them on to the job.

Low level:
```bash
#!/bin/bash
ntasks=20
niter=2
filename=FA
sbatch --output=llcalcs.log --error=llcalcs.err -n $ntasks --mem-per-cpu=2G -t 00:10:00 llcalcs.sh ${filename}.dat $ntasks $niter
```

High level, with Gaussian or ORCA (`-c` sets the cores of each
calculation):
```bash
#!/bin/bash
ntasks=8
ncores=4
filename=FA
module load g16   # or however Gaussian/ORCA is loaded on your cluster
sbatch --output=hlcalcs.log --error=hlcalcs.err -n $ntasks -c $ncores --mem-per-cpu=2G -t 00:30:00 hlcalcs.sh ${filename}.dat
```

High level with an MLIP on a GPU. With a GPU, one process per visible GPU
is used and the number of tasks is ignored, so ask for the GPUs you want to
use (adapt the partition and GPU options to your cluster, and submit from a
shell where `amk_env` is active):
```bash
#!/bin/bash
filename=FA
sbatch --output=hlcalcs.log --error=hlcalcs.err -n 1 --gres=gpu:1 --mem=32G -t 01:00:00 hlcalcs.sh ${filename}.dat
```

{: .note }
Without a GPU, an MLIP run uses `runningtasks` CPU processes, limited by the
available RAM, because each one loads its own copy of the model (about 24 GB
for UMA and 2 GB for MACE). To choose which GPUs a run can see, set
`export CUDA_VISIBLE_DEVICES=...` before launching it. See
[Using ML potentials](mlip.html) for the models and their options.

## After the calculations <a name="after"></a>

- The contents of the `FINAL_*` folders are described in
  [Output files](results.html).
- The networks can be visualized and analyzed with
  [amk_tools_X](analysis.html#amktools).
- The individual scripts that `llcalcs.sh` and `hlcalcs.sh` call are
  described in [Usage of scripts](scripts.html).
- If something goes wrong, [this section](scripts.html#abort) explains how
  to stop the calculations.
