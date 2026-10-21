# Changelog

All notable changes to TrainerForge are documented here. The project follows
[Semantic Versioning](https://semver.org/) once it reaches a stable API.

## [0.1.0] — 2026-10-21

First public alpha.

### Added

- Attach to 32-bit and 64-bit Windows processes with read/write memory access.
- First scans for `Int32`, `Int64`, `Float`, and `Double` exact values.
- Next-scan filters: exact value, changed, unchanged, increased, decreased.
- Writable-only filtering and 1/2/4/8-byte address alignment.
- Direct addresses and module-relative bases (`game.exe+0x1234`).
- Multi-level pointer-chain resolution with module-relative bases.
- Frozen values backed by a background writer.
- Global freeze-toggle hotkeys using `RegisterHotKey`.
- Live value column and manual value writes.
- JSON `.tforge.json` tables with validation and atomic saves.
- Single-player safety notice, critical-process blocklist, and anti-cheat
  name checks.
- Dark Tkinter UI, process selector, entry editor, activity log, and clear
  status reporting.
- Demo target, pytest suite, Tk UI smoke test, global-hotkey smoke test,
  PyInstaller build script, and a GitHub Actions workflow template.
- English and Arabic READMEs plus architecture, safety, table-format, and
  WeMod/Wand research notes.

### Known limitations

- No automatic pointer-chain or signature scanner.
- No game catalog, prebuilt trainers, overlay, scripting, or remote services.
- Exact-value scans only; unknown-value scans are not implemented.
- Some elevated or protected games cannot be opened without matching privileges.
- The executable is unsigned; verify the published SHA-256.

### Safety boundaries

Not supported and not planned: multiplayer, anti-cheat evasion, process hiding,
driver loading, subscription bypass, or redistribution of proprietary trainer
content.

[0.1.0]: https://github.com/xCaptainTroy/trainerforge/releases/tag/v0.1.0
