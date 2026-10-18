"""Genera la página de descarga (docs/, servida por GitHub Pages): español en docs/index.html
e inglés en docs/en/index.html, con los mismos colores, tipografía e iconos que la app.

    python tools\\build_site.py

Sin frameworks, sin CDNs, sin estadísticas: HTML + CSS + un poco de JS. Lee la versión de
ui/app.py y, si existe, el tamaño y el SHA-256 de docs/version.json (lo actualiza
tools/release.py). Las capturas (docs/img) las genera tools/make_screenshots.py.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"

from core import project  # noqa: E402

USER = project.GITHUB_USER or "GITHUB_USER"
REPO_URL = f"https://github.com/{USER}/{project.REPO}"
SITE_URL = f"https://{USER.lower()}.github.io/{project.REPO}/"
DOWNLOAD_URL = f"{REPO_URL}/releases/latest/download/PDFKit_Setup.exe"


def app_version() -> str:
    return re.search(r'VERSION = "([^"]+)"', (ROOT / "ui" / "app.py").read_text(encoding="utf-8")).group(1)


# (clave, color, nombre ES, nombre EN, [(icono, ES, EN)])
CATEGORIES = [
    ("ordenar", "#E5484D", "Ordenar PDF", "Organize PDF", [
        ("merge", "Unir PDF", "Merge PDF"), ("split", "Dividir PDF", "Split PDF"),
        ("extract", "Extraer páginas", "Extract pages"), ("delete", "Eliminar páginas", "Delete pages"),
        ("organize", "Ordenar páginas", "Reorder pages")]),
    ("optimizar", "#30A46C", "Optimizar PDF", "Optimize PDF", [
        ("compress", "Comprimir PDF", "Compress PDF"), ("repair", "Reparar PDF", "Repair PDF"),
        ("ocr", "OCR PDF", "OCR PDF")]),
    ("convertir-a", "#F08C1A", "Convertir a PDF", "Convert to PDF", [
        ("jpg2pdf", "JPG a PDF", "JPG to PDF"), ("word2pdf", "Word a PDF", "Word to PDF"),
        ("pptx2pdf", "PowerPoint a PDF", "PowerPoint to PDF"), ("excel2pdf", "Excel a PDF", "Excel to PDF"),
        ("html2pdf", "HTML a PDF", "HTML to PDF")]),
    ("convertir-desde", "#8E4EC6", "Convertir desde PDF", "Convert from PDF", [
        ("pdf2jpg", "PDF a JPG", "PDF to JPG"), ("pdf2word", "PDF a Word", "PDF to Word"),
        ("pdf2pptx", "PDF a PowerPoint", "PDF to PowerPoint"), ("pdf2excel", "PDF a Excel", "PDF to Excel"),
        ("pdfa", "PDF a PDF/A", "PDF to PDF/A")]),
    ("editar", "#2F7FE0", "Editar PDF", "Edit PDF", [
        ("rotate", "Rotar PDF", "Rotate PDF"), ("numbers", "Números de página", "Page numbers"),
        ("watermark", "Marca de agua", "Watermark"), ("crop", "Recortar PDF", "Crop PDF"),
        ("edit", "Editar PDF", "Edit PDF"), ("forms", "Formularios PDF", "PDF forms")]),
    ("seguridad", "#0FA3B1", "Editar y firmar", "Edit & sign", [
        ("sign", "Firmar PDF", "Sign PDF"), ("protect", "Proteger PDF", "Protect PDF"),
        ("unprotect", "Desproteger PDF", "Unlock PDF"), ("redact", "Censurar PDF", "Redact PDF"),
        ("compare", "Comparar PDF", "Compare PDF")]),
    ("imagenes", "#5E7387", "Imágenes", "Images", [
        ("imgconvert", "Convertir imágenes", "Convert images"),
        ("imgcompress", "Comprimir imágenes", "Compress images")]),
]

T = {
    "es": {
        "lang": "es", "title": "PDFKit · Todas tus herramientas PDF, sin internet",
        "description": "PDFKit es una caja de herramientas PDF gratuita y de código abierto para Windows: "
                       "unir, dividir, comprimir, convertir, editar y firmar PDFs sin internet. "
                       "Tus archivos nunca salen de tu computadora.",
        "skip": "Saltar al contenido", "nav_features": "Funciones", "nav_privacy": "Privacidad",
        "nav_install": "Instalación", "nav_faq": "Preguntas", "theme": "Cambiar tema claro/oscuro",
        "hero_title": "Todas tus herramientas PDF, sin internet",
        "hero_sub": "Une, divide, comprime, convierte, edita y firma tus PDFs en tu propia computadora. "
                    "Rápido, privado y sin anuncios.",
        "download": "Descargar para Windows", "for": "Windows 10/11 · 64 bits",
        "badges": "Código abierto · Gratis · Sin anuncios", "version": "Versión",
        "shots_title": "Así se ve", "shot_home": "Inicio en modo claro", "shot_home_dark": "Inicio en modo oscuro",
        "shot_editor": "Editor: doble clic en un texto para cambiarlo con su misma fuente",
        "shot_split": "Dividir un PDF por tamaño máximo",
        "alt_home": "Pantalla de inicio de PDFKit con todas las herramientas, en modo claro",
        "alt_home_dark": "Pantalla de inicio de PDFKit en modo oscuro",
        "alt_editor": "Editor de PDF con una línea de texto seleccionada para editarla",
        "alt_split": "Herramienta Dividir PDF con la opción de tamaño máximo en MB",
        "features_title": "31 herramientas en una sola app",
        "features_sub": "Las mismas categorías e iconos que verás en PDFKit.",
        "privacy_title": "Tus archivos nunca salen de tu computadora",
        "privacy_body": "Todo el procesamiento ocurre en tu equipo. PDFKit no tiene telemetría, estadísticas "
                        "ni anuncios, y no se conecta a internet. La única excepción es opcional: en «HTML a "
                        "PDF» puedes escribir la dirección de una página web, y entonces se descarga esa página "
                        "para convertirla.",
        "privacy_points": ["Funciona sin conexión", "Sin cuentas ni registros", "Sin rastreadores ni anuncios",
                           "Código abierto: cualquiera puede revisarlo"],
        "install_title": "Instalación", "install_steps": [
            "Descarga <strong>PDFKit_Setup.exe</strong> con el botón de arriba.",
            "Ábrelo. Si Windows muestra «Windows protegió su PC», haz clic en <strong>Más información</strong> "
            "y luego en <strong>Ejecutar de todas formas</strong>.",
            "Sigue el asistente. PDFKit queda en el menú Inicio y en el Escritorio."],
        "smartscreen_why": "¿Por qué aparece ese aviso? El instalador no tiene una firma digital de pago "
                           "(cuesta cientos de dólares al año), así que Windows no reconoce al autor. No "
                           "significa que tenga virus: el código es público y puedes comprobar que el archivo "
                           "es el original con su SHA-256.",
        "ss_title": "Windows protegió su PC",
        "ss_body": "Microsoft Defender SmartScreen impidió el inicio de una aplicación no reconocida. "
                   "Ejecutar esta aplicación puede poner su PC en riesgo.",
        "ss_more": "Más información", "ss_app": "Aplicación:", "ss_publisher": "Editor:",
        "ss_unknown": "Editor desconocido", "ss_run": "Ejecutar de todas formas", "ss_dont": "No ejecutar",
        "ss_step1": "1. Haz clic en «Más información»", "ss_step2": "2. Luego en «Ejecutar de todas formas»",
        "sha_label": "SHA-256 del instalador:",
        "faq_title": "Preguntas frecuentes", "faq": [
            ("¿Es gratis?", "Sí, completamente gratis y sin anuncios. Es software libre con licencia AGPL-3.0."),
            ("¿Necesita internet?", "No. Todas las herramientas funcionan sin conexión. Solo «HTML a PDF» usa "
                                    "internet si tú escribes la dirección de una página web."),
            ("¿En qué versiones de Windows funciona?", "En Windows 10 y Windows 11 de 64 bits. Word, PowerPoint "
             "o LibreOffice son opcionales: mejoran «Word a PDF» y «PowerPoint a PDF»."),
            ("¿Cómo lo desinstalo?", "En <em>Configuración → Aplicaciones → Aplicaciones instaladas</em>, busca "
             "PDFKit y elige <em>Desinstalar</em>."),
            ("¿Dónde está el código fuente?", f'En GitHub: <a href="{REPO_URL}">{REPO_URL.replace("https://", "")}</a>. '
             "Puedes revisarlo, compilarlo tú mismo y proponer mejoras."),
            ("¿Está en otros idiomas?", "La aplicación está en español. Esta página también está en inglés."),
        ],
        "footer_license": "Licencia AGPL-3.0", "footer_third": "Licencias de terceros",
        "footer_repo": "Código fuente en GitHub", "footer_changelog": "Cambios",
        "footer_note": "PDFKit no está relacionado con Apple PDFKit ni con iLovePDF.",
        "other_lang": "English", "other_lang_code": "en",
    },
    "en": {
        "lang": "en", "title": "PDFKit · All your PDF tools, offline",
        "description": "PDFKit is a free, open-source PDF toolbox for Windows: merge, split, compress, convert, "
                       "edit and sign PDFs offline. Your files never leave your computer.",
        "skip": "Skip to content", "nav_features": "Features", "nav_privacy": "Privacy",
        "nav_install": "Install", "nav_faq": "FAQ", "theme": "Toggle light/dark theme",
        "hero_title": "All your PDF tools, offline",
        "hero_sub": "Merge, split, compress, convert, edit and sign your PDFs on your own computer. "
                    "Fast, private and ad-free.",
        "download": "Download for Windows", "for": "Windows 10/11 · 64-bit",
        "badges": "Open source · Free · No ads", "version": "Version",
        "shots_title": "Take a look", "shot_home": "Home screen, light mode", "shot_home_dark": "Home screen, dark mode",
        "shot_editor": "Editor: double-click any text to change it with its own font",
        "shot_split": "Splitting a PDF by maximum size",
        "alt_home": "PDFKit home screen with all the tools, light mode",
        "alt_home_dark": "PDFKit home screen in dark mode",
        "alt_editor": "PDF editor with a line of text selected for editing",
        "alt_split": "Split PDF tool with the maximum size (MB) option",
        "features_title": "31 tools in a single app",
        "features_sub": "The same categories and icons you will see in PDFKit (the app interface is in Spanish).",
        "privacy_title": "Your files never leave your computer",
        "privacy_body": "All processing happens on your machine. PDFKit has no telemetry, analytics or ads, and "
                        "it does not connect to the internet. The only exception is optional: in \"HTML a PDF\" "
                        "you can type a web address, and that page is then downloaded to convert it.",
        "privacy_points": ["Works offline", "No accounts or sign-ups", "No trackers or ads",
                           "Open source: anyone can review it"],
        "install_title": "Installation", "install_steps": [
            "Download <strong>PDFKit_Setup.exe</strong> with the button above.",
            "Run it. If Windows shows \"Windows protected your PC\", click <strong>More info</strong> and then "
            "<strong>Run anyway</strong>.",
            "Follow the wizard. PDFKit is added to the Start menu and the Desktop."],
        "smartscreen_why": "Why does that warning appear? The installer has no paid code-signing certificate "
                           "(they cost hundreds of dollars a year), so Windows does not recognize the publisher. "
                           "It does not mean it has a virus: the code is public and you can check that the file "
                           "is the original with its SHA-256.",
        "ss_title": "Windows protected your PC",
        "ss_body": "Microsoft Defender SmartScreen prevented an unrecognized app from starting. Running this "
                   "app might put your PC at risk.",
        "ss_more": "More info", "ss_app": "App:", "ss_publisher": "Publisher:",
        "ss_unknown": "Unknown publisher", "ss_run": "Run anyway", "ss_dont": "Don't run",
        "ss_step1": "1. Click \"More info\"", "ss_step2": "2. Then \"Run anyway\"",
        "sha_label": "Installer SHA-256:",
        "faq_title": "Frequently asked questions", "faq": [
            ("Is it free?", "Yes, completely free and ad-free. It is free software under the AGPL-3.0 license."),
            ("Does it need the internet?", "No. Every tool works offline. Only \"HTML a PDF\" uses the internet "
                                           "if you type a web address."),
            ("Which Windows versions are supported?", "Windows 10 and Windows 11, 64-bit. Word, PowerPoint or "
             "LibreOffice are optional: they improve \"Word to PDF\" and \"PowerPoint to PDF\"."),
            ("How do I uninstall it?", "Go to <em>Settings → Apps → Installed apps</em>, find PDFKit and choose "
             "<em>Uninstall</em>."),
            ("Where is the source code?", f'On GitHub: <a href="{REPO_URL}">{REPO_URL.replace("https://", "")}</a>. '
             "You can review it, build it yourself and suggest improvements."),
            ("Is the app in English?", "The app interface is in Spanish. This page is available in both languages."),
        ],
        "footer_license": "AGPL-3.0 license", "footer_third": "Third-party licenses",
        "footer_repo": "Source code on GitHub", "footer_changelog": "Changelog",
        "footer_note": "PDFKit is not affiliated with Apple PDFKit or iLovePDF.",
        "other_lang": "Español", "other_lang_code": "es",
    },
}


def svg_icon(name: str) -> str:
    svg = (ROOT / "tools" / "lucide_svg" / f"{name}.svg").read_text(encoding="utf-8")
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S).strip()
    svg = re.sub(r'\s(width|height)="\d+"', "", svg, count=2)
    svg = svg.replace("<svg", '<svg aria-hidden="true" focusable="false"', 1)
    return re.sub(r"\s+", " ", svg)


def page(lang: str, version: dict) -> str:
    t = T[lang]
    prefix = "" if lang == "es" else "../"
    other = "en/" if lang == "es" else "../"
    canonical = SITE_URL if lang == "es" else SITE_URL + "en/"
    e = html.escape
    features = []
    for key, color, name_es, name_en, tools in CATEGORIES:
        items = "".join(
            f'<li class="tool"><span class="tool-icon" style="--c:{color}">{svg_icon(icon)}</span>'
            f'<span>{e(es if lang == "es" else en)}</span></li>' for icon, es, en in tools)
        features.append(f'<section class="category" aria-labelledby="cat-{key}"><h3 id="cat-{key}">'
                        f'<span class="dot" style="--c:{color}"></span>{e(name_es if lang == "es" else name_en)}'
                        f'</h3><ul class="tools">{items}</ul></section>')
    shots = [("home-claro", "shot_home", "alt_home"), ("home-oscuro", "shot_home_dark", "alt_home_dark"),
             ("editor-claro", "shot_editor", "alt_editor"), ("dividir-claro", "shot_split", "alt_split")]
    shot_html = "".join(
        f'<figure class="shot"><img src="{prefix}img/{name}.webp" width="1280" height="800" loading="lazy" '
        f'decoding="async" alt="{e(t[alt])}"><figcaption>{e(t[cap])}</figcaption></figure>'
        for name, cap, alt in shots)
    faq = "".join(f"<details><summary>{e(q)}</summary><p>{a}</p></details>" for q, a in t["faq"])
    steps = "".join(f"<li>{s}</li>" for s in t["install_steps"])
    points = "".join(f"<li>{e(p)}</li>" for p in t["privacy_points"])
    size = f'{version["size_mb"]} MB · ' if version.get("size_mb") else ""
    sha = version.get("sha256", "")
    return f"""<!doctype html>
