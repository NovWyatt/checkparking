"""A small, reusable vertical scroll container for long Tkinter pages."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    """Canvas-backed content frame with wheel, touchpad and keyboard support.

    The wheel handler is intentionally scoped to the widget under the pointer
    (or focus for keyboard navigation), so a separate page never steals input
    and a native Combobox drop-down remains in control of its own list.
    """

    def __init__(self, parent: tk.Misc, *, style: str = "App.TFrame", padding=0):
        super().__init__(parent, style=style)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        palette = getattr(parent.winfo_toplevel(), "_combobox_dropdown_palette", {})
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, bg=palette.get("background", "#F6F7FA"))
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.content = ttk.Frame(self.canvas, style=style, padding=padding)
        self._window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._on_content_configure, add=True)
        self.canvas.bind("<Configure>", self._on_canvas_configure, add=True)
        self.content.bind("<FocusIn>", self._on_focus_in, add=True)
        self.canvas.bind("<MouseWheel>", self._on_wheel, add=True)
        self.canvas.bind("<Shift-MouseWheel>", self._on_wheel, add=True)
        for sequence in ("<Prior>", "<Next>", "<Home>", "<End>"):
            self.canvas.bind(sequence, self._on_key_scroll, add=True)

    def _on_content_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)
        self._on_content_configure()

    def _on_focus_in(self, event) -> None:
        self.after_idle(lambda widget=event.widget: self.scroll_to_widget(widget))

    def _is_descendant(self, widget: tk.Misc | None) -> bool:
        while widget is not None:
            if widget is self.content or widget is self.canvas or widget is self:
                return True
            parent_name = widget.winfo_parent()
            if not parent_name:
                return False
            try:
                widget = widget.nametowidget(parent_name)
            except (KeyError, tk.TclError):
                return False
        return False

    def _on_wheel(self, event) -> str | None:
        event_widget = getattr(event, "widget", None)
        widget = event_widget if self._is_descendant(event_widget) else self.winfo_containing(event.x_root, event.y_root)
        if widget is None or widget.winfo_class() == "Listbox" or not self._is_descendant(widget):
            return None
        delta = int(getattr(event, "delta", 0) or 0)
        if not delta:
            return "break"
        units = max(1, abs(delta) // 120)
        direction = -units if delta > 0 else units
        self.canvas.yview_scroll(direction, "units")
        return "break"

    def _on_key_scroll(self, event) -> str:
        if event.keysym == "Home":
            self.canvas.yview_moveto(0)
        elif event.keysym == "End":
            self.canvas.yview_moveto(1)
        else:
            self.canvas.yview_scroll(-1 if event.keysym == "Prior" else 1, "pages")
        return "break"

    def scroll_to_widget(self, widget: tk.Misc) -> None:
        if not self._is_descendant(widget):
            return
        self.update_idletasks()
        region = self.canvas.bbox("all")
        if not region or region[3] <= self.canvas.winfo_height():
            return
        top = widget.winfo_rooty() - self.canvas.winfo_rooty() + self.canvas.canvasy(0)
        bottom = top + max(1, widget.winfo_height())
        view_top = self.canvas.canvasy(0)
        view_bottom = view_top + self.canvas.winfo_height()
        target = view_top
        if top < view_top:
            target = top
        elif bottom > view_bottom:
            target = bottom - self.canvas.winfo_height()
        target = max(0, min(target, region[3] - self.canvas.winfo_height()))
        self.canvas.yview_moveto(target / max(1, region[3]))

    def refresh_theme(self) -> None:
        palette = getattr(self.winfo_toplevel(), "_combobox_dropdown_palette", {})
        self.canvas.configure(bg=palette.get("background", "#F6F7FA"))
