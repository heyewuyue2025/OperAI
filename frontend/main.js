(function () {
  "use strict";

  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function initWorkbenchLinks() {
    var workbenchUrl = "http://127.0.0.1:8501";
    document.querySelectorAll("[data-workbench]").forEach(function (el) {
      el.setAttribute("href", workbenchUrl);
    });
    document.querySelectorAll("a[href='/app']").forEach(function (el) {
      el.setAttribute("href", location.port === "8080" ? "/app" : workbenchUrl);
    });
  }

  function initActiveNav() {
    var current = location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll(".nav-links a").forEach(function (a) {
      var href = a.getAttribute("href");
      if (href === current || (current === "" && href === "index.html")) {
        a.classList.add("active");
      }
    });
  }

  function initRevealObserver() {
    if (reduced || !("IntersectionObserver" in window)) {
      document.querySelectorAll(".reveal").forEach(function (el) {
        el.classList.add("visible");
      });
      return;
    }
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
          } else {
            entry.target.classList.remove("visible");
          }
        });
      },
      { rootMargin: "-8% 0px -10% 0px", threshold: 0.08 }
    );
    document.querySelectorAll(".reveal").forEach(function (el) {
      observer.observe(el);
    });
  }

  function initPointerScan() {
    if (reduced || matchMedia("(pointer: coarse)").matches) return;
    var scan = document.createElement("div");
    scan.className = "scan-field";
    document.body.appendChild(scan);

    var x = 0;
    var y = 0;
    var tx = 0;
    var ty = 0;
    var active = false;

    function frame() {
      x += (tx - x) * 0.18;
      y += (ty - y) * 0.18;
      scan.style.left = x + "px";
      scan.style.top = y + "px";
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);

    window.addEventListener("pointermove", function (event) {
      tx = event.clientX;
      ty = event.clientY;
      if (!active) {
        active = true;
        scan.classList.add("active");
      }
      document.documentElement.style.setProperty("--pointer-x", event.clientX + "px");
      document.documentElement.style.setProperty("--pointer-y", event.clientY + "px");
    });
    window.addEventListener("pointerleave", function () {
      active = false;
      scan.classList.remove("active");
    });
  }

  function initTiltCards() {
    if (reduced || matchMedia("(pointer: coarse)").matches) return;
    document.querySelectorAll(".file-card, .dossier-panel, .index-row").forEach(function (card) {
      card.addEventListener("pointermove", function (event) {
        var rect = card.getBoundingClientRect();
        var dx = (event.clientX - rect.left) / rect.width - 0.5;
        var dy = (event.clientY - rect.top) / rect.height - 0.5;
        card.style.transform = "perspective(900px) rotateX(" + (-dy * 2.8) + "deg) rotateY(" + (dx * 3.2) + "deg) translateY(-2px)";
      });
      card.addEventListener("pointerleave", function () {
        card.style.transform = "";
      });
    });
  }

  function initPageAssemble() {
    if (reduced) return;
    document.documentElement.classList.add("archive-assembled");
  }

  function initScrollMotion() {
    if (reduced) return;

    var root = document.documentElement;
    var sections = Array.prototype.slice.call(document.querySelectorAll(".hero, .section"));
    var reactive = Array.prototype.slice.call(
      document.querySelectorAll(".hero-ledger, .map-node, .index-row, .file-card, .dossier-panel, .evidence-panel")
    );
    var navLinks = Array.prototype.slice.call(document.querySelectorAll(".nav-directory a[href^='#']"));

    reactive.forEach(function (el) {
      el.classList.add("scroll-reactive");
    });

    var ticking = false;
    var timer = 0;

    function clamp(value, min, max) {
      return Math.max(min, Math.min(max, value));
    }

    function markActiveNav() {
      var currentId = "";
      var best = Infinity;
      sections.forEach(function (section) {
        if (!section.id) return;
        var rect = section.getBoundingClientRect();
        var distance = Math.abs(rect.top - window.innerHeight * 0.24);
        if (rect.bottom > 120 && rect.top < window.innerHeight * 0.72 && distance < best) {
          best = distance;
          currentId = section.id;
        }
      });
      navLinks.forEach(function (link) {
        link.classList.toggle("active", link.getAttribute("href") === "#" + currentId);
      });
    }

    function update() {
      ticking = false;
      var maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      var y = window.scrollY || window.pageYOffset || 0;
      var progress = clamp(y / maxScroll, 0, 1);

      root.style.setProperty("--scroll-progress", progress.toFixed(4));
      root.style.setProperty("--grid-shift", (y * 0.045).toFixed(1) + "px");

      sections.forEach(function (section) {
        var rect = section.getBoundingClientRect();
        section.classList.toggle("in-view", rect.top < window.innerHeight * 0.72 && rect.bottom > window.innerHeight * 0.22);
      });

      reactive.forEach(function (el) {
        var rect = el.getBoundingClientRect();
        var center = (rect.top + rect.height / 2) / window.innerHeight;
        var energy = clamp(1 - Math.abs(center - 0.52) * 1.65, 0, 1);
        el.style.setProperty("--scroll-energy", energy.toFixed(3));
        el.classList.toggle("scroll-live", energy > 0.28);
      });

      markActiveNav();
    }

    function onScroll() {
      root.classList.add("is-scrolling");
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        root.classList.remove("is-scrolling");
      }, 190);
      if (!ticking) {
        ticking = true;
        window.requestAnimationFrame(update);
      }
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    update();
  }

  initWorkbenchLinks();
  initActiveNav();
  initRevealObserver();
  initPointerScan();
  initTiltCards();
  initPageAssemble();
  initScrollMotion();
})();