<html lang="{t['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(t['title'])}</title>
<meta name="description" content="{e(t['description'])}">
<link rel="canonical" href="{canonical}">
<link rel="alternate" hreflang="es" href="{SITE_URL}">
<link rel="alternate" hreflang="en" href="{SITE_URL}en/">
<link rel="alternate" hreflang="x-default" href="{SITE_URL}">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#FFFFFF" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#16171D" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="website">
<meta property="og:site_name" content="PDFKit">
<meta property="og:title" content="{e(t['title'])}">
<meta property="og:description" content="{e(t['description'])}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE_URL}assets/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{'es_MX' if lang == 'es' else 'en_US'}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(t['title'])}">
<meta name="twitter:description" content="{e(t['description'])}">
<meta name="twitter:image" content="{SITE_URL}assets/og-image.png">
<link rel="icon" href="{prefix}assets/favicon.ico" sizes="any">
<link rel="icon" href="{prefix}assets/icon-192.png" type="image/png">
<link rel="apple-touch-icon" href="{prefix}assets/apple-touch-icon.png">
<link rel="preload" href="{prefix}assets/fonts/PlusJakartaSans-Regular.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{prefix}assets/site.css">
<script>{early_script(lang)}</script>
</head>
<body>
<a class="skip" href="#contenido">{e(t['skip'])}</a>
<header class="topbar">
  <div class="wrap topbar-row">
    <a class="brand" href="{prefix or './'}" aria-label="PDFKit">
      <img class="logo-light" src="{prefix}assets/logo-wordmark.png" width="132" height="44" alt="PDFKit">
      <img class="logo-dark" src="{prefix}assets/logo-wordmark-dark.png" width="132" height="44" alt="PDFKit">
    </a>
    <nav aria-label="{'Secciones' if lang == 'es' else 'Sections'}">
      <a href="#funciones">{e(t['nav_features'])}</a>
      <a href="#privacidad">{e(t['nav_privacy'])}</a>
      <a href="#instalacion">{e(t['nav_install'])}</a>
      <a href="#preguntas">{e(t['nav_faq'])}</a>
    </nav>
    <div class="controls">
      <a class="lang" href="{other}" hreflang="{t['other_lang_code']}" lang="{t['other_lang_code']}"
         data-lang="{t['other_lang_code']}">{t['other_lang']}</a>
      <button class="theme-toggle" type="button" aria-label="{e(t['theme'])}" title="{e(t['theme'])}">
        <svg class="i-sun" aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4"/></svg>
        <svg class="i-moon" aria-hidden="true" viewBox="0 0 24 24"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
      </button>
    </div>
  </div>
