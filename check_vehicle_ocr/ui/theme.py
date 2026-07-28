from __future__ import annotations

import tkinter as tk
from tkinter import ttk


TOKENS = {
    "light": {
        "background": "#F6F7FA",
        "surface": "#FFFFFF",
        "surface_hover": "#F0F2F6",
        "surface_selected": "#E4E8F3",
        "border": "#C8CDD8",
        "text_primary": "#171923",
        "text_secondary": "#4D5563",
        "text_muted": "#596271",
        "accent": "#4C5CCB",
        "accent_hover": "#3F4DB0",
        "on_accent": "#FFFFFF",
        "success": "#146C45",
        "warning": "#8A5709",
        "danger": "#B42335",
        "info": "#245DC1",
        "preview": "#111319",
    },
    "dark": {
        "background": "#121318",
        "surface": "#1C1E25",
        "surface_hover": "#262933",
        "surface_selected": "#303442",
        "border": "#4B5060",
        "text_primary": "#F5F7FB",
        "text_secondary": "#CDD3DD",
        "text_muted": "#B6BECA",
        "accent": "#AEB6FF",
        "accent_hover": "#C1C7FF",
        "on_accent": "#14172B",
        "success": "#78D6A5",
        "warning": "#FFD080",
        "danger": "#FF9EAA",
        "info": "#9DC1FF",
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
    style.configure("Warning.TLabel", background=palette["surface"], foreground=palette["warning"], font=("Segoe UI", 9, "bold"))
    style.configure("Error.TLabel", background=palette["surface"], foreground=palette["danger"], font=("Segoe UI", 9, "bold"))
    style.configure("Success.TLabel", background=palette["surface"], foreground=palette["success"], font=("Segoe UI", 9, "bold"))
    style.configure("AppTitle.TLabel", background=palette["surface"], foreground=palette["text_primary"], font=("Segoe UI", 15, "bold"))
    style.configure("PageTitle.TLabel", background=palette["background"], foreground=palette["text_primary"], font=("Segoe UI", 16, "bold"))
    style.configure("Section.TLabel", background=palette["surface"], foreground=palette["text_primary"], font=("Segoe UI", 11, "bold"))
    style.configure("Metric.TLabel", background=palette["surface"], foreground=palette["accent"], font=("Segoe UI", 16, "bold"))
    style.configure("Nav.TButton", anchor="w", padding=(12, 8), background=palette["surface"], foreground=palette["text_secondary"], bordercolor=palette["surface"])
    style.map("Nav.TButton", background=[("active", palette["surface_hover"]), ("selected", palette["surface_selected"])], foreground=[("selected", palette["text_primary"])])
    style.configure("Primary.TButton", padding=(14, 8), background=palette["accent"], foreground=palette["on_accent"], bordercolor=palette["accent"], font=("Segoe UI", 10, "bold"))
    style.map("Primary.TButton", background=[("active", palette["accent_hover"]), ("disabled", palette["border"])], foreground=[("disabled", palette["text_secondary"])])
    style.configure("TButton", padding=(10, 7), background=palette["surface"], foreground=palette["text_primary"], bordercolor=palette["border"])
    style.map("TButton", background=[("active", palette["surface_hover"]), ("disabled", palette["background"])], foreground=[("disabled", palette["text_secondary"])])
    style.configure("TCheckbutton", background=palette["surface"], foreground=palette["text_primary"], font=font)
    style.configure("TEntry", fieldbackground=palette["surface"], foreground=palette["text_primary"], insertcolor=palette["text_primary"], bordercolor=palette["border"])
    style.configure("TCombobox", fieldbackground=palette["surface"], foreground=palette["text_primary"], background=palette["surface"], bordercolor=palette["border"])
    style.configure("TSpinbox", fieldbackground=palette["surface"], foreground=palette["text_primary"], background=palette["surface"], bordercolor=palette["border"])
    style.configure("Treeview", background=palette["surface"], fieldbackground=palette["surface"], foreground=palette["text_primary"], rowheight=30, bordercolor=palette["border"], font=("Segoe UI", 9))
    style.map("Treeview", background=[("selected", palette["surface_selected"])], foreground=[("selected", palette["text_primary"])])
    style.configure("Treeview.Heading", background=palette["surface_hover"], foreground=palette["text_primary"], bordercolor=palette["border"], font=("Segoe UI", 9, "bold"))
    style.configure("TProgressbar", background=palette["accent"], troughcolor=palette["border"], bordercolor=palette["border"])
    style.configure("TNotebook", background=palette["background"], bordercolor=palette["border"])
    style.configure("TNotebook.Tab", background=palette["surface"], foreground=palette["text_secondary"], padding=(12, 7))
    style.map("TNotebook.Tab", background=[("selected", palette["surface_selected"]), ("active", palette["surface_hover"])], foreground=[("selected", palette["text_primary"])])
