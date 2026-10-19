"""Empaqueta dist\\Pliegue (la salida de build.bat) como MSIX para la Microsoft Store.

    python tools\\build_msix.py                 # build\\msix\\Pliegue_<versión>_x64.msix (sin firmar)
    python tools\\build_msix.py --firmar-prueba # además una copia firmada con un certificado de
                                               # prueba (para instalarla en esta PC)

La Store firma el paquete al publicarlo: a Partner Center se sube el .msix SIN firmar.

Es una app de escritorio de confianza total (Desktop Bridge): EntryPoint
Windows.FullTrustApplication + la capacidad restringida runFullTrust. La identidad (nombre,
editor) sale de core/project.py y tiene que ser idéntica a la de Partner Center.

Capacidades:
  runFullTrust    obligatoria para una app de escritorio Win32 empaquetada (Python, Tk, y los
                  programas incluidos: Poppler, Tesseract, WeasyPrint).
  internetClient  "HTML a PDF" puede descargar una página web cuando el usuario escribe una
                  URL. Nada más usa la red.

Pasos: (1) copia dist\\Pliegue a build\\msix\\layout; (2) genera los iconos del paquete desde
assets\\logo_icon.png en todas las escalas y tamaños; (3) escribe AppxManifest.xml y las
descripciones en español e inglés (resources.pri, con makepri); (4) makeappx pack.
Necesita el Windows SDK (makeappx, makepri, signtool):
    winget install Microsoft.WindowsSDK.10.0.26100
"""
from __future__ import annotations

import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from core import project  # noqa: E402
from make_logo_assets import _resize, _square, _trim  # noqa: E402

DIST = ROOT / "dist" / "Pliegue"
OUT = ROOT / "build" / "msix"
LAYOUT = OUT / "layout"
PRI_SRC = OUT / "pri_src"          # solo Assets\ y strings\ (makepri no debe indexar _internal)
CERT_DIR = OUT / "certificado_prueba"
MIN_WINDOWS = "10.0.17763.0"        # Windows 10 1809
MAX_TESTED = "10.0.26100.0"         # Windows 11 24H2
LANGUAGES = ["es-MX", "en-US"]      # el primero es el idioma predeterminado
DESCRIPTION = {
    "es-MX": "Todas tus herramientas PDF, sin internet: unir, dividir, comprimir, editar texto, "
             "firmar, OCR y convertir.",
    "en-US": "All your PDF tools, offline: merge, split, compress, edit text, sign, OCR and convert.",
}
SCALES = [100, 125, 150, 200, 400]
TARGET_SIZES = [16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256]
SHARPEN_UP_TO = 32
# (nombre, ancho, alto a escala 100, fracción del alto que ocupa el icono)
TILES = [("Square44x44Logo", 44, 44, 1.0), ("StoreLogo", 50, 50, 1.0),
         ("Square71x71Logo", 71, 71, 0.62), ("Square150x150Logo", 150, 150, 0.58),
         ("Wide310x150Logo", 310, 150, 0.58), ("Square310x310Logo", 310, 310, 0.5),
         ("SplashScreen", 620, 300, 0.4)]


def version() -> str:
    text = (ROOT / "ui" / "app.py").read_text(encoding="utf-8")
    parts = re.search(r'VERSION = "([^"]+)"', text).group(1).split(".")
    return ".".join((parts + ["0"] * 4)[:3] + ["0"])   # la Store exige que la 4.ª parte sea 0


def sdk_tool(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    base = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    candidates = sorted(base.glob(f"10.*/x64/{name}"), key=lambda p: [int(n) for n in p.parts[-3].split(".")])
    if not candidates:
        raise SystemExit(f"No encontré {name}: instala el Windows SDK "
                         "(winget install Microsoft.WindowsSDK.10.0.26100)")
    return str(candidates[-1])


def run(cmd: list) -> None:
    print("  $", " ".join(str(c) for c in cmd), flush=True)
    proc = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, errors="replace")
    if proc.returncode:
        print(proc.stdout[-4000:], proc.stderr[-4000:])
        raise SystemExit(f"Falló {Path(cmd[0]).name} (código {proc.returncode})")


# --------------------------------------------------------------------------- nombres válidos

