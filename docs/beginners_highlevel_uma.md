---
title: 4. High-level (HL) calculations with UMA (MLIP)
layout: home
parent: Complete tutorial for beginners
grand_parent: Tutorial
nav_order: 4
---

# High-level (HL) calculations with UMA (MLIP)

Continuation of the [ORCA high-level
page](beginners_highlevel_orca.html): this page refines the same LL
reaction network, but using a **machine-learning interatomic
potential (MLIP)** — UMA — instead of a traditional DFT calculation.

## Contents

- [What changes with MLIP vs. ORCA](#what-changes)
- [Requirements](#requirements)
- [Adjusting the `amk.dat`](#adjust-input)
- [Launching the calculation](#launch)
- [GPU vs. CPU](#gpu-vs-cpu)
- [Where results live](#where)
- [Full verified example: FA with UMA](#example-fa)
- [Common troubleshooting](#troubleshooting)
- [What's next](#whats-next)

## What changes with MLIP vs. ORCA <a name="what-changes"></a>

The goal is the same as on the previous page: refine the TSs already
discovered at LL. The difference is the engine doing the refinement —
instead of a DFT calculation with ORCA, this uses **UMA**, a
neural-network model trained to predict energies and forces directly,
without solving any quantum-mechanical equation.

## Requirements <a name="requirements"></a>

- The LL page completed (`tsdirLL_FA/tslist` already generated).
- UMA model downloaded to `$AMK/models/` (see the [installation
  page](beginners_install.html), step 7.3):
  `uma-m-1p1.pt` + `uma-m-1p1_atom_refs.yaml`.
- Python libraries installed (same page, step 7.3): `torch`, `sella`,
  `omegaconf`, `fairchem-core`.

## Adjusting the `amk.dat` <a name="adjust-input"></a>

Reuse the same `amk.dat` from the LL and ORCA pages, changing only the
`HighLevel` keyword:

```
HighLevel mlip uma
```

Nothing else needs to change — `HL_rxn_network`, `IRCpoints`,
`charge`, `mult`, and everything under `--Screening--`/`--Method--`
stay the same.

{: .note }
One real MLIP-specific constraint: `--Kinetics--` must use `Energy
<value>`, not `Temperature`, because MLIP models don't compute the
Gibbs free-energy correction needed to sort by Boltzmann weighting at
a given temperature — with `Energy`, AutoMeKin sorts using E+ZPE
instead. The example `amk.dat` already uses `Energy 150`, so no change
is needed there.

## Launching the calculation <a name="launch"></a>

The exact same command as with ORCA:

```bash
nohup hlcalcs.sh FA.dat 10 > hlcalcs.log 2>&1 &
```

But **what the `10` (`runningtasks`) means is different**. With ORCA,
it's 10 concurrent ORCA processes. With MLIP, if a GPU is available,
`runningtasks` is ignored entirely and **one process per GPU** is used
(as many as `torch.cuda.device_count()` detects); if there's no GPU,
the work is split across `runningtasks` CPU processes instead, each
loading its own copy of the model — this is automatically capped so
it doesn't exceed the available RAM (UMA's checkpoint needs a
sizeable amount of memory per worker while loading).

## GPU vs. CPU <a name="gpu-vs-cpu"></a>

For the formic acid example: **with a GPU, UMA took ~7 minutes** to
refine the 13 TSs from the LL page (vs. ~1h50min with ORCA).
**Without a GPU, it took ~14.6 minutes** — slower than with a GPU, but
still much faster than ORCA. A GPU should be prioritized for this kind
of calculation when available; CPU is still a reasonable fallback
otherwise.

## Where results live <a name="where"></a>

Same as LL/HL, but with a different folder name: since `HighLevel` is
`mlip`, the final folder is called **`FINAL_ML_<molecule>/`**, not
`FINAL_HL_<molecule>/`. The rest of the layout
(`tsdirHL_<molecule>/TSs`, `IRC`, `MINs`, `PRODs`, `KMC`) is identical
to the ORCA page's.

## Full verified example: FA with UMA <a name="example-fa"></a>

**`RXNet`** — 12 TSs survived refinement (out of the 13 candidates
from LL):

```
 TS #   DE(kcal/mol)           Reaction path information
 ====   ============           =========================
    1        7.4             MIN    1 <--->             MIN    2
    5       62.6             MIN    1 ---->       PR1:  CO + H2O
    8       69.0             MIN    4 ---->       PR1:  CO + H2O
   11      103.6       PR3:  CHO + HO <--->       PR3:  CHO + HO
   12      111.4       PR1:  CO + H2O <--->       PR2:  CO2 + H2
```

**`rxn_kin.txt`** — 67.6% of the flux ends at CO+H₂O, 7.8% at H₂+CO₂,
the rest trapped in the MIN 3 isomer:

```
1 3 0.245852
1 CO+H2O 0.675716
3 CO+H2O 0.0784314
```

The main barrier (MIN1→CO+H₂O, 62.6 kcal/mol) lands very close to
what ORCA gave on the previous page (65.7 kcal/mol) — a difference of
only ~3 kcal/mol, at a fraction of the computational cost.

## Common troubleshooting <a name="troubleshooting"></a>

| Symptom | Cause | Fix |
|---|---|---|
| `MLIP model file not found: ...` | `uma-m-1p1.pt` is missing from `$AMK/models/`, or the name doesn't match exactly | Check the [installation page](beginners_install.html), step 7.3 |
| `_pickle.UnpicklingError: Weights only load failed` when loading UMA | The installed `e3nn` version loads its own `constants.pt` file without `weights_only=False`, and PyTorch ≥2.6 no longer allows that by default | `E3NN_WIGNER=$(python3 -c "import e3nn, os; print(os.path.join(os.path.dirname(e3nn.__file__), 'o3', '_wigner.py'))"); sed -i "s/'constants.pt'))/'constants.pt'), weights_only=False)/" "$E3NN_WIGNER"` — then delete `tsdirHL_<molecule>/` and `FINAL_ML_<molecule>/` and rerun |
| `AMK_ERROR: CppCompileError` / `g++: error: unrecognized command line option '-std=c++20'` | UMA tries to compile the model with `torch.compile`, and the installed `g++` is too old for the `-std=c++20` flag | `export TORCHDYNAMO_DISABLE=1` before launching (add it to `~/.bashrc` to make it permanent); delete `tsdirHL_<molecule>/` and `FINAL_ML_<molecule>/` and rerun |
| `Limiting CPU workers to N (requested M)...` appears, and fewer workers run than `runningtasks` | Without a GPU, each worker loads its own full copy of the model into RAM (peaks at ~24 GB for UMA while loading, ~2 GB for MACE); the worker count is automatically reduced to avoid running out of memory | Not an error — this is the expected safeguard; with plenty of RAM to spare, free up memory or use a machine with more RAM to allow more workers |
| The run is very slow without a GPU | Expected: CPU is slower than GPU (see above) | Use a GPU if available; otherwise be patient — it's still faster than ORCA |
| `IRC inner loop failed to converge!` warning | One particular TS doesn't give a clean IRC at the MLIP level | Not fatal — AutoMeKin discards that path and continues; check whether that TS still shows up in the final `RXNet` |
| The final folder is called `FINAL_ML_FA`, not `FINAL_HL_FA` | Different name for `HighLevel mlip` | Expected behavior — look for `FINAL_ML_<molecule>/` |

## What's next <a name="whats-next"></a>

With ORCA and UMA, there are now two ways to refine the same LL
network, with a clear cost/accuracy trade-off. The same workflow (just
swapping `HighLevel mlip uma` for `HighLevel mlip mace`) works to try
MACE, the other supported MLIP model. The [next
page](beginners_amktools.html) covers how to visualize and analyze
these results with `amk_tools`.
