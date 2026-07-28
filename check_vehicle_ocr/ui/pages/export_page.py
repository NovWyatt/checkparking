from __future__ import annotations

from tkinter import ttk

from .base import Page


class ExportPage(Page):
    page_title = "Xuất Excel"
    primary_label = "Xuất tất cả"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.columnconfigure(0, weight=1)
        card = ttk.LabelFrame(self, text="Báo cáo Excel", style="Card.TLabelframe")
        card.grid(row=0, column=0, sticky="new")
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text="Xuất snapshot độc lập. Thay đổi review sau khi bấm xuất không làm thay đổi file đang tạo.", style="SurfaceMuted.TLabel", wraplength=720).grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Entry(card, textvariable=controller.output_var).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(card, text="Chọn nơi lưu", command=controller.choose_output).grid(row=2, column=0, sticky="w", pady=4)
        ttk.Checkbutton(card, text="Nhúng ảnh và crop vào Excel (file lớn hơn, chậm hơn)", variable=controller.embed_excel_images_var).grid(row=3, column=0, sticky="w", pady=(8, 10))
        actions = ttk.Frame(card, style="Surface.TFrame")
        actions.grid(row=4, column=0, sticky="ew")
        actions.columnconfigure((0, 1), weight=1)
        controller.export_button = ttk.Button(actions, text="Xuất tất cả kết quả", command=controller.export_all_results, state="disabled", style="Primary.TButton")
        controller.export_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        controller.export_reviewed_button = ttk.Button(actions, text="Chỉ xuất đã duyệt", command=controller.export_reviewed_results, state="disabled")
        controller.export_reviewed_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Label(card, textvariable=controller.export_status_var, style="SurfaceMuted.TLabel", wraplength=700).grid(row=5, column=0, sticky="w", pady=(12, 0))
