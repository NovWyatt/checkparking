from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .pages import ResultsPage, ScanPage, SettingsPage


class ApplicationShell:
    """Small operator-facing shell.

    Older page names remain accepted as routing aliases so controllers and
    saved workflows do not break, but they no longer create separate pages.
    """

    NAVIGATION = (
        ("scan", "Quét ảnh", "scan"),
        ("results", "Kết quả", "results"),
        ("settings", "Cài đặt", "settings"),
    )
    PAGE_ALIASES = {
        "session": "results",
        "review": "results",
        "export": "results",
        "providers": "settings",
        "telegram": "settings",
        "updates": "settings",
    }

    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        self.pages: dict[str, ttk.Frame] = {}
        self._page_types = {"scan": ScanPage, "results": ResultsPage, "settings": SettingsPage}
        self.nav_buttons: dict[str, ttk.Button] = {}
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)
        self._build_sidebar()
        self._build_header()
        self.content = ttk.Frame(root, style="App.TFrame", padding=(18, 10, 18, 18))
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)
        self._create_page("scan")

    @classmethod
    def canonical_page(cls, name: str) -> str:
        return cls.PAGE_ALIASES.get(name, name)

    def _build_sidebar(self) -> None:
        sidebar = ttk.Frame(self.root, style="Sidebar.TFrame", padding=(10, 14))
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sidebar.columnconfigure(0, weight=1)
        ttk.Label(sidebar, text="Check Vehicle", style="AppTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(sidebar, text="Nhận diện biển số", style="SurfaceMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 18))
        for row, (page, label, icon) in enumerate(self.NAVIGATION, start=2):
            image = self.controller.load_ui_icon(icon)
            button = ttk.Button(sidebar, text=label, image=image, compound="left", style="Nav.TButton", command=lambda name=page: self.show_page(name))
            button.grid(row=row, column=0, sticky="ew", pady=2)
            self.nav_buttons[page] = button
        sidebar.rowconfigure(len(self.NAVIGATION) + 2, weight=1)
        ttk.Label(sidebar, textvariable=self.controller.notification_var, style="SurfaceMuted.TLabel", wraplength=190).grid(
            row=len(self.NAVIGATION) + 3, column=0, sticky="sw"
        )

    def _build_header(self) -> None:
        header = ttk.Frame(self.root, style="App.TFrame", padding=(18, 14, 18, 8))
        header.grid(row=0, column=1, sticky="ew")
        header.columnconfigure(0, weight=1)
        self.title_var = tk.StringVar(value="Quét ảnh")
        ttk.Label(header, textvariable=self.title_var, style="PageTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.controller.header_status_var, style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.action_button = ttk.Button(header, style="Primary.TButton", command=self._primary_action)
        self.action_button.grid(row=0, column=1, rowspan=2, sticky="e")

    def _create_page(self, name: str) -> ttk.Frame:
        page = self.pages.get(name)
        if page is not None:
            return page
        page = self._page_types[name](self.content, self.controller)
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_remove()
        self.pages[name] = page
        return page

    def show_page(self, name: str) -> None:
        name = self.canonical_page(name)
        if name not in self._page_types:
            name = "scan"
        page = self._create_page(name)
        for other in self.pages.values():
            other.grid_remove()
        page.grid()
        self.controller.ui_state.current_page = name
        self.title_var.set(page.page_title)
        self.nav_buttons[name].state(["selected"])
        for other_name, button in self.nav_buttons.items():
            if other_name != name:
                button.state(["!selected"])
        self.refresh_primary_action()
        page.on_show()

    def refresh_primary_action(self) -> None:
        current = self.controller.ui_state.current_page
        if current == "scan":
            running = bool(self.controller.worker and self.controller.worker.is_alive())
            self.action_button.configure(text="Dừng" if running else "Bắt đầu quét")
        elif current == "results":
            self.action_button.configure(text="Xuất Excel")
        else:
            self.action_button.configure(text="Lưu thay đổi")

    def _primary_action(self) -> None:
        page = self.controller.ui_state.current_page
        if page == "scan":
            if self.controller.worker and self.controller.worker.is_alive():
                self.controller.stop_processing()
            else:
                self.controller.start_processing()
        elif page == "results":
            self.controller.export_all_results()
        else:
            self.controller._save_settings()
