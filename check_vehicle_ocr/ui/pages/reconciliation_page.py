from __future__ import annotations

from tkinter import ttk

from .base import Page
from ..components.forms import labelled_combo
from ..components.scrollable import ScrollableFrame


class ReconciliationPage(Page):
    """Operator entry point for the non-destructive Excel comparison flow."""

    page_title = "Đối chiếu"
    primary_label = "Tạo báo cáo"

    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.scroll = ScrollableFrame(self, padding=(0, 0, 8, 0))
        self.scroll.grid(row=0, column=0, sticky="nsew")
        content = self.scroll.content
        content.columnconfigure(0, weight=1)
        self._build_source_card(content, controller)
        self._build_rules_card(content, controller)
        self._build_action_card(content, controller)

    def _build_source_card(self, parent, controller) -> None:
        card = ttk.LabelFrame(parent, text="Nguồn dữ liệu", style="Card.TLabelframe")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        card.columnconfigure(1, weight=1)
        ttk.Label(
            card,
            text="Chọn file OCR đã duyệt, sau đó chọn báo phí. Phần mềm là tùy chọn.",
            style="SurfaceMuted.TLabel",
            wraplength=900,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self._file_row(card, 1, "File OCR đã xuất", controller.reconciliation_ocr_path_var, controller.choose_reconciliation_ocr_file)
        self._file_row(card, 2, "File báo phí", controller.reconciliation_fee_path_var, controller.choose_reconciliation_fee_file)
        ttk.Button(card, text="Tải mẫu báo phí", command=controller.download_fee_template).grid(row=2, column=3, sticky="e", padx=(8, 0), pady=4)

        controller.reconciliation_software_toggle = ttk.Checkbutton(
            card,
            text="Đối chiếu thêm với phần mềm",
            variable=controller.reconciliation_compare_software_var,
            command=self._sync_software_controls,
        )
        controller.reconciliation_software_toggle.grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 2))
        self.software_entry, self.software_button = self._file_row(
            card,
            4,
            "File phần mềm",
            controller.reconciliation_software_path_var,
            controller.choose_reconciliation_software_file,
        )
        self.software_template_button = ttk.Button(card, text="Tải mẫu phần mềm", command=controller.download_software_template)
        self.software_template_button.grid(row=4, column=3, sticky="e", padx=(8, 0), pady=4)
        ttk.Label(
            card,
            text="File mẫu chỉ có cột Biển số. Dán dữ liệu vào sheet Danh_sach từ dòng 2, không cần đổi file nguồn hiện có.",
            style="SurfaceMuted.TLabel",
            wraplength=900,
        ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))

    @staticmethod
    def _file_row(parent, row, label, variable, command):
        ttk.Label(parent, text=label, style="Surface.TLabel").grid(row=row, column=0, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=variable, state="readonly")
        entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        button = ttk.Button(parent, text="Chọn file", command=command)
        button.grid(row=row, column=3, sticky="e", padx=(8, 0), pady=4)
        return entry, button

    def _build_rules_card(self, parent, controller) -> None:
        card = ttk.LabelFrame(parent, text="Quy tắc đối chiếu", style="Card.TLabelframe")
        card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        card.columnconfigure(1, weight=1)
        labelled_combo(
            card,
            0,
            "Kiểm tra gần đúng",
            controller.reconciliation_suffix_length_var,
            ("4 ký tự cuối - Khuyên dùng", "3 ký tự cuối"),
            readonly=True,
        )
        ttk.Label(
            card,
            text="Khớp hoàn toàn được dò trước. Khớp gần chỉ được chấp nhận khi có đúng một ứng viên, sai tối đa một ký tự và còn trùng ít nhất 2 hoặc 3 ký tự cuối theo lựa chọn.",
            style="SurfaceMuted.TLabel",
            wraplength=900,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(
            card,
            text="Trường hợp thiếu hoặc dư ký tự, sai khác lớn hơn một ký tự hay có nhiều ứng viên sẽ được đưa vào sheet Cần_xác_nhận.",
            style="SurfaceMuted.TLabel",
            wraplength=900,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

    def _build_action_card(self, parent, controller) -> None:
        card = ttk.LabelFrame(parent, text="Tạo báo cáo", style="Card.TLabelframe")
        card.grid(row=2, column=0, sticky="ew")
        card.columnconfigure(0, weight=1)
        ttk.Label(
            card,
            text="Báo cáo không sửa file OCR, báo phí hoặc phần mềm. Các dòng khớp gần và biển trùng được tách riêng để kiểm tra.",
            style="SurfaceMuted.TLabel",
            wraplength=900,
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))
        controller.reconciliation_run_button = ttk.Button(card, text="Tạo file đối chiếu", command=controller.start_reconciliation, style="Primary.TButton")
        controller.reconciliation_run_button.grid(row=1, column=0, sticky="w")
        ttk.Label(card, textvariable=controller.reconciliation_status_var, style="SurfaceMuted.TLabel", wraplength=900).grid(
            row=2, column=0, sticky="w", pady=(10, 0)
        )

    def _sync_software_controls(self) -> None:
        enabled = self.controller.reconciliation_compare_software_var.get()
        state = "readonly" if enabled else "disabled"
        self.software_entry.configure(state=state)
        self.software_button.configure(state="normal" if enabled else "disabled")
        self.software_template_button.configure(state="normal" if enabled else "disabled")
        self.controller.refresh_reconciliation_controls()

    def on_show(self) -> None:
        self._sync_software_controls()
        self.controller.refresh_reconciliation_controls()
