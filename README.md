# TrainerForge

<p align="center">
  <img src="docs/icon.png" alt="TrainerForge icon" width="112">
</p>

<p align="center">
  <a href="README.ar.md">العربية</a>
</p>

<p align="center">
  <strong>Open-source, local-first memory trainer toolkit for single-player Windows games.</strong>
</p>

<p align="center">
  <img alt="MIT license" src="https://img.shields.io/badge/license-MIT-3DDC97">
  <img alt="Windows 10/11" src="https://img.shields.io/badge/platform-Windows%2010%2F11-5B8CFF">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-FFD166">
  <img alt="Alpha" src="https://img.shields.io/badge/status-alpha-FF6B81">
</p>

TrainerForge is a small, independent trainer framework: attach to a single-player
game, scan for a value, narrow the results, then build a reusable table with
frozen values and global hotkeys. Tables are plain JSON and can be shared,
reviewed, and versioned like any other text file.

It is a **clean-room implementation** built on the Windows memory APIs. It ships
no game-specific cheats, no injected payloads, and no proprietary trainer
content.

> **Not affiliated with WeMod, Cheat Engine, or any game publisher.** TrainerForge
> is an independent project. See [docs/WEMOD-ANALYSIS.md](docs/WEMOD-ANALYSIS.md)
> for the research note that informed the design.

![TrainerForge main window](docs/screenshot-main.png)

## What it can do

| Feature | Status |
|---|---|
| Attach to 32-bit or 64-bit Windows processes | ✅ |
| Scan for `Int32`, `Int64`, `Float`, `Double` values | ✅ |
| Next scans: exact, changed, unchanged, increased, decreased | ✅ |
| Address alignment and writable-only filtering | ✅ |
| Direct addresses and module-relative bases | ✅ |
| Multi-level pointer chains (resolve and edit) | ✅ |
| Freeze values with a background writer | ✅ |
| Global hotkeys that toggle freeze | ✅ |
| Live value column and manual “Write value” | ✅ |
| Portable, human-readable JSON tables | ✅ |
| Accounts, ads, telemetry, cloud sync | ❌ never |
| Anti-cheat bypass or multiplayer support | ❌ never |
| Prebuilt game catalog / bundled trainers | ❌ not included |
| Overlay, capture, or remote control | 🗺️ roadmap |

TrainerForge is deliberately small. It is the **functional core** of a trainer,
not a clone of a commercial catalog. The interesting part is the table you
build and share, not a subscription service.

## Quick start

### Option A — portable executable

Download `TrainerForge.exe` from the repository’s **Releases** page and run it.
The executable is unsigned; Windows SmartScreen may ask for confirmation.
Verify the published SHA-256 if you want extra assurance.

### Option B — run from source

Requirements: Windows 10/11 and 64-bit Python 3.10 or newer.

```powershell
git clone https://github.com/xCaptainTroy/trainerforge.git
cd trainerforge
python -m trainerforge
```

There are no third-party runtime dependencies. Tkinter ships with standard
CPython on Windows.

On first launch, read and accept the single-player safety notice. Then:

1. Choose a running single-player game in **Target process** and press **Attach**.
2. Pick a value type, enter a value you can see in the game (for example, health
   `100`), and press **First scan**.
3. Return to the game, change the value, then use **Next scan** with **Changed**
   or **Exact value**. Repeat until a small number of results remain.
4. Double-click a result (or select it and press **Add selected →**) to add it to
   your table.
5. Set a value, check **Freeze**, and optionally assign a global hotkey.

The demo target is useful for a first run:

```powershell
python tools\demo_target.py
```

It prints a JSON line with a sentinel `int_value`. Attach to that `python.exe`
process, scan the printed value, and try writing a new one. This is a synthetic
target, not a game cheat.

## Building a table

A table entry can be:

- **Direct address** — `0x7FF6A1B2C3D4`. Simple, but usually changes when the
  game restarts.
- **Pointer chain** — a base such as `game.exe+0x1A2B0`, followed by offsets
  such as `0x10, 0x20`. TrainerForge reads a pointer at each level and adds the
  next offset. This is how you make a table survive restarts.

TrainerForge **resolves** pointer chains you provide; it does not yet find pointer
chains automatically. Use your game knowledge, a debugger, or another tool to
locate the chain, then record it in the table. This limitation is intentional for
the first release and is on the roadmap.

