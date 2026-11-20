---
title: Home
layout: home
nav_order: 1
---

<div class="amk-landing">

<section class="landing-hero">
  <canvas class="pes-canvas" aria-hidden="true"></canvas>
  <div class="landing-hero-text">
    <span class="hero-eyebrow">Automated reaction discovery</span>
    <h1 class="landing-title">AutoMeKin<span>-X</span></h1>
    <p class="landing-lead">From a single structure to the full reaction network and its kinetics. Transition states are found with molecular dynamics and graph theory, refined with quantum chemistry or machine-learning potentials, and connected into a network solved with kinetic Monte Carlo.</p>
    <div class="hero-actions">
      <a class="btn-amk btn-amk-primary" href="{{ '/docs/installation.html' | relative_url }}">Get started</a>
      <a class="btn-amk btn-amk-secondary" href="https://colab.research.google.com/github/ComputationalChem-USC/AutoMeKin-X/blob/main/notebooks/AutoMeKin.ipynb" target="_blank" rel="noopener">Try it in Colab</a>
      <a class="btn-amk btn-amk-ghost" href="https://github.com/ComputationalChem-USC/AutoMeKin-X" target="_blank" rel="noopener">GitHub</a>
    </div>
  </div>
</section>

<section class="stats reveal" aria-label="AutoMeKin-X in numbers">
  <div class="stat"><span class="stat-value">{{ site.data.publications.size }}</span><span class="stat-label">publications since 2021</span></div>
  <div class="stat"><span class="stat-value">6</span><span class="stat-label">engines: MOPAC, Qcore, Gaussian, ORCA, UMA, MACE</span></div>
  <div class="stat"><span class="stat-value">{{ site.data.keywords.size }}</span><span class="stat-label">documented input keywords</span></div>
  <div class="stat"><span class="stat-value">1</span><span class="stat-label">XYZ file is all you need to start</span></div>
</section>

