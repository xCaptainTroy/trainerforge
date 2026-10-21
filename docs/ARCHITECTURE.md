# Architecture

TrainerForge is intentionally small enough to read in one sitting. It has no
third-party runtime dependencies beyond the Python standard library and Tkinter.

## Layers

```text
trainerforge/
├── app.py                 argument parsing, DPI/logging, first-run dialog
├── core/
│   ├── winapi.py          ctypes declarations for the Win32 calls we use
│   ├── process.py         Process, module discovery, VirtualQueryEx regions
│   ├── scanner.py         exact scan + next-scan comparison engine
│   ├── pointers.py        base expressions and multi-level pointer chains
│   ├── table.py           Table/TableEntry model and atomic JSON persistence
│   ├── freezer.py         background writer for frozen entries
│   ├── hotkeys.py         hidden Win32 message window + Tk-side dispatch
│   ├── safety.py          critical-process and anti-cheat blocklist
│   ├── config.py          local settings in %APPDATA%\TrainerForge
│   └── utils.py           integer parsing and formatting helpers
└── ui/
    ├── theme.py           dark ttk theme
    ├── dialogs.py         safety notice and entry editor
    └── main_window.py     scanner/table UI and orchestration
```

The UI depends on the core; the core never imports Tkinter except for the
hotkey manager’s small UI-side event poller.

## Process and memory access

`Process` opens a target with:

```text
PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION
| PROCESS_VM_READ | PROCESS_VM_WRITE
```

It determines the target’s pointer size with `IsWow64Process2` when available
and falls back to `IsWow64Process`. Reads use `ReadProcessMemory` with exact-size
buffers. Short reads are treated as errors rather than silently truncated.

`Process.regions()` walks `VirtualQueryEx` from address zero and merges adjacent
committed regions with identical protection. It skips guard pages and
non-readable pages. The default scanner filter is writable-only, which avoids
most image/read-only noise.

No driver, service, DLL injection, remote thread, or API hook is used.

## Scanner

### First scan

1. Encode the target value in little-endian form for the selected type.
2. Enumerate committed readable regions (writable-only by default).
3. Read each region in 4 MiB chunks, with `pattern_size - 1` bytes of overlap
   so patterns crossing a chunk boundary are found exactly once.
4. Use `bytes.find` for the actual search; results are filtered by the requested
   address alignment.
5. Store `(address, previous_bytes, current_bytes, type)` for each match.
6. Stop at a configurable result cap (250,000 by default) and mark the session
   as truncated.

Results are stored as byte snapshots so that next scans can compare the current
bytes without re-reading the old value from the target.

### Next scan

The result set is grouped by 4 KiB page. One page read covers many adjacent
candidates; if a page cannot be read, TrainerForge falls back to individual
reads so one inaccessible page does not discard the whole scan. Each candidate
is compared according to the selected mode:

- **Exact** — current bytes equal the encoded target.
- **Changed / unchanged** — current bytes differ from / equal the previous
  snapshot.
- **Increased / decreased** — decoded numbers compare; NaN is never reported as
  increased or decreased.

The next session contains only matching candidates, with the previous snapshot
updated to the value observed at the start of that scan.

### Performance notes

The scanner is a first-pass, exact-value scanner. A large game with hundreds of
megabytes of writable memory can take seconds, especially in Python. Use a
specific value and `Writable memory only`; align to 4 bytes unless you have a
reason not to. A future release may add a native scan backend.

## Pointer chains

A base expression is one of:

- `0x7FF6A1B2C3D4`
- `game.exe+0x1A2B0`
- `game.exe` (offset 0)
- `0x1000+0x20` (convenience arithmetic)

For a pointer entry, TrainerForge starts at the base, reads one pointer-width
value, adds the first offset, reads the next pointer, and so on. The final result
is the address that will be read or written; it is not dereferenced again.

Module lookup is case-insensitive and accepts either the base name or the full
path. A null pointer or an address outside the target’s user-space limit raises
a descriptive error rather than crashing the app.

## Freezing

`Freezer` runs one daemon thread. Every 50 ms it takes a snapshot of the table
under a lock and writes each frozen entry’s configured value. Writes are
best-effort; an error is reported once per changed error message through a
thread-safe queue to the UI.

Freezing is not a kernel-level protection. A game that rewrites its own value
after the write will win until the next freezer tick. That is normal for
user-mode trainers.

## Hotkeys

Global hotkeys are registered against a hidden message-only Win32 window owned
by a dedicated daemon thread. The Tk thread marshals registration and
unregistration requests to that thread; `WM_HOTKEY` messages arrive in the
window’s message loop, which enqueues the matching entry token. A Tk `after()`
poller drains that queue and runs the freeze toggle on the UI thread.

This avoids a race with Tk’s own message pump and keeps every Tk call on the main
thread. `MOD_NOREPEAT` prevents key-repeat storms. Conflicts and reserved
combinations are reported in the activity log; the entry remains in the table.

## Threading model

| Thread | Responsibility |
|---|---|
| Tk main thread | all widget access, process attach/detach, hotkey callback dispatch, table/freezer state |
| scan worker | one first/next scan at a time; never touches Tk widgets |
| freezer worker | periodic writes; never touches Tk widgets |
| hotkey window thread | hidden window, `RegisterHotKey`, `WM_HOTKEY` message loop; never touches Tk widgets |
| UI queue | freezer errors and hotkey events are marshalled back to the main thread |

Scan results and errors are sent through a `queue.Queue`; the main thread polls
it with `after()`. The target process handle is kept open until detach or exit.
The UI blocks attach/detach while a scan is running, and closing requires
cancelling a running scan.

## Persistence and configuration

- Tables: `.tforge.json`, schema `trainerforge.table/1`, UTF-8, written through
  a temporary file and `os.replace`.
- Settings: `%APPDATA%\TrainerForge\config.json` (disclaimer acknowledgement,
  window geometry, last table).
- Logs: `%APPDATA%\TrainerForge\logs\trainerforge.log` with rotation.

No configuration contains credentials, tokens, or telemetry.

## Safety boundary

`safety.py` refuses Windows-critical process names and known anti-cheat
markers. This is a product boundary and a best-effort guardrail, not a security
control. There is no code path that attempts to evade or disable protection.