Example pointer entry:

```json
{
  "schema": "trainerforge.table/1",
  "name": "Example table",
  "process_name": "MyGame.exe",
  "entries": [
    {
      "id": "a1b2c3d4e5f6",
      "description": "Player health",
      "kind": "pointer",
      "base": "MyGame.exe+0x1A2B0",
      "offsets": ["0x10", "0x20"],
      "value_type": "float",
      "value": "100.0",
      "frozen": true,
      "hotkey": "F1",
      "notes": "Offline save only"
    }
  ]
}
```

The full schema is documented in [docs/TABLE-FORMAT.md](docs/TABLE-FORMAT.md).
Tables are validated on load and saved atomically.

## Safety and scope

TrainerForge is for **single-player or offline games you own**. It intentionally
does not support multiplayer or anti-cheat-protected processes.

- No code injection, DLL loading, driver installation, or anti-cheat evasion.
- Known anti-cheat modules and Windows-critical processes are refused.
- The blocklist is best-effort, not a security guarantee. Do not try to use the
  tool around anti-cheat.
- Memory editing can crash a game or corrupt a save. Back up saves.
- There is no warranty; you are responsible for complying with game terms and
  local law.

Read [docs/SAFETY.md](docs/SAFETY.md) before using TrainerForge with a game you
care about.

## How it works

TrainerForge is a Python/Tkinter application with a small `ctypes` Win32 layer:

```text
Tkinter UI
   │
   ├── scanner.py     exact-value scans and next-scan filters
   ├── pointers.py    module+offset and multi-level pointer resolution
   ├── table.py       JSON table model and validation
   ├── freezer.py     background writer for frozen values
   ├── hotkeys.py     hidden Win32 hotkey window + Tk-side dispatch
   └── winapi.py      OpenProcess, ReadProcessMemory, VirtualQueryEx, …
```

No remote service is involved. The only network operation in the source tree is
the optional “Project on GitHub” link in the Help menu.

The WeMod research note documents the observed Electron + native trainer host
architecture and the boundaries of the clean-room work:
[docs/WEMOD-ANALYSIS.md](docs/WEMOD-ANALYSIS.md).

## Build a portable executable

```powershell
python -m pip install -r requirements-dev.txt
.\build.ps1
```

The build script creates `dist\TrainerForge.exe`, a one-file windowed build, and
prints its SHA-256. The executable is not code-signed; SmartScreen may warn. If
you distribute a build, publish the checksum and consider signing it with a
code-signing certificate.

PyInstaller output is platform-specific. Build on Windows for Windows.

## Development

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tools\ui_smoke_test.py
python tools\hotkey_smoke_test.py
```

- `tests/test_integration.py` launches `tools/demo_target.py` and verifies scans,
  writes, next scans, and pointer resolution against real process memory.
- `tools/ui_smoke_test.py` drives the Tk window against the same target.
- `tools/hotkey_smoke_test.py` exercises the global hotkey window and message
  queue with a synthetic chord (interactive desktop required).
- Tests are marked `integration`; they run on Windows only.

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the project layout and design
notes. Release history is in [CHANGELOG.md](CHANGELOG.md).

## Roadmap

- Pointer-chain scanner and signature scanning.
- Table packs with a manifest and checksums for community sharing.
- More hotkey actions (write value, toggle multiple entries).
- Optional overlay and per-game profiles.
- Scripting with a deliberately small, sandboxed action DSL.

Out of scope: multiplayer, anti-cheat bypass, piracy tools, bundled proprietary
trainer content, and anything that depends on another product’s account or
subscription.

## Contributing

Contributions are welcome if they preserve the project’s safety boundaries. In
particular:

- Do not add game-specific cheats or copied trainer content.
- Do not add anti-cheat evasion, process-hiding, or multiplayer features.
- Keep tables human-readable and free of executable payloads.
- Add tests for scanner, pointer, table, or safety changes.

Open an issue with a clear reproduction or a pull request with a focused change.
Read [CONTRIBUTING.md](CONTRIBUTING.md) first. For vulnerabilities in TrainerForge
itself, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## License

MIT © 2026 TrainerForge contributors. See [LICENSE](LICENSE).

“WeMod”, “Wand”, “Cheat Engine”, and game names are trademarks of their
respective owners. They are mentioned only for identification and comparison.
No affiliation or endorsement is implied.
