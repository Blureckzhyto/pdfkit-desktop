@echo off
setlocal
cd /d "%~dp0"
rem Siempre con Python 3.11 (el que tiene todas las dependencias)
set PY=py -3.11

echo [1/3] Comprobando icono, logos y pantalla de carga...
if not exist assets\icon.ico (
    %PY% tools\make_logo_assets.py
    if errorlevel 1 (
        echo ERROR: no se pudo generar assets\icon.ico desde assets\logo_icon.png
        exit /b 1
    )
)
if not exist assets\splash.png %PY% tools\make_splash.py
rem nombre, version y autor en las propiedades de Pliegue.exe y el Administrador de tareas
%PY% tools\make_version_info.py >nul
if errorlevel 1 (
    echo ERROR: no se pudo generar build\version_info.txt
    exit /b 1
)

echo [2/3] Compilando dist\Pliegue\ con PyInstaller (carpeta: arranque rapido)...
rem --onedir: la app se instala una sola vez como carpeta; nada se extrae al abrir
rem (con --onefile se descomprimian ~380 MB en cada arranque: 10-15 s).
rem --splash: el logo aparece al instante mientras Python arranca.
rem Sin UPX: aumenta falsos positivos del antivirus y hace mas lento el arranque.
%PY% -m PyInstaller --noconfirm --clean --onedir --windowed --noupx --name Pliegue --icon=assets\icon.ico ^
  --splash assets\splash.png ^
  --version-file build\version_info.txt ^
  --additional-hooks-dir hooks ^
  --add-data "assets;assets" ^
  --collect-all customtkinter ^
  --collect-all tkinterdnd2 ^
  --collect-all pillow_heif ^
  --collect-all weasyprint ^
  --collect-data pptx ^
  --hidden-import pytesseract ^
  --hidden-import pptx ^
  --hidden-import pypdf ^
  --hidden-import pikepdf ^
  --hidden-import pymupdf ^
  --hidden-import fitz ^
  --hidden-import fontTools.varLib.instancer ^
  --hidden-import fontTools.subset ^
  --collect-submodules fontTools ^
  --hidden-import core.errors ^
  --hidden-import ui.selftest ^
  --collect-submodules ui.views ^
  --hidden-import cryptography ^
  --hidden-import pdf2docx ^
  --hidden-import docx2pdf ^
  --hidden-import pythoncom ^
  --hidden-import camelot ^
  --hidden-import pandas ^
  --hidden-import openpyxl ^
  --hidden-import reportlab ^
  --hidden-import pdf2image ^
  --hidden-import img2pdf ^
  --hidden-import PIL ^
  --exclude-module numba ^
  --exclude-module llvmlite ^
  --exclude-module matplotlib ^
  --exclude-module mpl_toolkits ^
  --exclude-module scipy ^
  --exclude-module IPython ^
  --exclude-module pytest ^
  --exclude-module sphinx ^
  --exclude-module torch ^
  --exclude-module sympy ^
  --exclude-module pygments ^
  --exclude-module PyQt5 ^
  --exclude-module PyQt6 ^
  --exclude-module PySide2 ^
  --exclude-module PySide6 ^
  --exclude-module tkinter.test ^
  main.py
if errorlevel 1 (
    echo ERROR: fallo la compilacion con PyInstaller.
    exit /b 1
)

rem Licencias junto a la app (lo exige la AGPL al distribuir el binario)
if not exist dist\Pliegue\Licencias mkdir dist\Pliegue\Licencias
copy /y LICENSE dist\Pliegue\Licencias\LICENSE.txt >nul
copy /y THIRD_PARTY_LICENSES.md dist\Pliegue\Licencias\ >nul
xcopy /e /i /y /q licenses dist\Pliegue\Licencias\terceros >nul

echo [3/3] Anclando a la barra de tareas...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0post_build.ps1"

echo.
echo Listo: dist\Pliegue\Pliegue.exe  (la carpeta dist\Pliegue completa es la app)
endlocal
