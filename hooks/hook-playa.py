"""playa (lo usa camelot en "PDF a Excel") está compilado con mypyc y carga un módulo de
apoyo con nombre de hash (p. ej. 49480697f7d29e053205__mypyc) que PyInstaller no ve: sin
él, `import camelot` falla dentro del exe. Se agregan todos los módulos *__mypyc."""
import pkgutil

hiddenimports = sorted(m.name for m in pkgutil.iter_modules() if m.name.endswith("__mypyc"))
