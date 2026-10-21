# Development

## Requirements

- Windows 10/11 (x64 is the tested target).
- Python 3.10+ with Tkinter. Python 3.15.0 was used for the initial release.
- No runtime third-party packages.
- Development extras: `pytest`, `pyinstaller`, `pillow` (only for regenerating
  the icon).

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Project layout

| Path | Purpose |
|---|---|
| `trainerforge/core/winapi.py` | `ctypes` declarations and Win32 constants. |
| `trainerforge/core/process.py` | process/module enumeration, `ReadProcessMemory`, `VirtualQueryEx`. |
| `trainerforge/core/scanner.py` | first scan, next scan, value encoding. |
| `trainerforge/core/pointers.py` | base expressions and multi-level pointer chains. |
| `trainerforge/core/table.py` | schema, validation, atomic JSON save/load. |
| `trainerforge/core/freezer.py` | background writer. |
| `trainerforge/core/hotkeys.py` | global hotkey registration and polling. |
| `trainerforge/core/safety.py` | critical-process and anti-cheat guardrail. |
| `trainerforge/ui/main_window.py` | scanner/table window and orchestration. |
| `trainerforge/ui/dialogs.py` | safety notice and entry editor. |
| `trainerforge/ui/theme.py` | dark ttk theme. |
| `tools/demo_target.py` | harmless process with sentinel values. |
| `tools/ui_smoke_test.py` | drives the window against the demo target. |
| `tools/hotkey_smoke_test.py` | sends a real global chord through the hidden window. |
| `tests/` | unit and integration tests. |

## Tests

```powershell
python -m pytest -q
```

The integration tests launch `tools/demo_target.py`, find its pagefile-backed
mapping, scan for the sentinels, write a value, run next scans, and resolve a
pointer chain. The demo process is terminated in a fixture finalizer.

The UI smoke test is intentionally separate from pytest because it creates a Tk
window:

```powershell
python tools\ui_smoke_test.py
```

It checks attach, first scan, adding a frozen entry, the freezer writer, and
detach. It writes the normal settings log/config under `%APPDATA%\TrainerForge`;
that is harmless but can be removed.

Global hotkeys use a hidden Win32 message window and a worker thread; verify the
full path (including a synthetic key chord) with:

```powershell
python tools\hotkey_smoke_test.py
```

This test needs an interactive desktop session. It registers
`Ctrl+Alt+Shift+F24` and releases it before exiting.

## Manual smoke test

1. `python tools\demo_target.py` in one terminal; note the printed JSON.
2. In another terminal: `python -m trainerforge --skip-disclaimer`.
3. Attach to the demo target’s `python.exe` PID.
4. Scan the printed `int_value` as `Int32`, alignment 4, writable-only.
5. Add the result, set a different value, freeze, and check the target value.
6. Save the table as `.tforge.json`, close, reopen it, and reattach.

## Design decisions

- **No external runtime dependencies.** `ctypes` is enough for the Win32 calls,
  and standard Tkinter keeps the executable small and auditable.
- **Exact-value scanning first.** Cheat Engine-style unknown-value scanning is
  much more memory- and performance-intensive. The next-scan modes cover the
  common “value changed” workflow without keeping a full memory dump.
- **Tables over built-in cheats.** A table is reviewable, versionable, and
  carries no executable payload. TrainerForge does not need a per-game server.
- **Pointer chains are resolved, not discovered.** Automatic pointer scanning is
  a substantial feature with false-positive and performance trade-offs; it is
  deferred rather than half-implemented.
- **Safety is a product boundary.** The anti-cheat blocklist is intentionally
  conservative and documented. It is not a sandbox.
- **UI work stays on the Tk thread.** Scan and freezer workers communicate only
  through queues; this avoids the classic Tkinter cross-thread crash.

## Packaging

```powershell
.\build.ps1
```

The script runs tests, calls PyInstaller in one-file windowed mode, adds the
icon and assets, and writes a SHA-256 sidecar file:

```text
dist\TrainerForge.exe
dist\TrainerForge.exe.sha256
```

PyInstaller one-file builds unpack to a temporary directory at launch, so the
first start can be slower than subsequent starts. The executable is unsigned;
use a code-signing certificate if you distribute it widely.

## Regenerating the icon

```powershell
python tools\generate_icon.py
```

The script needs Pillow and writes `trainerforge/assets/icon.ico`,
`trainerforge/assets/icon.png`, and `docs/icon.png`.

## Continuous integration

A ready-to-use GitHub Actions workflow is kept at `docs/ci-example.yml` so the
project can be cloned and pushed by maintainers whose GitHub CLI token does not
have the `workflow` OAuth scope. To enable it in a fork or in the upstream repo:

```powershell
New-Item -ItemType Directory -Force .github\workflows | Out-Null
Copy-Item docs\ci-example.yml .github\workflows\ci.yml
git add .github\workflows\ci.yml
git commit -m "Enable GitHub Actions CI"
git push
```

If GitHub rejects that push, refresh the CLI token with:
`gh auth refresh -h github.com -s workflow`.

## Common issues

| Symptom | Cause / fix |
|---|---|
| `Access denied while opening PID` | Target is elevated or protected. Run TrainerForge as administrator only if appropriate; do not use it around anti-cheat. |
| Scan finds no matches | Wrong type, value, alignment, or the value is not in writable memory. Try alignment 1 and `Writable memory only` off. |
| Next scan finds zero | The value changed again, the address moved, or the wrong mode was used. Reset and scan again. |
| Pointer resolves to null | The game has not initialized the structure, or the chain/offset is wrong. |
| Hotkey rejected | Windows reserved it or another app owns it. Choose another combination. |
| `Module ... is not loaded` | The base module name is wrong, or you are attached to a different process. |
| Portable exe is flagged | Unsigned PyInstaller binaries often trigger SmartScreen. Publish a checksum, or sign the binary. |

## Code style

- Type hints on public functions and dataclasses.
- Core code must remain importable without creating a Tk root.
- Never touch Tk widgets from a worker thread; use `queue.Queue` and `after()`.
- Do not add network calls, telemetry, or automatic downloads to the runtime.
- Add a test for every scanner, pointer, table, or safety change.
