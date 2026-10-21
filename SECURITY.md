# Security policy

TrainerForge is a local, single-player memory editor. It is not a sandbox, an
anti-cheat product, or a security boundary. The project still takes reports about
its own code seriously.

## Supported versions

The current `main` branch and the latest tagged release receive fixes.

## What to report privately

Please do not open a public issue for:

- A bug that lets a table file execute code, write outside the selected process,
  or escape path/extension handling.
- A guardrail bypass that attaches to a known anti-cheat process without an
  explicit warning.
- A privilege-escalation or arbitrary-file-write issue in the application.
- A supply-chain issue in the build/release process.

You can use GitHub’s **Report a vulnerability** feature on the repository, or
contact the maintainer through the profile at
<https://github.com/xCaptainTroy>. Include:

1. TrainerForge version and Windows version.
2. A minimal reproduction, ideally a table file or exact steps.
3. The observed behavior and the behavior you expected.
4. Whether the issue requires administrator rights or a malicious local file.

Please allow reasonable time for a fix before public disclosure.

## What is not a vulnerability

- The app can read/write memory in the process you attach to. That is the
  intended feature.
- The anti-cheat/critical-process blocklist is best-effort and not a complete
  security control.
- An unsigned PyInstaller build triggers SmartScreen. This is expected; verify
  the published SHA-256 or build from source.
- A table can contain arbitrary numeric addresses, including addresses that
  crash the target game. Tables are user-authored data, and the app warns about
  this.
- The app does not support multiplayer or anti-cheat-protected games. Requests
  to add such support are not security reports.

## Runtime network behavior

The shipped application has no network code. The only external link is the
optional “Project on GitHub” menu item, which opens the default browser. There is
no telemetry, update check, account, or cloud sync.