<section class="landing-section reveal" id="how-it-works">
  <h2 class="landing-h2">How it works</h2>
  <p class="landing-sub">The potential energy surface is explored at a low cost, iteratively, until no new transition states appear. The network is then refined at a higher level. Click any step, or let it play.</p>

  <div class="flow" data-flow>
    <div class="flow-diagram">
      <div class="flow-node flow-input" data-step="0">Input structure</div>

      <div class="flow-panel flow-panel-pes">
        <span class="flow-panel-title">PES exploration</span>
        <div class="flow-row">
          <div class="flow-node flow-chip" data-step="1">SQM (PM7)</div>
          <div class="flow-node flow-chip flow-chip-ml" data-step="1">MLIPs</div>
        </div>
        <div class="flow-loop">
          <div class="flow-node" data-step="2">Reactive MD<small>BBFS event detection</small></div>
          <div class="flow-node" data-step="3">Partial opt. + TS opt.<small>Torsional scans</small></div>
          <div class="flow-node" data-step="4">IRC + minima<small>Barrierless search</small></div>
          <div class="flow-node" data-step="5">Reaction network</div>
          <div class="flow-node flow-decision" data-step="6"><span>Converged?</span></div>
          <span class="flow-loop-label">no: iterate from the new minima</span>
        </div>
      </div>

      <span class="flow-yes">yes</span>

      <div class="flow-panel flow-panel-refine">
        <span class="flow-panel-title">Network refinement</span>
        <div class="flow-node" data-step="7">TS candidates</div>
        <div class="flow-row flow-row-3">
          <div class="flow-node flow-chip" data-step="8">DFT / ab initio</div>
          <div class="flow-node flow-chip flow-chip-ml" data-step="8">MLIPs</div>
          <div class="flow-node flow-chip" data-step="8">Δ-ML corrections</div>
        </div>
        <div class="flow-node" data-step="9">TS re-optimization<small>IRC + minima, barrierless channels</small></div>
        <div class="flow-node flow-final" data-step="10">Refined and final network<small>Rate constants and kinetic Monte Carlo</small></div>
      </div>
    </div>

    <div class="flow-viewer" aria-live="polite">
      <div class="flow-slide" data-slide="0"><img src="{{ '/assets/images/workflow/input.png' | relative_url }}" alt="Formic acid molecule"><p><strong>Input structure.</strong> One XYZ file, here formic acid.</p></div>
      <div class="flow-slide" data-slide="1"><img src="{{ '/assets/images/workflow/pes.png' | relative_url }}" alt="Potential energy surface"><p><strong>Low-level engine.</strong> The surface is explored at low cost with a semiempirical method (PM7) or a machine-learning potential.</p></div>
      <div class="flow-slide" data-slide="2"><img class="on-light" src="{{ '/assets/images/workflow/md.png' | relative_url }}" alt="Bond distances along a reactive trajectory"><p><strong>Reactive MD.</strong> Trajectories at high energy; the BBFS algorithm detects bond breaking and formation (here at 232 fs).</p></div>
      <div class="flow-slide" data-slide="3"><img src="{{ '/assets/images/workflow/ts.png' | relative_url }}" alt="Transition state with its imaginary mode"><p><strong>TS optimization.</strong> Each event gives a guess that is optimized to a transition state; torsional scans add conformers.</p></div>
      <div class="flow-slide" data-slide="4"><img class="on-light" src="{{ '/assets/images/workflow/irc.png' | relative_url }}" alt="IRC energy profile"><p><strong>IRC and minima.</strong> IRC calculations connect each TS with its reactant and products; barrierless channels are searched too.</p></div>
      <div class="flow-slide" data-slide="5"><img class="on-light" src="{{ '/assets/images/workflow/network.png' | relative_url }}" alt="Reaction network graph"><p><strong>Reaction network.</strong> All the elementary reactions are joined into a graph of minima, products and transition states.</p></div>
      <div class="flow-slide" data-slide="6"><img class="on-light" src="{{ '/assets/images/workflow/convergence.png' | relative_url }}" alt="Number of TSs found per iteration"><p><strong>Converged?</strong> New iterations start from the minima found so far, until no new transition states appear.</p></div>
      <div class="flow-slide" data-slide="7"><img src="{{ '/assets/images/workflow/candidates.png' | relative_url }}" alt="Transition state candidates"><p><strong>TS candidates.</strong> The low-level transition states are passed to the refinement.</p></div>
      <div class="flow-slide" data-slide="8"><div class="engine-cloud"><span>Gaussian</span><span>ORCA</span><span>Qcore</span><span>UMA</span><span>MACE</span><span>Δ-ML</span></div><p><strong>High-level engine.</strong> DFT or ab initio codes, ML potentials, or DFT with a Δ-ML correction.</p></div>
      <div class="flow-slide" data-slide="9"><img class="on-light" src="{{ '/assets/images/workflow/irc.png' | relative_url }}" alt="IRC energy profile"><p><strong>Re-optimization.</strong> TSs, IRCs, minima and barrierless channels are recomputed at the high level.</p></div>
      <div class="flow-slide" data-slide="10"><img class="on-light" src="{{ '/assets/images/beginners_tutorial/network.png' | relative_url }}" alt="Final reaction network of formic acid"><p><strong>Final network.</strong> Rate constants and kinetic Monte Carlo give the populations of every species over time.</p></div>
    </div>
  </div>
  <p class="flow-more"><a href="{{ '/assets/images/workflow/workflow-full.jpg' | relative_url }}" target="_blank" rel="noopener">See the full diagram</a> · <a href="{{ '/docs/tutorial.html' | relative_url }}">Read how it works</a></p>
</section>

<section class="landing-section reveal" id="demo">
  <h2 class="landing-h2">Explore a real reaction network</h2>
  <p class="landing-sub">The low-level network of formic acid, as produced by AutoMeKin-X and drawn with <a href="https://github.com/OmarRodriguezLopez1398/amk_tools_X" target="_blank" rel="noopener">amk_tools_X</a>. Drag and zoom the network, click a node or an edge to see its 3D structure and normal modes, and follow the energy profiles.</p>
  <div class="demo-frame" data-demo-src="{{ '/assets/demo/formic-acid-network.html' | relative_url }}">
    <img src="{{ '/assets/images/beginners_tutorial/network.png' | relative_url }}" alt="Preview of the formic acid reaction network">
    <button type="button" class="btn-amk btn-amk-primary demo-launch">Launch the interactive demo</button>
  </div>
  <p class="demo-note">The demo loads Bokeh and JSmol from the internet. <a href="{{ '/assets/demo/formic-acid-network.html' | relative_url }}" target="_blank" rel="noopener">Open it in a new tab</a>.</p>
