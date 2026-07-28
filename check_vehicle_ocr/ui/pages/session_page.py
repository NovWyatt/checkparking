from __future__ import annotations

from tkinter import ttk

from .base import Page


class SessionPage(Page):
    page_title = "Phiên hiện tại"
    primary_label = "Duyệt kết quả"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        metrics = ttk.Frame(self, style="App.TFrame")
        metrics.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        metrics.columnconfigure((0, 1, 2, 3), weight=1)
        for index, (label, variable) in enumerate((("Ảnh đã nhập", controller.total_var), ("Đã xử lý", controller.scanned_var), ("Biển số", controller.plates_var), ("Cần kiểm tra", controller.review_var))):
            card = ttk.Frame(metrics, style="Surface.TFrame", padding=(12, 10))
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            ttk.Label(card, textvariable=variable, style="Metric.TLabel").pack(anchor="w")
            ttk.Label(card, text=label, style="SurfaceMuted.TLabel").pack(anchor="w")

        panel = ttk.Frame(self, style="Surface.TFrame", padding=12)
        panel.grid(row=1, column=0, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(2, weight=1)
        top = ttk.Frame(panel, style="Surface.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(0, weight=1)
        ttk.Label(top, text="Kết quả trong phiên", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        controller.session_search_entry = ttk.Entry(top, textvariable=controller.session_search_var, width=28)
        controller.session_search_entry.grid(row=0, column=1, padx=(8, 4))
        ttk.Button(top, text="Lọc", command=controller.refresh_result_tables).grid(row=0, column=2)
        controller.image_tree = self._create_tree(panel, controller)
        controller._configure_tree_tags()
        controller.image_tree.grid(row=2, column=0, sticky="nsew")
        controller.image_tree.bind("<<TreeviewSelect>>", controller._on_image_selected)
        controller.image_tree.bind("<Double-1>", lambda _event: controller.show_page("review"))
        scroll = ttk.Scrollbar(panel, orient="vertical", command=controller.image_tree.yview)
        scroll.grid(row=2, column=1, sticky="ns")
        controller.image_tree.configure(yscrollcommand=scroll.set)
        controller.review_button = ttk.Button(panel, text="Mở trang kiểm tra", command=lambda: controller.show_page("review"), state="disabled")
        controller.review_button.grid(row=3, column=0, sticky="e", pady=(10, 0))

    @staticmethod
    def _create_tree(parent, controller):
        columns = ("status", "file", "raw", "plate", "confidence", "review", "source")
        tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="extended")
        headings = {"status": "Trạng thái", "file": "Tên ảnh", "raw": "OCR thô", "plate": "Kết quả chọn", "confidence": "Tin cậy", "review": "Review", "source": "Nguồn"}
        widths = {"status": 108, "file": 190, "raw": 180, "plate": 150, "confidence": 82, "review": 88, "source": 120}
        for key in columns:
            tree.heading(key, text=headings[key], command=lambda column=key: controller.sort_result_table(column))
            tree.column(key, width=widths[key], anchor="w")
        return tree
