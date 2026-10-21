# How WeMod/Wand is put together — a clean-room research note

This note records the architecture-level findings that informed TrainerForge. It
is **not** a guide to copying WeMod, bypassing its subscription, or reusing its
trainer content. No WeMod code, Lua scripts, trainer packages, images, or
binaries are included in this repository.

## Scope and method

- Target: a locally installed **WeMod/Wand 12.65.1** on Windows 11.
- Shell location: `%LOCALAPPDATA%\Wand\app-12.65.1`.
- Main archive: `resources/app.asar` (~54.6 MB), SHA-256
  `75003f7000e4e6e4c5c0ce2ae30a11b4dcebb8d5232f08ee871c560cd83e99cf`.
- The archive was analyzed statically with REA’s JavaScript application
  analyzer. The complete analysis is recorded as Evidence
  `ev_cee8e65e1a862a08ef4d33861e85363e0baf293c17bb800f76e7382166496de6`
  (summary: `ev_09f4553b67d05acc18384c8b1e0dd88ba40ba5e2d08b406ace7ed65547ba16e5`).
- File names and component inventory were observed directly from the installed
  application directory.
- The app was **not** executed for this study, no trainer was launched, no
  network request was made, and no downloaded trainer content was extracted or
  redistributed.

## What REA observed

The analyzer treated the ASAR as a JavaScript application, not as a running
program. It reported:

| Measurement | Result |
|---|---:|
| Relevant files | 570 |
| Parsed JavaScript files | 538 |
| Skipped JavaScript files | 1 |
| AST nodes visited | 2,302,590 |
| Modules/references | 4,473 |
| Browser windows declared | 5 |
| Explicit web preferences | 16 |
| Context-bridge APIs | 4 |
| Exposed API members | 4 |
| IPC operations | 21 |
| Literal IPC channels | 17 |
| Dynamic channel operations | 2 |

Static strings in the main bundle reference `https://api.wemod.com`, and the
performance-telemetry code names two external processes: `auxService` and
`trainerHost`. The Electron shell also contains code for an overlay, game
capture, screenshots, automatic updates, account/auth state, ads/rewarded-ad
views, analytics, and hardware/performance sampling.

## Observed component layout

The installed app is an Electron shell plus native components unpacked beside
the ASAR:

```text
%LOCALAPPDATA%\Wand\
├── Update.exe                  Squirrel updater
├── WeMod.exe                   small launcher
├── app-12.65.1\
│   ├── Wand.exe                Electron main executable (~223 MB)
│   └── resources\
│       ├── app.asar            bundled web UI + Electron main code (~54.6 MB)
│       └── app.asar.unpacked\
│           └── static\unpacked\
│               ├── trainerlib\
│               │   ├── TrainerHost_x64.exe / x86
│               │   ├── CELib_x64.dll / x86
│               │   ├── LuaExecutorPlugin_x64.dll / x86
│               │   ├── TrainerLibPlugin_x64.dll / x86
│               │   ├── ContractRuntimePlugin_x64.dll / x86
│               │   ├── InputCapturePlugin_x64.dll / x86
│               │   └── tophat_service_x64.dll / x86
│               ├── overlay\       overlay add-on and overlay_game DLLs
│               ├── capture\       capture add-on
│               ├── auxiliary\     WandAuxiliary.exe and .NET support DLLs
│               └── preload\       ad/analytics preload scripts
└── packages\                     Squirrel package/update cache
```

The names are evidence about the shipped architecture, not proof of the
internal implementation of each component. In particular, the presence of a
`LuaExecutorPlugin` and a `TrainerHost` strongly indicates that trainer
definitions are executed by a native host that hosts Lua, while `CELib` naming
indicates a Cheat Engine-style memory library. We did not inspect or reuse the
internals of those proprietary binaries.

## High-level architecture (inferred)

```text
┌─────────────────────────────────────────────────────────────┐
│ Electron renderer: bundled web UI (game library, trainer UI)│
└───────────────────────┬─────────────────────────────────────┘
                        │  IPC / context bridge
┌───────────────────────▼─────────────────────────────────────┐
│ Electron main process: windows, auth, updates, overlay,     │
│ capture, analytics, process supervision, cloud API client   │
└───────┬───────────────────┬───────────────────┬─────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
  TrainerHost         WandAuxiliary       overlay/capture
  + LuaExecutor       (auxiliary tasks)   native add-ons
  + CELib
        ▲
        │ trainer definitions / packages
   WeMod cloud catalog (api.wemod.com)
```

The clear architectural split is:

1. **A web UI in Electron** handles discovery, account/subscription surfaces,
   game pages, and the trainer control panel.
2. **A native trainer host** loads trainer definitions and performs memory
   reads/writes and hotkey/input work. The shipped `LuaExecutorPlugin` suggests
   Lua is the trainer scripting layer.
3. **Native sidekicks** provide overlay rendering, capture, game launching and
   hardware/auxiliary information.
4. **A cloud service** supplies the game catalog and trainer content; it is not
   bundled in the client.

This is a sensible architecture for a commercial catalog product: the client is
an updateable UI, while game-specific behavior lives in remotely delivered
trainer packages and a small native runtime. It is also a large attack surface
and a large trust surface, which is why TrainerForge takes a different route.

## What TrainerForge does instead

TrainerForge keeps the useful functional core and removes the commercial and
network layers:

| WeMod/Wand concept | TrainerForge equivalent |
|---|---|
| Cloud game catalog | Local `.tforge.json` tables you author |
| Remote trainer definitions | Human-readable table entries |
| Lua trainer runtime | Small Python scan/pointer/freeze engine |
| CELib-style native memory access | `ctypes` + documented Win32 APIs |
| Overlay | Not implemented in v0.1 |
| Account, subscription, ads | None |
| Capture/analytics/telemetry | None |
| Native hotkey/overlay DLLs | `RegisterHotKey` on a hidden Win32 message window |
| Prebuilt cheats | None; no game-specific content shipped |

The result is not feature parity with a commercial catalog. It is a transparent
tool for building and sharing the part that matters: a table that describes
where a value lives, how to resolve it after a restart, and what to do with it.

## Deliberate boundaries

TrainerForge will not add:

- anti-cheat bypass, process hiding, driver loading, or multiplayer support;
- copied trainer scripts, tables, or binary payloads from WeMod or elsewhere;
- a service that redistributes another product’s catalog;
- code that circumvents a subscription, license check, or account system.

The blocker is not only legal caution. A memory editor that targets anti-cheat
or multiplayer processes is a different product with a different threat model.
TrainerForge is explicitly a single-player/offline tool.

## Reproducing the public observations

If you want to verify the shell layout yourself, inspect the installed
`resources/app.asar` and `app.asar.unpacked/static/unpacked` directory with a
normal archive/file browser. Do not run downloaded trainers or send your account
token to an untrusted endpoint. This note does not require or recommend
extracting proprietary payloads.

For a general-purpose open-source memory editor with a much larger feature set,
see the well-established Cheat Engine project. TrainerForge does not reuse its
code or assets either; it exists to provide a small, auditable, table-first
alternative with explicit safety boundaries.
