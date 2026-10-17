// PDFKit · página de descarga: tema claro/oscuro, idioma recordado y datos de la versión.
// Sin estadísticas ni servicios externos.
(function () {
  var root = document.documentElement;

  function store(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* modo privado: no pasa nada */ }
  }

  function currentTheme() {
    var forced = root.getAttribute("data-theme");
    if (forced) return forced;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function syncHeroShot() {
    var img = document.querySelector(".hero-shot");
    if (!img) return;
    var wanted = currentTheme() === "dark" ? img.getAttribute("data-dark") : img.getAttribute("data-light");
    if (img.getAttribute("src") !== wanted) img.setAttribute("src", wanted);
  }

  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      store("pdfkit-theme", next);
      syncHeroShot();
    });
  }
  if (window.matchMedia) {
    var media = window.matchMedia("(prefers-color-scheme: dark)");
    if (media.addEventListener) media.addEventListener("change", syncHeroShot);
  }
  syncHeroShot();

  // el idioma elegido a mano se recuerda (la primera visita usa el del navegador)
  var lang = document.querySelector(".lang");
  if (lang) {
    lang.addEventListener("click", function () { store("pdfkit-lang", lang.getAttribute("data-lang")); });
  }

  // versión, tamaño y SHA-256 publicados (docs/version.json, lo actualiza tools/release.py)
  var base = document.documentElement.lang === "en" ? "../" : "";
  if (window.fetch) {
    fetch(base + "version.json", { cache: "no-cache" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (info) {
        if (!info) return;
        document.querySelectorAll("[data-version]").forEach(function (el) { el.textContent = info.version; });
        if (info.size_mb) {
          document.querySelectorAll("[data-size]").forEach(function (el) { el.textContent = info.size_mb + " MB · "; });
        }
        if (info.sha256) {
          document.querySelectorAll("[data-sha]").forEach(function (el) { el.textContent = info.sha256; });
        }
      })
      .catch(function () { /* sin red o archivo local: quedan los datos de la página */ });
  }
})();
