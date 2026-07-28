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
        heading = ttk.Frame(parent, style="App.TFrame")
        heading.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        heading.columnconfigure(0, weight=1)
        ttk.Label(heading, text="Cập nhật", style="PageTitle.TLabel").grid(row=0, column=0, sticky="w")
        controller.check_all_button = ttk.Button(heading, text="Kiểm tra tất cả", command=controller.check_all_updates, style="Primary.TButton")
        controller.check_all_button.grid(row=0, column=1, sticky="e")

        app_card = self._card(parent, "Ứng dụng Check Vehicle OCR")
        ttk.Label(app_card, textvariable=controller.update_version_var, style="Surface.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(app_card, textvariable=controller.update_status_var, style="SurfaceMuted.TLabel", wraplength=410).grid(row=1, column=0, sticky="w", pady=(4, 8))
        controller.update_check_button = ttk.Button(app_card, text="Thiết lập nguồn", command=controller.configure_update_source, style="Primary.TButton")
        controller.update_check_button.grid(row=2, column=0, sticky="w")
        ttk.Button(app_card, text="Chi tiết", command=controller.configure_update_source).grid(row=2, column=1, sticky="e")
        # Application download uses the same, stateful primary action.  There
        # is never a second, disabled download button competing with it.
        controller.update_download_button = None

        paddle_card = self._card(parent, "PaddleOCR")
        ttk.Label(paddle_card, textvariable=controller.paddle_runtime_var, style="Surface.TLabel", wraplength=410).grid(row=0, column=0, sticky="w")
        ttk.Label(paddle_card, textvariable=controller.paddle_update_status_var, style="SurfaceMuted.TLabel", wraplength=410).grid(row=1, column=0, sticky="w", pady=(4, 8))
        controller.paddle_stage_button = ttk.Button(paddle_card, text="Kiểm tra", command=controller.check_paddle_updates, style="Primary.TButton")
        controller.paddle_stage_button.grid(row=2, column=0, sticky="w")
        ttk.Button(paddle_card, text="Chi tiết", command=controller.show_paddle_update_details).grid(row=2, column=1, sticky="e")

        model_card = self._card(parent, "Model OCR")
        ttk.Label(model_card, textvariable=controller.model_inventory_var, style="Surface.TLabel", wraplength=410).grid(row=0, column=0, sticky="w")
        ttk.Label(model_card, textvariable=controller.model_update_status_var, style="SurfaceMuted.TLabel", wraplength=410).grid(row=1, column=0, sticky="w", pady=(4, 8))
        controller.model_manage_button = ttk.Button(model_card, text="Quản lý model", command=controller.manage_models, style="Primary.TButton")
        controller.model_manage_button.grid(row=2, column=0, sticky="w")
        ttk.Button(model_card, text="Chi tiết", command=controller.manage_models).grid(row=2, column=1, sticky="e")

        tesseract_card = self._card(parent, "Tesseract dự phòng")
        ttk.Label(tesseract_card, textvariable=controller.tesseract_status_var, style="Surface.TLabel", wraplength=410).grid(row=0, column=0, sticky="w")
        ttk.Label(tesseract_card, text="Không bắt buộc khi PaddleOCR hoạt động.", style="SurfaceMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 8))
        controller.tesseract_manage_button = ttk.Button(tesseract_card, text="Cài hoặc chọn", command=controller.manage_tesseract, style="Primary.TButton")
        controller.tesseract_manage_button.grid(row=2, column=0, sticky="w")
        ttk.Button(tesseract_card, text="Chi tiết", command=controller.manage_tesseract).grid(row=2, column=1, sticky="e")

        details_toggle = ttk.Button(parent, text="Hiển thị chi tiết kỹ thuật")
        details_toggle.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        details = ttk.LabelFrame(parent, text="Chi tiết kỹ thuật", style="Card.TLabelframe")
        details.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        details.columnconfigure(1, weight=1)
        labelled_combo(details, 0, "Nguồn ứng dụng", controller.update_source_mode_var, ("Tắt cập nhật", "GitHub Releases", "Manifest tùy chỉnh"), readonly=True)
        labelled_entry(details, 1, "Repository GitHub", controller.github_repository_var)
        token = labelled_entry(details, 2, "GitHub token (repo private, tùy chọn)", controller.github_token_var, secret=True)
        controller.custom_secret_entries.append(token)
        labelled_entry(details, 3, "Manifest tùy chỉnh", controller.update_manifest_url_var)
        labelled_entry(details, 4, "PaddleOCR thử nghiệm", controller.paddle_candidate_version_var)
        labelled_entry(details, 5, "Nguồn model", controller.model_manifest_url_var)
        labelled_entry(details, 6, "Nguồn gói Tesseract", controller.tesseract_manifest_url_var)
        actions = ttk.Frame(details, style="Surface.TFrame")
        actions.grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))
        controller.paddle_activate_button = ttk.Button(actions, text="Dùng bản đã thử ở lần mở sau", command=controller.activate_paddle_runtime, state="disabled")
        controller.paddle_activate_button.grid(row=0, column=0, sticky="w", padx=(0, 6))
        controller.paddle_rollback_button = ttk.Button(actions, text="Quay lại bản PaddleOCR trước", command=controller.rollback_paddle_runtime)
        controller.paddle_rollback_button.grid(row=0, column=1, sticky="w")
        controller.model_activate_button = ttk.Button(actions, text="Dùng model đã thử", command=controller.activate_staged_model, state="disabled")
        controller.model_activate_button.grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(6, 0))
        controller.model_rollback_button = ttk.Button(actions, text="Quay lại model trước", command=controller.rollback_staged_model)
        controller.model_rollback_button.grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Label(details, textvariable=controller.update_notes_var, style="SurfaceMuted.TLabel", wraplength=760).grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

        def toggle_details() -> None:
            if details.winfo_ismapped():
                details.grid_remove()
                details_toggle.configure(text="Hiển thị chi tiết kỹ thuật")
            else:
                details.grid()
                details_toggle.configure(text="Ẩn chi tiết kỹ thuật")

        details_toggle.configure(command=toggle_details)
        controller.toggle_update_technical_details = toggle_details
        controller.update_technical_details_visible = details.winfo_ismapped
        details.grid_remove()

        app_card.grid_configure(row=1, column=0, sticky="nsew", padx=(0, 6))
        paddle_card.grid_configure(row=1, column=1, sticky="nsew", padx=(6, 0))
        model_card.grid_configure(row=2, column=0, sticky="nsew", padx=(0, 6))
        tesseract_card.grid_configure(row=2, column=1, sticky="nsew", padx=(6, 0))

    def _build_advanced(self, parent, controller) -> None:
        workers = self._card(parent, "Hiệu năng và xử lý kỹ thuật")
        ttk.Label(workers, text="Các thông số này dành cho người có kinh nghiệm. Cài đặt Hiệu năng ở trang Quét ảnh là lựa chọn nên dùng.", style="SurfaceMuted.TLabel", wraplength=760).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        labelled_spin(workers, 1, "Xử lý ảnh song song", controller.image_workers_var, 1, max(1, controller.cpu_count), 1)
        ttk.Label(workers, text="OCR cục bộ — PaddleOCR", style="Surface.TLabel").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Label(workers, text="1 worker cố định để ổn định", style="StatusPill.TLabel").grid(row=2, column=1, sticky="w", pady=4)
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
