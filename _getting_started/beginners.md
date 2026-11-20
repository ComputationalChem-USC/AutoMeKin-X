---
title: Beginners tutorial
layout: home
nav_order: 3
has_children: true
has_toc: false
permalink: /docs/beginners.html
---
# Complete tutorial for beginners

<p align="center">
  <a class="pdf-download-button" href="{{ "/assets/files/AutoMeKin-Beginners-Tutorial.pdf" | relative_url }}" download>
    Download this tutorial as a PDF
  </a>
</p>

This tutorial is a from-zero, step-by-step walkthrough aimed at people
who are **not yet familiar with AutoMeKin or computational chemistry**.
It complements the User guide (which assumes some prior familiarity
with the program) by spelling out every command,
every file, and every error message a first-time user is likely to run
into — all of it tested end to end on the same worked example (formic
acid, `FA`) before being written down.

{: .note }
This tutorial is self-contained: you can follow it on its own without
having read the User guide first.

<div class="step-cards">
  <a class="step-card" href="beginners_install.html">
    <span class="step-num">1</span>
    <span class="step-title">Installation from zero</span>
    <p>System dependencies, Miniconda, building AutoMeKin-X from source and the optional high-level backends (ORCA, MACE, UMA).</p>
  </a>
  <a class="step-card" href="beginners_lowlevel.html">
    <span class="step-num">2</span>
    <span class="step-title">Low-level (LL) calculations</span>
    <p>Preparing an input file, running <code>llcalcs.sh</code> and reading the resulting reaction network.</p>
  </a>
  <a class="step-card" href="beginners_highlevel_orca.html">
    <span class="step-num">3</span>
    <span class="step-title">High level with ORCA</span>
    <p>Refining the LL transition states with DFT.</p>
  </a>
  <a class="step-card" href="beginners_highlevel_uma.html">
    <span class="step-num">4</span>
    <span class="step-title">High level with an ML potential</span>
    <p>Refining the same transition states with a machine-learning interatomic potential, and comparing cost and accuracy against DFT.</p>
  </a>
  <a class="step-card" href="beginners_amktools.html">
    <span class="step-num">5</span>
    <span class="step-title">Visualization with amk_tools</span>
    <p>Interactive reaction-network dashboards and network statistics from your results.</p>
  </a>
</div>

Follow the five parts in order; each one ends with a link to the next.
