"""Genera build\\version_info.txt para PyInstaller (--version-file): nombre, versión y autor que
Windows muestra en las propiedades de Pliegue.exe y en el Administrador de tareas. Lee la
versión de ui/app.py y el autor de core/project.py."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core import project  # noqa: E402

TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({t}), prodvers=({t}), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040A04B0', [
      StringStruct('CompanyName', '{author}'),
      StringStruct('FileDescription', 'Pliegue'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', 'Pliegue'),
      StringStruct('LegalCopyright', '© {year} {author} · AGPL-3.0'),
      StringStruct('OriginalFilename', 'Pliegue.exe'),
      StringStruct('ProductName', 'Pliegue'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [0x040A, 1200])])
  ]
)
"""


def main() -> None:
    version = re.search(r'VERSION = "([^"]+)"', (ROOT / "ui" / "app.py").read_text(encoding="utf-8")).group(1)
    parts = (version.split(".") + ["0", "0", "0"])[:4]
    out = ROOT / "build" / "version_info.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text(TEMPLATE.format(t=", ".join(parts), v=version, author=project.GITHUB_USER or "Pliegue",
                                   year=project.YEAR), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
