"""Main TrainerForge window and application flow."""

from __future__ import annotations

import logging
import os
import queue
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from .. import __version__
from ..core import winapi
from ..core.config import AppConfig
from ..core.freezer import Freezer
from ..core.hotkeys import HotkeyManager
from ..core.process import (
    MemoryReadError,
    Process,
    ProcessAccessError,
    ProcessError,
    ProcessInfo,
    list_processes,
)
from ..core.safety import UnsafeTargetError, ensure_safe_target
from ..core.scanner import (
    LABEL_TO_SCAN_MODE,
    LABEL_TO_VALUE_TYPE,
    SCAN_MODE_LABELS,
    VALUE_TYPE_LABELS,
    ScanMode,
    ScanProgress,
    ScanSession,
    ValueType,
    decode_value,
    first_scan,
    format_value,
    next_scan,
    parse_value,
)
from ..core.table import TABLE_SUFFIX, Table, TableEntry
from ..core.utils import format_hex, human_bytes, parse_int
from .dialogs import DisclaimerDialog, EntryDialog
from .theme import COLORS, FONTS, apply_theme

logger = logging.getLogger("trainerforge")

RESULT_RENDER_LIMIT = 5000
LIVE_UPDATE_MS = 700
UI_QUEUE_MS = 120
SCAN_QUEUE_MS = 80
PROCESS_PLACEHOLDER = "Select a running process…"


