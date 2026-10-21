from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from trainerforge.core.pointers import resolve_chain
from trainerforge.core.process import Process
from trainerforge.core.scanner import (
    ScanMode,
    ValueType,
    decode_value,
    encode_value,
    first_scan,
    next_scan,
)
from trainerforge.core.utils import format_hex

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "tools" / "demo_target.py"


@pytest.fixture()
def demo_target():
    process = subprocess.Popen(
        [sys.executable, str(DEMO)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        assert process.stdout is not None
        line = process.stdout.readline()
        if not line:
            error = process.stderr.read() if process.stderr else ""
            raise AssertionError(f"demo target did not start: {error}")
        data = json.loads(line)
        time.sleep(0.1)
        yield data, process
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _mapping_region(process: Process, base: int, size: int):
    for region in process.regions(writable_only=True):
        if region.base <= base and region.end >= base + size:
            return region
    raise AssertionError(f"no writable region contains {base:#x}..{base + size:#x}")


def test_scan_write_and_filter(demo_target):
    data, _child = demo_target
    process = Process(data["pid"], name="python.exe")
    try:
        region = _mapping_region(process, data["base"], 0x4000)
        int_address = data["int_address"]
        int_value = data["int_value"]

        session = first_scan(
            process,
            ValueType.INT32,
            int_value,
            alignment=4,
            regions=[region],
            max_results=64,
        )
        addresses = {result.address for result in session.results}
        assert int_address in addresses, f"sentinel not found; got {addresses}"
        result = next(result for result in session.results if result.address == int_address)
        assert result.value == int_value

        # Changed and exact next scans operate on the same address.
        process.write(int_address, encode_value(int_value + 1, ValueType.INT32))
        changed = next_scan(session, ScanMode.CHANGED)
        assert int_address in {result.address for result in changed.results}
        exact = next_scan(session, ScanMode.EXACT, int_value + 1)
        assert int_address in {result.address for result in exact.results}
        unchanged = next_scan(session, ScanMode.UNCHANGED)
        assert int_address not in {result.address for result in unchanged.results}

        # A second exact scan sees the new value directly.
        updated = first_scan(
            process,
            ValueType.INT32,
            int_value + 1,
            alignment=4,
            regions=[region],
            max_results=64,
        )
        assert int_address in {result.address for result in updated.results}
        assert decode_value(process.read(int_address, 4), ValueType.INT32) == int_value + 1
    finally:
        process.close()


def test_float_scan_and_pointer_chain(demo_target):
    data, _child = demo_target
    process = Process(data["pid"], name="python.exe")
    try:
        region = _mapping_region(process, data["base"], 0x4000)
        session = first_scan(
            process,
            ValueType.FLOAT,
            data["float_value"],
            alignment=4,
            regions=[region],
            max_results=64,
        )
        addresses = {result.address for result in session.results}
        assert data["float_address"] in addresses

        resolved = resolve_chain(
            process,
            format_hex(data["pointer_cell"]),
            [0x10],
        )
        assert resolved == data["pointer_target_address"]
        value = decode_value(process.read(resolved, 4), ValueType.INT32)
        assert value == data["pointer_target_value"]
        assert process.pointer_size == 8
    finally:
        process.close()
