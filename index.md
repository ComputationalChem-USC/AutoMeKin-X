---
title: Home
layout: home
nav_order: 1
---

<img class="hero-banner" src="{{ "/assets/images/banner.jpg" | relative_url }}" alt="AutoMeKin-X">

<div class="hero">
  <span class="hero-eyebrow">Automated reaction discovery</span>
  <h1 class="hero-title">AutoMeKin<span>-X</span></h1>
  <p>Discover reaction mechanisms automatically. Transition states are located with molecular dynamics and graph theory, refined with quantum chemistry or machine-learning potentials, and connected into a reaction network whose kinetics is solved with Monte Carlo simulations. All you need is a starting structure in XYZ format.</p>
  <div class="hero-actions">
    <a class="btn-amk btn-amk-primary" href="docs/installation.html">Get started</a>
    <a class="btn-amk btn-amk-secondary" href="docs/beginners.html">Beginners tutorial</a>
  </div>
</div>

<div class="feature-grid">
  <a class="feature-card" href="docs/installation.html">
    <div class="feature-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg></div>
    <h3>Installation</h3>
    <p>Build from source with the standard GNU toolchain.</p>
  </a>
  <a class="feature-card" href="docs/engines.html">
    <div class="feature-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/></svg></div>
    <h3>Engines</h3>
    <p>MOPAC, Qcore, Gaussian, ORCA and ML potentials.</p>
  </a>
  <a class="feature-card" href="docs/mlip.html">
    <div class="feature-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="5" cy="12" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><circle cx="12" cy="12" r="2"/><path d="M7 12h3M14 11l3.5-4.5M14 13l3.5 4.5"/></svg></div>
    <h3>ML potentials</h3>
    <p>UMA or MACE for high-level refinement, with no QM code required.</p>
  </a>
  <a class="feature-card" href="docs/beginners.html">
    <div class="feature-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/></svg></div>
    <h3>Tutorial</h3>
    <p>From installation to your first reaction network, step by step.</p>
  </a>
</div>

## Quick start

1. **Install** AutoMeKin-X from source following [Installation](docs/installation.html),
   or the more detailed [Installation from zero](docs/beginners_install.html).
2. **Run the tests** to check that everything works: [Running the tests](docs/tests.html).
3. **Prepare your input**: an XYZ file and a `.dat` input file, described in
   [Input files](docs/input.html).
4. **Launch the workflows** with `llcalcs.sh` and `hlcalcs.sh`:
   [Automated workflows](docs/running.html).

```bash
git clone https://github.com/ComputationalChem-USC/AutoMeKin-X.git
cd AutoMeKin-X
autoreconf -i
./configure --prefix=path_to_program
make
make install
```

{: .highlight }
If you are new to AutoMeKin, start with the [complete tutorial for beginners](docs/beginners.html),
also available as a [PDF]({{ "/assets/files/AutoMeKin-Beginners-Tutorial.pdf" | relative_url }}).