</header>
<main id="contenido">
  <section class="hero">
    <div class="wrap hero-grid">
      <div>
        <img class="hero-icon" src="{prefix}assets/icon-192.png" width="96" height="96" alt="">
        <h1>{e(t['hero_title'])}</h1>
        <p class="lead">{e(t['hero_sub'])}</p>
        <a class="btn-download" href="{DOWNLOAD_URL}">
          <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 3v12M7 10l5 5 5-5M5 21h14"/></svg>
          {e(t['download'])}
        </a>
        <p class="meta"><span>{e(t['version'])} <span data-version>{e(version['version'])}</span></span> ·
          <span data-size>{e(size)}</span><span>{e(t['for'])}</span></p>
        <p class="badges">{e(t['badges'])}</p>
      </div>
      <img class="hero-shot" src="{prefix}img/home-claro.webp" width="1280" height="800" alt="{e(t['alt_home'])}"
           data-light="{prefix}img/home-claro.webp" data-dark="{prefix}img/home-oscuro.webp" fetchpriority="high">
    </div>
  </section>

  <section class="section" aria-labelledby="capturas-titulo">
    <div class="wrap">
      <h2 id="capturas-titulo">{e(t['shots_title'])}</h2>
      <div class="shots">{shot_html}</div>
    </div>
  </section>

  <section class="section alt" id="funciones" aria-labelledby="funciones-titulo">
    <div class="wrap">
      <h2 id="funciones-titulo">{e(t['features_title'])}</h2>
      <p class="section-sub">{e(t['features_sub'])}</p>
      <div class="categories">{''.join(features)}</div>
    </div>
  </section>

  <section class="section" id="privacidad" aria-labelledby="privacidad-titulo">
    <div class="wrap privacy">
      <div class="privacy-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg></div>
      <div>
        <h2 id="privacidad-titulo">{e(t['privacy_title'])}</h2>
        <p>{e(t['privacy_body'])}</p>
        <ul class="checks">{points}</ul>
      </div>
    </div>
  </section>

  <section class="section alt" id="instalacion" aria-labelledby="instalacion-titulo">
    <div class="wrap install-grid">
      <div>
        <h2 id="instalacion-titulo">{e(t['install_title'])}</h2>
        <ol class="steps">{steps}</ol>
        <p class="note">{e(t['smartscreen_why'])}</p>
        <p class="sha"><span>{e(t['sha_label'])}</span> <code data-sha>{e(sha or '—')}</code></p>
      </div>
      <figure class="smartscreen" aria-label="{e(t['ss_title'])}">
        <div class="ss-window">
          <p class="ss-title">{e(t['ss_title'])}</p>
          <p class="ss-body">{e(t['ss_body'])}</p>
          <p class="ss-link"><span class="ss-mark">{e(t['ss_more'])}</span></p>
          <p class="ss-detail">{e(t['ss_app'])} PDFKit_Setup.exe<br>{e(t['ss_publisher'])} {e(t['ss_unknown'])}</p>
          <div class="ss-buttons"><span class="ss-run ss-mark">{e(t['ss_run'])}</span><span class="ss-dont">{e(t['ss_dont'])}</span></div>
        </div>
        <figcaption><span>{e(t['ss_step1'])}</span><span>{e(t['ss_step2'])}</span></figcaption>
      </figure>
    </div>
  </section>

  <section class="section" id="preguntas" aria-labelledby="preguntas-titulo">
    <div class="wrap narrow">
      <h2 id="preguntas-titulo">{e(t['faq_title'])}</h2>
      <div class="faq">{faq}</div>
    </div>
  </section>
