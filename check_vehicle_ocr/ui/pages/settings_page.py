from __future__ import annotations

from tkinter import ttk

from .base import Page


class SettingsPage(Page):
    page_title = "Cài đặt"
    primary_label = "Lưu cài đặt"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.columnconfigure(0, weight=1)
        card = ttk.LabelFrame(self, text="Giao diện và bảo mật", style="Card.TLabelframe")
        card.grid(row=0, column=0, sticky="new")
        ttk.Checkbutton(card, text="Giao diện tối", variable=controller.dark_mode_var, command=controller._on_theme_toggle).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Checkbutton(card, text="Lưu khóa API cho lần sau", variable=controller.remember_key_var).grid(row=1, column=0, sticky="w", pady=4)
        ttk.Button(card, text="Lưu cài đặt ngay", command=controller._save_settings, style="Primary.TButton").grid(row=2, column=0, sticky="w", pady=(12, 4))
        ttk.Button(card, text="Xóa khóa đã lưu", command=controller.clear_saved_key).grid(row=3, column=0, sticky="w")
        ttk.Label(card, textvariable=controller.key_status_var, style="SurfaceMuted.TLabel", wraplength=700).grid(row=4, column=0, sticky="w", pady=(10, 0))
