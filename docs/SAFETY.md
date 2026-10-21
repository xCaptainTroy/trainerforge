# Safety and acceptable use

TrainerForge is a memory editor. Memory editors are powerful and can damage
software or saves when used carelessly. Read this before using it with a game.

## Intended use

- Single-player or offline games you own.
- Local experimentation and learning about process memory.
- Building your own tables, including for games with no commercial trainer.
- Sharing human-readable tables with other single-player users.

## Not supported

- Multiplayer games, competitive modes, or any process protected by anti-cheat.
- Circumventing a subscription, license check, or account system.
- Anti-cheat evasion, process hiding, driver loading, or code injection.
- Distributing copied commercial trainer content or proprietary binaries.
- Windows-critical processes, services, or other users’ processes.

TrainerForge refuses known critical process names and known anti-cheat module
markers. This is a best-effort guardrail, not a guarantee. If you are unsure
whether a game permits memory editing, do not use TrainerForge with it.

## Practical precautions

1. **Back up saves.** Editing the wrong address can corrupt a save or crash the
   game.
2. **Start in an offline/single-player save.** Do not test on a competitive
   account.
3. **Use one change at a time.** If the game crashes, you can identify the entry
   that caused it.
4. **Prefer pointer chains over absolute addresses.** Addresses move between
   launches; a bad pointer chain will fail safely with a null/read error rather
   than writing somewhere arbitrary in most cases.
5. **Avoid writing to code or read-only regions.** The scanner defaults to
   writable memory, but a manually entered address can point anywhere.
6. **Run as administrator only when necessary.** Elevated games may require it;
   most single-player games do not. TrainerForge never installs a service or
   driver.
7. **Do not share personal data.** Tables can contain process names and notes;
   review them before publishing.

## Anti-cheat

TrainerForge does not attach to processes with obvious anti-cheat modules. It
does not attempt to hide itself, defeat integrity checks, or operate in
multiplayer. Do not ask for or contribute such features.

If a game uses anti-cheat but has an explicit offline mode, use the game’s
single-player/offline mode and follow its rules. If the game does not allow
memory editing, do not use TrainerForge.

## Legal and terms-of-service note

Memory editing is regulated differently around the world, and game terms vary.
TrainerForge is not legal advice. You are responsible for complying with the
terms of the games you use, local law, and any applicable agreements. The
authors provide the software under the MIT license, without warranty.

## Reporting a safety issue

If you find a path that bypasses the anti-cheat/critical-process guardrail, do
not publish an exploit. Open a private security report or contact the maintainer
with a minimal reproduction. The project’s goal is to keep the boundary simple
and visible, not to win an arms race.