</section>

<section class="landing-section reveal" id="results">
  <h2 class="landing-h2">What you get</h2>
  <div class="gallery">
    <figure>
      <img src="{{ '/assets/images/beginners_tutorial/network.png' | relative_url }}" alt="Reaction network with structures">
      <figcaption><strong>Reaction network.</strong> Minima, products and transition states with their structures.</figcaption>
    </figure>
    <figure>
      <img src="{{ '/assets/images/beginners_tutorial/PLOT.png' | relative_url }}" alt="Energy profiles">
      <figcaption><strong>Energy profiles.</strong> Every path between two species, filtered by energy.</figcaption>
    </figure>
    <figure>
      <img src="{{ '/assets/images/kinetics.png' | relative_url }}" alt="Populations versus time">
      <figcaption><strong>Kinetics.</strong> Populations over time and product branching ratios.</figcaption>
    </figure>
  </div>
</section>

<section class="landing-section reveal" id="news">
  <h2 class="landing-h2">What's new</h2>
  <div class="news-strip">
  {% for n in site.data.news limit: 3 %}
    <a class="news-card" href="{% if n.link contains '://' %}{{ n.link }}{% else %}{{ n.link | relative_url }}{% endif %}">
      <span class="news-date">{{ n.date }}</span>
      <span class="news-title">{{ n.title }}</span>
      <span class="news-text">{{ n.text }}</span>
    </a>
  {% endfor %}
  </div>
  <p class="flow-more"><a href="{{ '/docs/news.html' | relative_url }}">All news</a></p>
</section>

<section class="landing-section reveal" id="start">
  <h2 class="landing-h2">Start now</h2>
  <div class="amk-tabs">
    <div role="tablist" aria-label="Ways to run AutoMeKin-X">
      <button role="tab" aria-selected="true">From source</button>
      <button role="tab" aria-selected="false">Google Colab</button>
      <button role="tab" aria-selected="false">Web app</button>
    </div>
    <div role="tabpanel">
<div class="language-bash highlighter-rouge"><div class="highlight"><pre class="highlight"><code>git clone https://github.com/ComputationalChem-USC/AutoMeKin-X.git
cd AutoMeKin-X
autoreconf -i
./configure --prefix=path_to_program
make
make install
</code></pre></div></div>
      <p>Then <a href="{{ '/docs/tests.html' | relative_url }}">run the tests</a> and follow the <a href="{{ '/docs/beginners.html' | relative_url }}">beginners tutorial</a>. Full details in <a href="{{ '/docs/installation.html' | relative_url }}">Installation</a>.</p>
    </div>
    <div role="tabpanel" hidden>
      <p>Run a complete example in your browser, with nothing to install: formic acid at the PM7 level, refined with the MACE potential, and the interactive dashboards.</p>
      <p><a class="btn-amk btn-amk-primary" href="https://colab.research.google.com/github/ComputationalChem-USC/AutoMeKin-X/blob/main/notebooks/AutoMeKin.ipynb" target="_blank" rel="noopener">Open the notebook in Colab</a></p>
    </div>
    <div role="tabpanel" hidden>
      <p>Submit small systems from the AutoMeKin web server at the University of Santiago de Compostela.</p>
      <p><a class="btn-amk btn-amk-primary" href="https://rxnkin.usc.es/amk/" target="_blank" rel="noopener">Go to the web app</a></p>
    </div>
  </div>
</section>

<section class="landing-section cite-box reveal" id="cite">
  <h2 class="landing-h2">Cite AutoMeKin-X</h2>
  <p id="cite-main">Rodriguez-Lopez, O. et al., J. Chem. Theory Comput. 2026, 22, 10816. https://doi.org/10.1021/acs.jctc.6c01565</p>
  <p><button type="button" class="btn-amk btn-amk-secondary" data-copy-target="cite-main">Copy citation</button> <a href="{{ '/docs/cite.html' | relative_url }}">All references to cite</a></p>
</section>

</div>
