---
title: Publications
layout: home
nav_order: 2
permalink: /docs/works.html
---
# Publications using AutoMeKin

{% assign pubs = site.data.publications %}
{% assign by_year = pubs | group_by: "year" | sort: "name" | reverse %}
{% assign first_year = by_year | last %}
{{ pubs.size }} works have used AutoMeKin or its algorithms since {{ first_year.name }}. The list is kept in
[`_data/publications.yml`](https://github.com/ComputationalChem-USC/AutoMeKin-X/blob/gh-pages/_data/publications.yml).
If you have used AutoMeKin in your work, please [cite it](cite.html).

{% assign max = 0 %}
{% for g in by_year %}{% if g.size > max %}{% assign max = g.size %}{% endif %}{% endfor %}
<div class="pub-chart" role="img" aria-label="Publications per year">
{% for g in by_year reversed %}
  <div class="pub-bar-col">
    <span class="pub-bar-value">{{ g.size }}</span>
    <span class="pub-bar" style="height: {{ g.size | times: 100 | divided_by: max }}%"></span>
    <span class="pub-bar-year">{{ g.name }}</span>
  </div>
{% endfor %}
</div>

<div class="pub-filter">
  <input type="search" id="pub-search" placeholder="Filter by journal or year" aria-label="Filter publications">
</div>

{% for g in by_year %}
<h2 id="y{{ g.name }}">{{ g.name }} <span class="pub-count">{{ g.size }}</span></h2>
<div class="pub-grid">
{% for p in g.items %}
  <a class="pub-card" href="{{ p.url }}" target="_blank" rel="noopener" data-search="{{ p.journal | downcase }} {{ p.year }} {{ p.title | strip_html | downcase }} {{ p.authors | downcase }}">
    <span class="pub-journal">{{ p.journal }}</span>
    {% if p.title != "" %}<span class="pub-title">{{ p.title }}</span>{% endif %}
    {% if p.authors %}<span class="pub-meta">{{ p.authors }}</span>{% endif %}
    <span class="pub-meta">{{ p.year }} · {% if p.url contains "doi" %}DOI{% else %}Article{% endif %} ↗</span>
  </a>
{% endfor %}
</div>
{% endfor %}

<script>
  (function () {
    var input = document.getElementById("pub-search");
    if (!input) return;
    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase();
      document.querySelectorAll(".pub-card").forEach(function (c) {
        c.hidden = q && c.getAttribute("data-search").indexOf(q) === -1;
      });
      document.querySelectorAll(".pub-grid").forEach(function (g) {
        var any = g.querySelector(".pub-card:not([hidden])");
        g.hidden = !any;
        g.previousElementSibling.hidden = !any;
      });
    });
  })();
</script>
