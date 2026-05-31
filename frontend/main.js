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
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08 }
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

  initWorkbenchLinks();
  initActiveNav();
  initRevealObserver();
  initPointerScan();
  initTiltCards();
  initPageAssemble();
})();
