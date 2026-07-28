from __future__ import annotations

import tkinter as tk
from tkinter import ttk


TOKENS = {
    "light": {
        "background": "#F7F8FA",
        "surface": "#FFFFFF",
        "surface_hover": "#F1F3F7",
        "surface_selected": "#E9ECF5",
        "border": "#DEE1E8",
        "text_primary": "#1B1D24",
        "text_secondary": "#656B78",
        "text_muted": "#8A91A0",
        "accent": "#5865F2",
        "accent_hover": "#4753D7",
        "on_accent": "#FFFFFF",
        "success": "#208A5B",
        "warning": "#B7791F",
        "danger": "#C43D4B",
        "info": "#3273DC",
        "preview": "#17181D",
    },
    "dark": {
        "background": "#15161A",
        "surface": "#1D1E24",
        "surface_hover": "#252731",
        "surface_selected": "#272A35",
        "border": "#30323D",
        "text_primary": "#F1F3F8",
        "text_secondary": "#A9AFBC",
        "text_muted": "#747B8B",
        "accent": "#8892FF",
        "accent_hover": "#A1A9FF",
        "on_accent": "#16182A",
        "success": "#55B987",
        "warning": "#E7B45F",
        "danger": "#F07784",
        "info": "#7DAAFF",
        "preview": "#08090C",
    },
}


def colors(dark_mode: bool) -> dict[str, str]:
    return dict(TOKENS["dark" if dark_mode else "light"])


def configure_styles(root: tk.Misc, palette: dict[str, str], *, initialize_theme: bool = False) -> None:
    style = ttk.Style(root)
    if initialize_theme:
        for theme in ("clam", "vista", "xpnative"):
            try:
                style.theme_use(theme)
                break
            except tk.TclError:
                continue
    root.configure(bg=palette["background"])
    font = ("Segoe UI", 10)
    style.configure("App.TFrame", background=palette["background"])
    style.configure("Surface.TFrame", background=palette["surface"])
    style.configure("Sidebar.TFrame", background=palette["surface"])
    style.configure("Card.TLabelframe", background=palette["surface"], bordercolor=palette["border"], relief="solid", padding=12)
    style.configure("Card.TLabelframe.Label", background=palette["surface"], foreground=palette["text_primary"], font=("Segoe UI", 10, "bold"))
    style.configure("TLabel", background=palette["background"], foreground=palette["text_primary"], font=font)
    style.configure("Surface.TLabel", background=palette["surface"], foreground=palette["text_primary"], font=font)
    style.configure("Muted.TLabel", background=palette["background"], foreground=palette["text_secondary"], font=("Segoe UI", 9))
    style.configure("SurfaceMuted.TLabel", background=palette["surface"], foreground=palette["text_secondary"], font=("Segoe UI", 9))
    style.configure("AppTitle.TLabel", background=palette["surface"], foreground=palette["text_primary"], font=("Segoe UI", 15, "bold"))
    style.configure("PageTitle.TLabel", background=palette["background"], foreground=palette["text_primary"], font=("Segoe UI", 16, "bold"))
    style.configure("Section.TLabel", background=palette["surface"], foreground=palette["text_primary"], font=("Segoe UI", 11, "bold"))
    style.configure("Metric.TLabel", background=palette["surface"], foreground=palette["accent"], font=("Segoe UI", 16, "bold"))
    style.configure("Nav.TButton", anchor="w", padding=(12, 8), background=palette["surface"], foreground=palette["text_secondary"], bordercolor=palette["surface"])
    style.map("Nav.TButton", background=[("active", palette["surface_hover"]), ("selected", palette["surface_selected"])], foreground=[("selected", palette["text_primary"])])
    style.configure("Primary.TButton", padding=(14, 8), background=palette["accent"], foreground=palette["on_accent"], bordercolor=palette["accent"], font=("Segoe UI", 10, "bold"))
    style.map("Primary.TButton", background=[("active", palette["accent_hover"]), ("disabled", palette["border"])], foreground=[("disabled", palette["text_muted"])])
    style.configure("TButton", padding=(10, 7), background=palette["surface"], foreground=palette["text_primary"], bordercolor=palette["border"])
    style.map("TButton", background=[("active", palette["surface_hover"]), ("disabled", palette["background"])], foreground=[("disabled", palette["text_muted"])])
    style.configure("TCheckbutton", background=palette["surface"], foreground=palette["text_primary"], font=font)
    style.configure("TEntry", fieldbackground=palette["surface"], foreground=palette["text_primary"], insertcolor=palette["text_primary"], bordercolor=palette["border"])
    style.configure("TCombobox", fieldbackground=palette["surface"], foreground=palette["text_primary"], background=palette["surface"], bordercolor=palette["border"])
    style.configure("TSpinbox", fieldbackground=palette["surface"], foreground=palette["text_primary"], background=palette["surface"], bordercolor=palette["border"])
    style.configure("Treeview", background=palette["surface"], fieldbackground=palette["surface"], foreground=palette["text_primary"], rowheight=30, bordercolor=palette["border"], font=("Segoe UI", 9))
    style.map("Treeview", background=[("selected", palette["surface_selected"])], foreground=[("selected", palette["text_primary"])])
    style.configure("Treeview.Heading", background=palette["surface_hover"], foreground=palette["text_primary"], bordercolor=palette["border"], font=("Segoe UI", 9, "bold"))
    style.configure("TProgressbar", background=palette["accent"], troughcolor=palette["border"], bordercolor=palette["border"])
