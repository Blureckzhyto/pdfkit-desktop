"""1.4.0: los datos de PDFKit (%LOCALAPPDATA%\\PDFKit y ~\\.pdfkit\\settings.json) se mudan a
%LOCALAPPDATA%\\Pliegue. Todo en carpetas temporales (PLIEGUE_DATA_DIR / PLIEGUE_LEGACY_DIRS):
nunca toca los datos reales."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import paths  # noqa: E402

results, log = [], []


def check(name, cond, detail=""):
    results.append(bool(cond))
    log.append(("  PASS  " if cond else "  FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def setup_case():
    root = Path(tempfile.mkdtemp(prefix="pliegue_migracion_"))
    old = root / "Local" / "PDFKit"
    (old / "logs").mkdir(parents=True)
    (old / "font_cache").mkdir()
    (old / "logs" / "errores.log").write_text("error viejo\n", encoding="utf-8")
    (old / "font_index.json").write_text('{"x": 1}', encoding="utf-8")
    (old / "font_cache" / "montserrat_700.ttf").write_bytes(os.urandom(4096))
    home = root / "home" / ".pdfkit"
    home.mkdir(parents=True)
    (home / "settings.json").write_text(json.dumps({"theme": "oscuro", "output_dir": "C:/x"}), encoding="utf-8")
    new = root / "Local" / "Pliegue"
    os.environ["PLIEGUE_DATA_DIR"] = str(new)
    os.environ["PLIEGUE_LEGACY_DIRS"] = f"{old};{home}"
    return old, home, new


# 1) migración completa
old, home, new = setup_case()
notes = paths.migrate()
check("copia registros, índice y caché de fuentes", (new / "logs" / "errores.log").read_text(encoding="utf-8")
      == "error viejo\n" and (new / "font_index.json").exists() and (new / "font_cache" / "montserrat_700.ttf").exists())
check("la configuración de ~/.pdfkit pasa a Pliegue/settings.json",
      json.loads((new / "settings.json").read_text(encoding="utf-8")).get("theme") == "oscuro")
check("las carpetas viejas se borran después de verificar", not old.exists() and not home.exists())
check("queda constancia de la migración", any("migrados" in n for n in notes), str(notes))

from core.settings import Settings  # noqa: E402

check("la app lee la configuración migrada", Settings().get("theme") == "oscuro")

# 2) segunda vez: no hace nada
check("si ya no hay datos viejos no hace nada", paths.migrate() == [])

# 3) lo nuevo nunca se pisa
old, home, new = setup_case()
new.mkdir(parents=True)
(new / "settings.json").write_text(json.dumps({"theme": "claro"}), encoding="utf-8")
paths.migrate()
check("si ya existe configuración de Pliegue, no se reemplaza",
      json.loads((new / "settings.json").read_text(encoding="utf-8"))["theme"] == "claro")

# 4) si una copia no coincide, el original se conserva
old, home, new = setup_case()
cache_hash = paths._sha256(old / "font_cache" / "montserrat_700.ttf")
real = paths._sha256
with mock.patch.object(paths, "_sha256", side_effect=lambda p: "x" if "font_cache" in str(p) and "Pliegue" in str(p)
                       else real(p)):
    notes = paths.migrate()
check("copia que no coincide: no se borra la carpeta vieja", old.exists() and (old / "font_cache").exists(), str(notes))
check("y se avisa", any("no coinciden" in n for n in notes), str(notes))
check("las copias fallidas se deshacen (no quedan archivos dudosos)", not (new / "font_cache").exists()
      or not any((new / "font_cache").iterdir()))
paths.migrate()
check("en el siguiente inicio se completa con copias correctas", not old.exists()
      and paths._sha256(new / "font_cache" / "montserrat_700.ttf") == cache_hash)

# 5) sin datos viejos (instalación nueva)
os.environ["PLIEGUE_DATA_DIR"] = tempfile.mkdtemp(prefix="pliegue_nuevo_")
os.environ["PLIEGUE_LEGACY_DIRS"] = str(Path(tempfile.gettempdir()) / "no_existe_PDFKit_x")
check("instalación nueva: funciona sin carpeta vieja", paths.migrate() == [])
check("la carpeta de datos es la de Pliegue", paths.data_dir().name.startswith("pliegue_nuevo_")
      and paths.settings_file().parent == paths.data_dir())
del os.environ["PLIEGUE_DATA_DIR"], os.environ["PLIEGUE_LEGACY_DIRS"]
check("sin variables: %LOCALAPPDATA%\\Pliegue", paths.data_dir().name == "Pliegue"
      and [p.name for p, _k in paths.legacy_sources()] == ["PDFKit", ".pdfkit"])

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
print("\n".join(log))
print(f"\n{sum(results)}/{len(results)} OK")
sys.exit(0 if results and all(results) else 1)
