from __future__ import annotations

from tkinter import ttk

from .base import Page
from ..components.forms import labelled_combo, labelled_entry, labelled_spin


class SettingsPage(Page):
    page_title = "Cài đặt"
    primary_label = "Lưu thay đổi"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        controller.settings_notebook = self.notebook
        self.tabs: dict[str, ttk.Frame] = {}
        for key, title in (
            ("general", "Chung"),
            ("ai", "AI trực tuyến"),
            ("notifications", "Thông báo"),
            ("updates", "Cập nhật"),
            ("advanced", "Nâng cao"),
        ):
            tab = ttk.Frame(self.notebook, style="App.TFrame", padding=12)
            tab.columnconfigure(0, weight=1)
            self.notebook.add(tab, text=title)
            self.tabs[key] = tab
        self._build_general(self.tabs["general"], controller)
        self._build_ai(self.tabs["ai"], controller)
        self._build_notifications(self.tabs["notifications"], controller)
        self._build_updates(self.tabs["updates"], controller)
        self._build_advanced(self.tabs["advanced"], controller)

    @staticmethod
    def _card(parent, title: str):
        card = ttk.LabelFrame(parent, text=title, style="Card.TLabelframe")
        card.grid(sticky="ew", pady=(0, 12))
        card.columnconfigure(1, weight=1)
        return card

    def _build_general(self, parent, controller) -> None:
        card = self._card(parent, "Giao diện và xuất Excel")
        ttk.Checkbutton(card, text="Giao diện tối", variable=controller.dark_mode_var, command=controller._on_theme_toggle).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
        labelled_entry(card, 1, "Thư mục xuất mặc định", controller.output_dir_var)
        ttk.Button(card, text="Chọn thư mục", command=controller.choose_output_directory).grid(row=2, column=1, sticky="w", pady=(2, 6))
        ttk.Checkbutton(card, text="Nhúng ảnh và crop vào Excel (file lớn hơn)", variable=controller.embed_excel_images_var).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=4
        )
        ttk.Checkbutton(card, text="Lưu khóa API cho lần sau", variable=controller.remember_key_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Button(card, text="Xóa khóa đã lưu", command=controller.clear_saved_key).grid(row=5, column=0, sticky="w", pady=(8, 2))
        ttk.Label(card, textvariable=controller.key_status_var, style="SurfaceMuted.TLabel", wraplength=700).grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _build_ai(self, parent, controller) -> None:
        card = self._card(parent, "Dịch vụ AI trực tuyến")
        ttk.Label(card, text="Chỉ cần cấu hình phần này khi bạn chọn AI trực tuyến hoặc AI kiểm tra ảnh khó.", style="SurfaceMuted.TLabel", wraplength=760).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        ttk.Checkbutton(card, text="Bật dịch vụ AI trực tuyến", variable=controller.custom_provider_enabled_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
        labelled_entry(card, 2, "Tên dịch vụ", controller.custom_provider_name_var)
        labelled_entry(card, 3, "Địa chỉ dịch vụ", controller.custom_base_url_var)
        token = labelled_entry(card, 4, "Khóa API", controller.custom_api_key_var, secret=True)
        controller.custom_secret_entries.append(token)
        ttk.Checkbutton(card, text="Hiện khóa", variable=controller.show_key_var, command=controller._toggle_key_visibility).grid(row=4, column=2, sticky="w", padx=(8, 0))
        controller.custom_model_combo = labelled_combo(card, 5, "Model", controller.custom_model_var, controller.custom_model_values)
        actions = ttk.Frame(card, style="Surface.TFrame")
        actions.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        actions.columnconfigure((0, 1), weight=1)
        controller.provider_refresh_button = ttk.Button(actions, text="Làm mới danh sách model", command=controller.refresh_provider_models)
        controller.provider_refresh_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        controller.provider_test_button = ttk.Button(actions, text="Kiểm tra kết nối", command=controller.test_provider_connection)
        controller.provider_test_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Label(card, textvariable=controller.provider_status_var, style="SurfaceMuted.TLabel", wraplength=760).grid(row=7, column=0, columnspan=3, sticky="w")

        advanced = ttk.LabelFrame(parent, text="Tùy chọn kết nối nâng cao", style="Card.TLabelframe")
        advanced.grid(sticky="ew", pady=(0, 12))
        advanced.columnconfigure(1, weight=1)
        labelled_combo(advanced, 0, "Cách gọi API", controller.custom_api_mode_var, ("auto", "responses", "chat_completions"), readonly=True)
        labelled_spin(advanced, 1, "Thời gian chờ (giây)", controller.provider_timeout_var, 3, 120, 1)
        ttk.Label(
            advanced,
            text="Tự động chỉ thử cách gọi thay thế khi dịch vụ báo endpoint không hỗ trợ (404/405). Không thử lại khi lỗi xác thực.",
            style="SurfaceMuted.TLabel",
            wraplength=760,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

    def _build_notifications(self, parent, controller) -> None:
        card = self._card(parent, "Thông báo Telegram")
        ttk.Checkbutton(card, text="Bật Telegram", variable=controller.telegram_enabled_var).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        token = labelled_entry(card, 1, "Bot token", controller.telegram_bot_token_var, secret=True)
        controller.custom_secret_entries.append(token)
        labelled_entry(card, 2, "Chat ID", controller.telegram_chat_id_var)
        flags = ttk.Frame(card, style="Surface.TFrame")
        flags.grid(row=3, column=0, columnspan=2, sticky="w", pady=6)
        for index, (label, variable) in enumerate(
            (("Bắt đầu", controller.telegram_notify_start_var), ("Tiến trình", controller.telegram_notify_progress_var), ("Hoàn tất", controller.telegram_notify_complete_var), ("Lỗi", controller.telegram_notify_error_var))
        ):
            ttk.Checkbutton(flags, text=label, variable=variable).grid(row=0, column=index, padx=(0, 10))
        labelled_spin(card, 4, "Báo tiến trình mỗi (%)", controller.telegram_progress_step_var, 5, 100, 5)
        labelled_spin(card, 5, "Khoảng cách tối thiểu (giây)", controller.telegram_min_interval_var, 0, 3600, 10)
        ttk.Checkbutton(card, text="Che biển số trong thông báo", variable=controller.telegram_mask_plate_var).grid(row=6, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Button(card, text="Gửi tin thử", command=controller.send_telegram_test, style="Primary.TButton").grid(row=7, column=0, sticky="w", pady=(8, 6))
        ttk.Label(card, textvariable=controller.telegram_status_var, style="SurfaceMuted.TLabel", wraplength=760).grid(row=8, column=0, columnspan=2, sticky="w")

    def _build_updates(self, parent, controller) -> None:
        parent.columnconfigure((0, 1), weight=1)
        app_card = self._card(parent, "1. Ứng dụng Check Vehicle OCR")
        ttk.Label(app_card, textvariable=controller.update_version_var, style="Surface.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        labelled_entry(app_card, 1, "Nguồn cập nhật", controller.update_manifest_url_var)
        ttk.Label(app_card, text="Chưa cấu hình nguồn cập nhật ứng dụng." if not controller.update_manifest_url_var.get().strip() else "Nguồn được kiểm tra khi bạn bấm nút bên dưới.", style="SurfaceMuted.TLabel", wraplength=500).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 8)
        )
        actions = ttk.Frame(app_card, style="Surface.TFrame")
        actions.grid(row=3, column=0, columnspan=2, sticky="ew")
        actions.columnconfigure((0, 1), weight=1)
        controller.update_check_button = ttk.Button(actions, text="Kiểm tra bản mới", command=controller.check_for_updates, style="Primary.TButton")
        controller.update_check_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        controller.update_download_button = ttk.Button(actions, text="Tải gói đã xác minh", command=controller.download_update, state="disabled")
        controller.update_download_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Label(app_card, textvariable=controller.update_status_var, style="SurfaceMuted.TLabel", wraplength=500).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(app_card, textvariable=controller.update_notes_var, style="SurfaceMuted.TLabel", wraplength=500).grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

        paddle_card = self._card(parent, "2. PaddleOCR")
        ttk.Label(paddle_card, textvariable=controller.paddle_runtime_var, style="Surface.TLabel", wraplength=500).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(paddle_card, textvariable=controller.paddle_compatibility_var, style="SurfaceMuted.TLabel", wraplength=500).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 6))
        ttk.Label(paddle_card, textvariable=controller.paddle_release_source_var, style="SurfaceMuted.TLabel", wraplength=500).grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Button(paddle_card, text="Kiểm tra bản mới", command=controller.check_paddle_updates).grid(row=3, column=0, sticky="w", pady=(6, 0))
        controller.paddle_stage_button = ttk.Button(paddle_card, text="Xem kế hoạch kiểm thử", command=controller.prepare_paddle_staging, state="disabled")
        controller.paddle_stage_button.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        ttk.Label(paddle_card, textvariable=controller.paddle_update_status_var, style="SurfaceMuted.TLabel", wraplength=500).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(paddle_card, textvariable=controller.paddle_release_notes_var, style="SurfaceMuted.TLabel", wraplength=500).grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(
            paddle_card,
            text="Không cập nhật trực tiếp môi trường đang chạy. Chỉ thử nghiệm bản release/tag cụ thể trong môi trường riêng, rồi smoke test và benchmark trước khi chuyển phiên bản.",
            style="SurfaceMuted.TLabel",
            wraplength=500,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))

        model_card = self._card(parent, "3. Model PaddleOCR")
        ttk.Label(model_card, textvariable=controller.model_inventory_var, style="Surface.TLabel", wraplength=500).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(model_card, textvariable=controller.model_update_status_var, style="SurfaceMuted.TLabel", wraplength=500).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(
            model_card,
            text="Model mới phải được tải vào thư mục phiên bản riêng, kiểm checksum và chạy smoke/benchmark trước khi kích hoạt. Không ghi đè model cũ.",
            style="SurfaceMuted.TLabel",
            wraplength=500,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        tesseract_card = self._card(parent, "4. Tesseract dự phòng")
        ttk.Label(tesseract_card, textvariable=controller.tesseract_status_var, style="Surface.TLabel", wraplength=500).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Button(tesseract_card, text="Kiểm tra trạng thái", command=controller.refresh_tesseract_status).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(
            tesseract_card,
            text="Tesseract là OCR dự phòng và không bắt buộc khi PaddleOCR hoạt động. Ứng dụng không tự tải hoặc tự cài Tesseract.",
            style="SurfaceMuted.TLabel",
            wraplength=500,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        app_card.grid_configure(row=0, column=0, sticky="nsew", padx=(0, 6))
        paddle_card.grid_configure(row=0, column=1, sticky="nsew", padx=(6, 0))
        model_card.grid_configure(row=1, column=0, sticky="nsew", padx=(0, 6))
        tesseract_card.grid_configure(row=1, column=1, sticky="nsew", padx=(6, 0))

    def _build_advanced(self, parent, controller) -> None:
        workers = self._card(parent, "Hiệu năng và xử lý kỹ thuật")
        ttk.Label(workers, text="Các thông số này dành cho người có kinh nghiệm. Cài đặt Hiệu năng ở trang Quét ảnh là lựa chọn nên dùng.", style="SurfaceMuted.TLabel", wraplength=760).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        labelled_spin(workers, 1, "Xử lý ảnh song song", controller.image_workers_var, 1, max(1, controller.cpu_count), 1)
        controller.local_ocr_workers_advanced_spin = labelled_spin(workers, 2, "OCR cục bộ — PaddleOCR", controller.local_ocr_workers_var, 1, 1, 1)
        labelled_spin(workers, 3, "Yêu cầu AI song song", controller.api_workers_var, 1, 8, 1)
        labelled_spin(workers, 4, "Hàng chờ tối đa", controller.queue_capacity_var, 1, 128, 1)
        labelled_spin(workers, 5, "Ngưỡng tin cậy", controller.conf_threshold_var, 10, 95, 5)
        labelled_spin(workers, 6, "Ngưỡng ảnh mờ", controller.blur_threshold_var, 10, 500, 5)
        labelled_entry(workers, 7, "Nguồn manifest model", controller.model_manifest_url_var)

        fallback = self._card(parent, "OCR dự phòng — Tesseract")
        ttk.Checkbutton(fallback, text="Cho phép dùng Tesseract khi AI trực tuyến không đọc được", variable=controller.tesseract_fallback_enabled_var).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )
        labelled_entry(fallback, 1, "Đường dẫn Tesseract", controller.tesseract_var)
        ttk.Button(fallback, text="Chọn tesseract.exe", command=controller.choose_tesseract).grid(row=2, column=1, sticky="w", pady=(2, 0))
        ttk.Label(fallback, textvariable=controller.tesseract_status_var, style="SurfaceMuted.TLabel", wraplength=760).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def on_show(self) -> None:
        self.controller.refresh_update_center_state()
        self.controller.refresh_tesseract_status()
