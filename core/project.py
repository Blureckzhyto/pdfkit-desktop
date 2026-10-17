"""Datos públicos del proyecto (repositorio, sitio). Los usan "Acerca de" y la publicación."""

GITHUB_USER = "Blureckzhyto"   # dueño del repositorio en GitHub
REPO = "pdfkit-desktop"
YEAR = 2026


def source_url() -> str:
    return f"https://github.com/{GITHUB_USER}/{REPO}" if GITHUB_USER else "https://github.com/"


def site_url() -> str:
    return f"https://{GITHUB_USER.lower()}.github.io/{REPO}/" if GITHUB_USER else ""
