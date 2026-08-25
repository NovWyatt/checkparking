from __future__ import annotations

from tkinter import ttk

from .base import Page
from ..components.forms import labelled_combo
from ..components.scrollable import ScrollableFrame
from ..components.tooltip import attach_tooltip


class ScanPage(Page):
    page_title = "Quét ảnh"
    primary_label = "Bắt đầu quét"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.scroll = ScrollableFrame(self, padding=(0, 0, 8, 0))
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.content = self.scroll.content
        self.content.columnconfigure((0, 1), weight=1)
        self.content.rowconfigure(2, weight=1)
        self._build_input_step(controller)
        self._build_recognition_step(controller)
        self._build_progress_step(controller)
        self.content.bind("<Configure>", self._on_resize, add=True)

    def _build_input_step(self, controller) -> None:
        inputs = ttk.LabelFrame(self.content, text="Bước 1 — Chọn dữ liệu", style="Card.TLabelframe")
        self.inputs = inputs
        inputs.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 16))
        inputs.columnconfigure((0, 1), weight=1)
        ttk.Label(inputs, text="Chọn từng ảnh hoặc một thư mục ảnh để bắt đầu.", style="SurfaceMuted.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        ttk.Button(inputs, text="Chọn ảnh  Ctrl+O", command=controller.add_files, style="Primary.TButton").grid(row=1, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(inputs, text="Chọn thư mục  Ctrl+Shift+O", command=controller.add_folder).grid(row=1, column=1, sticky="ew", padx=(4, 0))
        ttk.Checkbutton(inputs, text="Quét cả thư mục con", variable=controller.recursive_var).grid(row=2, column=0, sticky="w", pady=(10, 2))
        ttk.Label(inputs, textvariable=controller.input_summary_var, style="SurfaceMuted.TLabel").grid(row=2, column=1, sticky="e", pady=(10, 2))
        self.plate_type_combo = labelled_combo(
            inputs,
            3,
            "Loại biển số",
            controller.plate_type_var,
            controller.plate_type_choices,
            readonly=True,
        )
        attach_tooltip(
            self.plate_type_combo,
            "Ứng dụng chỉ thêm dấu gạch cho biển số khớp đúng mẫu; biển đặc biệt được giữ nguyên để kiểm tra.",
        )
        ttk.Label(inputs, textvariable=controller.plate_type_hint_var, style="SurfaceMuted.TLabel", wraplength=440).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(1, 2)
        )
        self.expected_plate_count_combo = labelled_combo(
            inputs,
            5,
            "Số biển số dự kiến trong mỗi ảnh",
            controller.expected_plate_count_var,
            controller.expected_plate_count_choices,
            readonly=True,
        )
        attach_tooltip(
            self.expected_plate_count_combo,
            "Mặc định chỉ xuất một biển số tốt nhất cho mỗi ảnh; chữ overlay và candidate phụ không làm tăng tổng biển số.",
        )
        ttk.Label(inputs, textvariable=controller.expected_plate_count_hint_var, style="SurfaceMuted.TLabel", wraplength=440).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(1, 2)
        )
        ttk.Label(
            inputs,
            text="Ứng dụng sẽ tự thêm dấu gạch cho các biển số đúng mẫu. Biển đặc biệt sẽ được giữ nguyên để kiểm tra.",
            style="SurfaceMuted.TLabel",
            wraplength=440,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(2, 2))
        ttk.Button(inputs, text="Xóa danh sách", command=controller.clear_all).grid(row=8, column=1, sticky="e", pady=(6, 0))

    def _build_recognition_step(self, controller) -> None:
        settings = ttk.LabelFrame(self.content, text="Bước 2 — Chọn cách nhận diện", style="Card.TLabelframe")
        self.settings = settings
        settings.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 16))
        settings.columnconfigure(0, weight=1)
        choices = (
            (
                "local",
                "Cục bộ — Khuyên dùng",
                "Chạy PaddleOCR trên máy, không cần API và không gửi ảnh ra ngoài.",
            ),
            (
                "local_ai_review",
                "Cục bộ + AI kiểm tra ảnh khó",
                "PaddleOCR chạy trước. AI trực tuyến chỉ kiểm tra kết quả không chắc chắn.",
            ),
            (
                "online",
                "AI trực tuyến",
                "Dùng dịch vụ AI đã cấu hình. Có thể phát sinh chi phí và ảnh sẽ được gửi tới nhà cung cấp.",
            ),
        )
        for row, (value, label, description) in enumerate(choices):
            item = ttk.Frame(settings, style="Surface.TFrame")
            item.grid(row=row, column=0, sticky="ew", pady=(0, 6))
            item.columnconfigure(1, weight=1)
            ttk.Radiobutton(item, text=label, value=value, variable=controller.recognition_mode_var, command=controller._on_recognition_mode_changed).grid(
                row=0, column=0, sticky="nw", padx=(0, 8)
            )
            ttk.Label(item, text=description, style="SurfaceMuted.TLabel", wraplength=430).grid(row=0, column=1, sticky="w")
        controller.ai_config_warning_label = ttk.Label(settings, textvariable=controller.ai_config_warning_var, style="Warning.TLabel", wraplength=500)
        controller.ai_config_warning_label.grid(row=3, column=0, sticky="w", pady=(4, 2))
        controller.open_ai_settings_button = ttk.Button(settings, text="Mở cài đặt AI", command=lambda: controller.show_settings_section("ai"))
        controller.open_ai_settings_button.grid(row=4, column=0, sticky="w", pady=(0, 10))

        controller.ai_review_policy_combo = labelled_combo(
            settings,
            5,
            "Mức dùng AI",
            controller.ai_review_policy_var,
            controller.ai_review_policy_choices,
            readonly=True,
        )
        controller.ai_review_policy_hint_label = ttk.Label(
            settings,
            textvariable=controller.ai_review_policy_hint_var,
            style="SurfaceMuted.TLabel",
            wraplength=500,
        )
        controller.ai_review_policy_hint_label.grid(row=6, column=0, sticky="w", pady=(0, 8))

        performance = ttk.Frame(settings, style="Surface.TFrame")
        performance.grid(row=7, column=0, sticky="ew", pady=(4, 0))
        performance.columnconfigure(1, weight=1)
        self.scan_mode_combo = labelled_combo(performance, 0, "Chế độ quét", controller.paddle_scan_mode_var, controller.paddle_scan_choices, readonly=True)
        ttk.Label(performance, textvariable=controller.scan_mode_hint_var, style="SurfaceMuted.TLabel", wraplength=500).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )
        self.performance_combo = labelled_combo(performance, 2, "Hiệu năng", controller.performance_preset_var, controller.performance_preset_choices, readonly=True)
        ttk.Label(performance, textvariable=controller.performance_hint_var, style="SurfaceMuted.TLabel", wraplength=500).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )

        self.advanced = ttk.Frame(settings, style="Surface.TFrame")
        self.advanced.columnconfigure(0, weight=1)
        ttk.Label(self.advanced, text="Thông tin kỹ thuật", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Label(self.advanced, textvariable=controller.advanced_worker_summary_var, style="SurfaceMuted.TLabel", wraplength=500).grid(
            row=1, column=0, sticky="w", pady=(0, 4)
        )
        ttk.Button(self.advanced, text="Mở phần Nâng cao trong Cài đặt", command=lambda: controller.show_settings_section("advanced")).grid(
            row=2, column=0, sticky="w"
        )
        self.advanced_toggle = ttk.Button(settings, text="Hiện cài đặt nâng cao", command=self._toggle_advanced)
        self.advanced_toggle.grid(row=8, column=0, sticky="w", pady=(8, 0))

    def _build_progress_step(self, controller) -> None:
        progress = ttk.LabelFrame(self.content, text="Bước 3 — Bắt đầu", style="Card.TLabelframe")
        self.progress_panel = progress
        progress.grid(row=1, column=0, columnspan=2, sticky="new", pady=(0, 16))
        progress.columnconfigure(0, weight=1)
        controller.progress = ttk.Progressbar(progress, mode="determinate")
        controller.progress.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 12))
        ttk.Label(progress, textvariable=controller.progress_primary_var, style="Surface.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(progress, textvariable=controller.progress_timing_var, style="SurfaceMuted.TLabel").grid(row=1, column=1, sticky="w", padx=16)
        ttk.Label(progress, textvariable=controller.progress_workers_var, style="SurfaceMuted.TLabel").grid(row=1, column=2, sticky="e")
        ttk.Label(progress, textvariable=controller.progress_detail_var, style="SurfaceMuted.TLabel", wraplength=850).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(4, 10)
        )
        actions = ttk.Frame(progress, style="Surface.TFrame")
        actions.grid(row=3, column=0, columnspan=3, sticky="ew")
        actions.columnconfigure(0, weight=1)
        controller.start_button = ttk.Button(actions, text="Bắt đầu quét", command=controller.start_processing, style="Primary.TButton")
        controller.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        controller.stop_button = ttk.Button(actions, text="Dừng", command=controller.stop_processing, state="disabled", style="Danger.TButton")
        controller.stop_button.grid(row=0, column=1, sticky="ew", padx=4)
        controller.view_results_button = ttk.Button(actions, text="Xem kết quả", command=lambda: controller.show_page("results"), state="disabled")
        controller.view_results_button.grid(row=0, column=2, sticky="ew", padx=4)
        controller.scan_export_button = ttk.Button(actions, text="Xuất Excel", command=controller.export_selected_results, state="disabled")
        controller.scan_export_button.grid(row=0, column=3, sticky="ew", padx=(4, 0))

    def _toggle_advanced(self) -> None:
        if self.advanced.winfo_ismapped():
            self.advanced.grid_remove()
            self.advanced_toggle.configure(text="Hiện cài đặt nâng cao")
        else:
            self.advanced.grid(row=9, column=0, sticky="ew", pady=(6, 0))
            self.advanced_toggle.configure(text="Ẩn cài đặt nâng cao")

    def _on_resize(self, event) -> None:
        # At high Windows scaling a 1366 px screen has less logical width.
        # Stack the two setup steps instead of clipping their descriptions.
        if event.width < 980:
            self.inputs.grid_configure(row=0, column=0, columnspan=2, padx=0)
            self.settings.grid_configure(row=1, column=0, columnspan=2, padx=0)
            self.progress_panel.grid_configure(row=2, column=0, columnspan=2)
        else:
            self.inputs.grid_configure(row=0, column=0, columnspan=1, padx=(0, 8))
            self.settings.grid_configure(row=0, column=1, columnspan=1, padx=(8, 0))
            self.progress_panel.grid_configure(row=1, column=0, columnspan=2)
