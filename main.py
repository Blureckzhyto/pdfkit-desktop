"""Pliegue — offline PDF & image toolbox. Entry point."""
import sys
from pathlib import Path

# Allow running both as `python main.py` (from the project folder) and `python <carpeta>/main.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _test_options() -> Path | None:
    """Solo pruebas (tools/msix_check.py): la app de la Store se lanza dentro de su paquete sin
    heredar variables de entorno, así que --entorno <json> las carga antes de todo (p. ej.
    PLIEGUE_DATA_DIR) y --fin <archivo> deja ahí el código de salida al terminar."""
    import json
    import os

    done = None
    for flag in ("--entorno", "--fin"):
        if flag in sys.argv:
            i = sys.argv.index(flag)
            value = Path(sys.argv[i + 1])
            del sys.argv[i:i + 2]
            if flag == "--entorno":
                os.environ.update(json.loads(value.read_text(encoding="utf-8")))
            else:
                done = value
    return done


_DONE = _test_options()

from ui import startup  # noqa: E402

startup.mark("python")   # Python ya arrancó (antes: cargador del exe)
startup.prepare()  # antes de crear cualquier ventana

from ui.app import App  # noqa: E402


def main():
    if "--autotest" in sys.argv:   # verificación de la versión instalada (ver ui/selftest.py)
        from ui import selftest

        return selftest.run(sys.argv)
    if "--run-script" in sys.argv:   # una suite de tests/ dentro del exe (tests/run_all.py --exe)
        from ui import selftest

        startup.close_splash()
        return selftest.run_script(sys.argv)
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    finally:
        if _DONE is not None:
            _DONE.write_text(str(code), encoding="utf-8")
    sys.exit(code)
