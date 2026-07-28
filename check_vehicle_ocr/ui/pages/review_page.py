from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .base import Page


class ReviewPage(Page):
    page_title = "Cần kiểm tra"
    primary_label = "Lưu chỉnh sửa"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.columnconfigure(0, weight=2, minsize=330)
        self.columnconfigure(1, weight=3, minsize=420)
        self.rowconfigure(0, weight=1)
        left = ttk.Frame(self, style="Surface.TFrame", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        ttk.Label(left, text="Ảnh cần đối chiếu", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        controller.review_tree = ttk.Treeview(left, columns=("file", "plate", "reason"), show="headings")
        for column, title, width in (("file", "Tên ảnh", 160), ("plate", "Kết quả", 110), ("reason", "Lý do", 220)):
            controller.review_tree.heading(column, text=title)
            controller.review_tree.column(column, width=width, anchor="w")
        controller.review_tree.grid(row=1, column=0, sticky="nsew")
        controller.review_tree.bind("<<TreeviewSelect>>", controller._on_review_selected)
        right = ttk.Frame(self, style="Surface.TFrame", padding=12)
        right.grid(row=0, column=1, sticky="nsew")
        self._build_detail(right, controller)

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
        controller.preview_label = tk.Label(preview_holder, bg=controller.colors["preview"], fg=controller.colors["on_accent"], text="Chọn một ảnh để xem", compound="center")
        controller.preview_label.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        crop_holder = ttk.Frame(preview_holder, style="Surface.TFrame")
        crop_holder.grid(row=0, column=1, sticky="nsew")
        ttk.Label(crop_holder, text="Crop biển số", style="SurfaceMuted.TLabel").pack(anchor="w")
        controller.crop_preview_label = tk.Label(crop_holder, bg=controller.colors["preview"], fg=controller.colors["on_accent"], text="Chưa có crop", compound="center")
        controller.crop_preview_label.pack(fill="both", expand=True, pady=(4, 0))
        ttk.Label(parent, text="OCR thô, kết quả chọn và gợi ý", style="Section.TLabel").grid(row=3, column=0, sticky="w", pady=(0, 6))
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
        ttk.Button(buttons, text="Lưu chỉnh sửa", command=controller.save_detail_edits, style="Primary.TButton").grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 6))
        ttk.Button(buttons, text="Đánh dấu đã kiểm tra", command=controller.approve_current_image).grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 6))
        ttk.Button(buttons, text="Thêm biển số", command=controller.add_manual_plate).grid(row=1, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Mở ảnh gốc", command=controller.open_current_image).grid(row=1, column=1, sticky="ew", padx=(4, 0))

    def on_show(self) -> None:
        self.controller.refresh_result_tables()
        if self.controller.selected_image_path:
            self.controller._select_path(self.controller.selected_image_path)
