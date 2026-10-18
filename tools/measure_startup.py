"""Mide el arranque de Pliegue: desde que se lanza el .exe hasta que la ventana se ve y hasta
que se puede usar.

    python tools\\measure_startup.py <Pliegue.exe> [veces] [--frio]

* aviso: aparece la primera ventana del proceso (la pantalla de carga, si la hay);
* visible: la ventana principal "Pliegue" (o "PDFKit" en versiones viejas) del proceso (o de sus hijos) está visible;
* usable: visible, responde a mensajes (SendMessageTimeout) y el proceso ya no trabaja
  (menos de 10 % de un núcleo durante 400 ms) — sirve igual para versiones viejas y nuevas.
`--frio` copia antes la app (el .exe o su carpeta) a una carpeta nueva: archivos nunca
abiertos, que Windows y el antivirus tienen que leer y revisar como en el primer arranque.
La app corre con una carpeta de datos temporal (no toca la configuración del usuario).
"""
from __future__ import annotations

import ctypes
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
PROCESS_QUERY = 0x1000
SANDBOX = tempfile.mkdtemp(prefix="pliegue_arranque_")
WM_NULL, WM_CLOSE = 0x0000, 0x0010


def _children(pid: int) -> set[int]:
    """El proceso y sus descendientes (el exe "onefile" relanza un proceso hijo)."""
    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)
    entry = Entry()
    entry.dwSize = ctypes.sizeof(Entry)
    pairs = []
    ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
    while ok:
        pairs.append((entry.th32ParentProcessID, entry.th32ProcessID))
        ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    kernel32.CloseHandle(snapshot)
    family, changed = {pid}, True
    while changed:
        changed = False
        for parent, child in pairs:
            if parent in family and child not in family:
                family.add(child)
                changed = True
    return family


def _main_window(pids: set[int], any_title: bool = False):
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value in pids and user32.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(64)
            user32.GetWindowTextW(hwnd, title, 64)
            if title.value in ("Pliegue", "PDFKit") or any_title:
                found.append((hwnd, owner.value))
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else (None, None)


def _cpu_seconds(pid: int) -> float:
    handle = kernel32.OpenProcess(PROCESS_QUERY, False, pid)
    if not handle:
        return 0.0
    times = [wintypes.FILETIME() for _ in range(4)]
    kernel32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times])
    kernel32.CloseHandle(handle)
    as_int = lambda ft: (ft.dwHighDateTime << 32) | ft.dwLowDateTime  # noqa: E731
    return (as_int(times[2]) + as_int(times[3])) / 1e7


def _responds(hwnd) -> bool:
    result = ctypes.c_size_t()
    return bool(user32.SendMessageTimeoutW(hwnd, WM_NULL, 0, 0, 0x0002, 100, ctypes.byref(result)))


def launch(exe: Path, timeout: float = 90.0):
    start = time.perf_counter()
    env = dict(os.environ, PLIEGUE_DATA_DIR=SANDBOX, PLIEGUE_LEGACY_DIRS="")
    proc = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env)
    first = visible = usable = None
    pids, last_family = {proc.pid}, 0.0
    hwnd = owner = None
    try:
        while time.perf_counter() - start < timeout:
            now = time.perf_counter()
            if now - last_family > 1.0:
                pids, last_family = _children(proc.pid), now
            if first is None and _main_window(pids, any_title=True)[0]:
                first = time.perf_counter() - start
            if hwnd is None:
                hwnd, owner = _main_window(pids)
                if hwnd is None:
                    time.sleep(0.02)
                    continue
                visible = time.perf_counter() - start
            if _responds(hwnd):
                before = _cpu_seconds(owner)
                time.sleep(0.4)
                busy = (_cpu_seconds(owner) - before) / 0.4
                if busy < 0.10 and _responds(hwnd):
                    usable = time.perf_counter() - start - 0.4
                    break
            else:
                time.sleep(0.05)
    finally:
        if hwnd:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        try:
            proc.wait(15)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        time.sleep(1.0)
    return first, visible, usable


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    exe = Path(argv[0]).resolve()
    runs = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 3
    cold = "--frio" in argv
    settings = Path.home() / ".pdfkit" / "settings.json"   # solo versiones viejas (PDFKit); Pliegue usa datos temporales
    backup = settings.read_bytes() if settings.exists() else None
    results = []
    try:
        for n in range(runs):
            target = exe
            if cold:   # copia nueva: nada en caché para estos archivos
                folder = Path(tempfile.mkdtemp(prefix="pliegue_frio_"))
                if (exe.parent / "_internal").is_dir():
                    shutil.copytree(exe.parent, folder / "app")
                    target = folder / "app" / exe.name
                else:
                    target = folder / exe.name
                    shutil.copy2(exe, target)
            first, visible, usable = launch(target)
            results.append((visible, usable, first))
            print(f"  {'frío' if cold else 'tibio'} {n + 1}: primer aviso {first or float('nan'):5.2f} s · "
                  f"ventana visible {visible or float('nan'):5.2f} s · "
                  f"usable {usable or float('nan'):5.2f} s", flush=True)
            if cold:
                shutil.rmtree(target.parent if target.parent.name == "app" else target.parent,
                              ignore_errors=True)
    finally:
        if backup is not None:
            settings.write_bytes(backup)
    ok = [r for r in results if r[0] and r[1]]
    if ok:
        print(f"mediana: primer aviso {statistics.median(r[2] for r in ok):.2f} s · "
              f"visible {statistics.median(r[0] for r in ok):.2f} s · "
              f"usable {statistics.median(r[1] for r in ok):.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
