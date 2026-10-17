"""Arranca dist\\PDFKit.exe, espera su ventana, captura solo esa ventana y lo cierra."""
import ctypes
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

EXE = Path(__file__).resolve().parent.parent / "dist" / "PDFKit" / "PDFKit.exe"
OUT = Path(__file__).parent / "_capturas" / "shots_v131" / "frozen_exe.png"
OUT.parent.mkdir(parents=True, exist_ok=True)
user32 = ctypes.windll.user32
ctypes.windll.shcore.SetProcessDpiAwareness(2)
proc = subprocess.Popen([str(EXE)])
hwnd, start = 0, time.time()
while time.time() - start < 90 and not hwnd:
    time.sleep(0.05)
    hwnd = user32.FindWindowW(None, "PDFKit")
    if hwnd and not user32.IsWindowVisible(hwnd):
        hwnd = 0
ok = bool(hwnd) and proc.poll() is None
shown_after = time.time() - start
if ok:
    time.sleep(4)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    user32.SetForegroundWindow(hwnd)
    time.sleep(1)
    ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True).save(OUT)
    value = ctypes.c_int(0)
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 20, ctypes.byref(value), 4)
    print(f"ventana visible en {shown_after:.1f} s; barra de título oscura={bool(value.value)}; "
          f"proceso vivo={proc.poll() is None}")
subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
print("OK" if ok else "FALLO: no apareció la ventana")
sys.exit(0 if ok else 1)