class MainWindow:
    def __init__(self, root: tk.Tk, config: AppConfig, args):
        self.root = root
        self.config = config
        self.args = args
        self.process: Process | None = None
        self.scan_session: ScanSession | None = None
        self.table = Table.new("Untitled")
        self.dirty = False
        self.closed = False
        self.busy = False
        self._scan_thread: threading.Thread | None = None
        self._cancel_event = threading.Event()
        self._scan_queue: queue.Queue = queue.Queue()
        self._ui_queue: queue.Queue = queue.Queue()
        self._processes: dict[str, ProcessInfo] = {}
        self._visible_results: list = []
        self._live_job: str | None = None
        self._poll_jobs: list[str] = []
        self._last_hotkey_errors: dict[str, str] = {}
        self._smoke_test = bool(getattr(args, "smoke_test", False))
        self.admin = winapi.is_admin()
        if self.admin:
            enabled, message = winapi.enable_debug_privilege()
            if not enabled:
                logger.warning("Could not enable SeDebugPrivilege: %s", message)

        self.freezer = Freezer(interval=0.05, on_error=self._on_freezer_error)
        self.freezer.start()
        self.hotkeys = HotkeyManager(root, self._on_hotkey)

        self._build_menu()
        self._build_header()
        self._build_body()
        self._build_log()
        self._build_status()
        self._bind_shortcuts()
        self._refresh_processes(initial=True)
        self._clear_results(log_it=False)
        self._refresh_table(select_id=None)
        self.hotkeys.start()
        self._register_hotkeys()
        self._schedule_live()
        self._poll_queues()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._update_title()
        self._log(
            "TrainerForge ready. Attach to a single-player game, scan a value, "
            "then add the result to your table."
        )
        if self.table.entries:
            self._log(f"Loaded {len(self.table.entries)} table entries.")
        if getattr(args, "table", None):
            self.root.after(200, lambda: self._open_table_path(Path(args.table), silent=True))
        if getattr(args, "process", None):
            self.root.after(400, lambda: self._attach_by_name(args.process))
        if self._smoke_test:
            self.root.after(1500, self.smoke_close)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root, tearoff=0)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New table", accelerator="Ctrl+N", command=self._new_table)
        file_menu.add_command(label="Open table…", accelerator="Ctrl+O", command=self._open_table)
        file_menu.add_command(label="Save table", accelerator="Ctrl+S", command=self._save_table)
        file_menu.add_command(label="Save table as…", command=self._save_table_as)
        file_menu.add_separator()
        file_menu.add_command(label="Refresh process list", command=self._refresh_processes)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        table_menu = tk.Menu(menubar, tearoff=0)
        table_menu.add_command(label="Add entry…", accelerator="Ctrl+E", command=self._add_entry)
        table_menu.add_command(label="Edit selected", accelerator="F2", command=self._edit_entry)
        table_menu.add_command(label="Remove selected", accelerator="Delete", command=self._remove_entry)
        table_menu.add_separator()
        table_menu.add_command(label="Toggle freeze", command=self._toggle_freeze_selected)
        table_menu.add_command(label="Write value now", command=self._apply_selected)
        menubar.add_cascade(label="Table", menu=table_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Safety and scope", command=self._show_safety)
        help_menu.add_command(label="How WeMod works (research note)", command=self._show_analysis)
        help_menu.add_command(label="Project on GitHub", command=self._open_github)
        help_menu.add_separator()
        help_menu.add_command(label="About TrainerForge", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.configure(menu=menubar)

    def _build_header(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(18, 13))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        left = ttk.Frame(header, style="Header.TFrame")
        left.grid(row=0, column=0, sticky="w")
        ttk.Label(left, text="TrainerForge", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            left,
            text="Open-source memory trainer toolkit  ·  single-player only  ·  no telemetry",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        right = ttk.Frame(header, style="Header.TFrame")
        right.grid(row=0, column=1, sticky="e")
        target_row = ttk.Frame(right, style="Header.TFrame")
        target_row.pack(anchor="e")
        ttk.Label(target_row, text="TARGET PROCESS", style="HeaderMuted.TLabel", font=FONTS["tiny"]).pack(
            side="left", padx=(0, 8)
        )
        self.attach_pill = tk.Label(
            target_row,
            text="NOT ATTACHED",
            bg=COLORS["panel2"],
            fg=COLORS["muted"],
            font=("Segoe UI Semibold", 8),
            padx=8,
            pady=2,
        )
        self.attach_pill.pack(side="left")

        controls = ttk.Frame(right, style="Header.TFrame")
        controls.pack(anchor="e", pady=(5, 0))
        self.process_var = tk.StringVar()
        self.process_combo = ttk.Combobox(
            controls,
            textvariable=self.process_var,
            state="readonly",
            width=44,
            values=[],
        )
        self.process_combo.pack(side="left")
        self.process_combo.bind("<<ComboboxSelected>>", self._on_process_selected)
        self.refresh_button = ttk.Button(
            controls, text="Refresh", style="Ghost.TButton", command=self._refresh_processes
        )
        self.refresh_button.pack(side="left", padx=(6, 0))
        self.attach_button = ttk.Button(
            controls, text="Attach", style="Accent.TButton", command=self._toggle_attach
        )
        self.attach_button.pack(side="left", padx=(6, 0))

        badge = tk.Label(
            controls,
            text="ADMIN" if self.admin else "STANDARD",
            bg=COLORS["panel2"],
            fg=COLORS["green"] if self.admin else COLORS["amber"],
            font=("Segoe UI Semibold", 8),
            padx=7,
            pady=4,
        )
        badge.pack(side="left", padx=(8, 0))

    def _build_body(self) -> None:
        body = ttk.Frame(self.root, padding=(14, 12, 14, 7))
        body.grid(row=1, column=0, sticky="nsew")
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)
        body.columnconfigure(0, weight=1, uniform="panel")
        body.columnconfigure(1, weight=1, uniform="panel")
        body.rowconfigure(0, weight=1)

        self._build_scanner_panel(body)
        self._build_table_panel(body)

    def _build_scanner_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Card.TFrame", padding=15)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(7, weight=1)

        ttk.Label(panel, text="1 · Find a value", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            panel,
            text="Search committed memory for an exact value, then narrow the results.",
            style="CardDim.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        controls = ttk.Frame(panel, style="Inner.TFrame")
        controls.grid(row=2, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="Value type", style="CardMuted.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        ttk.Label(controls, text="Value", style="CardMuted.TLabel").grid(row=0, column=1, sticky="w")
        self.scan_type_var = tk.StringVar(value=ValueType.INT32.label)
        self.scan_type_combo = ttk.Combobox(
            controls,
            textvariable=self.scan_type_var,
            values=list(VALUE_TYPE_LABELS.values()),
            state="readonly",
            width=17,
        )
        self.scan_type_combo.grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(3, 8))
        self.scan_value_var = tk.StringVar(value="")
        self.scan_value_entry = ttk.Entry(controls, textvariable=self.scan_value_var)
        self.scan_value_entry.grid(row=1, column=1, sticky="ew", pady=(3, 8))
        self.scan_value_entry.bind("<Return>", lambda _event: self._start_first_scan())

        advanced = ttk.Frame(panel, style="Inner.TFrame")
        advanced.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(advanced, text="Alignment", style="CardMuted.TLabel").pack(side="left")
        self.alignment_var = tk.StringVar(value="4")
        self.alignment_combo = ttk.Combobox(
            advanced,
            textvariable=self.alignment_var,
            values=("1", "2", "4", "8"),
            state="readonly",
            width=4,
        )
        self.alignment_combo.pack(side="left", padx=(5, 14))
        self.writable_only_var = tk.BooleanVar(value=True)
        self.writable_check = ttk.Checkbutton(
            advanced,
            text="Writable memory only",
            variable=self.writable_only_var,
        )
        self.writable_check.pack(side="left")
        self.cancel_button = ttk.Button(
            advanced,
            text="Cancel",
            style="Small.TButton",
            command=self._cancel_scan,
            state="disabled",
        )
        self.cancel_button.pack(side="right")

        buttons = ttk.Frame(panel, style="Inner.TFrame")
        buttons.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self.first_scan_button = ttk.Button(
            buttons, text="First scan", style="Accent.TButton", command=self._start_first_scan
        )
        self.first_scan_button.pack(side="left")
        self.reset_button = ttk.Button(
            buttons, text="Reset", style="Ghost.TButton", command=self._reset_scan, state="disabled"
        )
        self.reset_button.pack(side="left", padx=(6, 0))
        self.results_count_var = tk.StringVar(value="No scan yet")
        ttk.Label(buttons, textvariable=self.results_count_var, style="CardDim.TLabel").pack(
            side="right"
        )

        next_frame = ttk.Frame(panel, style="Inner.TFrame")
        next_frame.grid(row=5, column=0, sticky="ew", pady=(0, 7))
        next_frame.columnconfigure(2, weight=1)
        ttk.Label(next_frame, text="NEXT SCAN", style="CardDim.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        self.scan_mode_var = tk.StringVar(value=ScanMode.CHANGED.label)
        self.scan_mode_combo = ttk.Combobox(
            next_frame,
            textvariable=self.scan_mode_var,
            values=list(SCAN_MODE_LABELS.values()),
            state="readonly",
            width=14,
        )
        self.scan_mode_combo.grid(row=0, column=1, sticky="w")
        self.scan_mode_combo.bind("<<ComboboxSelected>>", self._on_scan_mode_changed)
        self.next_value_var = tk.StringVar(value="")
        self.next_value_entry = ttk.Entry(next_frame, textvariable=self.next_value_var)
        self.next_value_entry.grid(row=0, column=2, sticky="ew", padx=8)
        self.next_scan_button = ttk.Button(
            next_frame,
            text="Next scan",
            style="TButton",
            command=self._start_next_scan,
            state="disabled",
        )
        self.next_scan_button.grid(row=0, column=3, sticky="e")

        progress_frame = ttk.Frame(panel, style="Inner.TFrame")
        progress_frame.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        progress_frame.columnconfigure(0, weight=1)
        self.progress_bar = ttk.Progressbar(progress_frame, mode="determinate", maximum=100)
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_label = ttk.Label(
            progress_frame,
            text="Ready · no scan running",
            style="CardDim.TLabel",
        )
        self.progress_label.grid(row=1, column=0, sticky="w", pady=(3, 0))

        tree_frame = ttk.Frame(panel, style="Inner.TFrame")
        tree_frame.grid(row=7, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.results_tree = ttk.Treeview(
            tree_frame,
            columns=("address", "value", "previous"),
            show="headings",
            selectmode="browse",
            height=10,
        )
        self.results_tree.heading("address", text="ADDRESS", anchor="w")
        self.results_tree.heading("value", text="CURRENT", anchor="w")
        self.results_tree.heading("previous", text="PREVIOUS", anchor="w")
        self.results_tree.column("address", width=150, minwidth=110, stretch=False, anchor="w")
        self.results_tree.column("value", width=120, minwidth=80, stretch=True, anchor="w")
        self.results_tree.column("previous", width=120, minwidth=80, stretch=True, anchor="w")
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.results_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.results_tree.configure(yscrollcommand=vsb.set)
        self.results_tree.bind("<<TreeviewSelect>>", self._on_result_selected)
        self.results_tree.bind("<Double-1>", lambda _event: self._add_selected_result())

        results_footer = ttk.Frame(panel, style="Inner.TFrame")
        results_footer.grid(row=8, column=0, sticky="ew", pady=(8, 0))
        self.results_note_var = tk.StringVar(
            value="Results appear here. Next scans filter the current result set."
        )
        ttk.Label(
            results_footer,
            textvariable=self.results_note_var,
            style="CardDim.TLabel",
            wraplength=500,
            justify="left",
        ).pack(side="left")
        self.add_result_button = ttk.Button(
            results_footer,
            text="Add selected →",
            style="TButton",
            command=self._add_selected_result,
            state="disabled",
        )
        self.add_result_button.pack(side="right")

        self._update_scan_controls()

    def _build_table_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Card.TFrame", padding=15)
        panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(3, weight=1)

        ttk.Label(panel, text="2 · Build your table", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            panel,
            text="Keep addresses, freeze values, bind global hotkeys, and save a shareable table.",
            style="CardDim.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        toolbar = ttk.Frame(panel, style="Inner.TFrame")
        toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="Add", style="TButton", command=self._add_entry).pack(side="left")
        self.edit_button = ttk.Button(
            toolbar, text="Edit", style="TButton", command=self._edit_entry, state="disabled"
        )
        self.edit_button.pack(side="left", padx=(5, 0))
        self.remove_button = ttk.Button(
            toolbar, text="Remove", style="Danger.TButton", command=self._remove_entry, state="disabled"
        )
        self.remove_button.pack(side="left", padx=(5, 0))
        self.freeze_button = ttk.Button(
            toolbar,
            text="Freeze",
            style="TButton",
            command=self._toggle_freeze_selected,
            state="disabled",
        )
        self.freeze_button.pack(side="right")
        self.apply_button = ttk.Button(
            toolbar,
            text="Write value",
            style="TButton",
            command=self._apply_selected,
            state="disabled",
        )
        self.apply_button.pack(side="right", padx=(0, 5))

        tree_frame = ttk.Frame(panel, style="Inner.TFrame")
        tree_frame.grid(row=3, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.table_tree = ttk.Treeview(
            tree_frame,
            columns=("description", "address", "type", "value", "live", "frozen", "hotkey"),
            show="headings",
            selectmode="browse",
            height=14,
        )
        headings = {
            "description": ("DESCRIPTION", 140, 90),
            "address": ("ADDRESS / CHAIN", 140, 100),
            "type": ("TYPE", 46, 42),
            "value": ("VALUE", 58, 50),
            "live": ("LIVE", 50, 44),
            "frozen": ("FROZEN", 62, 54),
            "hotkey": ("HOTKEY", 70, 56),
        }
        for column, (text, width, minwidth) in headings.items():
            self.table_tree.heading(column, text=text, anchor="w")
            self.table_tree.column(
                column,
                width=width,
                minwidth=minwidth,
                stretch=column in ("description", "address"),
                anchor="w",
            )
        self.table_tree.tag_configure("frozen", background=COLORS["frozen"])
        self.table_tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.table_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.table_tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.table_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.table_tree.bind("<<TreeviewSelect>>", self._on_table_selected)
        self.table_tree.bind("<Double-1>", lambda _event: self._edit_entry())
        self.table_tree.bind("<Return>", lambda _event: self._edit_entry())
        self.table_tree.bind("<Delete>", lambda _event: self._remove_entry())

        footer = ttk.Frame(panel, style="Inner.TFrame")
        footer.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.table_count_var = tk.StringVar(value="0 entries")
        ttk.Label(footer, textvariable=self.table_count_var, style="CardDim.TLabel").pack(side="left")
        ttk.Label(
            footer,
            text="Double-click an entry to edit  ·  F2  ·  global hotkeys toggle freeze",
            style="CardDim.TLabel",
        ).pack(side="right")

    def _build_log(self) -> None:
        wrapper = ttk.Frame(self.root, padding=(14, 0, 14, 7))
        wrapper.grid(row=2, column=0, sticky="ew")
        wrapper.columnconfigure(0, weight=1)
        head = ttk.Frame(wrapper)
        head.grid(row=0, column=0, sticky="ew")
        ttk.Label(head, text="ACTIVITY", style="Subtitle.TLabel", foreground=COLORS["muted"]).pack(
            side="left"
        )
        ttk.Button(head, text="Clear", style="Small.TButton", command=self._clear_log).pack(side="right")
        log_frame = ttk.Frame(wrapper, style="Card.TFrame", padding=1)
        log_frame.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(
            log_frame,
            height=5,
            wrap="word",
            bg=COLORS["panel2"],
            fg=COLORS["muted"],
            insertbackground=COLORS["text"],
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=7,
            font=FONTS["mono"],
            state="disabled",
        )
        self.log_text.grid(row=0, column=0, sticky="ew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

    def _build_status(self) -> None:
        status = ttk.Frame(self.root, style="Status.TFrame", padding=(14, 6))
        status.grid(row=3, column=0, sticky="ew")
        status.columnconfigure(1, weight=1)
        self.status_dot = tk.Label(
            status, text="●", bg=COLORS["header"], fg=COLORS["dim"], font=("Segoe UI", 8)
        )
        self.status_dot.grid(row=0, column=0, sticky="w")
        self.status_var = tk.StringVar(value="Not attached")
        ttk.Label(status, textvariable=self.status_var, style="StatusValue.TLabel").grid(
            row=0, column=1, sticky="w", padx=(5, 0)
        )
        self.info_var = tk.StringVar(value="Independent project · MIT license")
        ttk.Label(status, textvariable=self.info_var, style="Status.TLabel").grid(
            row=0, column=2, sticky="e"
        )

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-n>", lambda _event: self._new_table())
        self.root.bind("<Control-o>", lambda _event: self._open_table())
        self.root.bind("<Control-s>", lambda _event: self._save_table())
        self.root.bind("<Control-e>", lambda _event: self._add_entry())
        self.root.bind("<F2>", lambda _event: self._edit_entry())

    # ------------------------------------------------------------------
    # Logging and UI queue
    # ------------------------------------------------------------------
    def _log(self, message: str, *, level: str = "info") -> None:
        if self.closed:
            return
        stamp = time.strftime("%H:%M:%S")
        line = f"[{stamp}] {message}\n"
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line)
            line_count = int(self.log_text.index("end-1c").split(".")[0])
            if line_count > 600:
                self.log_text.delete("1.0", "100.0")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        except tk.TclError:
            pass
        log_method = getattr(logger, level, logger.info)
        log_method(message)

    def _clear_log(self) -> None:
        try:
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
        except tk.TclError:
            pass

    def _on_freezer_error(self, entry_id: str, message: str) -> None:
        self._ui_queue.put(("freezer_error", entry_id, message))

    def _poll_queues(self) -> None:
        if self.closed:
            return
        self._drain_scan_queue()
        self._drain_ui_queue()
        self.root.after(SCAN_QUEUE_MS, self._poll_queues)

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                item = self._ui_queue.get_nowait()
            except queue.Empty:
                return
            if item[0] == "freezer_error":
                _, entry_id, message = item
                entry = self.table.entry(entry_id)
                name = entry.description if entry else entry_id
                self._log(f"Freeze failed for {name}: {message}", level="warning")

    def _drain_scan_queue(self) -> None:
        while True:
            try:
                item = self._scan_queue.get_nowait()
            except queue.Empty:
                return
            kind = item[0]
            if kind == "progress":
                self._apply_scan_progress(item[1])
            elif kind == "done":
                _, scan_kind, session, duration = item
                self._finish_scan(scan_kind, session, duration)
            elif kind == "error":
                _, scan_kind, exc, trace = item
                self._finish_scan_error(scan_kind, exc, trace)

    # ------------------------------------------------------------------
    # Process handling
    # ------------------------------------------------------------------
    def _refresh_processes(self, initial: bool = False) -> None:
        if self.busy:
            return
        try:
            processes = list_processes()
        except Exception as exc:
            self._log(f"Could not enumerate processes: {exc}", level="error")
            if not initial:
                messagebox.showerror("Process list", str(exc), parent=self.root)
            return
        current_label = self.process_var.get()
        self._processes = {info.label: info for info in processes}
        labels = [PROCESS_PLACEHOLDER, *self._processes]
        self.process_combo.configure(values=labels)
        if self.process is not None:
            for label, info in self._processes.items():
                if info.pid == self.process.pid:
                    self.process_var.set(label)
                    break
        elif current_label in self._processes:
            self.process_var.set(current_label)
        else:
            self.process_var.set(PROCESS_PLACEHOLDER)
        self.info_var.set(f"{len(processes)} processes visible · Independent project · MIT license")
        if not initial:
            self._log(f"Refreshed process list ({len(processes)} processes).")

    def _on_process_selected(self, _event=None) -> None:
        if self.process is not None:
            return
        info = self._processes.get(self.process_var.get())
        if info:
            self.status_var.set(f"Selected {info.name} (PID {info.pid}) — press Attach")
            self.info_var.set(f"PID {info.pid}  ·  {info.path or 'path unavailable'}")

    def _toggle_attach(self) -> None:
        if self.busy:
            return
        if self.process is not None:
            self._detach()
        else:
            self._attach_selected()

    def _attach_selected(self) -> None:
        info = self._processes.get(self.process_var.get())
        if info is None:
            messagebox.showinfo(
                "Choose a process",
                "Select a target process from the list first.",
                parent=self.root,
            )
            return
        if info.pid == os.getpid():
            messagebox.showerror("Unsafe target", "TrainerForge will not attach to itself.", parent=self.root)
            return
        try:
            process = Process(info.pid, name=info.name)
        except ProcessAccessError as exc:
            messagebox.showerror("Access denied", str(exc), parent=self.root)
            self._log(str(exc), level="error")
            return
        except ProcessError as exc:
            messagebox.showerror("Could not attach", str(exc), parent=self.root)
            self._log(str(exc), level="error")
            return

        try:
            warnings = ensure_safe_target(process, own_pid=os.getpid())
        except UnsafeTargetError as exc:
            process.close()
            messagebox.showerror("Unsafe target", str(exc), parent=self.root)
            self._log(str(exc), level="error")
            return
        except Exception as exc:
            process.close()
            messagebox.showerror("Safety check failed", str(exc), parent=self.root)
            self._log(f"Safety check failed: {exc}", level="error")
            return

        self.process = process
        self.scan_session = None
        self._clear_results(log_it=False)
        self.freezer.set_target(process)
        self._set_attached_ui(True)
        self._log(
            f"Attached to {process.name} (PID {process.pid}, {process.arch}, "
            f"{process.pointer_size}-byte pointers)."
        )
        for warning in warnings:
            self._log(warning, level="warning")
        if not self.table.process_name:
            self.table.process_name = process.name
            self._mark_dirty()
        elif self.table.process_name.lower() != process.name.lower():
            self._log(
                f"Note: this table was built for {self.table.process_name}, "
                f"but you attached {process.name}.",
                level="warning",
            )
        self.status_var.set(f"Attached to {process.name} (PID {process.pid})")
        self.info_var.set(
            f"{process.arch} target  ·  {process.pointer_size}-byte pointers  ·  "
            f"{'administrator' if self.admin else 'standard user'}"
        )
        self._update_live_values()
        self._update_scan_controls()

    def _detach(self) -> None:
        if self.process is None:
            return
        name = self.process.name
        self.freezer.set_target(None)
        self.process.close()
        self.process = None
        self.scan_session = None
        self._clear_results(log_it=False)
        self._set_attached_ui(False)
        self._clear_live_values()
        self.status_var.set("Not attached")
        self.info_var.set(f"Detached from {name} · Independent project · MIT license")
        self._log(f"Detached from {name}.")
        self._update_scan_controls()

    def _attach_by_name(self, name: str) -> None:
        wanted = (name or "").strip().lower()
        if not wanted:
            return
        for label, info in self._processes.items():
            if info.name.lower() == wanted or wanted in info.path.lower():
                self.process_var.set(label)
                self._attach_selected()
                return
        self._log(f"Process {name!r} was not found in the process list.", level="warning")

    def _set_attached_ui(self, attached: bool) -> None:
        if attached:
            self.process_combo.state(["disabled"])
            self.refresh_button.state(["disabled"])
            self.attach_button.configure(text="Detach", style="TButton")
            self.attach_pill.configure(text="ATTACHED", bg=COLORS["panel3"], fg=COLORS["green"])
            self.status_dot.configure(fg=COLORS["green"])
        else:
            self.process_combo.state(["readonly"])
            self.refresh_button.state(["!disabled"])
            self.attach_button.configure(text="Attach", style="Accent.TButton")
            self.attach_pill.configure(text="NOT ATTACHED", bg=COLORS["panel2"], fg=COLORS["muted"])
            self.status_dot.configure(fg=COLORS["dim"])
        self._update_scan_controls()
        self._update_table_controls()

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------
    def _current_value_type(self) -> ValueType:
        value_type = LABEL_TO_VALUE_TYPE.get(self.scan_type_var.get())
        if value_type is None:
            raise ValueError("Choose a value type.")
        return value_type

    def _on_scan_mode_changed(self, _event=None) -> None:
        mode = LABEL_TO_SCAN_MODE.get(self.scan_mode_var.get(), ScanMode.CHANGED)
        if mode.needs_value and not self.busy:
            self.next_value_entry.state(["!disabled"])
        else:
            self.next_value_entry.state(["disabled"])
        self._update_scan_controls()

    def _start_first_scan(self) -> None:
        if self.busy or self.process is None:
            return
        try:
            value_type = self._current_value_type()
            value = parse_value(self.scan_value_var.get(), value_type)
            alignment = int(self.alignment_var.get())
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Invalid scan", str(exc), parent=self.root)
            return
        self.scan_session = None
        self._clear_results(log_it=False)
        self._cancel_event.clear()
        self._set_busy(True, "Scanning memory…")
        writable_only = bool(self.writable_only_var.get())
        process = self.process
        self._log(
            f"First scan: {value_type.label} = {value!r}, alignment {alignment}, "
            f"{'writable only' if writable_only else 'all readable'}."
        )

        def worker():
            last_emit = [0.0]

            def progress(update: ScanProgress):
                now = time.monotonic()
                if now - last_emit[0] >= 0.08 or update.units_done >= update.units_total:
                    last_emit[0] = now
                    self._scan_queue.put(("progress", update))

            try:
                session = first_scan(
                    process,
                    value_type,
                    value,
                    alignment=alignment,
                    writable_only=writable_only,
                    progress=progress,
                    should_cancel=self._cancel_event.is_set,
                )
                self._scan_queue.put(("done", "first", session, session.duration))
            except Exception as exc:  # noqa: BLE001 - worker boundary
                self._scan_queue.put(("error", "first", exc, traceback.format_exc()))

        self._scan_thread = threading.Thread(
            target=worker, name="trainerforge-first-scan", daemon=True
        )
        self._scan_thread.start()

    def _start_next_scan(self) -> None:
        if self.busy or self.process is None or self.scan_session is None:
            return
        mode = LABEL_TO_SCAN_MODE.get(self.scan_mode_var.get(), ScanMode.CHANGED)
        value = None
        if mode.needs_value:
            try:
                value = parse_value(self.next_value_var.get(), self.scan_session.value_type)
            except ValueError as exc:
                messagebox.showerror("Invalid next scan", str(exc), parent=self.root)
                return
        session = self.scan_session
        self._cancel_event.clear()
        self._set_busy(True, f"Filtering {session.count:,} matches…")
        self._log(
            f"Next scan: {mode.label}"
            + (f" = {value!r}" if mode.needs_value else "")
            + f" across {session.count:,} matches."
        )

        def worker():
            last_emit = [0.0]

            def progress(update: ScanProgress):
                now = time.monotonic()
                if now - last_emit[0] >= 0.08 or update.units_done >= update.units_total:
                    last_emit[0] = now
                    self._scan_queue.put(("progress", update))

            try:
                filtered = next_scan(
                    session,
                    mode,
                    value,
                    progress=progress,
                    should_cancel=self._cancel_event.is_set,
                )
                self._scan_queue.put(("done", "next", filtered, filtered.duration))
            except Exception as exc:  # noqa: BLE001 - worker boundary
                self._scan_queue.put(("error", "next", exc, traceback.format_exc()))

        self._scan_thread = threading.Thread(
            target=worker, name="trainerforge-next-scan", daemon=True
        )
        self._scan_thread.start()

    def _cancel_scan(self) -> None:
        if self.busy:
            self._cancel_event.set()
            self.cancel_button.state(["disabled"])
            self._log("Cancelling scan…")

    def _apply_scan_progress(self, progress: ScanProgress) -> None:
        percent = progress.fraction * 100.0
        try:
            self.progress_bar.configure(value=percent)
        except AttributeError:
            pass
        text = progress.message or f"{human_bytes(progress.bytes_done)} / {human_bytes(progress.bytes_total)}"
        self.progress_label.configure(
            text=f"{text}  ·  {human_bytes(progress.bytes_done)} / {human_bytes(progress.bytes_total)}"
        )

    def _finish_scan(self, kind: str, session: ScanSession, duration: float) -> None:
        self.scan_session = session
        self._render_results(session)
        self._set_busy(False)
        if session.truncated:
            self._log(
                f"Stopped at the {session.count:,}-result limit. "
                "Use a more specific value or narrower alignment.",
                level="warning",
            )
        elif session.cancelled:
            self._log(f"Scan cancelled after {session.count:,} matches.", level="warning")
        else:
            self._log(
                f"{'First' if kind == 'first' else 'Next'} scan finished: "
                f"{session.count:,} matches in {duration:.2f}s "
                f"({human_bytes(session.scanned_bytes)} read)."
            )
        if session.read_errors:
            self._log(f"{session.read_errors} memory pages could not be read and were skipped.", level="warning")
        self.progress_bar.configure(value=100)
        self.progress_label.configure(
            text=f"{session.count:,} matches  ·  {human_bytes(session.scanned_bytes)} read  ·  {duration:.2f}s"
        )
        self._update_scan_controls()

    def _finish_scan_error(self, kind: str, exc: Exception, trace: str) -> None:
        self._set_busy(False)
        self._log(f"Scan failed: {exc}", level="error")
        logger.error("Scan failed:\n%s", trace)
        messagebox.showerror("Scan failed", str(exc), parent=self.root)
        self._update_scan_controls()

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.busy = busy
        if busy:
            self.progress_bar.configure(value=0)
            self.progress_label.configure(text=message or "Working…")
            self.cancel_button.state(["!disabled"])
            self.process_combo.state(["disabled"])
            self.refresh_button.state(["disabled"])
            self.attach_button.state(["disabled"])
        else:
            self.cancel_button.state(["disabled"])
            if self.process is None:
                self.process_combo.state(["readonly"])
                self.refresh_button.state(["!disabled"])
                self.attach_button.state(["!disabled"])
            else:
                self.process_combo.state(["disabled"])
                self.refresh_button.state(["disabled"])
                self.attach_button.state(["!disabled"])
            self.progress_bar.configure(value=100 if self.scan_session else 0)
            if self.scan_session:
                self.progress_label.configure(
                    text=f"{self.scan_session.count:,} matches  ·  {self.scan_session.duration:.2f}s"
                )
        self._update_scan_controls()
        self._update_table_controls()

    def _update_scan_controls(self) -> None:
        ready = self.process is not None and not self.busy
        has_session = self.scan_session is not None and bool(self.scan_session.results)
        for button, enabled in (
            (self.first_scan_button, ready),
            (self.next_scan_button, ready and has_session),
            (self.reset_button, self.process is not None and not self.busy and self.scan_session is not None),
        ):
            try:
                button.state(["!disabled"] if enabled else ["disabled"])
            except tk.TclError:
                pass
        mode = LABEL_TO_SCAN_MODE.get(self.scan_mode_var.get(), ScanMode.CHANGED)
        if mode.needs_value and not self.busy:
            self.next_value_entry.state(["!disabled"])
        else:
            self.next_value_entry.state(["disabled"])
        for widget in (
            self.scan_type_combo,
            self.alignment_combo,
            self.scan_value_entry,
            self.writable_check,
            self.scan_mode_combo,
        ):
            try:
                widget.state(["!disabled"] if not self.busy else ["disabled"])
            except tk.TclError:
                pass

    def _reset_scan(self) -> None:
        if self.busy:
            return
        self.scan_session = None
        self._clear_results(log_it=True)
        self.progress_bar.configure(value=0)
        self.progress_label.configure(text="Ready")
        self._update_scan_controls()

    def _clear_results(self, *, log_it: bool) -> None:
        try:
            self.results_tree.delete(*self.results_tree.get_children())
        except tk.TclError:
            pass
        self._visible_results = []
        self.results_count_var.set("No scan yet")
        self.results_note_var.set("Results appear here. Next scans filter the current result set.")
        self.add_result_button.state(["disabled"])
        if log_it:
            self._log("Scan results cleared.")

    def _render_results(self, session: ScanSession) -> None:
        try:
            self.results_tree.delete(*self.results_tree.get_children())
        except tk.TclError:
            return
        visible = session.results[:RESULT_RENDER_LIMIT]
        self._visible_results = visible
        for index, result in enumerate(visible):
            self.results_tree.insert(
                "",
                "end",
                iid=f"result-{index}",
                values=(format_hex(result.address), result.value_text, result.previous_text),
            )
        self.results_count_var.set(
            f"{session.count:,} matches"
            + (f" · showing {len(visible):,}" if len(visible) < session.count else "")
        )
        if session.count == 0:
            self.results_note_var.set(
                "No matches. Try a different value, type, or alignment; "
                "some games store health as a float."
            )
        elif len(visible) < session.count:
            self.results_note_var.set(
                f"Showing the first {len(visible):,} of {session.count:,} matches. "
                "Next scans still use the full result set."
            )
        else:
            self.results_note_var.set(
                f"All {session.count:,} matches are shown. Add one to the table, "
                "or narrow the results with a next scan."
            )
        self.add_result_button.state(["disabled"])

    def _on_result_selected(self, _event=None) -> None:
        enabled = bool(self.results_tree.selection()) and not self.busy
        self.add_result_button.state(["!disabled"] if enabled else ["disabled"])

    def _selected_result(self):
        selection = self.results_tree.selection()
        if not selection:
            return None
        try:
            index = int(selection[0].split("-", 1)[1])
        except (ValueError, IndexError):
            return None
        if 0 <= index < len(self._visible_results):
            return self._visible_results[index]
        return None

    def _add_selected_result(self) -> None:
        result = self._selected_result()
        if result is None or self.busy:
            return
        dialog = EntryDialog(
            self.root,
            process=self.process,
            initial_address=result.address,
            initial_type=result.value_type,
            initial_value=result.value_text,
        )
        self.root.wait_window(dialog)
        if dialog.result is None:
            return
        self.table.add(dialog.result)
        self._mark_dirty()
        self._refresh_table(select_id=dialog.result.id)
        self._log(f"Added {dialog.result.description!r} at {dialog.result.display_address()} to the table.")

    # ------------------------------------------------------------------
    # Table handling
    # ------------------------------------------------------------------
    def _refresh_table(self, select_id: str | None = None) -> None:
        if select_id is None:
            selection = self.table_tree.selection()
            if selection:
                select_id = selection[0]
        try:
            self.table_tree.delete(*self.table_tree.get_children())
        except tk.TclError:
            return
        for entry in self.table.entries:
            try:
                type_short = ValueType(entry.value_type).value
            except ValueError:
                type_short = entry.value_type
            self.table_tree.insert(
                "",
                "end",
                iid=entry.id,
                values=(
                    entry.description,
                    entry.display_address(),
                    type_short,
                    entry.value,
                    "—",
                    "Yes" if entry.frozen else "",
                    entry.hotkey,
                ),
                tags=("frozen",) if entry.frozen else (),
            )
        if select_id and self.table.entry(select_id):
            try:
                self.table_tree.selection_set(select_id)
                self.table_tree.focus(select_id)
            except tk.TclError:
                pass
        self.table_count_var.set(f"{len(self.table.entries)} entr{'y' if len(self.table.entries) == 1 else 'ies'}")
        self._sync_freezer()
        self._register_hotkeys()
        self._update_table_controls()
        self._update_title()
        self._update_live_values()

    def _sync_freezer(self) -> None:
        self.freezer.set_entries(self.table.entries)
        if self.process is not None:
            self.freezer.set_target(self.process)

    def _update_table_controls(self) -> None:
        entry = self._selected_entry()
        has_entry = entry is not None and not self.busy
        for button in (self.edit_button, self.remove_button):
            try:
                button.state(["!disabled"] if has_entry else ["disabled"])
            except tk.TclError:
                pass
        try:
            self.freeze_button.state(
                ["!disabled"] if has_entry else ["disabled"]
            )
            self.freeze_button.configure(text="Unfreeze" if entry and entry.frozen else "Freeze")
            self.apply_button.state(
                ["!disabled"]
                if has_entry and self.process is not None
                else ["disabled"]
            )
        except tk.TclError:
            pass

    def _selected_entry(self) -> TableEntry | None:
        selection = self.table_tree.selection()
        if not selection:
            return None
        return self.table.entry(selection[0])

    def _on_table_selected(self, _event=None) -> None:
        self._update_table_controls()

    def _add_entry(self) -> None:
        if self.busy:
            return
        dialog = EntryDialog(self.root, process=self.process)
        self.root.wait_window(dialog)
        if dialog.result is None:
            return
        self.table.add(dialog.result)
        self._mark_dirty()
        self._refresh_table(select_id=dialog.result.id)
        self._log(f"Added table entry {dialog.result.description!r}.")

    def _edit_entry(self) -> None:
        entry = self._selected_entry()
        if entry is None or self.busy:
            return
        dialog = EntryDialog(self.root, process=self.process, entry=entry)
        self.root.wait_window(dialog)
        if dialog.result is None:
            return
        for index, existing in enumerate(self.table.entries):
            if existing.id == entry.id:
                self.table.entries[index] = dialog.result
                break
        self.table.touch()
        self._mark_dirty()
        self._refresh_table(select_id=dialog.result.id)
        self._log(f"Updated table entry {dialog.result.description!r}.")

    def _remove_entry(self) -> None:
        entry = self._selected_entry()
        if entry is None or self.busy:
            return
        if not messagebox.askyesno(
            "Remove entry",
            f"Remove {entry.description!r} from the table?",
            parent=self.root,
        ):
            return
        self.table.remove(entry.id)
        self._mark_dirty()
        self._refresh_table()
        self._log(f"Removed table entry {entry.description!r}.")

    def _toggle_freeze_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None or self.busy:
            return
        self._toggle_freeze(entry.id)

    def _toggle_freeze(self, entry_id: str) -> None:
        entry = self.table.entry(entry_id)
        if entry is None:
            return
        entry.frozen = not entry.frozen
        self.table.touch()
        self._mark_dirty()
        self._sync_freezer()
        self._refresh_table(select_id=entry.id)
        self._log(f"{'Frozen' if entry.frozen else 'Unfroze'} {entry.description!r}.")

    def _apply_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None or self.process is None or self.busy:
            return
        try:
            address = entry.resolve(self.process)
            data = entry.value_bytes()
            self.process.write(address, data)
        except (ProcessError, ValueError) as exc:
            messagebox.showerror("Write failed", str(exc), parent=self.root)
            self._log(f"Write failed for {entry.description!r}: {exc}", level="error")
            return
        self._log(
            f"Wrote {entry.value_text()} to {entry.description!r} at {format_hex(address)}."
        )
        self._update_live_values()

    def _on_hotkey(self, token: str, hotkey_text: str) -> None:
        entry = self.table.entry(token)
        if entry is None:
            return
        self._toggle_freeze(token)
        self._log(f"Hotkey {hotkey_text}: toggled freeze for {entry.description!r}.")

    def _register_hotkeys(self) -> None:
        mapping = {entry.id: entry.hotkey for entry in self.table.entries if entry.hotkey.strip()}
        errors = self.hotkeys.replace(mapping)
        current = {token: message for token, message in errors}
        for token, message in errors:
            if self._last_hotkey_errors.get(token) != message:
                entry = self.table.entry(token)
                name = entry.description if entry else token
                self._log(f"Hotkey for {name!r}: {message}", level="warning")
        self._last_hotkey_errors = current

    def _clear_live_values(self) -> None:
        for entry in self.table.entries:
            try:
                if self.table_tree.exists(entry.id):
                    self.table_tree.set(entry.id, "live", "—")
            except tk.TclError:
                pass

    def _schedule_live(self) -> None:
        if self.closed:
            return
        self._update_live_values()
        self._live_job = self.root.after(LIVE_UPDATE_MS, self._schedule_live)

    def _update_live_values(self) -> None:
        if self.closed or self.process is None or self.process.closed:
            return
        if self.busy:
            return
        for entry in self.table.entries:
            if not self.table_tree.exists(entry.id):
                continue
            try:
                address = entry.resolve(self.process)
                value_type = entry.value_enum
                value = decode_value(self.process.read(address, value_type.size), value_type)
                text = format_value(value, value_type)
            except Exception:
                text = "—"
            try:
                self.table_tree.set(entry.id, "live", text)
            except tk.TclError:
                return

    # ------------------------------------------------------------------
    # File menu
    # ------------------------------------------------------------------
    def _new_table(self) -> None:
        if not self._maybe_save_changes():
            return
        self.table = Table.new("Untitled")
        self.dirty = False
        self.scan_session = None
        self._clear_results(log_it=False)
        self._refresh_table()
        self._log("Started a new table.")
        self._update_title()

    def _open_table(self) -> None:
        if not self._maybe_save_changes():
            return
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Open TrainerForge table",
            filetypes=[
                ("TrainerForge table", "*.json"),
                ("All files", "*.*"),
            ],
        )
        if filename:
            self._open_table_path(Path(filename), silent=False)

    def _open_table_path(self, path: Path, *, silent: bool) -> None:
        try:
            table = Table.load(path)
        except ValueError as exc:
            if silent:
                self._log(f"Could not open table: {exc}", level="error")
            else:
                messagebox.showerror("Open table", str(exc), parent=self.root)
            return
        self.table = table
        self.dirty = False
        self.config.last_table = str(path)
        self._refresh_table()
        self._log(f"Opened table {table.name!r} ({len(table.entries)} entries) from {path}.")
        if table.process_name:
            self.status_var.set(f"Table is for {table.process_name} — attach that process")
        self._update_title()

    def _save_table(self) -> bool:
        if self.table.path is None:
            return self._save_table_as()
        try:
            path = self.table.save()
        except ValueError as exc:
            messagebox.showerror("Save table", str(exc), parent=self.root)
            self._log(str(exc), level="error")
            return False
        self.dirty = False
        self.config.last_table = str(path)
        self._update_title()
        self._log(f"Saved table to {path}.")
        return True

    def _save_table_as(self) -> bool:
        filename = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save TrainerForge table",
            defaultextension=TABLE_SUFFIX,
            initialfile="my-trainer.tforge.json",
            filetypes=[
                ("TrainerForge table", "*.json"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return False
        try:
            path = self.table.save(filename)
        except ValueError as exc:
            messagebox.showerror("Save table", str(exc), parent=self.root)
            self._log(str(exc), level="error")
            return False
        self.dirty = False
        self.config.last_table = str(path)
        self._update_title()
        self._log(f"Saved table to {path}.")
        return True

    def _maybe_save_changes(self) -> bool:
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved changes",
            "Save changes to the current table before continuing?",
            parent=self.root,
        )
        if answer is None:
            return False
        if answer:
            return self._save_table()
        return True

    def _mark_dirty(self) -> None:
        self.dirty = True
        self._update_title()

    def _update_title(self) -> None:
        marker = " *" if self.dirty else ""
        try:
            self.root.title(f"TrainerForge — {self.table.name}{marker}")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Help / lifecycle
    # ------------------------------------------------------------------
    def _show_safety(self) -> None:
        messagebox.showinfo(
            "Safety and scope",
            "TrainerForge is for single-player and offline games only.\n\n"
            "It does not attach to known anti-cheat components, inject code, "
            "disable protections, or bypass licensing. It has no network "
            "features and no game-specific cheats.\n\n"
            "Memory editing can crash a game or corrupt a save. Back up saves. "
            "You are responsible for complying with game terms and local law.",
            parent=self.root,
        )

    def _show_analysis(self) -> None:
        messagebox.showinfo(
            "How WeMod works — research note",
            "TrainerForge was informed by a clean-room study of a locally "
            "installed WeMod/Wand build. The Electron shell loads a bundled "
            "web UI and native trainer components, including a trainer host, "
            "a Lua executor, and a Cheat Engine-style CELib. Trainers are "
            "delivered by WeMod's cloud service; the catalog, scripts, and "
            "binaries are proprietary and are not used or redistributed here.\n\n"
            "TrainerForge is an independent implementation using Win32 memory "
            "APIs and its own JSON table format. See docs/WEMOD-ANALYSIS.md.",
            parent=self.root,
        )

    def _open_github(self) -> None:
        webbrowser.open("https://github.com/xCaptainTroy/trainerforge")

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About TrainerForge",
            f"TrainerForge {__version__}\n\n"
            "An open-source, local-first memory trainer toolkit for "
            "single-player Windows games.\n\n"
            "MIT licensed. Not affiliated with WeMod, Cheat Engine, or any "
            "game publisher. No telemetry, accounts, ads, or cloud service.",
            parent=self.root,
        )

    def on_close(self) -> None:
        if self.busy:
            messagebox.showinfo(
                "Scan in progress",
                "Cancel the running scan before closing TrainerForge.",
                parent=self.root,
            )
            return
        if not self._maybe_save_changes():
            return
        self.shutdown()

    def smoke_close(self) -> None:
        self.shutdown()

    def shutdown(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            geometry = self.root.winfo_geometry()
            if geometry:
                self.config.window_geometry = geometry
        except tk.TclError:
            pass
        self.config.last_table = str(self.table.path) if self.table.path else ""
        self.config.save()
        try:
            self.hotkeys.stop()
        except Exception:
            pass
        try:
            self.freezer.stop()
        except Exception:
            pass
        if self._live_job is not None:
            try:
                self.root.after_cancel(self._live_job)
            except tk.TclError:
                pass
        if self.process is not None:
            self.freezer.set_target(None)
            self.process.close()
            self.process = None
        try:
            self.root.destroy()
        except tk.TclError:
            pass
