---
title: 5. Visualization and analysis with amk_tools
layout: home
parent: Complete tutorial for beginners
grand_parent: Tutorial
nav_order: 5
---

# Visualization and analysis with `amk_tools`

Continuation of the previous two pages: this page installs
`amk_tools`, the companion tool for **visualizing** and **analyzing**
the reaction networks AutoMeKin generates, and walks through all of
its features on the real results from the ORCA/DFT and UMA pages.

## Contents

- [What `amk_tools` is, and why it lives in a separate environment](#what-is)
- [Isolated installation](#installation)
- [The two tools: overview](#tools-overview)
- [`amk_gen_view.py`: complete option reference](#gen-view-reference)
- [Practical example: network from the global MIN, DFT vs UMA](#practical-example)
- [`amk_rxn_stats.py`: network statistics](#rxn-stats)
- [Common troubleshooting](#troubleshooting)
- [What's next](#whats-next)

## What `amk_tools` is, and why it lives in a separate environment <a name="what-is"></a>

[`amk_tools`](https://github.com/dgarayr/amk_tools), by Diego Garay,
doesn't run any calculations — it's purely a reader/visualizer. It
reads the plain-text files and SQLite databases already present inside
a `FINAL_LL_*`, `FINAL_HL_*`, or `FINAL_ML_*` folder, and from that
builds:

- an **interactive visualization** of the reaction network (HTML,
  navigable in any browser), and
- **statistics** on that network's topology (number of nodes/edges,
  average path length, clustering coefficient, etc., compared against
  an equivalent random graph).

{: .note }
**Why it needs its own conda environment, separate from `amk_env`:**
`amk_tools` pins `bokeh<3.0.0`, and due to that Bokeh version's own
dependencies, requires `numpy<2`. If the MLIP models (MACE/UMA) were
installed on the [installation page](beginners_install.html) (step
7.3), `amk_env` has `numpy>=2` — a combination `amk_tools` simply
won't start with (`AttributeError: module 'numpy' has no attribute
'bool8'`). Rather than forcing a version combination that breaks one
thing or the other, the cleanest approach is a completely separate
`amk_view` environment, just for this. This is safe because
`amk_tools` **never interacts with AutoMeKin itself** — it only reads
already-generated files. Installing, upgrading, or even deleting
`amk_view` entirely has zero effect on the AutoMeKin installation or
on `amk_env`.

## Isolated installation <a name="installation"></a>

```bash
conda create -n amk_view python=3.11 -y
conda activate amk_view
pip install git+https://github.com/dgarayr/jsmol_to_bokeh.git
pip install --no-deps git+https://github.com/dgarayr/amk_tools.git
pip install "bokeh>=2.3.2,<3.0.0" "numpy<2" networkx matplotlib scipy
```

`pip install` only provides the importable `RXReader`/`RXVisualizer`
modules — it doesn't install the command-line tools (`amk_gen_view.py`,
`amk_rxn_stats.py`), since the package doesn't declare them as entry
points. Fetch those separately into this same environment's `bin`
folder:

```bash
curl -L -o $CONDA_PREFIX/bin/amk_gen_view.py https://github.com/dgarayr/amk_tools/raw/master/scripts/amk_gen_view.py
curl -L -o $CONDA_PREFIX/bin/amk_rxn_stats.py https://github.com/dgarayr/amk_tools/raw/master/scripts/amk_rxn_stats.py
chmod +x $CONDA_PREFIX/bin/amk_gen_view.py $CONDA_PREFIX/bin/amk_rxn_stats.py
```

Verify both commands respond:

```bash
amk_gen_view.py --help
amk_rxn_stats.py --help
```

From here on, generating a visualization or statistics only requires
`conda activate amk_view` — `amk_env` or AutoMeKin do **not** need to
be active at the same time.

## The two tools: overview <a name="tools-overview"></a>

| Tool | What it does | Output |
|---|---|---|
| `amk_gen_view.py` | Builds an interactive graph of the reaction network (nodes = minima/products, edges = TSs) | A self-contained `.html` file |
| `amk_rxn_stats.py` | Computes topological properties of that same network and compares them to an equivalent random graph | A `.txt` file with the statistics |

Both are invoked the same way: first the `FINAL_*` folder with the
results, then which version of the network to use.

## `amk_gen_view.py`: complete option reference <a name="gen-view-reference"></a>

```
amk_gen_view.py <finaldir> <rxnfile> [options]
```

**Positional (required):**

| Argument | Meaning |
|---|---|
| `finaldir` | The results folder: `FINAL_LL_<molecule>`, `FINAL_HL_<molecule>`, or `FINAL_ML_<molecule>` |
| `rxnfile` | Which version of the network to use: `RXNet` (full), `RXNet.cg` (connected graph), or `RXNet.rel` (already filtered/relativized) |

**"RXN parsing" group — what to include and how to reference energies:**

| Option | Short | What it does |
|---|---|---|
| `--barrierless` | `-b` | Adds the barrierless channels from `RXNet.barrless` to the graph (otherwise they're left out entirely) |
| `--vibrations NVIBR` | `-v` | Number of normal vibrational modes to include in the visualization; `-1` for all |
| `--ref_state REF_STATE` | `-rs` | Switches the reference state (energy zero) to a different node than the one AutoMeKin used by default |

**"Path handling" group — building paths/energy profiles:**

| Option | Short | What it does |
|---|---|---|
| `--paths [SOURCE [TARGET ...]]` | `-p` | Generates paths. **With no arguments**, builds every possible profile starting from the **global minimum** (AutoMeKin's internal reference node) — this is exactly what's used in the example below. With a `SOURCE`, filters paths connected to that node. With both `SOURCE` and `TARGET`, searches specifically for paths between them |
| `--cutoff_path CUTOFF` | `-c` | Maximum search depth when `SOURCE`+`TARGET` are used together (default 4) |
| `--efilter EFILTER` | `-e` | Energy threshold (kcal/mol) for discarding paths; no filter by default |
| `--unreduced` | `-u` | Generates the full graph, without excluding nodes that don't appear in any path |
| `--geomolden` | `-ng` | Updates the displayed geometries from MOLDEN files |

**"File handling" group — output name and title:**

| Option | Short | What it does |
|---|---|---|
| `--outfile OUTFILE` | `-o` | Output HTML filename (default `network.html`) |
| `--title TITLE` | `-t` | Visualization title (default "Reaction network visualization") |

**"Aspect handling" group — appearance:**

| Option | Short | What it does |
|---|---|---|
| `--resolution RESOLUTION` | `-r` | HTML size, `WIDTH,HEIGHT` in pixels (default `1400,800`) |
| `--fasterlayout` | `-f` | Uses the faster layout algorithm (`nx.spring_layout`) instead of the default (`nx.kamada_kawai_layout`) — useful for large networks |

## Practical example: network from the global MIN, DFT vs UMA <a name="practical-example"></a>

This builds the network from the global minimum (`--paths`, no
arguments — see the table above), using `RXNet.rel` and including the
barrierless channels, for the two HL results from the previous two
pages.

**With the ORCA/DFT results:**

```bash
cd test_example_dft
amk_gen_view.py FINAL_HL_FA RXNet.rel --paths --barrierless --outfile network_rel_with_barrierless.html
```

**With the UMA results:**

```bash
cd test_example_uma_cpu
amk_gen_view.py FINAL_ML_FA RXNet.rel --paths --barrierless --outfile network_rel_with_barrierless.html
```

Both commands are identical except for the input folder — that's how
simple it is to visualize the same system computed with two different
HL methods (each lives in its own folder, so using the same filename
for both doesn't clash).

<p align="center">
   <img src="{{ "/assets/images/beginners_tutorial/network.png" | relative_url }}" alt="Reaction network generated from RXNet.rel with UMA-refined results" width="700">
</p>

This is the network generated from `RXNet.rel` with the results
refined using UMA: each node is a species (minima or products) and
each edge is a transition state connecting them, positioned relative
to the global minimum's energy.

<p align="center">
   <img src="{{ "/assets/images/beginners_tutorial/PLOT.png" | relative_url }}" alt="Energy profile of the reaction network" width="600">
</p>

The generated HTML file also includes an energy profile of the
reaction network, viewable by clicking the "Show profile" tab. In the
image above, **PR8** and **PR9** are the barrierless products,
obtained and stored in `RXNet.barrless`.

{: .note }
Product numbers (PR#) may not match between different runs. That's
expected, not an error: LL sampling launches its MD trajectories from
randomized starting conditions, so which minima and products get
discovered — and in what order — can differ slightly between runs,
even for the same molecule and input file. The PR numbering is just
the order of discovery, so it shifts accordingly; the actual topology
and energies are what matter, and those are reproducible.

Opening both HTML files in a browser and comparing them shows the same
topology (what connects to what), but the barrier heights differ as
seen on the previous two pages.

## `amk_rxn_stats.py`: network statistics <a name="rxn-stats"></a>

```
amk_rxn_stats.py <finaldir> [options]
```

| Option | Short | What it does |
|---|---|---|
| `--rxnfile RXNFILE` | `-r` | Which network version to use (default `RXNet.cg`) |
| `--skip_barrierless` | `-sb` | Excludes the `RXNet.barrless` channels (included by default if the file exists) |
| `--Ngraphs NGRAPHS` | `-Ng` | Number of equivalent random Erdős–Rényi graphs to generate for comparison (default 1000) |
| `--outfilename OUTFILENAME` | `-o` | Output filename (default `rxn_stats.txt`) |

Computes: number of nodes and edges, average shortest path length,
clustering coefficient, transitivity, edge density, and degree
assortativity coefficient — all compared against the average of
`Ngraphs` random graphs of the same size, to show whether a reaction
network is "more ordered" or "more random" than would be expected by
pure chance.

**Real example** (on the ORCA/DFT results):

```bash
cd test_example_dft
amk_rxn_stats.py FINAL_HL_FA --rxnfile RXNet.rel --outfilename FA_DFT_stats.txt
```

```
   Number of nodes =       6
   Number of edges =       7
   Average shortest path length of the current network             =     1.6
   Average shortest path length of the equivalent random network   = 2.11
   Average clustering coefficient of the current network           = 0.44
   Average clustering coefficient of the equivalent random network = 0.36
   Transitivity of the current network                             = 0.43
   Transitivity of the equivalent random network                   = 0.37
   Density of edges (edges/possible_edges)                         = 0.47
   Degree assortativity coefficient                                = -0.70
```

FA's network has a shorter average path (1.6 vs. 2.11) and more edge
density than an equivalent random graph — expected for a real reaction
network of a small molecule, where minima tend to be well
interconnected rather than randomly scattered.

## Common troubleshooting <a name="troubleshooting"></a>

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'RXVisualizer'` | `pip install` only provides the modules, not the command-line scripts | Download `amk_gen_view.py`/`amk_rxn_stats.py` with `curl` as shown above |
| `AttributeError: module 'numpy' has no attribute 'bool8'` | `amk_env` is active (with `numpy>=2` from the MLIP setup) instead of `amk_view` | `conda activate amk_view` before running any `amk_tools` command |
| The HTML comes out blank or very small | Network with very few nodes, or `--efilter` too restrictive | Try without `--efilter`, or check that `finaldir`/`rxnfile` point to real results |
| `finaldir must be passed` from `amk_rxn_stats.py` | Missing the required `finaldir` positional argument | `amk_rxn_stats.py <FINAL_folder>` — it's required, unlike the options |

## What's next <a name="whats-next"></a>

With this, the full cycle is complete: install AutoMeKin, explore at
low level, refine at high level with DFT or an MLIP, and visualize and
analyze the result. From here, the natural next step is applying the
whole workflow to a molecule other than FA.
