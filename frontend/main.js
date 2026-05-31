/* OperAI Frontend · Obsidian Instrument */
(function () {
  "use strict";

  /* ── Workbench link: always point to Streamlit port ── */
  var workbenchPort = 8501;
  var workbenchUrl = "http://127.0.0.1:" + workbenchPort;
  document.querySelectorAll("[data-workbench]").forEach(function (el) {
    el.setAttribute("href", workbenchUrl);
  });
  /* Also handle /app redirect links */
  var is8080 = location.port === "8080";
  document.querySelectorAll("a[href='/app']").forEach(function (el) {
    if (is8080) {
      /* serve.py handles /app -> :8501 redirect */
      el.setAttribute("href", "/app");
    } else {
      el.setAttribute("href", workbenchUrl);
    }
  });

  /* ── Nav active state ── */
  var current = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-links a").forEach(function (a) {
    var href = a.getAttribute("href");
    if (href === current || (current === "" && href === "index.html")) {
      a.classList.add("active");
    }
  });

  /* ── Fade-in on scroll ── */
  if ("IntersectionObserver" in window) {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.style.opacity = "1";
            entry.target.style.transform = "translateY(0)";
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.06 }
    );

    document.querySelectorAll(".card:not(.fade-in)").forEach(function (el) {
      el.style.opacity = "0";
      el.style.transform = "translateY(12px)";
      el.style.transition = "opacity 0.35s cubic-bezier(0.22, 1, 0.36, 1), transform 0.35s cubic-bezier(0.22, 1, 0.36, 1)";
      observer.observe(el);
    });
  }
})();