</main>
<footer class="footer">
  <div class="wrap footer-row">
    <p>PDFKit <span data-version>{e(version['version'])}</span> · © {project.YEAR} {e(USER)}</p>
    <nav aria-label="{'Enlaces' if lang == 'es' else 'Links'}">
      <a href="{REPO_URL}">{e(t['footer_repo'])}</a>
      <a href="{REPO_URL}/blob/main/LICENSE">{e(t['footer_license'])}</a>
      <a href="{REPO_URL}/blob/main/THIRD_PARTY_LICENSES.md">{e(t['footer_third'])}</a>
      <a href="{REPO_URL}/blob/main/CHANGELOG.md">{e(t['footer_changelog'])}</a>
    </nav>
    <p class="fine">{e(t['footer_note'])}</p>
  </div>
</footer>
<script src="{prefix}assets/site.js" defer></script>
</body>
</html>
"""


def early_script(lang: str) -> str:
    """Antes de pintar: tema guardado y, en la primera visita, el idioma del navegador."""
    other = "en/" if lang == "es" else "../"
    wants_other = ("!/^es\\b/i.test(nav)" if lang == "es" else "/^es\\b/i.test(nav)")
    return ("(function(){var d=document.documentElement,s=null,l=null;"
            "try{s=localStorage.getItem('pdfkit-theme');l=localStorage.getItem('pdfkit-lang');}catch(e){}"
            "if(s==='light'||s==='dark')d.setAttribute('data-theme',s);"
            "var nav=(navigator.languages&&navigator.languages[0])||navigator.language||'es';"
            f"if(!l){{try{{localStorage.setItem('pdfkit-lang',{json.dumps(lang)});}}catch(e){{}}"
            f"if({wants_other})location.replace({json.dumps(other)}+location.hash);}}"
            "})();")


def build_assets() -> None:
    from fontTools.ttLib import TTFont
    from PIL import Image, ImageDraw, ImageFont

    (ASSETS / "fonts").mkdir(parents=True, exist_ok=True)
    for weight in ("Regular", "SemiBold", "Bold"):
        font = TTFont(ROOT / "assets" / "fonts" / f"PlusJakartaSans-{weight}.ttf", recalcTimestamp=False)  # mismo archivo en cada build
        font.flavor = "woff2"
        font.save(ASSETS / "fonts" / f"PlusJakartaSans-{weight}.woff2")
    shutil.copy(ROOT / "assets" / "fonts" / "PlusJakartaSans-OFL.txt", ASSETS / "fonts" / "OFL.txt")

    icon = Image.open(ROOT / "assets" / "logo_icon.png").convert("RGBA")
    for size, name in ((192, "icon-192.png"), (512, "icon-512.png"), (180, "apple-touch-icon.png")):
        icon.resize((size, size), Image.LANCZOS).save(ASSETS / name, optimize=True)
    shutil.copy(ROOT / "assets" / "icon.ico", ASSETS / "favicon.ico")
    word = Image.open(ROOT / "assets" / "logo_wordmark.png").convert("RGBA")
    width = 396
    word.resize((width, round(word.height * width / word.width)), Image.LANCZOS).save(
        ASSETS / "logo-wordmark.png", optimize=True)
    dark = Image.open(ROOT / "assets" / "logo" / "wordmark_sidebar_dark@2x.png").convert("RGBA")
    dark.resize((width, round(dark.height * width / dark.width)), Image.LANCZOS).save(
        ASSETS / "logo-wordmark-dark.png", optimize=True)

    # imagen para redes sociales (1200x630)
    og = Image.new("RGB", (1200, 630), "#FFFFFF")
    draw = ImageDraw.Draw(og)
    draw.rectangle((0, 0, 1200, 12), fill="#E5484D")
    mark = icon.resize((150, 150), Image.LANCZOS)
    og.paste(mark, (90, 110), mark)
    big = word.resize((520, round(word.height * 520 / word.width)), Image.LANCZOS)
    og.paste(big, (270, 118), big)
    bold = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "PlusJakartaSans-Bold.ttf"), 54)
    regular = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "PlusJakartaSans-Regular.ttf"), 34)
    draw.text((90, 330), "Todas tus herramientas PDF, sin internet", font=bold, fill="#1F2133")
    draw.text((90, 405), "All your PDF tools, offline", font=regular, fill="#666A7E")
    draw.text((90, 520), "Windows 10/11 · Código abierto · Gratis · Sin anuncios", font=regular, fill="#C23338")
    og.save(ASSETS / "og-image.png", optimize=True)


def main() -> int:
    DOCS.mkdir(exist_ok=True)
    (DOCS / "en").mkdir(exist_ok=True)
    build_assets()
    version_file = DOCS / "version.json"
    version = json.loads(version_file.read_text(encoding="utf-8")) if version_file.exists() else {}
    version["version"] = version.get("version") or app_version()
    version_file.write_text(json.dumps(version, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    (DOCS / "index.html").write_text(page("es", version), encoding="utf-8", newline="\n")
    (DOCS / "en" / "index.html").write_text(page("en", version), encoding="utf-8", newline="\n")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8", newline="\n")
    print("docs/ listo:", version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
