# Compilar Pliegue desde el código · Building from source

*English summary at the end.*

## Desde un clon nuevo

Requisitos: Windows 10/11 de 64 bits, [Python 3.11](https://www.python.org/downloads/) (con el
lanzador `py`), [Git](https://git-scm.com/) e [Inno Setup 6](https://jrsoftware.org/isinfo.php)
(solo para el instalador).

```powershell
git clone https://github.com/Blureckzhyto/pliegue.git
cd pliegue
py -3.11 -m pip install -r requirements.txt
py -3.11 tools\fetch_assets.py      # Poppler, Tesseract, WeasyPrint y la biblioteca de fuentes
py -3.11 main.py                    # ejecutar desde el código
build.bat                           # -> dist\Pliegue\Pliegue.exe
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer.iss   # -> installer\Pliegue_Setup.exe
```

`tools\fetch_assets.py` descarga los componentes de terceros que no están en el repositorio
(son grandes y tienen sus propias licencias) desde sus fuentes oficiales, con las mismas
versiones que usa la app, y verifica cada archivo con SHA-256 (`tools\assets_manifest.json`).
Para abrir el instalador de Tesseract descarga 7-Zip y lo extrae con `msiexec /a`, sin
instalar nada en Windows. `tools\make_assets_manifest.py` regenera el manifiesto al
actualizar alguno de esos componentes.

| Carpeta | Componente | Uso | Licencia |
|---|---|---|---|
| `assets/poppler` | Poppler 26.02 | vistas previas, PDF → JPG, OCR, PDF/A | GPL |
| `assets/tesseract` | Tesseract 5.4 (UB-Mannheim) + `spa`/`eng` de *tessdata_fast* | OCR | Apache 2.0 |
| `assets/weasyprint` | WeasyPrint 70 (ejecutable para Windows) | HTML → PDF | BSD |
| `assets/fonts/library` | 30 familias de Google Fonts | fuente completa para el editor | OFL / Apache / UFL |
| `assets/fonts` (en el repo) | Plus Jakarta Sans, Inter, Dancing Script | interfaz y firmas | OFL |
| `assets/icons` (en el repo) | Lucide (PNG generados con `tools/make_icons.py`) | iconos | ISC |

Las licencias de todo lo incluido están en [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md)
y sus textos en `licenses/` (`python tools\collect_licenses.py` los regenera). El build los
copia a `dist\Pliegue\Licencias` y el instalador a la carpeta **Licencias** de la app.

## El build

`build.bat` usa siempre Python 3.11 (`py -3.11`) y PyInstaller en modo **carpeta**
(`--onedir --windowed --splash --noupx`) → `dist\Pliegue\` (`Pliegue.exe` + `_internal\`): la app
se instala una vez y abre en ~1,5 s (el formato de un solo archivo descomprimía ~380 MB en
cada arranque). Se excluyen módulos que la app no usa y `hooks\hook-playa.py` agrega el
módulo compilado que necesita camelot ("PDF a Excel"). Las vistas y las bibliotecas pesadas
se cargan al abrir cada herramienta. `installer.iss` instala la carpeta completa; al
actualizar desde 1.3.6 o anterior reemplaza el Pliegue.exe de un solo archivo en el mismo
lugar (mismos accesos directos, una sola entrada en "Agregar o quitar programas").

## Lista de verificación de cada versión

1. Todas las suites desde el código (`tests\`; las capturas quedan en `tests\_capturas\`):
   `py -3.11 tests\run_all.py`
2. Las mismas suites **dentro de la app compilada** (`Pliegue.exe --run-script`):
   `py -3.11 tests\run_all.py --exe dist\Pliegue\Pliegue.exe`
3. La autoprueba del editor dentro del exe (edición con Enter y guardado, falla forzada al
   reinsertar, Enter vacío, y con clics y teclas reales: doble clic con la ventana sin foco,
   escribir y Retroceso sobre un texto elegido, Supr con «Deshacer»):
   `py -3.11 tools\release_check.py dist\Pliegue\Pliegue.exe [otro.pdf::texto de una línea]`
4. El instalador sobre una instalación anterior (con otro AppId: no toca la instalación
   real) y el arranque de esa copia: `py -3.11 tests\installer_upgrade_test.py <Pliegue-onefile-viejo.exe>`
   y `py -3.11 tools\measure_startup.py dist\Pliegue\Pliegue.exe 4`
5. Publicar: `py -3.11 tools\release.py` (instalador, SHA-256, `docs/version.json`, etiqueta y
   release de GitHub).

Las pruebas usan documentos generados (`tests/fixtures.py`); nunca archivos personales.

Datos de la app en `%LOCALAPPDATA%\Pliegue\` (`settings.json`, `font_index.json`, `font_cache\`). Al primer inicio de 1.4.0 se mudan ahí los datos de PDFKit (`%LOCALAPPDATA%\PDFKit` y `~\.pdfkit\settings.json`): se copian, se verifican y recién entonces se borran (`core/paths.py`). Las pruebas usan `PLIEGUE_DATA_DIR` y `PLIEGUE_LEGACY_DIRS` para no tocar los datos reales.

Registros de la app en `%LOCALAPPDATA%\Pliegue\logs\`: `errores.log`, `acciones.log`
(elementos borrados y qué lo provocó), `fuentes.log` e `inicio.log` (tiempos de arranque).

## Programas externos opcionales

| Herramienta | Programa | Sin él |
|---|---|---|
| Word → PDF | Microsoft Word o LibreOffice | no hay conversión |
| PowerPoint → PDF | Microsoft PowerPoint o LibreOffice | renderizado básico |
| Excel → PDF | LibreOffice | renderizado con ReportLab |
| HTML → PDF | Microsoft Edge | solo WeasyPrint |
| PDF → PDF/A | Ghostscript | PDF/A-1b básico (páginas como imagen) |

## Estructura

```
main.py            punto de entrada (también --autotest y --run-script para las pruebas del exe)
ui/                interfaz (customtkinter): app.py, theme.py, about.py, components/, views/
core/              procesamiento; nunca importa tkinter
tests/             suites (run_all.py), documentos generados (fixtures.py)
tools/             fetch_assets, collect_licenses, release_check, release, capturas, iconos
docs/              página de descarga (GitHub Pages)
hooks/             hook de PyInstaller
licenses/          textos de licencia de terceros
```

La interfaz y la lógica están separadas: `ui/` nunca procesa archivos y `core/` nunca
importa tkinter. Todo el procesamiento corre en hilos en segundo plano.

---

**English summary.** Requirements: Windows 10/11 x64, Python 3.11, Git, Inno Setup 6.
`git clone` → `py -3.11 -m pip install -r requirements.txt` → `py -3.11 tools\fetch_assets.py`
(downloads Poppler, Tesseract, WeasyPrint and the font library from their official sources
and verifies SHA-256) → `build.bat` → `ISCC.exe installer.iss`. Run all test suites with
`tests\run_all.py` (add `--exe dist\Pliegue\Pliegue.exe` to run them inside the built app).
