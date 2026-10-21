"""A compact dark theme for Tk/ttk."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

COLORS = {
    "bg": "#0F1218",
    "header": "#141A24",
    "panel": "#171E2B",
    "panel2": "#202939",
    "panel3": "#2A3548",
    "border": "#2B3648",
    "text": "#E8EDF5",
    "muted": "#96A2B8",
    "dim": "#6E7B91",
    "accent": "#5B8CFF",
    "accent_hover": "#7AA2FF",
    "green": "#3DDC97",
    "amber": "#F6C85F",
    "red": "#FF6B81",
    "purple": "#B48CFF",
    "selection": "#29436F",
    "frozen": "#1D2E2A",
}

FONTS = {
    "body": ("Segoe UI", 10),
    "small": ("Segoe UI", 9),
    "tiny": ("Segoe UI", 8),
    "section": ("Segoe UI Semibold", 11),
    "title": ("Segoe UI Semibold", 19),
    "subtitle": ("Segoe UI", 9),
    "mono": ("Consolas", 9),
}


def apply_theme(root: tk.Tk) -> ttk.Style:
    root.configure(bg=COLORS["bg"])
    root.option_add("*Font", FONTS["body"])
    root.option_add("*TCombobox*Listbox.background", COLORS["panel2"])
    root.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", COLORS["selection"])
    root.option_add("*TCombobox*Listbox.selectForeground", COLORS["text"])
    root.option_add("*Menu.background", COLORS["panel"])
    root.option_add("*Menu.foreground", COLORS["text"])
    root.option_add("*Menu.activeBackground", COLORS["selection"])
    root.option_add("*Menu.activeForeground", COLORS["text"])
    root.option_add("*Menu.selectColor", COLORS["accent"])

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["body"])
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Header.TFrame", background=COLORS["header"])
    style.configure("Status.TFrame", background=COLORS["header"])
    style.configure("Card.TFrame", background=COLORS["panel"])
    style.configure("Inner.TFrame", background=COLORS["panel"])
    style.configure("Toolbar.TFrame", background=COLORS["panel"])

    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("Header.TLabel", background=COLORS["header"], foreground=COLORS["text"])
    style.configure("HeaderMuted.TLabel", background=COLORS["header"], foreground=COLORS["muted"])
    style.configure("Title.TLabel", background=COLORS["header"], foreground=COLORS["text"], font=FONTS["title"])
    style.configure("Subtitle.TLabel", background=COLORS["header"], foreground=COLORS["muted"], font=FONTS["subtitle"])
    style.configure("Card.TLabel", background=COLORS["panel"], foreground=COLORS["text"])
    style.configure("CardMuted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])
    style.configure("CardDim.TLabel", background=COLORS["panel"], foreground=COLORS["dim"], font=FONTS["small"])
    style.configure("Section.TLabel", background=COLORS["panel"], foreground=COLORS["text"], font=FONTS["section"])
    style.configure("Status.TLabel", background=COLORS["header"], foreground=COLORS["muted"], font=FONTS["small"])
    style.configure("StatusValue.TLabel", background=COLORS["header"], foreground=COLORS["text"], font=FONTS["small"])

    style.configure(
        "TButton",
        background=COLORS["panel2"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["panel2"],
        darkcolor=COLORS["panel2"],
        focusthickness=0,
        focuscolor=COLORS["panel2"],
        borderwidth=0,
        padding=(10, 6),
    )
    style.map(
        "TButton",
        background=[("disabled", COLORS["panel"]), ("pressed", COLORS["panel3"]), ("active", COLORS["panel3"])],
        foreground=[("disabled", COLORS["dim"]), ("active", COLORS["text"])],
        bordercolor=[("active", COLORS["accent"])],
    )
    style.configure(
        "Accent.TButton",
        background=COLORS["accent"],
        foreground="#FFFFFF",
        bordercolor=COLORS["accent"],
        lightcolor=COLORS["accent"],
        darkcolor=COLORS["accent"],
        padding=(12, 7),
    )
    style.map(
        "Accent.TButton",
        background=[("disabled", COLORS["panel3"]), ("pressed", COLORS["accent"]), ("active", COLORS["accent_hover"])],
        foreground=[("disabled", COLORS["muted"]), ("active", "#FFFFFF")],
    )
    style.configure(
        "Ghost.TButton",
        background=COLORS["panel"],
        foreground=COLORS["muted"],
        bordercolor=COLORS["panel"],
        padding=(8, 5),
    )
    style.map(
        "Ghost.TButton",
        background=[("active", COLORS["panel2"]), ("pressed", COLORS["panel3"])],
        foreground=[("active", COLORS["text"])],
    )
    style.configure(
        "Danger.TButton",
        background=COLORS["panel2"],
        foreground=COLORS["red"],
        bordercolor=COLORS["border"],
        padding=(8, 5),
    )
    style.map(
        "Danger.TButton",
        background=[("active", "#3A2530")],
        foreground=[("active", COLORS["red"])],
    )
    style.configure(
        "Small.TButton",
        padding=(6, 3),
        font=FONTS["small"],
    )

    style.configure(
        "TEntry",
        fieldbackground=COLORS["panel2"],
        foreground=COLORS["text"],
        insertcolor=COLORS["text"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=(7, 6),
    )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", COLORS["panel"]), ("readonly", COLORS["panel2"])],
        foreground=[("disabled", COLORS["dim"])],
        bordercolor=[("focus", COLORS["accent"])],
    )
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["panel2"],
        background=COLORS["panel2"],
        foreground=COLORS["text"],
        arrowcolor=COLORS["muted"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=(7, 5),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORS["panel2"]), ("disabled", COLORS["panel"])],
        foreground=[("disabled", COLORS["dim"]), ("readonly", COLORS["text"])],
        selectbackground=[("readonly", COLORS["panel2"])],
        selectforeground=[("readonly", COLORS["text"])],
        bordercolor=[("focus", COLORS["accent"])],
    )

    style.configure(
        "Treeview",
        background=COLORS["panel2"],
        fieldbackground=COLORS["panel2"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        borderwidth=0,
        rowheight=26,
        font=FONTS["body"],
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["panel"],
        foreground=COLORS["muted"],
        font=("Segoe UI Semibold", 9),
        relief="flat",
        borderwidth=0,
        padding=(8, 6),
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["selection"])],
        foreground=[("selected", COLORS["text"])],
    )
    style.map(
        "Treeview.Heading",
        background=[("active", COLORS["panel2"])],
        foreground=[("active", COLORS["text"])],
    )

    style.configure(
        "TProgressbar",
        troughcolor=COLORS["panel2"],
        background=COLORS["accent"],
        bordercolor=COLORS["panel2"],
        lightcolor=COLORS["accent"],
        darkcolor=COLORS["accent"],
        thickness=6,
    )
    style.configure(
        "TCheckbutton",
        background=COLORS["panel"],
        foreground=COLORS["text"],
        indicatorcolor=COLORS["panel2"],
        focuscolor=COLORS["panel"],
        padding=(2, 3),
    )
    style.map(
        "TCheckbutton",
        background=[("active", COLORS["panel"])],
        foreground=[("disabled", COLORS["dim"])],
    )
    style.configure(
        "TRadiobutton",
        background=COLORS["panel"],
        foreground=COLORS["text"],
        indicatorcolor=COLORS["panel2"],
        focuscolor=COLORS["panel"],
    )
    style.map("TRadiobutton", background=[("active", COLORS["panel"])])
    style.configure(
        "TScrollbar",
        background=COLORS["panel2"],
        troughcolor=COLORS["panel"],
        arrowcolor=COLORS["muted"],
        bordercolor=COLORS["panel"],
        lightcolor=COLORS["panel2"],
        darkcolor=COLORS["panel2"],
        gripcount=0,
        width=10,
    )
    style.map("TScrollbar", background=[("active", COLORS["panel3"])])
    style.configure("TLabelframe", background=COLORS["panel"], bordercolor=COLORS["border"])
    style.configure(
        "TLabelframe.Label",
        background=COLORS["panel"],
        foreground=COLORS["muted"],
        font=("Segoe UI Semibold", 9),
    )
    style.configure("TPanedwindow", background=COLORS["bg"])
    style.configure("Sash", background=COLORS["border"])

    return style
