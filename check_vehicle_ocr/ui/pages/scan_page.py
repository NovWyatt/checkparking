from __future__ import annotations

from tkinter import ttk

from .base import Page
from ..components.forms import labelled_combo, labelled_entry, labelled_spin


class ScanPage(Page):
    page_title = "Quét ảnh"
    primary_label = "Bắt đầu quét"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)
        inputs = ttk.LabelFrame(self, text="Ảnh đầu vào", style="Card.TLabelframe")
        inputs.grid(row=0, column=0, sticky="new", padx=(0, 8), pady=(0, 12))
        inputs.columnconfigure(0, weight=1)
        ttk.Label(inputs, text="Kéo ảnh vào đây hoặc chọn ảnh/thư mục để bắt đầu.", style="SurfaceMuted.TLabel", wraplength=400).grid(row=0, column=0, sticky="w")
        buttons = ttk.Frame(inputs, style="Surface.TFrame")
        buttons.grid(row=1, column=0, sticky="ew", pady=(12, 6))
        buttons.columnconfigure((0, 1), weight=1)
        ttk.Button(buttons, text="Chọn ảnh  Ctrl+O", command=controller.add_files).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Chọn thư mục  Ctrl+Shift+O", command=controller.add_folder).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Checkbutton(inputs, text="Quét cả thư mục con", variable=controller.recursive_var).grid(row=2, column=0, sticky="w", pady=4)
        ttk.Label(inputs, textvariable=controller.input_summary_var, style="SurfaceMuted.TLabel").grid(row=3, column=0, sticky="w", pady=(4, 8))
        clear_row = ttk.Frame(inputs, style="Surface.TFrame")
        clear_row.grid(row=4, column=0, sticky="ew")
        clear_row.columnconfigure((0, 1), weight=1)
        ttk.Button(clear_row, text="Bỏ ảnh chọn", command=controller.remove_selected).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(clear_row, text="Xóa danh sách", command=controller.clear_all).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        settings = ttk.LabelFrame(self, text="Thiết lập quét", style="Card.TLabelframe")
        settings.grid(row=0, column=1, sticky="new", padx=(8, 0), pady=(0, 12))
        settings.columnconfigure(1, weight=1)
        labelled_combo(settings, 0, "Engine", controller.engine_var, controller.engine_choices, readonly=True)
        labelled_combo(settings, 1, "Chế độ", controller.paddle_scan_mode_var, controller.paddle_scan_choices, readonly=True)
        labelled_combo(settings, 2, "Chế độ worker", controller.worker_mode_var, ("AUTO", "MANUAL"), readonly=True)
        labelled_spin(settings, 3, "Worker ảnh", controller.image_workers_var, 1, max(1, controller.cpu_count), 1)
        controller.local_ocr_workers_spin = labelled_spin(settings, 4, "Worker OCR local", controller.local_ocr_workers_var, 1, max(1, controller.cpu_count), 1)
        controller.paddle_worker_hint = ttk.Label(settings, textvariable=controller.local_ocr_hint_var, style="SurfaceMuted.TLabel", wraplength=310)
        controller.paddle_worker_hint.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 3))
        labelled_spin(settings, 6, "Worker API", controller.api_workers_var, 1, 8, 1)
        self.advanced = ttk.Frame(settings, style="Surface.TFrame")
        self.advanced.columnconfigure(1, weight=1)
        labelled_spin(self.advanced, 0, "Queue tối đa", controller.queue_capacity_var, 1, 128, 1)
        labelled_spin(self.advanced, 1, "Tin cậy tối thiểu", controller.conf_threshold_var, 10, 95, 5)
        labelled_spin(self.advanced, 2, "Ngưỡng ảnh mờ", controller.blur_threshold_var, 10, 500, 5)
        labelled_entry(self.advanced, 3, "Tesseract", controller.tesseract_var)
        ttk.Button(self.advanced, text="Chọn tesseract.exe", command=controller.choose_tesseract).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Button(settings, text="Hiện thiết lập nâng cao", command=self._toggle_advanced).grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))

        progress = ttk.LabelFrame(self, text="Tiến trình batch", style="Card.TLabelframe")
        progress.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        progress.columnconfigure(0, weight=1)
        controller.progress = ttk.Progressbar(progress, mode="determinate")
        controller.progress.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        ttk.Label(progress, textvariable=controller.progress_primary_var, style="Surface.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(progress, textvariable=controller.progress_timing_var, style="SurfaceMuted.TLabel").grid(row=1, column=1, sticky="w", padx=16)
        ttk.Label(progress, textvariable=controller.progress_workers_var, style="SurfaceMuted.TLabel").grid(row=1, column=2, sticky="e")
        ttk.Label(progress, textvariable=controller.progress_detail_var, style="SurfaceMuted.TLabel", wraplength=800).grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 10))
        action_row = ttk.Frame(progress, style="Surface.TFrame")
        action_row.grid(row=3, column=0, columnspan=3, sticky="ew")
        action_row.columnconfigure(0, weight=1)
        controller.start_button = ttk.Button(action_row, text="Bắt đầu quét", command=controller.start_processing, style="Primary.TButton")
        controller.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        controller.stop_button = ttk.Button(action_row, text="Dừng sau ảnh hiện tại", command=controller.stop_processing, state="disabled")
        controller.stop_button.grid(row=0, column=1, sticky="ew", padx=6)
        controller.retry_failed_button = ttk.Button(action_row, text="Quét lại ảnh lỗi", command=controller.retry_failed_images, state="disabled")
        controller.retry_failed_button.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        empty = ttk.Frame(self, style="Surface.TFrame", padding=24)
        empty.grid(row=2, column=0, columnspan=2, sticky="nsew")
        ttk.Label(empty, text="Chưa có ảnh để quét", style="Section.TLabel").pack(anchor="w")
        ttk.Label(empty, text="Sau khi thêm ảnh, tiến trình và kết quả sẽ xuất hiện trong phiên hiện tại.", style="SurfaceMuted.TLabel", wraplength=700).pack(anchor="w", pady=(6, 0))

    def _toggle_advanced(self) -> None:
        if self.advanced.winfo_ismapped():
            self.advanced.grid_remove()
        else:
            self.advanced.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(4, 0))
