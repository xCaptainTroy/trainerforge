"""Headless-ish UI smoke test: starts a demo target and drives the window.

This is a developer tool, not part of the shipped app. It uses a withdrawn Tk
root so it can run on a normal Windows desktop without stealing focus.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path

logging.getLogger("trainerforge").addHandler(logging.NullHandler())
logging.getLogger("trainerforge").propagate = False

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trainerforge.core.scanner import ValueType  # noqa: E402
from trainerforge.core.table import TableEntry  # noqa: E402
from trainerforge.ui.main_window import MainWindow  # noqa: E402
from trainerforge.ui.theme import apply_theme  # noqa: E402

DEMO = ROOT / "tools" / "demo_target.py"


def pump(root: tk.Tk, window: MainWindow, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        root.update()
        if not window.busy:
            return
        time.sleep(0.02)


def main() -> int:
    child = subprocess.Popen(
        [sys.executable, str(DEMO)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert child.stdout is not None
    line = child.stdout.readline()
    if not line:
        print("demo target failed:", child.stderr.read() if child.stderr else "")
        child.terminate()
        return 1
    data = json.loads(line)
    root = tk.Tk()
    root.withdraw()
    apply_theme(root)
    args = argparse.Namespace(table=None, process=None, smoke_test=False, skip_disclaimer=True)
    from trainerforge.core.config import AppConfig

    window = MainWindow(root, AppConfig(), args)
    try:
        window.process_var.set(
            next(label for label, info in window._processes.items() if info.pid == data["pid"])
        )
        window._attach_selected()
        assert window.process is not None, "attach failed"
        window.scan_type_var.set(ValueType.INT32.label)
        window.scan_value_var.set(str(data["int_value"]))
        window.alignment_var.set("4")
        window.writable_only_var.set(True)
        window._start_first_scan()
        pump(root, window, 20.0)
        assert window.scan_session is not None, "no scan session"
        assert any(
            result.address == data["int_address"] for result in window.scan_session.results
        ), "sentinel address was not found"
        print(f"scan ok: {window.scan_session.count} matches")

        entry = TableEntry(
            description="UI smoke health",
            kind="absolute",
            base=hex(data["int_address"]),
            value_type="int32",
            value=str(data["int_value"] + 7),
            frozen=True,
        )
        window.table.add(entry)
        window._refresh_table(select_id=entry.id)
        time.sleep(0.35)
        root.update()
        from trainerforge.core.process import Process
        from trainerforge.core.scanner import decode_value

        with Process(data["pid"], name="python.exe") as probe:
            written = decode_value(probe.read(data["int_address"], 4), ValueType.INT32)
        assert written == data["int_value"] + 7, f"freezer did not write: {written}"
        print("freezer ok")
        window._detach()
        assert window.process is None
        print("UI smoke test passed")
        return 0
    finally:
        window.shutdown()
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()


if __name__ == "__main__":
    raise SystemExit(main())
