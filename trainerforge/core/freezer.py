"""Background writer for frozen table entries."""

from __future__ import annotations

import copy
import threading
from typing import Callable

from .process import Process
from .table import TableEntry

ErrorCallback = Callable[[str, str], None]


class Freezer:
    """Periodically writes the configured value of frozen entries.

    Snapshot copies are used so the UI can edit the table while the worker is
    writing. A single worker is enough for a typical table and keeps ordering
    predictable.
    """

    def __init__(self, interval: float = 0.05, on_error: ErrorCallback | None = None):
        self.interval = max(0.02, float(interval))
        self.on_error = on_error
        self._lock = threading.RLock()
        self._process: Process | None = None
        self._entries: list[TableEntry] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_errors: dict[str, str] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="trainerforge-freezer",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 1.5) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None

    def set_target(self, process: Process | None) -> None:
        with self._lock:
            self._process = process
            self._last_errors.clear()

    def set_entries(self, entries: list[TableEntry]) -> None:
        with self._lock:
            self._entries = [copy.deepcopy(entry) for entry in entries]

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                process = self._process
                entries = self._entries
            if process is not None and not process.closed:
                for entry in entries:
                    if not entry.frozen:
                        continue
                    try:
                        address = entry.resolve(process)
                        process.write(address, entry.value_bytes())
                    except Exception as exc:  # noqa: BLE001 - worker boundary
                        self._report(entry.id, str(exc))
                    else:
                        self._clear_error(entry.id)
            self._stop.wait(self.interval)

    def _report(self, entry_id: str, message: str) -> None:
        with self._lock:
            if self._last_errors.get(entry_id) == message:
                return
            self._last_errors[entry_id] = message
        if self.on_error:
            try:
                self.on_error(entry_id, message)
            except Exception:
                pass

    def _clear_error(self, entry_id: str) -> None:
        with self._lock:
            self._last_errors.pop(entry_id, None)
