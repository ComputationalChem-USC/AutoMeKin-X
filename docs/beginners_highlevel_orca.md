---
title: 3. High-level (HL) calculations with ORCA
layout: home
parent: Complete tutorial for beginners
grand_parent: Tutorial
nav_order: 3
---

# High-level (HL) calculations with ORCA

Continuation of the [low-level calculations
page](beginners_lowlevel.html): this page refines with ORCA (DFT) the
reaction network discovered at low level with MOPAC.

## Contents

- [What the HL step does](#what-hl-does)
- [Requirements before starting](#requirements)
- [Launching the calculation](#launch)
- [What happens while it runs: `hlcalcs.sh`'s phases](#phases)
- [Where results live](#where)
- [Reading the final results](#reading-results)
- [Full verified example: FA at wB97x-D3/def2-TZVP](#example-fa)
- [Common troubleshooting](#troubleshooting)
- [What's next](#whats-next)

## What the HL step does <a name="what-hl-does"></a>

Low level (previous page) is cheap but imprecise: MOPAC/PM7 is good
for **discovering** the topology of the reaction network (how many TSs
there are, which minima they connect), but its energies aren't
reliable. The **high-level (HL)** step takes exactly those
already-located TSs and:

1. **Re-optimizes** them with a more accurate method (here,
   wB97x-D3/def2-TZVP DFT with ORCA).
2. Confirms with **frequencies** that they're still real saddle
   points.
3. Repeats the **IRC** to confirm which minima each one connects, now
   at this level of theory.
4. Rebuilds the reaction network and kinetics with the corrected
   energies.

HL **doesn't search for new TSs** — it only refines the ones already
found. That's why there's no `ntasks`/`niter` like at LL: it's a
single pass, not an exploration loop.

## Requirements before starting <a name="requirements"></a>

- The [low-level page](beginners_lowlevel.html) completed:
  `tsdirLL_<molecule>/` with its `tslist` already generated.
- ORCA installed and on the `PATH` (see the [installation
  page](beginners_install.html), section 7.2).
- The same `amk.dat` from the LL page, with the `HighLevel` keyword
  already set — in this example `HighLevel orca wB97x-D3/def2-TZVP`.

{: .warning }
**One important adjustment to `amk.dat` before launching HL:** if
`timeout 1000` was set on the LL page for the MOPAC tasks, remove it
(or raise it a lot) before this step. A DFT calculation with ORCA can
easily take longer than 1000 seconds, and `parallel --timeout` would
kill the task mid-calculation. Without the keyword, it falls back to
the default (~11.6 days, effectively unlimited).

```bash
sed -i '/^timeout /d' FA.dat
```

## Launching the calculation <a name="launch"></a>

The script that orchestrates the whole HL refinement is `hlcalcs.sh`.
Unlike `llcalcs.sh`, it only takes **two arguments**:

```bash
nohup hlcalcs.sh FA.dat 10 > hlcalcs.log 2>&1 &
```

| Position | Name | Meaning |
|---|---|---|
| 1st (`FA.dat`) | input file | Same one from the LL page |
| 2nd (`10`) | **runningtasks** | How many ORCA jobs run concurrently |

**Important detail about parallelism:** outside SLURM, each ORCA job
defaults to **1 single core**
(`nprocs=${SLURM_CPUS_PER_TASK:-1}`, and outside SLURM that variable
doesn't exist → 1). In other words, parallelism doesn't come from
splitting cores within a single ORCA calculation, but from how many
ORCA calculations run *at once* — which is exactly what `runningtasks`
controls. With 10, up to 10 simultaneous `orca` processes run, each on
1 core.

Monitor it the same way as on the LL page:

```bash
tail -f hlcalcs.log
```

## What happens while it runs: `hlcalcs.sh`'s phases <a name="phases"></a>

`hlcalcs.sh` runs, in order, a different script per phase:

1. **Running TS opt** — reads the TSs from the LL page and launches an
   ORCA TS optimization for each one (`OptTS TightOpt TightSCF Freq`),
   plus an optimization of the starting minimum. All run in parallel,
   `runningtasks` at a time.
2. **Running IRC** — first checks, using each optimized TS's
   imaginary frequency, which ones are still real saddle points;
   discards the ones that aren't. Of those remaining, it also excludes
   any that exceed the energy threshold set by `Energy` in
   `--Kinetics--`. For the rest, it launches forward and backward IRC.
3. **Running min opt** — optimizes the minima each IRC endpoint
   connects to.
4. **Building network** — rebuilds the full network with HL energies.
5. **Running kinetics** — recomputes the Monte Carlo kinetics with the
   corrected network.
6. **Adding barrless procs** — repeats the barrierless-channel search
   (NEB), this time at DFT level (only if `barrierless yes` was set).
7. **Running frags opt** — optimizes the final products.

Finally, the results folder is built.

## Where results live <a name="where"></a>

Exactly the same pattern as at LL, but with `HL` instead of `LL` in
the names:

- **`tsdirHL_<molecule>/`** — the persistent working database: `TSs/`,
  `IRC/`, `MINs/`, `PRODs/`, `KMC/`, with the actual ORCA
  `.inp`/`.out` files and the corresponding SQLite databases.
- **`FINAL_HL_<molecule>/`** — the curated final summary, generated
  once everything finishes.

## Reading the final results <a name="reading-results"></a>

`FINAL_HL_<molecule>/` has the same files already familiar from LL:
`RXNet`, `RXNet.rel`, `RXNet.cg`, `RXNet.barrless`, `MINinfo`,
`TSinfo`, `kinetics.csv`, `rxn_kin.txt`, `min.db`, `ts.db`, `prod.db`.
The only difference is that the energies (`DE(kcal/mol)`) now come
from DFT instead of a semiempirical (SQM) method — much more reliable,
but also much more expensive to compute.

{: .note }
There's no `convergence.txt` at HL — that file is specific to the LL
iterative loop; HL is a single pass, so it doesn't apply.

## Full verified example: FA at wB97x-D3/def2-TZVP <a name="example-fa"></a>

With `runningtasks=10` over the 13 TSs from the LL page, this was the
result:

**Total time** (10 ORCA jobs in parallel, 1 core each): **~1h50min**.

**`RXNet`** — of the 13 candidate TSs from LL, **11 survived** HL
refinement (2 didn't converge to a real saddle point at this level, or
fell outside the energy threshold):

```
 TS #   DE(kcal/mol)           Reaction path information
 ====   ============           =========================
    1        7.6             MIN    1 <--->             MIN    2
    2       29.4             MIN    1 <--->             MIN    1
    5       64.1             MIN    2 ---->       PR2:  CO2 + H2
    6       65.7             MIN    1 ---->       PR1:  CO + H2O
    9       73.0             MIN    4 ---->       PR1:  CO + H2O
   10       77.1             MIN    5 ---->       PR2:  CO2 + H2
   11      122.2             MIN    6 <--->             MIN    6
```

**`rxn_kin.txt`** — branching shifts once energies are corrected:

```
1 3 0.15326
1 CO2+H2 0.0736664
1 CO+H2O 0.724809
3 CO+H2O 0.042337
3 CO2+H2 0.00592718
```

72.5% of the flux ends up at CO + H₂O, 7.4% at CO₂ + H₂, and the rest
gets trapped in the MIN 3 isomer.

## Common troubleshooting <a name="troubleshooting"></a>

| Symptom | Cause | Fix |
|---|---|---|
| `orca does not seem to be installed` / `Aborting...` | ORCA isn't on the `PATH` of the session launching the calculation | Check the [installation page](beginners_install.html), section 7.2; confirm with a bare `orca` that it prints the banner |
| `Keyword HL_rxn_network has not been specified` | That line is missing from the `.dat` | Add `HL_rxn_network complete` (or `reduced N`) under `--General--` |
| Fewer TSs in `FINAL_HL` than in `FINAL_LL` | Normal: some LL TSs don't converge to a real saddle point at HL, or exceed the `Energy` threshold from `--Kinetics--` | Not an error — check `tsdirHL_<molecule>/TSs/` for the detail on each one |
| The calculation takes much longer than LL | Expected: DFT with ORCA is orders of magnitude more expensive than PM7 | Tune `runningtasks` to the available cores; be patient — in this example (13 TSs, 5-atom molecule) it took ~2 hours |
| An ORCA job hangs indefinitely | The low `timeout` from the LL page (e.g. 1000 s) is still set, too short for DFT | Remove it or raise it substantially before launching HL (see above) |

## What's next <a name="whats-next"></a>

With a complete reaction network refined at DFT level, and its
corresponding kinetics, the [next page](beginners_highlevel_uma.html)
covers how to refine the same TSs with an MLIP backend (UMA) instead
of ORCA, comparing cost vs. accuracy. This same workflow (the LL and
HL pages) can also be applied to a molecule other than FA.
