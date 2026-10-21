"""Application entry point."""

from __future__ import annotations

import argparse
import ctypes
import logging
import logging.handlers
import os
import sys
import tkinter as tk
from pathlib import Path

from . import __version__
from .core.config import AppConfig, log_dir
from .ui.dialogs import DisclaimerDialog
from .ui.main_window import MainWindow
from .ui.theme import apply_theme

logger = logging.getLogger("trainerforge")


def _enable_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _resource_path(relative: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent.parent / relative


def _setup_logging() -> None:
    try:
        directory = log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        log_file = directory / "trainerforge.log"
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if sys.stderr is not None:
            console = logging.StreamHandler()
            console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
            logger.addHandler(console)
    except Exception:
        # A GUI app must still start if its log directory is not writable.
        pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trainerforge",
        description="Open-source memory trainer toolkit for single-player Windows games.",
    )
    parser.add_argument("--table", metavar="PATH", help="Open a .tforge.json table at startup.")
    parser.add_argument("--process", metavar="NAME", help="Try to attach to a process by image name.")
    parser.add_argument(
        "--skip-disclaimer",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--version", action="version", version=f"TrainerForge {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("TrainerForge is a Windows application.")

    _setup_logging()
    _enable_dpi_awareness()
    logger.info("Starting TrainerForge %s", __version__)
    config = AppConfig.load()

    root = tk.Tk()
    root.withdraw()
    root.title("TrainerForge")
    root.minsize(1100, 720)
    apply_theme(root)
    icon_png = _resource_path("trainerforge/assets/icon.png")
    if icon_png.exists():
        try:
            photo = tk.PhotoImage(file=str(icon_png))
            root.iconphoto(True, photo)
            root._trainerforge_icon = photo  # keep a reference alive
        except tk.TclError:
            pass
    icon = _resource_path("trainerforge/assets/icon.ico")
    if icon.exists():
        try:
            root.iconbitmap(default=str(icon))
        except tk.TclError:
            pass
    if config.window_geometry:
        try:
            root.geometry(config.window_geometry)
        except tk.TclError:
            root.geometry("1280x820")

    skip_disclaimer = args.skip_disclaimer or args.smoke_test
    if not skip_disclaimer and not config.disclaimer_accepted:
        dialog = DisclaimerDialog(root)
        root.wait_window(dialog)
        if not dialog.accepted:
            logger.info("Disclaimer was declined; exiting.")
            try:
                root.destroy()
            except tk.TclError:
                pass
            return 1
        config.disclaimer_accepted = True
        config.save()

    if args.smoke_test:
        print("TrainerForge smoke test: starting UI")
    root.deiconify()
    window = MainWindow(root, config, args)
    try:
        root.mainloop()
    finally:
        logger.info("TrainerForge exited.")
    if args.smoke_test:
        print("TrainerForge smoke test: UI created and destroyed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
