from __future__ import annotations

import tkinter as tk


def attach_tooltip(widget: tk.Misc, text: str) -> None:
    """Show a short, keyboard-neutral explanation after a brief hover."""

    state: dict[str, object] = {"after_id": None, "window": None}

    def hide(_event=None) -> None:
        after_id = state.get("after_id")
        if after_id:
            try:
                widget.after_cancel(str(after_id))
            except tk.TclError:
                pass
        state["after_id"] = None
        window = state.get("window")
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass
        state["window"] = None

    def show() -> None:
        state["after_id"] = None
        if state.get("window") is not None or not widget.winfo_exists():
            return
        window = tk.Toplevel(widget)
        window.wm_overrideredirect(True)
        window.attributes("-topmost", True)
        label = tk.Label(window, text=text, justify="left", padx=8, pady=5, relief="solid", borderwidth=1)
        label.pack()
        window.geometry(f"+{widget.winfo_rootx() + 8}+{widget.winfo_rooty() + widget.winfo_height() + 5}")
        state["window"] = window

    def schedule(_event=None) -> None:
        hide()
        state["after_id"] = widget.after(550, show)

    widget.bind("<Enter>", schedule, add=True)
    widget.bind("<Leave>", hide, add=True)
    widget.bind("<ButtonPress>", hide, add=True)
