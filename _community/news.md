---
title: What's new
layout: home
nav_order: 1
permalink: /docs/news.html
---
# What's new

<div class="news-list">
{% for n in site.data.news %}
  <div class="news-item">
    <span class="news-date">{{ n.date }}</span>
    <div>
      <p class="news-title">{{ n.title }}</p>
      <p class="news-text">{{ n.text }}</p>
      {% if n.link %}<a class="news-link" href="{% if n.link contains '://' %}{{ n.link }}{% else %}{{ n.link | relative_url }}{% endif %}">{{ n.link_text }} →</a>{% endif %}
    </div>
  </div>
{% endfor %}
</div>
