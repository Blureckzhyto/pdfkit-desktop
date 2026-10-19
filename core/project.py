"""Datos públicos del proyecto (repositorio, sitio). Los usan "Acerca de" y la publicación."""

GITHUB_USER = "Blureckzhyto"   # dueño del repositorio en GitHub
REPO = "pliegue"
YEAR = 2026


def source_url() -> str:
    return f"https://github.com/{GITHUB_USER}/{REPO}" if GITHUB_USER else "https://github.com/"


def site_url() -> str:
    return f"https://{GITHUB_USER.lower()}.github.io/{REPO}/" if GITHUB_USER else ""

# Microsoft Store (Partner Center -> Identidad del producto). Tienen que coincidir exactamente
# con el paquete MSIX (tools/build_msix.py); si no, la Store lo rechaza.
STORE_ID = "9PB6SBF3HZVN"
STORE_IDENTITY_NAME = "Blureck.Pliegue"
STORE_PUBLISHER = "CN=D0DDDE00-B489-49A9-A0D7-4208E98AF756"
STORE_PUBLISHER_DISPLAY_NAME = "Blureck"


def store_url() -> str:
    return f"https://apps.microsoft.com/detail/{STORE_ID}"


def issues_url() -> str:
    return f"{source_url()}/issues"
