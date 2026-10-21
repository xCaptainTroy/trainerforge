# TrainerForge 0.1.0

First public alpha: a local-first, open-source memory trainer toolkit for
single-player Windows games.

## Highlights

- Attach to 32-bit and 64-bit Windows processes.
- Exact-value scans for `Int32`, `Int64`, `Float`, and `Double`.
- Next-scan filters: exact, changed, unchanged, increased, decreased.
- Writable-only filter and 1/2/4/8-byte alignment.
- Direct addresses, module-relative bases, and multi-level pointer chains.
- Freeze values with a background writer.
- Global freeze hotkeys via a dedicated Win32 message window.
- Live value column and manual writes.
- Reviewable `.tforge.json` tables with validation and atomic saves.
- No accounts, ads, telemetry, cloud sync, or prebuilt cheats.

## Download

- `TrainerForge.exe` — portable one-file Windows build (**unsigned**).
- `TrainerForge.exe.sha256` — SHA-256 checksum.

SHA-256:

```text
80da6d2ff8795c2484feb97a3cb74a6ff94753d9de060e944d70a3383ca88bc9  TrainerForge.exe
```

Windows SmartScreen may warn because the build is unsigned. Verify the checksum
or build from source. Python 3.10+ is required only for the source build; the
portable executable includes its runtime.

## Scope and safety

TrainerForge is for **single-player or offline games you own**. It does not
support multiplayer, anti-cheat evasion, process hiding, driver loading, or
subscription bypass. The anti-cheat/critical-process blocklist is best-effort,
not a security boundary. Memory editing can crash a game or corrupt a save.

Read [SAFETY.md](https://github.com/xCaptainTroy/trainerforge/blob/main/docs/SAFETY.md)
before use. The WeMod/Wand architecture research is documented in
[WEMOD-ANALYSIS.md](https://github.com/xCaptainTroy/trainerforge/blob/main/docs/WEMOD-ANALYSIS.md);
TrainerForge contains no WeMod code, assets, trainer content, or branding.

## Known limitations

- No automatic pointer-chain or signature scanner.
- No game catalog, overlay, scripting runtime, or remote service.
- Exact-value scanning only; unknown-value scans are not implemented.
- Elevated/protected games may be unreadable without matching privileges.
- The CI workflow is provided as `docs/ci-example.yml` because the publishing
  token lacked the GitHub `workflow` scope; see
  [DEVELOPMENT.md](https://github.com/xCaptainTroy/trainerforge/blob/main/docs/DEVELOPMENT.md#continuous-integration)
  to enable it.

## Verify the release

```powershell
Get-FileHash .\TrainerForge.exe -Algorithm SHA256
Get-Content .\TrainerForge.exe.sha256
```

The values must match. Source, issues, and documentation:
<https://github.com/xCaptainTroy/trainerforge>.
