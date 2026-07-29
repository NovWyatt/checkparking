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
        "disabled_surface": "#E7EAF0",
        "disabled_text": "#4D5563",
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
        "disabled_surface": "#292D38",
        "disabled_text": "#C5CCD7",
    },
}


def colors(dark_mode: bool) -> dict[str, str]:
    return dict(TOKENS["dark" if dark_mode else "light"])


def configure_styles(root: tk.Misc, palette: dict[str, str], *, initialize_theme: bool = False) -> None:
    style = ttk.Style(root)
    if initialize_theme:
        # ``vista`` can ignore ttk field colours for readonly Comboboxes.  The
        # cross-platform clam renderer respects state maps in both themes.
        for theme in ("clam", "vista", "xpnative"):
            try:
                style.theme_use(theme)
                break
            except tk.TclError:
                continue
    root.configure(bg=palette["background"])
    # `ttk::combobox::PopdownWindow` is a Tk Listbox that some Windows themes
    # render outside ttk's colour map.  Components register a postcommand that
    # reads this palette immediately before the list is opened.
    root._combobox_dropdown_palette = dict(palette)
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
    style.map(
        "Primary.TButton",
        background=[("active", palette["accent_hover"]), ("disabled", palette["disabled_surface"])],
        foreground=[("disabled", palette["disabled_text"])],
        bordercolor=[("focus", palette["accent"]), ("disabled", palette["border"])],
    )
    style.configure("TButton", padding=(10, 7), background=palette["surface"], foreground=palette["text_primary"], bordercolor=palette["border"])
    style.map(
        "TButton",
        background=[("active", palette["surface_hover"]), ("disabled", palette["disabled_surface"])],
        foreground=[("disabled", palette["disabled_text"])],
        bordercolor=[("focus", palette["accent"]), ("disabled", palette["border"])],
    )
    style.configure("TCheckbutton", background=palette["surface"], foreground=palette["text_primary"], font=font)
    style.map("TCheckbutton", foreground=[("disabled", palette["disabled_text"]), ("focus", palette["text_primary"])])
    style.configure("TRadiobutton", background=palette["surface"], foreground=palette["text_primary"], font=font)
    style.map("TRadiobutton", foreground=[("disabled", palette["disabled_text"]), ("focus", palette["text_primary"])])
    style.configure("TEntry", fieldbackground=palette["surface"], foreground=palette["text_primary"], insertcolor=palette["text_primary"], bordercolor=palette["border"])
    style.map(
        "TEntry",
        foreground=[("disabled", palette["disabled_text"]), ("readonly", palette["text_primary"])],
        fieldbackground=[("disabled", palette["disabled_surface"]), ("readonly", palette["surface"]), ("focus", palette["surface"])],
        bordercolor=[("focus", palette["accent"]), ("disabled", palette["border"])],
    )
    combobox_options = {
        "fieldbackground": palette["surface"],
        "foreground": palette["text_primary"],
        "background": palette["surface"],
        "selectbackground": palette["surface_selected"],
        "selectforeground": palette["text_primary"],
        "arrowcolor": palette["text_primary"],
        "bordercolor": palette["border"],
    }
    combobox_map = {
        "foreground": [("disabled", palette["disabled_text"]), ("readonly", palette["text_primary"]), ("focus", palette["text_primary"])],
        "fieldbackground": [("disabled", palette["disabled_surface"]), ("readonly", palette["surface"]), ("focus", palette["surface"])],
        "background": [("disabled", palette["disabled_surface"]), ("readonly", palette["surface"]), ("active", palette["surface_hover"])],
        "selectforeground": [("readonly", palette["text_primary"]), ("focus", palette["text_primary"])],
        "selectbackground": [("readonly", palette["surface_selected"]), ("focus", palette["surface_selected"])],
        "arrowcolor": [("disabled", palette["disabled_text"]), ("readonly", palette["text_primary"]), ("focus", palette["accent"])],
        "bordercolor": [("focus", palette["accent"]), ("active", palette["accent"]), ("disabled", palette["border"])],
    }
    # Keep styling the standard class for existing widgets, but use the
    # explicit operator style for newly created combos.  Some Windows ttk
    # themes otherwise lose the readonly field foreground.
    style.configure(
        "TCombobox",
        **combobox_options,
    )
    style.map("TCombobox", **combobox_map)
    style.configure(
        "Operator.TCombobox",
        **combobox_options,
    )
    style.map("Operator.TCombobox", **combobox_map)
    style.configure("TSpinbox", fieldbackground=palette["surface"], foreground=palette["text_primary"], background=palette["surface"], arrowcolor=palette["text_primary"], bordercolor=palette["border"])
    style.map(
        "TSpinbox",
        foreground=[("disabled", palette["disabled_text"]), ("readonly", palette["text_primary"])],
        fieldbackground=[("disabled", palette["disabled_surface"]), ("readonly", palette["surface"]), ("focus", palette["surface"])],
        background=[("disabled", palette["disabled_surface"]), ("active", palette["surface_hover"])],
        arrowcolor=[("disabled", palette["disabled_text"]), ("focus", palette["accent"])],
        bordercolor=[("focus", palette["accent"]), ("disabled", palette["border"])],
    )
    style.configure("StatusPill.TLabel", background=palette["surface_selected"], foreground=palette["text_primary"], padding=(8, 4), font=("Segoe UI", 9, "bold"))
    style.configure("Treeview", background=palette["surface"], fieldbackground=palette["surface"], foreground=palette["text_primary"], rowheight=30, bordercolor=palette["border"], font=("Segoe UI", 9))
    style.map("Treeview", background=[("selected", palette["surface_selected"])], foreground=[("selected", palette["text_primary"])])
    style.configure("Treeview.Heading", background=palette["surface_hover"], foreground=palette["text_primary"], bordercolor=palette["border"], font=("Segoe UI", 9, "bold"))
    style.configure("TProgressbar", background=palette["accent"], troughcolor=palette["border"], bordercolor=palette["border"])
    style.configure("Success.Horizontal.TProgressbar", background=palette["success"], troughcolor=palette["border"], bordercolor=palette["success"])
    style.configure("TNotebook", background=palette["background"], bordercolor=palette["border"])
    style.configure("TNotebook.Tab", background=palette["surface"], foreground=palette["text_secondary"], padding=(12, 7))
    style.map("TNotebook.Tab", background=[("selected", palette["surface_selected"]), ("active", palette["surface_hover"])], foreground=[("selected", palette["text_primary"])])
    # ttk's pop-down Listbox is a Tk widget, not a ttk style.  Configure it
    # explicitly so a closed readonly field and its opened list remain legible.
    root.option_add("*TCombobox*Listbox.background", palette["surface"])
    root.option_add("*TCombobox*Listbox.foreground", palette["text_primary"])
    root.option_add("*TCombobox*Listbox.selectBackground", palette["surface_selected"])
    root.option_add("*TCombobox*Listbox.selectForeground", palette["text_primary"])
    root.option_add("*TCombobox*Listbox.highlightBackground", palette["border"])
