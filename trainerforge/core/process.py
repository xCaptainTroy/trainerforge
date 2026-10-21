"""Process and memory access built on the Win32 API."""

from __future__ import annotations

import ctypes
import os
import time
from dataclasses import dataclass
from typing import Iterator

from . import winapi


class ProcessError(RuntimeError):
    """Base class for process/memory failures."""


class ProcessAccessError(ProcessError):
    """The process exists but Windows denied the requested access."""


class ProcessNotFoundError(ProcessError):
    """The process is no longer running."""


class MemoryReadError(ProcessError):
    """ReadProcessMemory failed for the requested range."""


class MemoryWriteError(ProcessError):
    """WriteProcessMemory failed for the requested range."""


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    path: str = ""

    @property
    def label(self) -> str:
        return f"{self.name}  ·  {self.pid}"


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    path: str
    base: int
    size: int

    @property
    def end(self) -> int:
        return self.base + self.size


@dataclass(frozen=True)
class Region:
    base: int
    size: int
    protect: int
    state: int
    type: int

    @property
    def end(self) -> int:
        return self.base + self.size

    @property
    def is_readable(self) -> bool:
        if self.state != winapi.MEM_COMMIT:
            return False
        if self.protect & winapi.PAGE_GUARD:
            return False
        return bool(self.protect & winapi.READABLE_PROTECTIONS)

    @property
    def is_writable(self) -> bool:
        if self.state != winapi.MEM_COMMIT:
            return False
        if self.protect & winapi.PAGE_GUARD:
            return False
        return bool(self.protect & winapi.WRITABLE_PROTECTIONS)

    @property
    def is_private(self) -> bool:
        return self.type == winapi.MEM_PRIVATE

    @property
    def is_image(self) -> bool:
        return self.type == winapi.MEM_IMAGE


def list_processes() -> list[ProcessInfo]:
    """Enumerate running processes visible to the current user."""
    result: list[ProcessInfo] = []
    for pid in winapi.enum_process_ids():
        if pid in (0, 4):
            continue
        path = winapi.process_image_path(pid)
        name = os.path.basename(path) if path else ""
        if not name:
            name = f"<pid {pid}>"
        result.append(ProcessInfo(pid=pid, name=name, path=path))
    result.sort(key=lambda item: (item.name.lower(), item.pid))
    return result


def find_process_info(pid: int) -> ProcessInfo | None:
    for info in list_processes():
        if info.pid == pid:
            return info
    return None


