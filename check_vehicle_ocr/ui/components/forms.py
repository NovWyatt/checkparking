from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def labelled_entry(parent: ttk.Frame, row: int, label: str, variable: tk.Variable, *, secret: bool = False, width: int = 28) -> ttk.Entry:
    ttk.Label(parent, text=label, style="Surface.TLabel").grid(row=row, column=0, sticky="w", pady=4)
    entry = ttk.Entry(parent, textvariable=variable, show="*" if secret else "", width=width)
    entry.grid(row=row, column=1, sticky="ew", pady=4)
    return entry


def labelled_combo(parent: ttk.Frame, row: int, label: str, variable: tk.Variable, values, *, readonly: bool = False) -> ttk.Combobox:
    ttk.Label(parent, text=label, style="Surface.TLabel").grid(row=row, column=0, sticky="w", pady=4)
    combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly" if readonly else "normal")
    combo.grid(row=row, column=1, sticky="ew", pady=4)
    return combo


def labelled_spin(parent: ttk.Frame, row: int, label: str, variable: tk.Variable, from_: int, to: int, increment: int = 1) -> ttk.Spinbox:
    ttk.Label(parent, text=label, style="Surface.TLabel").grid(row=row, column=0, sticky="w", pady=4)
    spin = ttk.Spinbox(parent, from_=from_, to=to, increment=increment, textvariable=variable, width=10)
    spin.grid(row=row, column=1, sticky="w", pady=4)
    return spin
