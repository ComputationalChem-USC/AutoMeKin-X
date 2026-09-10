---
title: 2. Low-level (LL) calculations
layout: home
parent: Complete tutorial for beginners
grand_parent: Tutorial
nav_order: 2
---

# Low-level (LL) calculations

## Contents

- [LL vs HL: what this page covers](#ll-vs-hl)
- [Setting up the working folder](#setup)
- [The `amk.dat` input file](#input-file)
- [Launching the calculation](#launch)
- [What happens while it runs: the iteration loop](#loop)
- [Where results actually live — and why `batch*` disappears](#where)
- [Reading the final results](#reading-results)
- [Full verified example: FA (formic acid)](#example-fa)
- [Common troubleshooting](#troubleshooting)
- [What's next](#whats-next)

## LL vs HL: what this page covers <a name="ll-vs-hl"></a>

As covered on the [installation page](beginners_install.html),
AutoMeKin works at two levels:

- **LL (Low Level):** fast, uses MOPAC by default. Hundreds of
  molecular dynamics trajectories are launched from the starting
  structure to **discover** candidate transition states (TS), without
  worrying yet about final accuracy.
- **HL (High Level):** slow and accurate, supporting several
  computational chemistry programs (Gaussian, ORCA, Qcore, or an MLIP
  model). Applied only **afterward**, to the most promising TSs
  already found at LL — covered on the next two pages.

This page stays entirely at **LL**: AutoMeKin is used to explore a
molecule's potential energy surface with MOPAC and build its first
reaction network.

## Setting up the working folder <a name="setup"></a>

Create a folder for this exercise and enter it:

```bash
mkdir -p test_example_dft
cd test_example_dft
```

Two files are needed: the starting structure (`.xyz`) and the input
file (`.dat`).

### Starting structure

This example uses formic acid (CH₂O₂) — it's the reference molecule
AutoMeKin uses in its own test suite. Save this as `FA.xyz`:

```
5

C 0.000000 0.000000 0.000000
O 0.000000 0.000000 1.220000
O 1.212436 0.000000 -0.700000
H -0.943102 0.000000 -0.544500
H 1.038843 0.000000 -1.634005
```

The first line is the atom count, the second is left blank (or holds
a comment), then one line per atom: symbol + X Y Z coordinates in Å.
It doesn't need to be a perfectly optimized geometry — MOPAC optimizes
it as a first step anyway.

## The `amk.dat` input file <a name="input-file"></a>

AutoMeKin needs an input file with the instructions for the
calculations to run: which molecule to use, which method to explore
the potential energy surface with (LL), which method to refine the
results with (HL), and other settings that control the search.

Save this as `FA.dat` in the same folder:

```
--General--
molecule  FA
LowLevel  mopac pm7 t=5m
HighLevel orca wB97x-D3/def2-TZVP
HL_rxn_network complete
IRCpoints 29
charge 0
mult   1
timeout 1000

--Method--
sampling    MD
ntraj       10
barrierless yes

--Screening--
imagmin 200
MAPEmax 0.008
BAPEmax 2.5
eigLmax 0.1

--Kinetics--
Energy 150
```

**By section:**

| Section | Keyword | Meaning |
|---|---|---|
| `--General--` | `molecule FA` | Must match `FA.xyz` |
| | `LowLevel mopac pm7 t=5m` | LL engine: MOPAC, PM7 method. `t=5m` is MOPAC's own keyword (internal 5-minute limit per calculation) |
| | `HighLevel orca ...` | **Required even though this page doesn't use it** — see the warning below |
| | `charge`, `mult` | Charge and spin multiplicity |
| | `timeout 1000` | Max seconds a single task may run before it's killed (protects against hung calculations) |
| `--Method--` | `sampling MD` | Molecular-dynamics sampling (the default method) |
| | `ntraj 10` | Internal trajectory-sampling parameter |
| | `barrierless yes` | Also search for barrierless dissociation channels (NEB) |
| `--Screening--` | `imagmin`, `MAPEmax`, `BAPEmax`, `eigLmax` | Thresholds for filtering real TS candidates |
| `--Kinetics--` | `Energy 150` | Internal energy (kcal/mol) for the Monte Carlo kinetics simulation |

{: .warning }
Even for a 100% LL calculation, the `HighLevel` keyword is required —
omitting it causes an error (`HighLevel keyword has not been
defined`).

## Launching the calculation <a name="launch"></a>

The script that orchestrates the whole LL search, iteration after
iteration, is `llcalcs.sh`. Besides the input file, it takes three
arguments — `ntasks`, `niter`, and `runningtasks`:

| Position | Name | Meaning |
|---|---|---|
| 1st (`FA.dat`) | input file | |
| 2nd (`10`) | **ntasks** (`nbatch`) | How many new tasks/trajectories get launched **per iteration** |
| 3rd (`5`) | **niter** | Maximum number of search-loop iterations |
| 4th (`10`) | **runningtasks** | How many tasks run **concurrently** at once |

`10 5 10` is used in this example because formic acid is a small,
fast-to-compute molecule: 10 trajectories per iteration over 5
iterations (50 trajectories total) is enough to sample its potential
energy surface thoroughly, and running all 10 concurrently keeps the
whole search quick on a normal desktop.

It's invoked like this:

```bash
nohup llcalcs.sh FA.dat 10 5 10 > llcalcs.log 2>&1 &
```

With `ntasks=10` and `runningtasks=10`, all 10 tasks of each iteration
start at once (on a machine with ≥10 free cores). If `runningtasks`
were smaller than `ntasks`, they'd run in batches instead.

`nohup ... &` sends the process to the background and keeps it running
even if the terminal is closed. Monitor it with:

```bash
tail -f llcalcs.log
```

## What happens while it runs: the iteration loop <a name="loop"></a>

Each loop iteration does, in order:

1. **Running TS search** — launches `ntasks` new MD trajectories in
   parallel (up to `runningtasks` at a time), looking for candidate
   transition states.
2. **Running IRC** — for each TS candidate, integrates the reaction
   path forward and backward (IRC) to confirm which minima it
   connects.
3. **Checks for new TSs.** If none were found this iteration, it's
   discarded and the loop continues. If this happens **3 iterations in
   a row**, the loop stops early due to convergence, even if `niter`
   hasn't been reached yet.
4. **Running min opt** — optimizes the minima connected to the new
   TSs.
5. **Building network** — rebuilds the full reaction network with
   everything found so far.
6. **Running Kinetics** — recomputes the Monte Carlo kinetics with the
   updated network.

Once all iterations finish (or convergence stops it early), if
`barrierless yes` was set, one more phase runs:

7. **Adding Barrierless reactions** — searches for barrierless
   dissociation channels with NEB.

Then the final results folder is built.

## Where results actually live — and why `batch*` disappears <a name="where"></a>

There are two places where data actually persists:

### `tsdirLL_<molecule>/` — the working database (accumulates iteration after iteration)

| Folder | Contents |
|---|---|
| `TSs/` | MOPAC outputs for every TS found + `ts.db` |
| `IRC/` | IRC integrations (forward/backward) from each TS |
| `MINs/` | Optimized minima + `min.db` |
| `PRODs/` | Identified products + `prod.db` |
| `KMC/` | Kinetics results: `RXNet`, `kmcE*.out`, `branchingE*.out` |
| `track.db` | History of TSs per iteration (what the script uses to decide convergence) |

This folder can be inspected at any time, even while the run is still
active, to see the raw detail of a specific TS or minimum.

{: .note }
`batch1`, `batch2`, ... folders appear in the working directory while
a run is active — those are the *scratch* space for each individual
task. `llcalcs.sh` deletes them automatically once their useful
results have been copied elsewhere. Not seeing them after a run
finishes is expected, not a problem.

### `FINAL_LL_<molecule>/` — the curated final summary

Generated once, when the whole loop finishes. This is the folder to
read results from — covered next.

## Reading the final results <a name="reading-results"></a>

Inside `FINAL_LL_FA/` (replace `FA` with the molecule's name):

| File | What it is |
|---|---|
| `RXNet` | The full reaction network: each TS, its relative energy (ΔE in kcal/mol vs. the global minimum), and what it connects (`MIN i <---> MIN j`, or `MIN i ----> PRk: formula` for irreversible channels to products) |
| `RXNet.rel` / `RXNet.cg` | Filtered/reduced variants of the network (only the relevant channels, or the connected graph) |
| `RXNet.barrless` | Barrierless dissociation channels found by NEB |
| `MINinfo` | List of minima with their ΔE; conformational isomers are grouped on the same line |
| `TSinfo` | List of TSs with their ΔE (same format) |
| `convergence.txt` | How many TSs had been found after each batch of 100 trajectories — useful to see whether sampling is flattening out (converging) or whether more iterations would help |
| `kinetics.csv` | Time evolution (Monte Carlo) of each species' population |
| `rxn_kin.txt` | Branching ratios: what fraction of the reaction flux ends up at each product/minimum from the starting point |
| `min.db`, `ts.db`, `prod.db` | The same SQLite databases, now consolidated |

## Full verified example: FA (formic acid) <a name="example-fa"></a>

With the exact setup above (`ntasks=10 niter=5 runningtasks=10`), this
was the result of a complete run:

**`convergence.txt`** — sampling flattened out (7 → 11 → 12 → 12 → 13
TSs every 100 more trajectories):

```
 Iter #          TSs       ntrajs
      1            7          100
      2           11          200
      3           12          300
      4           12          400
      5           13          500
```

**`RXNet`** — 13 TSs found, including the two known decomposition
channels of formic acid:

```
 TS #   DE(kcal/mol)           Reaction path information
 ====   ============           =========================
    1       -1.4       PR1:  CO + H2O <--->       PR1:  CO + H2O
    2        1.9             MIN    1 <--->             MIN    2
    6       32.8       PR3:  H2 + CO2 <--->       PR1:  CO + H2O
    7       37.6             MIN    4 ---->       PR1:  CO + H2O
    9       44.0             MIN    3 ---->       PR3:  H2 + CO2
   ...
```

**`rxn_kin.txt`** — 83.8% of the reaction flux from the most stable
minimum ends up at CO + H₂O, 1.8% at H₂ + CO₂, and the rest gets
trapped in intermediate isomers:

```
1 3 0.0854545
1 6 0.00545455
3 CO+H2O 0.0518182
1 CO+H2O 0.838182
3 H2+CO2 0.000909091
1 H2+CO2 0.0181818
```

{: .note }
Slightly different numbers from a different run are expected: MD
sampling starts from random temperatures/velocities, so each run
explores a somewhat different set of trajectories.

## Common troubleshooting <a name="troubleshooting"></a>

| Symptom | Cause | Fix |
|---|---|---|
| `HighLevel keyword has not been defined` | Missing `HighLevel` line in the `.dat`, even for an LL-only run | Add `HighLevel orca <method>` (or `g09`/`g16`/`qcore`/`mlip`) — see [the input file section](#input-file) |
| `HighLevel value is X, and it should be qcore, g09, g16, orca or mlip` | An unsupported value (e.g. `mopac`) was put in `HighLevel` | Use one of the five valid values |
| No `batch*` folders after running | They auto-delete when each iteration/the run finishes — normal behavior | Check `tsdirLL_<molecule>/` for raw detail, or `FINAL_LL_<molecule>/` for the summary |
| `$inputfile is not in this folder` | `llcalcs.sh` was run from a different directory | `cd` into the folder with the `.dat` and `.xyz` before launching |
| `Number of batches and/or number of iterations have not been set` | `llcalcs.sh` was called with fewer than 4 arguments (outside SLURM) | Use the full form: `llcalcs.sh inputfile ntasks niter runningtasks` |
| The run stops before reaching `niter` | Convergence: 3 iterations in a row with no new TSs | Expected behavior, not an error — check `convergence.txt` |

## What's next <a name="whats-next"></a>

With a complete LL reaction network in hand, the [next
page](beginners_highlevel_orca.html) takes these same results and
refines the most relevant TSs at **high level (HL)** with ORCA,
comparing how the energies shift relative to LL.
