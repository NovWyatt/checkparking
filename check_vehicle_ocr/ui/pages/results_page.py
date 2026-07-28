from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .base import Page


class ResultsPage(Page):
    page_title = "Kết quả"
    primary_label = "Xuất Excel"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.columnconfigure(0, weight=3, minsize=470)
        self.columnconfigure(1, weight=4, minsize=430)
        self.rowconfigure(1, weight=1)

        metrics = ttk.Frame(self, style="App.TFrame")
        metrics.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        metrics.columnconfigure((0, 1, 2, 3), weight=1)
        for index, (label, variable) in enumerate(
            (("Ảnh đã chọn", controller.total_var), ("Đã xử lý", controller.scanned_var), ("Biển số", controller.plates_var), ("Cần kiểm tra", controller.review_var))
        ):
            card = ttk.Frame(metrics, style="Surface.TFrame", padding=(12, 10))
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            ttk.Label(card, textvariable=variable, style="Metric.TLabel").pack(anchor="w")
            ttk.Label(card, text=label, style="SurfaceMuted.TLabel").pack(anchor="w")

        left = ttk.Frame(self, style="Surface.TFrame", padding=12)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)
        self._build_toolbar(left, controller)
        controller.image_tree = self._create_tree(left, controller)
        controller._configure_tree_tags()
        controller.image_tree.grid(row=2, column=0, sticky="nsew")
        controller.image_tree.bind("<<TreeviewSelect>>", controller._on_image_selected)
        scroll = ttk.Scrollbar(left, orient="vertical", command=controller.image_tree.yview)
        scroll.grid(row=2, column=1, sticky="ns")
        controller.image_tree.configure(yscrollcommand=scroll.set)

        right = ttk.Frame(self, style="Surface.TFrame", padding=12)
        right.grid(row=1, column=1, sticky="nsew")
        self._build_detail(right, controller)

    @staticmethod
    def _build_toolbar(parent, controller) -> None:
        toolbar = ttk.Frame(parent, style="Surface.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)
        ttk.Label(toolbar, text="Danh sách kết quả", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        controller.result_filter_combo = ttk.Combobox(
            toolbar,
            textvariable=controller.result_filter_var,
            values=("Tất cả", "Cần kiểm tra", "Có lỗi"),
            width=15,
            state="readonly",
            style="Operator.TCombobox",
        )
        controller.result_filter_combo.grid(row=0, column=1, padx=(8, 4))
        controller.result_filter_combo.bind("<<ComboboxSelected>>", lambda _event: controller.refresh_result_tables())
        controller.session_search_entry = ttk.Entry(toolbar, textvariable=controller.session_search_var, width=22)
        controller.session_search_entry.grid(row=0, column=2, padx=(4, 0))
        controller.session_search_entry.bind("<Return>", lambda _event: controller.refresh_result_tables())

        actions = ttk.Frame(parent, style="Surface.TFrame")
        actions.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        actions.columnconfigure(0, weight=1)
        controller.export_button = ttk.Button(actions, text="Xuất Excel", command=controller.export_selected_results, state="disabled", style="Primary.TButton")
        controller.export_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(actions, text="Quét batch mới", command=lambda: controller.show_page("scan")).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Checkbutton(parent, text="Chỉ xuất biển số đã xác nhận", variable=controller.export_reviewed_only_var).grid(row=3, column=0, sticky="w", pady=(8, 0))

    @staticmethod
    def _create_tree(parent, controller):
        columns = ("status", "file", "raw", "plate", "confidence", "review")
        tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="extended")
        headings = {
            "status": "Trạng thái",
            "file": "Tên ảnh",
            "raw": "OCR thô",
            "plate": "Kết quả chọn",
            "confidence": "Tin cậy",
            "review": "Kiểm tra",
        }
        widths = {"status": 100, "file": 160, "raw": 150, "plate": 130, "confidence": 76, "review": 100}
        for key in columns:
            tree.heading(key, text=headings[key], command=lambda column=key: controller.sort_result_table(column))
            tree.column(key, width=widths[key], anchor="w")
        return tree

    @staticmethod
    def _build_detail(parent, controller) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        ttk.Label(parent, textvariable=controller.detail_title_var, style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(parent, textvariable=controller.detail_meta_var, style="SurfaceMuted.TLabel", wraplength=520).grid(row=1, column=0, sticky="w", pady=(3, 8))
        preview_holder = ttk.Frame(parent, style="Surface.TFrame")
        preview_holder.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        preview_holder.columnconfigure(0, weight=3, minsize=260)
        preview_holder.columnconfigure(1, weight=1, minsize=150)
        preview_holder.rowconfigure(0, weight=1)
        controller.preview_label = tk.Label(
            preview_holder, bg=controller.colors["preview"], fg=controller.colors["on_accent"], text="Chọn một ảnh để xem", compound="center"
        )
        controller.preview_label.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        crop_holder = ttk.Frame(preview_holder, style="Surface.TFrame")
        crop_holder.grid(row=0, column=1, sticky="nsew")
        ttk.Label(crop_holder, text="Crop biển số", style="SurfaceMuted.TLabel").pack(anchor="w")
        controller.crop_preview_label = tk.Label(
            crop_holder, bg=controller.colors["preview"], fg=controller.colors["on_accent"], text="Chưa có crop", compound="center"
        )
        controller.crop_preview_label.pack(fill="both", expand=True, pady=(4, 0))
        ttk.Label(parent, text="Thông tin nhận diện", style="Section.TLabel").grid(row=3, column=0, sticky="w", pady=(0, 6))
        frame = ttk.Frame(parent, style="Surface.TFrame")
        frame.grid(row=4, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        controller.plate_canvas = tk.Canvas(frame, height=128, bg=controller.colors["surface"], highlightthickness=0)
        controller.plate_canvas.grid(row=0, column=0, sticky="ew")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=controller.plate_canvas.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        controller.plates_frame = ttk.Frame(controller.plate_canvas, style="Surface.TFrame")
        controller.plate_canvas_window = controller.plate_canvas.create_window((0, 0), window=controller.plates_frame, anchor="nw")
        controller.plate_canvas.configure(yscrollcommand=scroll.set)
        controller.plates_frame.bind("<Configure>", lambda _event: controller.plate_canvas.configure(scrollregion=controller.plate_canvas.bbox("all")))
        controller.plate_canvas.bind("<Configure>", lambda event: controller.plate_canvas.itemconfigure(controller.plate_canvas_window, width=event.width))
        buttons = ttk.Frame(parent, style="Surface.TFrame")
        buttons.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        buttons.columnconfigure((0, 1), weight=1)
        ttk.Button(buttons, text="Lưu chỉnh sửa", command=controller.save_detail_edits, style="Primary.TButton").grid(
            row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 6)
        )
        ttk.Button(buttons, text="Đánh dấu đã kiểm tra", command=controller.approve_current_image).grid(
            row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 6)
        )
        ttk.Button(buttons, text="Thêm biển số", command=controller.add_manual_plate).grid(row=1, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Mở ảnh gốc", command=controller.open_current_image).grid(row=1, column=1, sticky="ew", padx=(4, 0))

    def on_show(self) -> None:
        self.controller.refresh_result_tables()
        if self.controller.selected_image_path:
            self.controller._select_path(self.controller.selected_image_path)