class Process:
    """An opened process with read/write/query helpers.

    The object is not thread-safe by itself, but ``ReadProcessMemory`` and
    ``WriteProcessMemory`` are safe to call from multiple threads as long as
    the handle stays valid. TrainerForge only closes it from the UI thread.
    """

    def __init__(self, pid: int, name: str | None = None, *, debug_privilege: bool = True):
        self.pid = int(pid)
        self.handle = winapi.open_process(
            self.pid,
            winapi.PROCESS_QUERY_INFORMATION
            | winapi.PROCESS_VM_OPERATION
            | winapi.PROCESS_VM_READ
            | winapi.PROCESS_VM_WRITE,
        )
        if not self.handle:
            code = winapi.last_error()
            if code == winapi.ERROR_ACCESS_DENIED:
                if debug_privilege:
                    winapi.enable_debug_privilege()
                raise ProcessAccessError(
                    f"Access denied while opening PID {self.pid}. "
                    "Try running TrainerForge as administrator, or choose a "
                    "process that is not elevated/protected."
                )
            raise ProcessNotFoundError(
                f"Could not open PID {self.pid}: {winapi.error_text(code)}"
            )
        self.pointer_size, self.arch = winapi.query_architecture(self.handle)
        self.name = name or os.path.basename(winapi.process_image_path(self.pid)) or f"pid-{self.pid}"
        self._modules: list[ModuleInfo] = []
        self._modules_at = 0.0
        self._closed = False

    # -- lifetime ---------------------------------------------------------
    @property
    def closed(self) -> bool:
        return self._closed or not self.handle

    @property
    def alive(self) -> bool:
        return not self.closed and winapi.is_process_alive(self.handle)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.handle:
            winapi.close_handle(self.handle)
            self.handle = 0

    def __enter__(self) -> "Process":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self):  # pragma: no cover - best effort
        try:
            self.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"Process(pid={self.pid}, name={self.name!r}, arch={self.arch!r})"

    # -- memory -----------------------------------------------------------
    @property
    def address_limit(self) -> int:
        if ctypes.sizeof(ctypes.c_void_p) == 4:
            return 0xFFFFFFFF
        return 0x7FFFFFFEFFFF

    def read(self, address: int, size: int) -> bytes:
        if self.closed:
            raise ProcessNotFoundError("The target process is no longer open.")
        if size <= 0:
            return b""
        if address < 0:
            raise MemoryReadError(f"Invalid address {address:#x}.")
        buffer = (ctypes.c_ubyte * int(size))()
        read = ctypes.c_size_t(0)
        ok = winapi.kernel32.ReadProcessMemory(
            self.handle,
            ctypes.c_void_p(int(address)),
            buffer,
            ctypes.c_size_t(int(size)),
            ctypes.byref(read),
        )
        if not ok:
            code = winapi.last_error()
            raise MemoryReadError(
                f"ReadProcessMemory failed at {address:#x} ({size} bytes): {winapi.error_text(code)}"
            )
        if read.value != size:
            raise MemoryReadError(
                f"Short read at {address:#x}: wanted {size} bytes, got {read.value}."
            )
        return bytes(buffer)

    def write(self, address: int, data: bytes) -> None:
        if self.closed:
            raise ProcessNotFoundError("The target process is no longer open.")
        payload = bytes(data)
        if not payload:
            return
        if address < 0:
            raise MemoryWriteError(f"Invalid address {address:#x}.")
        buffer = ctypes.create_string_buffer(payload, len(payload))
        written = ctypes.c_size_t(0)
        ok = winapi.kernel32.WriteProcessMemory(
            self.handle,
            ctypes.c_void_p(int(address)),
            buffer,
            ctypes.c_size_t(len(payload)),
            ctypes.byref(written),
        )
        if not ok:
            code = winapi.last_error()
            raise MemoryWriteError(
                f"WriteProcessMemory failed at {address:#x}: {winapi.error_text(code)}"
            )
        if written.value != len(payload):
            raise MemoryWriteError(
                f"Short write at {address:#x}: wanted {len(payload)} bytes, wrote {written.value}."
            )

    def read_pointer(self, address: int) -> int:
        return int.from_bytes(self.read(address, self.pointer_size), "little")

    def regions(self, *, writable_only: bool = False, readable_only: bool = True) -> Iterator[Region]:
        """Yield committed virtual-memory regions.

        VirtualQueryEx can report one region per page. To keep the scan fast,
        adjacent regions with the same protection properties are merged.
        """
        address = 0
        last: Region | None = None
        iterations = 0
        while address < self.address_limit:
            iterations += 1
            if iterations > 2_000_000:  # defensive guard against a broken driver
                break
            mbi = winapi.MEMORY_BASIC_INFORMATION()
            result = winapi.kernel32.VirtualQueryEx(
                self.handle,
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi),
            )
            if not result or not mbi.RegionSize:
                break
            base = int(mbi.BaseAddress or 0)
            size = int(mbi.RegionSize)
            region = Region(
                base=base,
                size=size,
                protect=int(mbi.Protect),
                state=int(mbi.State),
                type=int(mbi.Type),
            )
            if region.state == winapi.MEM_COMMIT:
                if (not readable_only or region.is_readable) and (
                    not writable_only or region.is_writable
                ):
                    if (
                        last is not None
                        and last.end == region.base
                        and last.protect == region.protect
                        and last.type == region.type
                    ):
                        last = Region(
                            base=last.base,
                            size=last.size + region.size,
                            protect=last.protect,
                            state=last.state,
                            type=last.type,
                        )
                    else:
                        if last is not None:
                            yield last
                        last = region
            else:
                if last is not None:
                    yield last
                    last = None
            next_address = base + size
            if next_address <= address:
                break
            address = next_address
        if last is not None:
            yield last

    # -- modules ----------------------------------------------------------
    def modules(self, *, max_age: float = 2.0, force: bool = False) -> list[ModuleInfo]:
        now = time.monotonic()
        if not force and self._modules and (now - self._modules_at) < max_age:
            return list(self._modules)
        if self.closed:
            raise ProcessNotFoundError("The target process is no longer open.")
        try:
            raw = winapi.enum_modules(self.handle)
        except OSError as exc:
            raise ProcessError(str(exc)) from exc
        self._modules = [
            ModuleInfo(name=name, path=path, base=base, size=size)
            for base, size, name, path in raw
        ]
        self._modules_at = now
        return list(self._modules)

    def module_by_name(self, name: str) -> ModuleInfo:
        wanted = (name or "").strip().strip('"').lower()
        if not wanted:
            raise ProcessError("Module name is empty.")
        wanted_base = os.path.basename(wanted)
        modules = self.modules()
        for module in modules:
            if module.name.lower() == wanted or module.path.lower() == wanted:
                return module
        for module in modules:
            if os.path.basename(module.path).lower() == wanted_base:
                return module
        raise ProcessError(f"Module {name!r} is not loaded in {self.name}.")
