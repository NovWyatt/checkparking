from __future__ import annotations

from tkinter import ttk


class Page(ttk.Frame):
    page_title = ""
    primary_label = ""

    def __init__(self, parent, controller):
        super().__init__(parent, style="App.TFrame")
        self.controller = controller

    def on_show(self) -> None:
        pass
