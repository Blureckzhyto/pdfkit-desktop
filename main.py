"""Pliegue — offline PDF & image toolbox. Entry point."""
import sys
from pathlib import Path

# Allow running both as `python main.py` (from the project folder) and `python <carpeta>/main.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui import startup

startup.mark("python")   # Python ya arrancó (antes: cargador del exe)
startup.prepare()  # antes de crear cualquier ventana

from ui.app import App  # noqa: E402


def main():
    if "--autotest" in sys.argv:   # verificación de la versión instalada (ver ui/selftest.py)
        from ui import selftest

        sys.exit(selftest.run(sys.argv))
    if "--run-script" in sys.argv:   # una suite de tests/ dentro del exe (tests/run_all.py --exe)
        from ui import selftest

        startup.close_splash()
        sys.exit(selftest.run_script(sys.argv))
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
