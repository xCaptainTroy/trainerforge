"""A tiny harmless target process for TrainerForge integration tests.

It allocates one pagefile-backed mapping, writes a few sentinel values into it,
and prints their addresses as JSON. Nothing is injected or hooked; the process
simply stays alive until it is terminated.

Run manually:
    python tools/demo_target.py
Then attach TrainerForge to ``python.exe`` and scan for 324481640.
"""

from __future__ import annotations

import json
import mmap
import os
import struct
import sys
import time

SIZE = 0x4000
INT_OFFSET = 0x100
INT_VALUE = 0x13572468
INT64_OFFSET = 0x200
INT64_VALUE = 0x1122334455667788
FLOAT_OFFSET = 0x300
FLOAT_VALUE = 1234.5
DOUBLE_OFFSET = 0x400
DOUBLE_VALUE = 9876.54321
POINTER_CELL_OFFSET = 0x800
POINTER_TARGET_OFFSET = 0x1000
POINTER_TARGET_VALUE = 424242
POINTER_TARGET_OFFSET_WITH_CHAIN = 0x1010


def main() -> int:
    mapping = mmap.mmap(-1, SIZE, access=mmap.ACCESS_WRITE)
    # Keep a reference alive for the lifetime of the process.
    globals()["_mapping"] = mapping
    base = _mapping_address(mapping)
    mapping[:] = b"\x00" * SIZE
    struct.pack_into("<i", mapping, INT_OFFSET, INT_VALUE)
    struct.pack_into("<q", mapping, INT64_OFFSET, INT64_VALUE)
    struct.pack_into("<f", mapping, FLOAT_OFFSET, FLOAT_VALUE)
    struct.pack_into("<d", mapping, DOUBLE_OFFSET, DOUBLE_VALUE)
    pointer_target = base + POINTER_TARGET_OFFSET
    struct.pack_into("<Q", mapping, POINTER_CELL_OFFSET, pointer_target)
    struct.pack_into("<i", mapping, POINTER_TARGET_OFFSET_WITH_CHAIN, POINTER_TARGET_VALUE)

    payload = {
        "pid": os.getpid(),
        "base": base,
        "int_address": base + INT_OFFSET,
        "int_value": INT_VALUE,
        "int64_address": base + INT64_OFFSET,
        "int64_value": INT64_VALUE,
        "float_address": base + FLOAT_OFFSET,
        "float_value": FLOAT_VALUE,
        "double_address": base + DOUBLE_OFFSET,
        "double_value": DOUBLE_VALUE,
        "pointer_cell": base + POINTER_CELL_OFFSET,
        "pointer_target": pointer_target,
        "pointer_target_address": base + POINTER_TARGET_OFFSET_WITH_CHAIN,
        "pointer_target_value": POINTER_TARGET_VALUE,
    }
    print(json.dumps(payload), flush=True)
    try:
        while True:
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    return 0


def _mapping_address(mapping: mmap.mmap) -> int:
    """Get the virtual address of a Python mmap using the buffer protocol.

    Py_buffer.buf is the first data byte. This is stable for the lifetime of
    the mapping and avoids relying on ctypes internals.
    """
    import ctypes

    class Py_buffer(ctypes.Structure):
        _fields_ = [
            ("buf", ctypes.c_void_p),
            ("obj", ctypes.py_object),
            ("len", ctypes.c_ssize_t),
            ("itemsize", ctypes.c_ssize_t),
            ("readonly", ctypes.c_int),
            ("ndim", ctypes.c_int),
            ("format", ctypes.c_char_p),
            ("shape", ctypes.POINTER(ctypes.c_ssize_t)),
            ("strides", ctypes.POINTER(ctypes.c_ssize_t)),
            ("suboffsets", ctypes.POINTER(ctypes.c_ssize_t)),
            ("internal", ctypes.c_void_p),
        ]

    view = Py_buffer()
    # PyObject_GetBuffer with PyBUF_SIMPLE (0)
    if ctypes.pythonapi.PyObject_GetBuffer(ctypes.py_object(mapping), ctypes.byref(view), 0) != 0:
        raise RuntimeError("Could not obtain the mmap buffer address.")
    try:
        return int(view.buf)
    finally:
        ctypes.pythonapi.PyBuffer_Release(ctypes.byref(view))


if __name__ == "__main__":
    raise SystemExit(main())
