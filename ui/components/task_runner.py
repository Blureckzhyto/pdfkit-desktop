"""Run core functions in a background thread, reporting back on the UI thread."""
from __future__ import annotations

import threading

from core import errors


def run_task(widget, work, on_success, on_error, on_progress=None) -> None:
    """Execute `work(progress)` in a daemon thread.

    `progress(fraction, message=None)` may be called freely from the worker;
    all callbacks are marshalled onto the Tk main loop via `widget.after`,
    so handlers can touch widgets safely. Every exception from `work` is written
    (with its traceback) to errores.log before `on_error` runs.
    """

    def progress(fraction: float, message: str | None = None) -> None:
        if on_progress is not None:
            try:
                widget.after(0, lambda: on_progress(fraction, message))
            except RuntimeError:
                pass  # window was closed mid-task

    def deliver(callback, value) -> None:
        try:
            widget.after(0, lambda: callback(value))
        except RuntimeError:
            pass  # window was closed mid-task

    def runner() -> None:
        try:
            result = work(progress)
        except Exception as exc:
            errors.record(f"Tarea en segundo plano ({getattr(work, '__qualname__', work)})", exc)
            deliver(on_error, exc)
        else:
            deliver(on_success, result)

    threading.Thread(target=runner, daemon=True).start()
