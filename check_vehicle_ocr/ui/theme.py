from __future__ import annotations

import tkinter as tk
from tkinter import ttk


TOKENS = {
    "light": {
        "background": "#F5F7FB",
        "surface": "#FFFFFF",
        "surface_raised": "#FBFCFF",
        "sidebar": "#FAFCFF",
        "surface_hover": "#F0F4FA",
        "surface_selected": "#E5EDFF",
        "border": "#D5DEEA",
        "text_primary": "#152033",
        "text_secondary": "#4B5B70",
        "text_muted": "#56677D",
        "accent": "#2457D6",
        "accent_hover": "#1D46AE",
        "accent_soft": "#E5EDFF",
        "on_accent": "#FFFFFF",
        "success": "#147C4B",
        "warning": "#945A08",
        "danger": "#B3263B",
        "info": "#265FD2",
        "preview": "#101827",
        "disabled_surface": "#E9EEF5",
        "disabled_text": "#6D7C8E",
    },
    "dark": {
        "background": "#10151D",
        "surface": "#171E28",
        "surface_raised": "#1B2430",
        "sidebar": "#141B24",
        "surface_hover": "#202A36",
        "surface_selected": "#263C62",
        "border": "#334356",
        "text_primary": "#F3F7FC",
        "text_secondary": "#C8D3E1",
        "text_muted": "#ABB8C9",
        "accent": "#9AB9FF",
        "accent_hover": "#B7CCFF",
        "accent_soft": "#263C62",
        "on_accent": "#10203D",
        "success": "#78DCAB",
        "warning": "#FFD17C",
        "danger": "#FFABB6",
        "info": "#A9C6FF",
        "preview": "#090F19",
        "disabled_surface": "#202936",
        "disabled_text": "#93A2B5",
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
    medium_font = ("Segoe UI Semibold", 10)
    style.configure("App.TFrame", background=palette["background"])
    style.configure("Surface.TFrame", background=palette["surface"])
    style.configure("Raised.TFrame", background=palette["surface_raised"])
    style.configure("Sidebar.TFrame", background=palette["sidebar"])
    style.configure("Header.TFrame", background=palette["background"])
    style.configure("MetricCard.TFrame", background=palette["surface"], bordercolor=palette["border"], relief="solid", borderwidth=1)
    style.configure("Card.TLabelframe", background=palette["surface"], bordercolor=palette["border"], relief="solid", borderwidth=1, padding=(16, 14))
    style.configure("Card.TLabelframe.Label", background=palette["surface"], foreground=palette["text_primary"], font=medium_font)
    style.configure("TLabel", background=palette["background"], foreground=palette["text_primary"], font=font)
    style.configure("Surface.TLabel", background=palette["surface"], foreground=palette["text_primary"], font=font)
    style.configure("Muted.TLabel", background=palette["background"], foreground=palette["text_secondary"], font=("Segoe UI", 9))
    style.configure("SurfaceMuted.TLabel", background=palette["surface"], foreground=palette["text_secondary"], font=("Segoe UI", 9))
    style.configure("Warning.TLabel", background=palette["surface"], foreground=palette["warning"], font=("Segoe UI", 9, "bold"))
    style.configure("Error.TLabel", background=palette["surface"], foreground=palette["danger"], font=("Segoe UI", 9, "bold"))
    style.configure("Success.TLabel", background=palette["surface"], foreground=palette["success"], font=("Segoe UI", 9, "bold"))
    style.configure("SidebarTitle.TLabel", background=palette["sidebar"], foreground=palette["text_primary"], font=("Segoe UI Semibold", 17))
    style.configure("SidebarSubtitle.TLabel", background=palette["sidebar"], foreground=palette["text_secondary"], font=("Segoe UI", 9))
    style.configure("SidebarStatus.TLabel", background=palette["sidebar"], foreground=palette["text_secondary"], font=("Segoe UI", 9))
    style.configure("AppTitle.TLabel", background=palette["sidebar"], foreground=palette["text_primary"], font=("Segoe UI Semibold", 16))
    style.configure("PageTitle.TLabel", background=palette["background"], foreground=palette["text_primary"], font=("Segoe UI Semibold", 20))
    style.configure("HeaderStatus.TLabel", background=palette["background"], foreground=palette["text_secondary"], font=("Segoe UI", 9))
    style.configure("Section.TLabel", background=palette["surface"], foreground=palette["text_primary"], font=("Segoe UI Semibold", 11))
    style.configure("Metric.TLabel", background=palette["surface"], foreground=palette["accent"], font=("Segoe UI Semibold", 21))
    style.configure("MetricCaption.TLabel", background=palette["surface"], foreground=palette["text_secondary"], font=("Segoe UI", 9))
    style.configure("Nav.TButton", anchor="w", padding=(12, 10), background=palette["sidebar"], foreground=palette["text_secondary"], bordercolor=palette["sidebar"], font=medium_font)
    style.map(
        "Nav.TButton",
        background=[("active", palette["surface_hover"]), ("selected", palette["surface_selected"])],
        foreground=[("selected", palette["accent"]), ("active", palette["text_primary"])],
        bordercolor=[("focus", palette["accent"]), ("selected", palette["surface_selected"])],
    )
    style.configure("Primary.TButton", padding=(16, 9), background=palette["accent"], foreground=palette["on_accent"], bordercolor=palette["accent"], font=medium_font)
    style.map(
        "Primary.TButton",
        background=[("active", palette["accent_hover"]), ("disabled", palette["disabled_surface"])],
        foreground=[("disabled", palette["disabled_text"])],
        bordercolor=[("focus", palette["accent"]), ("disabled", palette["border"])],
    )
    style.configure("TButton", padding=(11, 8), background=palette["surface"], foreground=palette["text_primary"], bordercolor=palette["border"], font=font)
    style.map(
        "TButton",
        background=[("active", palette["surface_hover"]), ("disabled", palette["disabled_surface"])],
        foreground=[("disabled", palette["disabled_text"])],
        bordercolor=[("focus", palette["accent"]), ("disabled", palette["border"])],
    )
    style.configure("Danger.TButton", padding=(14, 8), background=palette["surface"], foreground=palette["danger"], bordercolor=palette["border"], font=medium_font)
    style.map(
        "Danger.TButton",
        background=[("active", palette["surface_hover"]), ("disabled", palette["disabled_surface"])],
        foreground=[("disabled", palette["disabled_text"])],
        bordercolor=[("focus", palette["danger"]), ("active", palette["danger"]), ("disabled", palette["border"])],
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
    style.configure(
        "Plate.TEntry",
        fieldbackground=palette["surface_raised"],
        foreground=palette["text_primary"],
        insertcolor=palette["text_primary"],
        bordercolor=palette["border"],
        font=("Segoe UI Semibold", 14),
        padding=(10, 7),
    )
    style.map(
        "Plate.TEntry",
        fieldbackground=[("focus", palette["surface"]), ("disabled", palette["disabled_surface"])],
        foreground=[("disabled", palette["disabled_text"])],
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
    style.configure("StatusPill.TLabel", background=palette["accent_soft"], foreground=palette["accent"], padding=(9, 4), font=medium_font)
    style.configure("Treeview", background=palette["surface"], fieldbackground=palette["surface"], foreground=palette["text_primary"], rowheight=34, bordercolor=palette["border"], font=("Segoe UI", 9))
    style.map("Treeview", background=[("selected", palette["surface_selected"])], foreground=[("selected", palette["text_primary"])])
    style.configure("Treeview.Heading", background=palette["surface_hover"], foreground=palette["text_primary"], bordercolor=palette["border"], font=medium_font, padding=(10, 8))
    style.configure("TProgressbar", background=palette["accent"], troughcolor=palette["surface_hover"], bordercolor=palette["surface_hover"], thickness=8)
    style.configure("Success.Horizontal.TProgressbar", background=palette["success"], troughcolor=palette["surface_hover"], bordercolor=palette["surface_hover"], thickness=8)
    style.configure("TNotebook", background=palette["background"], bordercolor=palette["border"])
    style.configure("TNotebook.Tab", background=palette["surface"], foreground=palette["text_secondary"], padding=(14, 8), font=medium_font)
    style.map("TNotebook.Tab", background=[("selected", palette["surface_selected"]), ("active", palette["surface_hover"])], foreground=[("selected", palette["accent"]), ("active", palette["text_primary"])])
    style.configure("TSeparator", background=palette["border"])
    # ttk's pop-down Listbox is a Tk widget, not a ttk style.  Configure it
    # explicitly so a closed readonly field and its opened list remain legible.
    root.option_add("*TCombobox*Listbox.background", palette["surface"])
    root.option_add("*TCombobox*Listbox.foreground", palette["text_primary"])
    root.option_add("*TCombobox*Listbox.selectBackground", palette["surface_selected"])
    root.option_add("*TCombobox*Listbox.selectForeground", palette["text_primary"])
    root.option_add("*TCombobox*Listbox.highlightBackground", palette["border"])
