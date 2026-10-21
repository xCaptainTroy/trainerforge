# Contributing to TrainerForge

Thanks for considering a contribution. TrainerForge is a small, safety-scoped
memory trainer for single-player Windows games. The best contributions are
focused, testable, and preserve that scope.

## Good first contributions

- Scanner performance and correctness improvements.
- More value types or pointer-expression ergonomics.
- Table format validation and migration tooling.
- Documentation, examples, and reproducible bug reports.
- Tests against the included demo target.
- Accessibility and UI polish.

## Out of scope

These will be closed without merge:

- Anti-cheat evasion, process hiding, driver loading, or multiplayer support.
- Copied trainer scripts, tables, images, or binaries from WeMod or another
  commercial product.
- Bundled game-specific cheats.
- Network features that upload tables, process names, or memory data.
- Code that bypasses a subscription, license check, or account system.

## Development workflow

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tools\ui_smoke_test.py
```

For a UI change, include a screenshot or a short description of the before/after.
For a scanner or pointer change, add a test that uses `tools/demo_target.py`.
For a table-format change, update `docs/TABLE-FORMAT.md` and include a migration
path for existing `trainerforge.table/1` files.

## Code style

- Python 3.10+, standard library only at runtime.
- Type hints on public functions and dataclasses.
- Keep Tk widget access on the main thread. Workers use `queue.Queue`.
- Never add a network call to the runtime without an explicit design discussion.
- Prefer clear error messages over silent failure.
- Keep the app usable without administrator rights; elevated games are a
  documented limitation.

## Security reports

Do not open a public issue for a guardrail bypass or a code-execution problem.
See [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contribution is licensed under the MIT
License in [LICENSE](LICENSE).
