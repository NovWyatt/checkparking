from __future__ import annotations

from tkinter import ttk

from .base import Page
from ..components.forms import labelled_entry, labelled_spin


class TelegramPage(Page):
    page_title = "Telegram"
    primary_label = "Gửi tin thử"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.columnconfigure(0, weight=1)
        card = ttk.LabelFrame(self, text="Thông báo batch", style="Card.TLabelframe")
        card.grid(row=0, column=0, sticky="new")
        card.columnconfigure(1, weight=1)
        ttk.Checkbutton(card, text="Bật Telegram", variable=controller.telegram_enabled_var).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        token = labelled_entry(card, 1, "Bot token", controller.telegram_bot_token_var, secret=True)
        controller.custom_secret_entries.append(token)
        labelled_entry(card, 2, "Chat ID", controller.telegram_chat_id_var)
        flags = ttk.Frame(card, style="Surface.TFrame")
        flags.grid(row=3, column=0, columnspan=2, sticky="w", pady=6)
        for index, (label, variable) in enumerate((("Bắt đầu", controller.telegram_notify_start_var), ("Tiến trình", controller.telegram_notify_progress_var), ("Hoàn tất", controller.telegram_notify_complete_var), ("Lỗi", controller.telegram_notify_error_var))):
            ttk.Checkbutton(flags, text=label, variable=variable).grid(row=0, column=index, padx=(0, 10))
        labelled_spin(card, 4, "Mỗi %", controller.telegram_progress_step_var, 5, 100, 5)
        labelled_spin(card, 5, "Khoảng cách tối thiểu (giây)", controller.telegram_min_interval_var, 0, 3600, 10)
        ttk.Checkbutton(card, text="Che biển số trong thông báo", variable=controller.telegram_mask_plate_var).grid(row=6, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Button(card, text="Gửi tin thử", command=controller.send_telegram_test, style="Primary.TButton").grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 6))
        ttk.Label(card, textvariable=controller.telegram_status_var, style="SurfaceMuted.TLabel", wraplength=700).grid(row=8, column=0, columnspan=2, sticky="w")
