---
title: Keyword reference
layout: home
nav_order: 3
permalink: /docs/keywords.html
---
# Keyword reference

Every keyword of the input file on one page. Type to filter, or pick a section; click a keyword to open its full description.

<div class="kw-tools">
  <input type="search" id="kw-search" placeholder="Filter keywords, e.g. temperature, mlip, ntraj" aria-label="Filter keywords">
  <div class="kw-chips" id="kw-chips">
    <button type="button" class="kw-chip is-active" data-section="">All</button>
    {% assign sections = site.data.keywords | map: "section" | uniq %}
    {% for s in sections %}<button type="button" class="kw-chip" data-section="{{ s }}">{{ s }}</button>{% endfor %}
  </div>
</div>

<div class="table-wrapper">
<table class="kw-table">
  <thead>
    <tr><th>Keyword</th><th>Section</th><th>Values and default</th><th>What it does</th></tr>
  </thead>
  <tbody>
  {% for k in site.data.keywords %}
    <tr data-section="{{ k.section }}" data-search="{{ k.keyword | downcase }} {{ k.section | downcase }} {{ k.info | strip_html | downcase }} {{ k.desc | strip_html | downcase }}">
      <td><a href="{{ k.url | relative_url }}"><code>{{ k.syntax }}</code></a></td>
      <td>{{ k.section }}</td>
      <td>{{ k.info | markdownify | remove: "<p>" | remove: "</p>" }}</td>
      <td>{{ k.desc | markdownify | remove: "<p>" | remove: "</p>" }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
</div>
<p id="kw-empty" hidden>No keyword matches this filter.</p>

<script>
  (function () {
    var input = document.getElementById("kw-search");
    var chips = document.querySelectorAll(".kw-chip");
    var rows = document.querySelectorAll(".kw-table tbody tr");
    var empty = document.getElementById("kw-empty");
    var section = "";
    function apply() {
      var q = input.value.trim().toLowerCase(), shown = 0;
      rows.forEach(function (r) {
        var ok = (!section || r.getAttribute("data-section") === section) &&
                 (!q || r.getAttribute("data-search").indexOf(q) !== -1);
        r.hidden = !ok;
        if (ok) shown++;
      });
      empty.hidden = shown > 0;
    }
    input.addEventListener("input", apply);
    chips.forEach(function (c) {
      c.addEventListener("click", function () {
        chips.forEach(function (x) { x.classList.remove("is-active"); });
        c.classList.add("is-active");
        section = c.getAttribute("data-section");
        apply();
      });
    });
  })();
</script>
