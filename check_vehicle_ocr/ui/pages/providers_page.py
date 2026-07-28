from __future__ import annotations

from tkinter import ttk

from .base import Page
from ..components.forms import labelled_combo, labelled_entry, labelled_spin


class ProvidersPage(Page):
    page_title = "AI Providers"
    primary_label = "Làm mới model"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.columnconfigure(0, weight=1)
        card = ttk.LabelFrame(self, text="Provider tương thích OpenAI", style="Card.TLabelframe")
        card.grid(row=0, column=0, sticky="new")
        card.columnconfigure(1, weight=1)
        ttk.Checkbutton(card, text="Bật provider custom", variable=controller.custom_provider_enabled_var).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        labelled_entry(card, 1, "Tên cấu hình", controller.custom_provider_name_var)
        labelled_entry(card, 2, "Base URL", controller.custom_base_url_var)
        token = labelled_entry(card, 3, "API key", controller.custom_api_key_var, secret=True)
        controller.custom_secret_entries.append(token)
        ttk.Checkbutton(card, text="Hiện khóa", variable=controller.show_key_var, command=controller._toggle_key_visibility).grid(row=3, column=2, sticky="w", padx=(8, 0))
        controller.custom_model_combo = labelled_combo(card, 4, "Model", controller.custom_model_var, controller.custom_model_values)
        labelled_combo(card, 5, "API mode", controller.custom_api_mode_var, ("auto", "responses", "chat_completions"), readonly=True)
        labelled_spin(card, 6, "Timeout (giây)", controller.provider_timeout_var, 3, 120, 1)
        labelled_spin(card, 7, "API concurrency", controller.api_workers_var, 1, 8, 1)
        actions = ttk.Frame(card, style="Surface.TFrame")
        actions.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        actions.columnconfigure((0, 1), weight=1)
        controller.provider_refresh_button = ttk.Button(actions, text="Làm mới model", command=controller.refresh_provider_models)
        controller.provider_refresh_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        controller.provider_test_button = ttk.Button(actions, text="Kiểm tra kết nối", command=controller.test_provider_connection)
        controller.provider_test_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Label(card, textvariable=controller.provider_status_var, style="SurfaceMuted.TLabel", wraplength=700).grid(row=9, column=0, columnspan=2, sticky="w")
        ttk.Label(card, text="Auto ưu tiên capability cache; chỉ fallback Responses/Chat khi endpoint 404/405. Fallback có thể tạo thêm một request.", style="SurfaceMuted.TLabel", wraplength=700).grid(row=10, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(card, text="Model nhập tay vẫn được giữ nếu không xuất hiện trong danh sách từ provider.", style="SurfaceMuted.TLabel", wraplength=700).grid(row=11, column=0, columnspan=2, sticky="w", pady=(4, 0))
