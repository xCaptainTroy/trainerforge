"""Modal dialogs: first-run safety notice and table-entry editor."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Iterable

from ..core.hotkeys import HotkeyError, parse_hotkey
from ..core.pointers import describe_chain, parse_base_expression, resolve_base_chain
from ..core.process import Process
from ..core.scanner import (
    LABEL_TO_VALUE_TYPE,
    VALUE_TYPE_LABELS,
    ValueType,
    decode_value,
    format_value,
    parse_value,
)
from ..core.table import TableEntry
from ..core.utils import format_hex, parse_int
from .theme import COLORS, FONTS


def _center(window: tk.Toplevel, parent: tk.Misc | None = None) -> None:
    window.update_idletasks()
    width = max(window.winfo_reqwidth(), window.winfo_width())
    height = max(window.winfo_reqheight(), window.winfo_height())
    if parent is not None:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            if pw > 50 and ph > 50:
                x = px + (pw - width) // 2
                y = py + (ph - height) // 2
            else:
                x = (window.winfo_screenwidth() - width) // 2
                y = (window.winfo_screenheight() - height) // 2
        except tk.TclError:
            x = (window.winfo_screenwidth() - width) // 2
            y = (window.winfo_screenheight() - height) // 2
    else:
        x = (window.winfo_screenwidth() - width) // 2
        y = (window.winfo_screenheight() - height) // 2
    x = max(0, min(x, window.winfo_screenwidth() - width))
    y = max(0, min(y, window.winfo_screenheight() - height))
    window.geometry(f"+{x}+{y}")


class DisclaimerDialog(tk.Toplevel):
    """First-run acknowledgement of the single-player-only policy."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.accepted = False
        self.title("Before you begin")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._decline)
        self.grab_set()

        outer = ttk.Frame(self, padding=22)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="TrainerForge is for single-player games", style="TLabel", font=FONTS["section"]).pack(
            anchor="w"
        )
        ttk.Label(
            outer,
            text="A local, open-source memory trainer toolkit. Read this once, then build your own tables.",
            style="TLabel",
            foreground=COLORS["muted"],
            wraplength=620,
            justify="left",
        ).pack(anchor="w", pady=(4, 14))

        text_frame = ttk.Frame(outer, style="Card.TFrame", padding=2)
        text_frame.pack(fill="both", expand=True)
        text = tk.Text(
            text_frame,
            height=13,
            width=76,
            wrap="word",
            bg=COLORS["panel2"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=12,
            font=FONTS["body"],
            cursor="arrow",
        )
        text.pack(fill="both", expand=True)
        text.insert(
            "1.0",
            "• TrainerForge is intended only for single-player or offline games you own.\n\n"
            "• Do not use it with multiplayer games or processes protected by anti-cheat. "
            "TrainerForge refuses obvious anti-cheat targets and does not bypass, disable, "
            "or evade anti-cheat systems.\n\n"
            "• No game-specific cheats are bundled. You create your own tables by scanning "
            "memory and building pointer chains.\n\n"
            "• Memory editing can crash a game or corrupt a save. Back up your saves and use "
            "a separate save slot when experimenting.\n\n"
            "• TrainerForge has no accounts, ads, telemetry, or cloud service. It never "
            "uploads your table or game data.\n\n"
            "• This software comes with no warranty. You are responsible for complying with "
            "game terms and the laws where you live.",
        )
        text.configure(state="disabled")
        text.tag_configure("bullet", lmargin1=4, lmargin2=18)

        self.agree = tk.BooleanVar(value=False)
        check = ttk.Checkbutton(
            outer,
            text="I understand and will use TrainerForge only with single-player/offline games I own.",
            variable=self.agree,
            command=self._update_continue,
            style="TCheckbutton",
        )
        check.pack(anchor="w", pady=(14, 12))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Quit", style="Ghost.TButton", command=self._decline).pack(side="right")
        self.continue_button = ttk.Button(
            buttons,
            text="Continue",
            style="Accent.TButton",
            command=self._accept,
            state="disabled",
        )
        self.continue_button.pack(side="right", padx=(0, 8))

        _center(self, parent)
        self.lift()
        self.focus_force()
        self.after(50, check.focus_set)

    def _update_continue(self) -> None:
        self.continue_button.state(["!disabled"] if self.agree.get() else ["disabled"])

    def _accept(self) -> None:
        if not self.agree.get():
            return
        self.accepted = True
        self.destroy()

    def _decline(self) -> None:
        self.accepted = False
        self.destroy()


class EntryDialog(tk.Toplevel):
    """Create or edit one table entry."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        process: Process | None = None,
        entry: TableEntry | None = None,
        initial_address: int | None = None,
        initial_type: ValueType | None = None,
        initial_value: str | int | float | None = None,
    ):
        super().__init__(parent)
        self.parent_window = parent
        self.process = process
        self.original = entry.clone() if entry else None
        self.result: TableEntry | None = None
        self.title("Edit table entry" if entry else "Add table entry")
        self.configure(bg=COLORS["bg"])
        self.resizable(True, True)
        self.minsize(680, 610)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.description_var = tk.StringVar(value=entry.description if entry else "")
        self.kind_var = tk.StringVar(value=entry.kind if entry else "absolute")
        self.base_var = tk.StringVar(value=entry.base if entry else "0x0")
        self.offsets_var = tk.StringVar(
            value=", ".join(entry.offsets) if entry else ""
        )
        self.type_var = tk.StringVar(
            value=(
                entry.value_enum.label
                if entry
                else (initial_type or ValueType.INT32).label
            )
        )
        self.value_var = tk.StringVar(
            value=entry.value
            if entry
            else ("0" if initial_value is None else str(initial_value))
        )
        self.hotkey_var = tk.StringVar(value=entry.hotkey if entry else "")
        self.frozen_var = tk.BooleanVar(value=entry.frozen if entry else False)
        self.notes_var = tk.StringVar(value=entry.notes if entry else "")

        if initial_address is not None and entry is None:
            self.base_var.set(format_hex(initial_address))
            self.kind_var.set("absolute")

        self._build_ui()
        self._update_kind()
        _center(self, parent)
        self.bind("<Control-Return>", lambda _event: self._save())
        self.bind("<Escape>", lambda _event: self._cancel())
        self.after(50, self.description_entry.focus_set)

    # -- layout -----------------------------------------------------------
    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(
            header,
            text="Edit table entry" if self.original else "Add table entry",
            style="TLabel",
            font=FONTS["section"],
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="A direct address is simplest. A pointer chain survives most game restarts.",
            style="TLabel",
            foreground=COLORS["muted"],
        ).pack(anchor="w", pady=(3, 0))

        card = ttk.Frame(outer, style="Card.TFrame", padding=16)
        card.grid(row=1, column=0, sticky="nsew")
        card.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(card, text="Description", style="CardMuted.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 5)
        )
        self.description_entry = ttk.Entry(card, textvariable=self.description_var)
        self.description_entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=(0, 12))

        row += 1
        ttk.Label(card, text="Address kind", style="CardMuted.TLabel").grid(
            row=row, column=0, sticky="nw", pady=(2, 0)
        )
        kind_frame = ttk.Frame(card, style="Inner.TFrame")
        kind_frame.grid(row=row, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(
            kind_frame,
            text="Direct address",
            value="absolute",
            variable=self.kind_var,
            command=self._update_kind,
        ).pack(side="left")
        ttk.Radiobutton(
            kind_frame,
            text="Pointer chain",
            value="pointer",
            variable=self.kind_var,
            command=self._update_kind,
        ).pack(side="left", padx=(14, 0))

        row += 1
        ttk.Label(card, text="Base", style="CardMuted.TLabel").grid(
            row=row, column=0, sticky="w", pady=(10, 5)
        )
        self.base_entry = ttk.Entry(card, textvariable=self.base_var)
        self.base_entry.grid(row=row, column=1, sticky="ew", pady=(10, 5))
        module_frame = ttk.Frame(card, style="Inner.TFrame")
        module_frame.grid(row=row, column=2, sticky="e", padx=(8, 0), pady=(10, 5))
        modules = []
        if self.process is not None:
            try:
                modules = [module.name for module in self.process.modules()]
            except Exception:
                modules = []
        self.module_combo = ttk.Combobox(
            module_frame,
            values=modules,
            state="readonly" if modules else "disabled",
            width=23,
        )
        self.module_combo.pack(side="left")
        self.module_combo.bind("<<ComboboxSelected>>", self._insert_module)
        ttk.Label(
            card,
            text="Examples: 0x7FF6A1B2C3D4  ·  game.exe+0x1A2B0  (absolute + offset is allowed)",
            style="CardDim.TLabel",
        ).grid(row=row + 1, column=1, columnspan=2, sticky="w", pady=(0, 10))
        row += 2

        ttk.Label(card, text="Offsets", style="CardMuted.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 5)
        )
        self.offsets_entry = ttk.Entry(card, textvariable=self.offsets_var)
        self.offsets_entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=(0, 4))
        ttk.Label(
            card,
            text="Pointer chain only. Read a pointer, then add each offset in order. Example: 0x10, 0x20",
            style="CardDim.TLabel",
        ).grid(row=row + 1, column=1, columnspan=2, sticky="w", pady=(0, 10))
        row += 2

        ttk.Label(card, text="Value type", style="CardMuted.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 5)
        )
        type_frame = ttk.Frame(card, style="Inner.TFrame")
        type_frame.grid(row=row, column=1, columnspan=2, sticky="ew", pady=(0, 10))
        type_frame.columnconfigure(0, weight=1)
        self.type_combo = ttk.Combobox(
            type_frame,
            textvariable=self.type_var,
            values=list(VALUE_TYPE_LABELS.values()),
            state="readonly",
        )
        self.type_combo.grid(row=0, column=0, sticky="w")
        ttk.Label(card, text="Value", style="CardMuted.TLabel").grid(
            row=row + 1, column=0, sticky="w", pady=(0, 5)
        )
        self.value_entry = ttk.Entry(card, textvariable=self.value_var)
        self.value_entry.grid(row=row + 1, column=1, columnspan=2, sticky="ew", pady=(0, 10))
        row += 2

        ttk.Label(card, text="Hotkey", style="CardMuted.TLabel").grid(
            row=row, column=0, sticky="w", pady=(0, 5)
        )
        self.hotkey_entry = ttk.Entry(card, textvariable=self.hotkey_var)
        self.hotkey_entry.grid(row=row, column=1, sticky="ew", pady=(0, 5))
        ttk.Label(
            card,
            text="Optional. Toggles freeze for this entry. Format: F1, Ctrl+F2, Alt+Shift+3",
            style="CardDim.TLabel",
        ).grid(row=row + 1, column=1, columnspan=2, sticky="w", pady=(0, 10))
        row += 2

        ttk.Checkbutton(
            card,
            text="Freeze this value while attached",
            variable=self.frozen_var,
        ).grid(row=row, column=1, sticky="w", pady=(0, 10))
        row += 1

        ttk.Label(card, text="Notes", style="CardMuted.TLabel").grid(
            row=row, column=0, sticky="nw", pady=(0, 5)
        )
        self.notes_entry = ttk.Entry(card, textvariable=self.notes_var)
        self.notes_entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=(0, 10))
        row += 1

        preview_frame = ttk.Frame(card, style="Inner.TFrame")
        preview_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(2, 0))
        preview_frame.columnconfigure(1, weight=1)
        ttk.Button(
            preview_frame,
            text="Test address",
            style="Ghost.TButton",
            command=self._test_address,
        ).grid(row=0, column=0, sticky="w")
        self.preview_label = ttk.Label(
            preview_frame,
            text=(
                "Attach to a process to test the address."
                if self.process is None
                else "Test the address against the attached process."
            ),
            style="CardDim.TLabel",
            wraplength=520,
            justify="left",
        )
        self.preview_label.grid(row=0, column=1, sticky="w", padx=(10, 0))

        actions = ttk.Frame(outer)
        actions.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        ttk.Button(actions, text="Cancel", style="Ghost.TButton", command=self._cancel).pack(side="right")
        ttk.Button(actions, text="Save entry", style="Accent.TButton", command=self._save).pack(
            side="right", padx=(0, 8)
        )

    # -- behaviour --------------------------------------------------------
    def _update_kind(self) -> None:
        pointer = self.kind_var.get() == "pointer"
        if pointer:
            self.offsets_entry.state(["!disabled"])
            if self.module_combo["values"]:
                self.module_combo.state(["readonly"])
        else:
            self.offsets_entry.state(["disabled"])
            self.module_combo.state(["disabled"])
        self.preview_label.configure(text="Address settings changed; test again.")

    def _insert_module(self, _event=None) -> None:
        module = self.module_combo.get().strip()
        if not module:
            return
        self.base_var.set(f"{module}+0x0")
        self.base_entry.focus_set()
        self.base_entry.icursor("end")

    def _collect(self) -> TableEntry:
        description = self.description_var.get().strip()
        kind = self.kind_var.get().strip()
        base = self.base_var.get().strip()
        offsets_text = self.offsets_var.get().strip()
        offsets = []
        if kind == "pointer":
            offsets = [
                part.strip()
                for part in offsets_text.replace(";", ",").split(",")
                if part.strip()
            ]
        type_label = self.type_var.get()
        value_type = LABEL_TO_VALUE_TYPE.get(type_label)
        if value_type is None:
            raise ValueError("Choose a value type.")
        value = self.value_var.get().strip()
        hotkey = self.hotkey_var.get().strip()
        entry = TableEntry(
            id=self.original.id if self.original else TableEntry().id,
            description=description,
            kind=kind,
            base=base,
            offsets=offsets,
            value_type=value_type.value,
            value=value,
            frozen=bool(self.frozen_var.get()),
            hotkey=hotkey,
            notes=self.notes_var.get().strip(),
        )
        entry.validate()
        return entry

    def _save(self) -> None:
        try:
            entry = self._collect()
        except (ValueError, HotkeyError) as exc:
            messagebox.showerror("Invalid entry", str(exc), parent=self)
            return
        self.result = entry
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _test_address(self) -> None:
        if self.process is None:
            self.preview_label.configure(
                text="No process attached. The entry can be saved, but it cannot be tested yet."
            )
            return
        try:
            kind = self.kind_var.get()
            base = parse_base_expression(self.base_var.get())
            if kind == "pointer":
                offsets = [
                    parse_int(part, "offset")
                    for part in self.offsets_var.get().replace(";", ",").split(",")
                    if part.strip()
                ]
                address = resolve_base_chain(self.process, base, offsets)
                chain = describe_chain(base, offsets)
            else:
                if base.absolute is None:
                    raise ValueError("Direct entries need a numeric address.")
                address = base.absolute
                chain = format_hex(address)
            value_type = LABEL_TO_VALUE_TYPE[self.type_var.get()]
            raw = self.process.read(address, value_type.size)
            current = format_value(decode_value(raw, value_type), value_type)
            self.preview_label.configure(
                text=f"{chain}  →  {format_hex(address)}  =  {current}",
                foreground=COLORS["green"],
            )
        except Exception as exc:  # noqa: BLE001 - reported to the user
            self.preview_label.configure(
                text=f"Could not resolve/read: {exc}",
                foreground=COLORS["red"],
            )
