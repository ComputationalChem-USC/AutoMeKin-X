---
title: Complete tutorial for beginners
layout: home
parent: Tutorial
nav_order: 6
has_children: true
---

# Complete tutorial for beginners

<p align="center">
  <a class="pdf-download-button" href="{{ "/assets/files/AutoMeKin-Beginners-Tutorial.pdf" | relative_url }}" download>
    📥 Download this tutorial as a PDF
  </a>
</p>

This appendix is a from-zero, step-by-step walkthrough aimed at people
who are **not yet familiar with AutoMeKin or computational chemistry**.
It complements the rest of the Tutorial section above (which assumes
some prior familiarity with the program) by spelling out every command,
every file, and every error message a first-time user is likely to run
into — all of it tested end to end on the same worked example (formic
acid, `FA`) before being written down.

{: .note }
This appendix is self-contained: you can follow it on its own without
having read the other Tutorial pages first.

## Contents

1. **Installation from zero** — system dependencies, Miniconda, building
   AutoMeKin from source, and setting up the optional high-level
   backends (ORCA, MACE, UMA).
2. **Low-level (LL) calculations** — preparing an input file, running
   `llcalcs.sh`, and reading the resulting reaction network.
3. **High-level (HL) calculations with ORCA** — refining the LL
   transition states with DFT.
4. **High-level (HL) calculations with UMA (MLIP)** — refining the same
   transition states with a machine-learning interatomic potential
   instead, and comparing cost vs. accuracy against DFT.
5. **Visualization and analysis with `amk_tools`** — generating
   interactive reaction-network visualizations and network statistics
   from your results.

Use the sidebar to move between the five parts, in order.
