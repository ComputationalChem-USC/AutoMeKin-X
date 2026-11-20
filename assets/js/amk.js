// AutoMeKin-X site behaviour: "On this page" index, scroll reveals,
// tabs and copy buttons for citations. No dependencies.
(function () {
  "use strict";

  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- On this page -----------------------------------------------------
  function buildToc() {
    var main = document.querySelector(".main");
    var content = document.querySelector("#main-content main");
    if (!main || !content || document.querySelector(".amk-landing")) return;
    var heads = content.querySelectorAll("h2[id], h3[id]");
    if (heads.length < 3) return;

    var aside = document.createElement("aside");
    aside.className = "page-toc";
    aside.setAttribute("aria-label", "On this page");
    var title = document.createElement("p");
    title.className = "page-toc-title";
    title.textContent = "On this page";
    aside.appendChild(title);
    var list = document.createElement("ul");
    var links = [];
    heads.forEach(function (h) {
      var li = document.createElement("li");
      li.className = h.tagName === "H3" ? "toc-h3" : "toc-h2";
      var a = document.createElement("a");
      a.href = "#" + h.id;
      var c = h.cloneNode(true);
      c.querySelectorAll(".pub-count, .anchor-heading").forEach(function (x) { x.remove(); });
      a.textContent = c.textContent.trim();
      li.appendChild(a);
      list.appendChild(li);
      links.push({ a: a, h: h });
    });
    aside.appendChild(list);
    main.appendChild(aside);
    document.body.classList.add("has-page-toc");

    // Highlight the section being read
    if ("IntersectionObserver" in window) {
      var current = null;
      var obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) {
            var hit = links.filter(function (l) { return l.h === e.target; })[0];
            if (hit) {
              if (current) current.classList.remove("active");
              hit.a.classList.add("active");
              current = hit.a;
            }
          }
        });
      }, { rootMargin: "0px 0px -70% 0px" });
      links.forEach(function (l) { obs.observe(l.h); });
    }
  }

  // ---- Reveal on scroll --------------------------------------------------
  function reveals() {
    var items = document.querySelectorAll(".reveal");
    if (reduceMotion || !("IntersectionObserver" in window)) {
      items.forEach(function (el) { el.classList.add("is-visible"); });
      return;
    }
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("is-visible");
          obs.unobserve(e.target);
        }
      });
    }, { threshold: 0.15 });
    items.forEach(function (el) { obs.observe(el); });
  }

  // ---- Tabs ----------------------------------------------------------------
  function tabs() {
    document.querySelectorAll(".amk-tabs").forEach(function (box) {
      var buttons = box.querySelectorAll("[role=tab]");
      var panels = box.querySelectorAll("[role=tabpanel]");
      buttons.forEach(function (b, i) {
        b.addEventListener("click", function () {
          buttons.forEach(function (x, j) {
            x.setAttribute("aria-selected", j === i ? "true" : "false");
            panels[j].hidden = j !== i;
          });
        });
      });
    });
  }

  // ---- Copy buttons (citations) --------------------------------------------
  function copyButtons() {
    document.querySelectorAll("[data-copy-target]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var el = document.getElementById(btn.getAttribute("data-copy-target"));
        if (!el || !navigator.clipboard) return;
        navigator.clipboard.writeText(el.textContent.trim()).then(function () {
          var old = btn.textContent;
          btn.textContent = "Copied";
          setTimeout(function () { btn.textContent = old; }, 1500);
        });
      });
    });
  }

  // ---- Hero: a slowly moving potential energy surface ---------------------
  function pesHero() {
    var canvas = document.querySelector(".pes-canvas");
    if (!canvas || !canvas.getContext) return;
    var ctx = canvas.getContext("2d");
    var W = 0, H = 0, t = 0, raf = null, visible = true;
    var N = 34; // grid lines in each direction

    function size() {
      var r = canvas.getBoundingClientRect();
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = r.width; H = r.height;
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    // Two wells joined by a saddle, with a slow ripple
    function z(x, y, t) {
      var a = Math.exp(-((x + 0.45) * (x + 0.45) + (y + 0.1) * (y + 0.1)) / 0.09);
      var b = Math.exp(-((x - 0.4) * (x - 0.4) + (y - 0.15) * (y - 0.15)) / 0.12);
      var c = Math.exp(-((x - 0.05) * (x - 0.05) + (y + 0.55) * (y + 0.55)) / 0.07);
      return -1.0 * a - 0.8 * b - 0.55 * c + 0.12 * Math.sin(3 * x + t) * Math.cos(3 * y - 0.7 * t);
    }

    function project(x, y, h) {
      // simple oblique projection, surface placed on the right of the hero
      var cx = W * (W > 700 ? 0.68 : 0.5), cy = H * 0.55, s = Math.min(W * 0.42, H * 0.9);
      var rot = 0.55 + 0.08 * Math.sin(t * 0.15);
      var xr = x * Math.cos(rot) - y * Math.sin(rot);
      var yr = x * Math.sin(rot) + y * Math.cos(rot);
      return [cx + xr * s, cy + yr * s * 0.45 - h * s * 0.32];
    }

    function line(pts, i) {
      ctx.beginPath();
      for (var k = 0; k < pts.length; k++) {
        if (k === 0) ctx.moveTo(pts[k][0], pts[k][1]); else ctx.lineTo(pts[k][0], pts[k][1]);
      }
      ctx.stroke();
    }

    function draw() {
      ctx.clearRect(0, 0, W, H);
      ctx.lineWidth = 1;
      for (var dir = 0; dir < 2; dir++) {
        for (var i = 0; i <= N; i++) {
          var u = -1 + (2 * i) / N, pts = [], depth = 0;
          for (var j = 0; j <= N; j++) {
            var v = -1 + (2 * j) / N;
            var x = dir ? u : v, y = dir ? v : u;
            var h = z(x, y, t);
            depth += h;
            pts.push(project(x, y, h));
          }
          var alpha = 0.10 + 0.22 * Math.min(1, -depth / N * 1.6);
          ctx.strokeStyle = "rgba(96,165,250," + alpha.toFixed(3) + ")";
          line(pts);
        }
      }
      // a point rolling between the two wells, over the saddle
      var p = (Math.sin(t * 0.5) + 1) / 2;
      var px = -0.45 + 0.85 * p, py = -0.1 + 0.25 * p;
      var q = project(px, py, z(px, py, t) + 0.03);
      ctx.fillStyle = "rgba(52,211,153,0.95)";
      ctx.shadowColor = "rgba(52,211,153,0.8)";
      ctx.shadowBlur = 14;
      ctx.beginPath(); ctx.arc(q[0], q[1], 4.5, 0, Math.PI * 2); ctx.fill();
      ctx.shadowBlur = 0;
    }

    function loop() {
      t += 0.012;
      draw();
      raf = visible ? requestAnimationFrame(loop) : null;
    }

    size();
    window.addEventListener("resize", function () { size(); draw(); });
    if (reduceMotion) { draw(); return; }
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (e) {
        visible = e[0].isIntersecting;
        if (visible && !raf) loop();
      }).observe(canvas);
    }
    loop();
  }

  // ---- Workflow diagram: plays step by step, click to choose a step --------
  function flowDiagram() {
    var box = document.querySelector("[data-flow]");
    if (!box) return;
    var nodes = box.querySelectorAll("[data-step]");
    var slides = box.querySelectorAll("[data-slide]");
    var viewer = box.querySelector(".flow-viewer");
    var steps = slides.length;
    var current = 0, timer = null, paused = false;

    var bar = document.createElement("div");
    bar.className = "flow-progress";
    for (var i = 0; i < steps; i++) bar.appendChild(document.createElement("span"));
    viewer.appendChild(bar);
    var ticks = bar.querySelectorAll("span");

    function show(n) {
      current = n;
      nodes.forEach(function (el) {
        var s = +el.getAttribute("data-step");
        el.classList.toggle("is-active", s === n);
        el.classList.toggle("is-done", s < n);
      });
      slides.forEach(function (el) {
        el.classList.toggle("is-active", +el.getAttribute("data-slide") === n);
      });
      ticks.forEach(function (el, i) { el.classList.toggle("is-on", i <= n); });
    }

    function play() {
      if (timer || reduceMotion || paused) return;
      timer = setInterval(function () { show((current + 1) % steps); }, 2800);
    }
    function stop() { clearInterval(timer); timer = null; }

    nodes.forEach(function (el) {
      el.setAttribute("tabindex", "0");
      el.setAttribute("role", "button");
      function pick() {
        paused = true; stop();
        show(+el.getAttribute("data-step"));
        // resume the animation after a while without interaction
        clearTimeout(el._resume);
        el._resume = setTimeout(function () { paused = false; play(); }, 12000);
      }
      el.addEventListener("click", pick);
      el.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); }
      });
    });

    show(0);
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (e) {
        if (e[0].isIntersecting) play(); else stop();
      }, { threshold: 0.3 }).observe(box);
    } else {
      play();
    }
  }

  // ---- Interactive demo, loaded only on request ----------------------------
  function demo() {
    document.querySelectorAll(".demo-frame[data-demo-src]").forEach(function (frame) {
      var btn = frame.querySelector(".demo-launch");
      if (!btn) return;
      btn.addEventListener("click", function () {
        var f = document.createElement("iframe");
        f.src = frame.getAttribute("data-demo-src");
        f.title = "Interactive reaction network of formic acid";
        f.loading = "lazy";
        frame.innerHTML = "";
        frame.appendChild(f);
      });
    });
  }

  function init() {
    pesHero();
    flowDiagram();
    demo();
    buildToc();
    reveals();
    tabs();
    copyButtons();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