def fix_payload_names(layout: Path) -> list[str]:
    """MSIX no admite "[" ni "]" en las rutas del paquete. Las fuentes variables de la
    biblioteca se llaman así (Inter[opsz,wght].ttf): se renombran (Inter-opsz-wght.ttf; la app
    las busca recorriendo la carpeta, no por nombre). La plantilla descomprimida de python-docx
    ([Content_Types].xml) no se usa (python-docx abre default.docx): se quita."""
    changes = []
    template = layout / "_internal" / "docx" / "templates" / "default-docx-template"
    if template.exists():
        shutil.rmtree(template)
        changes.append(str(template.relative_to(layout)) + " (quitada)")
    for path in sorted(layout.rglob("*"), reverse=True):     # primero los archivos más profundos
        if "[" in path.name or "]" in path.name:
            if path.suffix.lower() not in (".ttf", ".otf"):
                raise SystemExit(f"Nombre no válido en MSIX, sin regla para renombrarlo: {path}")
            new = path.with_name(path.name.replace("[", "-").replace("]", "").replace(",", "-"))
            path.rename(new)
            changes.append(f"{path.name} -> {new.name}")
    return changes


# --------------------------------------------------------------------------- iconos

def _tile(icon, width: int, height: int, fraction: float, sharpen: bool):
    from PIL import Image

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    side = max(1, round(min(width, height) * fraction))
    logo = _resize(icon, (side, side), sharpen=sharpen)
    canvas.alpha_composite(logo, ((width - side) // 2, (height - side) // 2))
    return canvas


def make_assets(folder: Path) -> list[str]:
    from PIL import Image

    folder.mkdir(parents=True, exist_ok=True)
    icon = _square(_trim(Image.open(ROOT / "assets" / "logo_icon.png").convert("RGBA")))
    names = []
    for name, width, height, fraction in TILES:
        for scale in SCALES:
            w, h = round(width * scale / 100), round(height * scale / 100)
            _tile(icon, w, h, fraction, sharpen=min(w, h) <= SHARPEN_UP_TO).save(
                folder / f"{name}.scale-{scale}.png", optimize=True)
            names.append(f"{name}.scale-{scale}.png")
    # barra de tareas, Inicio, Explorador: tamaños exactos, sin placa de color detrás
    for size in TARGET_SIZES:
        image = _resize(icon, (size, size), sharpen=size <= SHARPEN_UP_TO)
        for suffix in ("", "_altform-unplated", "_altform-lightunplated"):
            file = f"Square44x44Logo.targetsize-{size}{suffix}.png"
            image.save(folder / file, optimize=True)
            names.append(file)
    return names


# --------------------------------------------------------------------------- manifiesto

def manifest(ver: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
         IgnorableNamespaces="uap rescap">
  <Identity Name="{escape(project.STORE_IDENTITY_NAME)}"
            Publisher="{escape(project.STORE_PUBLISHER)}"
            Version="{ver}"
            ProcessorArchitecture="x64" />
  <Properties>
    <DisplayName>Pliegue</DisplayName>
    <PublisherDisplayName>{escape(project.STORE_PUBLISHER_DISPLAY_NAME)}</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="{MIN_WINDOWS}" MaxVersionTested="{MAX_TESTED}" />
  </Dependencies>
  <Resources>
{chr(10).join(f'    <Resource Language="{lang}" />' for lang in LANGUAGES)}
  </Resources>
  <Applications>
    <Application Id="Pliegue" Executable="Pliegue.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="Pliegue" Description="ms-resource:Description"
                          BackgroundColor="transparent"
                          Square150x150Logo="Assets\\Square150x150Logo.png"
                          Square44x44Logo="Assets\\Square44x44Logo.png">
        <uap:DefaultTile Wide310x150Logo="Assets\\Wide310x150Logo.png"
                         Square71x71Logo="Assets\\Square71x71Logo.png"
                         Square310x310Logo="Assets\\Square310x310Logo.png"
                         ShortName="Pliegue" />
        <uap:SplashScreen Image="Assets\\SplashScreen.png" BackgroundColor="#FFFFFF" />
      </uap:VisualElements>
    </Application>
  </Applications>
  <Capabilities>
    <!-- "HTML a PDF" descarga la página cuando el usuario escribe una URL -->
    <Capability Name="internetClient" />
    <!-- app de escritorio Win32 (Desktop Bridge) -->
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>
"""


def resw(text: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<root>
  <resheader name="resmimetype"><value>text/microsoft-resx</value></resheader>
  <resheader name="version"><value>2.0</value></resheader>
  <resheader name="reader"><value>System.Resources.ResXResourceReader, System.Windows.Forms, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089</value></resheader>
  <resheader name="writer"><value>System.Resources.ResXResourceWriter, System.Windows.Forms, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089</value></resheader>
  <data name="Description" xml:space="preserve"><value>{escape(text)}</value></data>
</root>
"""


def make_pri(makepri: str) -> None:
    for lang in LANGUAGES:
        folder = PRI_SRC / "strings" / lang
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "resources.resw").write_text(resw(DESCRIPTION[lang]), encoding="utf-8")
    config = OUT / "priconfig.xml"
    run([makepri, "createconfig", "/cf", config, "/dq", LANGUAGES[0], "/pv", "10.0.0", "/o"])
    # un solo resources.pri (sin paquetes de recursos aparte: no es un bundle)
    text = re.sub(r"\s*<packaging>.*?</packaging>", "", config.read_text(encoding="utf-8"), flags=re.S)
    config.write_text(text, encoding="utf-8")
    run([makepri, "new", "/pr", PRI_SRC, "/cf", config, "/mn", LAYOUT / "AppxManifest.xml",
         "/of", LAYOUT / "resources.pri", "/o"])


# --------------------------------------------------------------------------- firma de prueba

def test_certificate() -> tuple[Path, Path, str]:
    """Certificado autofirmado con el mismo editor que el paquete. Se crea como archivo (no se
    agrega a ningún almacén de Windows); confiar en él para instalar es un paso aparte."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    pfx, cer, password = CERT_DIR / "Pliegue_prueba.pfx", CERT_DIR / "Pliegue_prueba.cer", "pliegue-prueba"
    if pfx.exists() and cer.exists():
        return pfx, cer, password
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    cn = project.STORE_PUBLISHER.removeprefix("CN=")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1)).not_valid_after(now + datetime.timedelta(days=30))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CODE_SIGNING]), critical=False)
            .sign(key, hashes.SHA256()))
    pfx.write_bytes(pkcs12.serialize_key_and_certificates(
        b"Pliegue prueba", key, cert, None, serialization.BestAvailableEncryption(password.encode())))
    cer.write_bytes(cert.public_bytes(serialization.Encoding.DER))
    return pfx, cer, password


# --------------------------------------------------------------------------- principal

def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not (DIST / "Pliegue.exe").exists():
        raise SystemExit(f"No existe {DIST / 'Pliegue.exe'}: corre build.bat primero")
    ver = version()
    makeappx, makepri = sdk_tool("makeappx.exe"), sdk_tool("makepri.exe")
    print(f"Pliegue {ver} · {project.STORE_IDENTITY_NAME} · {project.STORE_PUBLISHER}")

    for folder in (LAYOUT, PRI_SRC):
        if folder.exists():
            shutil.rmtree(folder)
    print("Copiando", DIST, "...", flush=True)
    shutil.copytree(DIST, LAYOUT)
    print(f"Nombres adaptados a MSIX: {len(fix_payload_names(LAYOUT))}")
    names = make_assets(PRI_SRC / "Assets")
    shutil.copytree(PRI_SRC / "Assets", LAYOUT / "Assets")
    print(f"Iconos: {len(names)} archivos")
    (LAYOUT / "AppxManifest.xml").write_text(manifest(ver), encoding="utf-8")
    make_pri(makepri)

    package = OUT / f"Pliegue_{ver}_x64.msix"
    run([makeappx, "pack", "/d", LAYOUT, "/p", package, "/o"])
    print(f"\nPaquete para la Store (sin firmar): {package} ({package.stat().st_size / 1e6:.0f} MB)")

    if "--firmar-prueba" in argv:
        pfx, cer, password = test_certificate()
        signed = OUT / f"Pliegue_{ver}_x64_prueba_firmado.msix"
        shutil.copyfile(package, signed)
        run([sdk_tool("signtool.exe"), "sign", "/fd", "SHA256", "/f", pfx, "/p", password, signed])
        print(f"Copia firmada para pruebas: {signed}\nCertificado de prueba: {cer}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
