"""Descarga la biblioteca de fuentes libres que usa el editor cuando la fuente de un PDF
no está instalada (assets/fonts/library/). Solo se usa durante el desarrollo.

Origen: el repositorio oficial de Google Fonts (github.com/google/fonts). Los archivos
se guardan tal cual (sin modificar) junto con la licencia de cada familia (OFL, Apache
o UFL). Variables donde existen; en las estáticas, solo los pesos útiles.
"""
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "fonts" / "library"
BASE = "https://raw.githubusercontent.com/google/fonts/main/"
APACHE = "https://www.apache.org/licenses/LICENSE-2.0.txt"

STATIC_4 = ["Regular", "Bold", "Italic", "BoldItalic"]
FAMILIES = {
    # carpeta: (directorio en google/fonts, [archivos], archivo de licencia o "apache")
    "Montserrat": ("ofl/montserrat", ["Montserrat[wght].ttf", "Montserrat-Italic[wght].ttf"], "OFL.txt"),
    "Roboto": ("ofl/roboto", ["Roboto[wdth,wght].ttf", "Roboto-Italic[wdth,wght].ttf"], "OFL.txt"),
    "OpenSans": ("ofl/opensans", ["OpenSans[wdth,wght].ttf", "OpenSans-Italic[wdth,wght].ttf"], "OFL.txt"),
    "Lato": ("ofl/lato", [f"Lato-{s}.ttf" for s in STATIC_4], "OFL.txt"),
    "Poppins": ("ofl/poppins", [f"Poppins-{s}.ttf" for s in (
        "Light", "Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black",
        "Italic", "MediumItalic", "SemiBoldItalic", "BoldItalic", "BlackItalic")], "OFL.txt"),
    "Raleway": ("ofl/raleway", ["Raleway[wght].ttf", "Raleway-Italic[wght].ttf"], "OFL.txt"),
    "Oswald": ("ofl/oswald", ["Oswald[wght].ttf"], "OFL.txt"),
    "Inter": ("ofl/inter", ["Inter[opsz,wght].ttf", "Inter-Italic[opsz,wght].ttf"], "OFL.txt"),
    "Nunito": ("ofl/nunito", ["Nunito[wght].ttf", "Nunito-Italic[wght].ttf"], "OFL.txt"),
    "SourceSans3": ("ofl/sourcesans3", ["SourceSans3[wght].ttf", "SourceSans3-Italic[wght].ttf"], "OFL.txt"),
    "NotoSans": ("ofl/notosans", ["NotoSans[wdth,wght].ttf"], "OFL.txt"),
    "NotoSerif": ("ofl/notoserif", ["NotoSerif[wdth,wght].ttf"], "OFL.txt"),
    "Merriweather": ("ofl/merriweather", ["Merriweather[opsz,wdth,wght].ttf"], "OFL.txt"),
    "PlayfairDisplay": ("ofl/playfairdisplay", ["PlayfairDisplay[wght].ttf",
                                                "PlayfairDisplay-Italic[wght].ttf"], "OFL.txt"),
    "Lora": ("ofl/lora", ["Lora[wght].ttf", "Lora-Italic[wght].ttf"], "OFL.txt"),
    "PTSans": ("ofl/ptsans", [f"PT_Sans-Web-{s}.ttf" for s in STATIC_4], "OFL.txt"),
    "Ubuntu": ("ufl/ubuntu", [f"Ubuntu-{s}.ttf" for s in STATIC_4 + ["Medium"]], "UFL.txt"),
    "WorkSans": ("ofl/worksans", ["WorkSans[wght].ttf", "WorkSans-Italic[wght].ttf"], "OFL.txt"),
    "Rubik": ("ofl/rubik", ["Rubik[wght].ttf", "Rubik-Italic[wght].ttf"], "OFL.txt"),
    "FiraSans": ("ofl/firasans", [f"FiraSans-{s}.ttf" for s in STATIC_4 + ["Medium", "SemiBold"]],
                 "OFL.txt"),
    "Barlow": ("ofl/barlow", [f"Barlow-{s}.ttf" for s in STATIC_4 + ["Light", "Medium", "SemiBold",
                                                                      "Black"]], "OFL.txt"),
    "DMSans": ("ofl/dmsans", ["DMSans[opsz,wght].ttf", "DMSans-Italic[opsz,wght].ttf"], "OFL.txt"),
    "Mulish": ("ofl/mulish", ["Mulish[wght].ttf", "Mulish-Italic[wght].ttf"], "OFL.txt"),
    "Quicksand": ("ofl/quicksand", ["Quicksand[wght].ttf"], "OFL.txt"),
    "EBGaramond": ("ofl/ebgaramond", ["EBGaramond[wght].ttf", "EBGaramond-Italic[wght].ttf"], "OFL.txt"),
    "Arimo": ("ofl/arimo", ["Arimo[wght].ttf", "Arimo-Italic[wght].ttf"], "OFL.txt"),
    "Tinos": ("ofl/tinos", [f"Tinos-{s}.ttf" for s in STATIC_4], "apache"),
    "Cousine": ("ofl/cousine", [f"Cousine-{s}.ttf" for s in STATIC_4], "OFL.txt"),
    "Carlito": ("ofl/carlito", [f"Carlito-{s}.ttf" for s in STATIC_4], "OFL.txt"),
    "Caladea": ("ofl/caladea", [f"Caladea-{s}.ttf" for s in STATIC_4], "OFL.txt"),
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "pdfkit-dev"})
    return urllib.request.urlopen(req, timeout=60).read()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    total, missing = 0, []
    for folder, (src, files, license_name) in FAMILIES.items():
        target = OUT / folder
        target.mkdir(exist_ok=True)
        for name in files:
            path = target / name
            if not path.exists():
                try:
                    path.write_bytes(fetch(BASE + src + "/" + name))
                except Exception as exc:
                    missing.append(f"{src}/{name}: {exc}")
                    continue
            total += path.stat().st_size
        license_path = target / ("LICENSE-Apache-2.0.txt" if license_name == "apache" else license_name)
        if not license_path.exists():
            try:
                license_path.write_bytes(fetch(APACHE if license_name == "apache"
                                               else BASE + src + "/" + license_name))
            except Exception as exc:
                missing.append(f"{src} licencia: {exc}")
    (OUT / "README.txt").write_text(
        "Fuentes libres incluidas con PDFKit (sin modificar), descargadas de\n"
        "https://github.com/google/fonts. Cada carpeta incluye su licencia\n"
        "(SIL Open Font License 1.1, Apache 2.0 o Ubuntu Font Licence 1.0).\n"
        "El editor de PDF las usa cuando la fuente original de un documento no\n"
        "está instalada en Windows.\n", encoding="utf-8")
    print(f"{len(FAMILIES)} familias, {total / 1024 / 1024:.1f} MB en {OUT}")
    if missing:
        print("faltan:\n  " + "\n  ".join(missing))
        sys.exit(1)


if __name__ == "__main__":
    main()
