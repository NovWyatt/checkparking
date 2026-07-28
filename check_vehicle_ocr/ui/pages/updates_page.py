from __future__ import annotations

from tkinter import ttk

from .base import Page
from ..components.forms import labelled_entry


class UpdatesPage(Page):
    page_title = "Cập nhật"
    primary_label = "Kiểm tra cập nhật"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.columnconfigure(0, weight=1)
        card = ttk.LabelFrame(self, text="Cập nhật an toàn", style="Card.TLabelframe")
        card.grid(row=0, column=0, sticky="new")
        card.columnconfigure(1, weight=1)
        ttk.Label(card, textvariable=controller.update_version_var, style="Surface.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        labelled_entry(card, 1, "Manifest URL", controller.update_manifest_url_var)
        ttk.Label(card, text="Để trống nếu chưa có máy chủ release. Có thể dùng manifest local/mock khi kiểm thử.", style="SurfaceMuted.TLabel", wraplength=700).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 8))
        actions = ttk.Frame(card, style="Surface.TFrame")
        actions.grid(row=3, column=0, columnspan=2, sticky="ew")
        actions.columnconfigure((0, 1), weight=1)
        controller.update_check_button = ttk.Button(actions, text="Kiểm tra cập nhật", command=controller.check_for_updates, style="Primary.TButton")
        controller.update_check_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        controller.update_download_button = ttk.Button(actions, text="Tải và xác minh", command=controller.download_update, state="disabled")
        controller.update_download_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Label(card, textvariable=controller.update_status_var, style="SurfaceMuted.TLabel", wraplength=700).grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Label(card, textvariable=controller.update_notes_var, style="SurfaceMuted.TLabel", wraplength=700).grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(card, text="Giai đoạn này chỉ kiểm tra/tải và xác minh checksum. App không tự thay executable hoặc tự cài cập nhật.", style="SurfaceMuted.TLabel", wraplength=700).grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
