from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..license_service import LicenseDecision, LicenseState


class LicenseActivationDialog(tk.Toplevel):
    """Modal activation flow for a release configured with a license service."""

    def __init__(self, master, decision: LicenseDecision, on_activate, on_revalidate, *, required: bool, allow_activation: bool) -> None:
        super().__init__(master)
        self._on_activate = on_activate
        self._on_revalidate = on_revalidate
        self._required = required
        self._allow_activation = allow_activation
        self.title("Kích hoạt Check Vehicle OCR")
        self.transient(master)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.status_var = tk.StringVar()
        self.key_var = tk.StringVar()
        self.columnconfigure(0, weight=1)

        body = ttk.Frame(self, padding=26, style="App.TFrame")
        body.grid(sticky="nsew")
        body.columnconfigure(0, weight=1)
        ttk.Label(body, text="Bản quyền", style="PageTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text="Nhập key để kích hoạt. Key được kiểm tra với máy chủ bản quyền và không được lưu ở dạng chữ thường trên máy.",
            style="SurfaceMuted.TLabel",
            wraplength=460,
        ).grid(row=1, column=0, sticky="w", pady=(6, 16))
        ttk.Label(body, text="Key bản quyền", style="Surface.TLabel").grid(row=2, column=0, sticky="w")
        self.entry = ttk.Entry(body, textvariable=self.key_var, width=48, style="Plate.TEntry")
        self.entry.grid(row=3, column=0, sticky="ew", pady=(5, 8))
        self.entry.bind("<Return>", lambda _event: self._activate())
        self.activate_button = ttk.Button(body, text="Kích hoạt", command=self._activate, style="Primary.TButton")
        self.activate_button.grid(row=4, column=0, sticky="ew", pady=(4, 6))
        self.revalidate_button = ttk.Button(body, text="Kiểm tra lại kết nối", command=on_revalidate)
        self.revalidate_button.grid(row=5, column=0, sticky="ew")
        ttk.Label(body, textvariable=self.status_var, style="SurfaceMuted.TLabel", wraplength=460).grid(row=6, column=0, sticky="w", pady=(14, 0))
        self.update_decision(decision)
        self.grab_set()
        self.after_idle(self.entry.focus_set)

    def update_decision(self, decision: LicenseDecision) -> None:
        self.status_var.set(decision.message)
        should_enter_key = self._allow_activation or decision.state in {
            LicenseState.NEEDS_ACTIVATION,
            LicenseState.EXPIRED,
            LicenseState.INVALID,
            LicenseState.REVOKED,
        }
        self.entry.configure(state="normal" if should_enter_key else "disabled")
        self.activate_button.configure(state="normal" if should_enter_key else "disabled")
        self.revalidate_button.configure(
            state="normal" if decision.certificate is not None and decision.state is not LicenseState.INVALID else "disabled"
        )

    def set_busy(self, message: str) -> None:
        self.status_var.set(message)
        self.entry.configure(state="disabled")
        self.activate_button.configure(state="disabled")
        self.revalidate_button.configure(state="disabled")

    def _activate(self) -> None:
        key = self.key_var.get().strip()
        if not key:
            self.status_var.set("Hãy nhập key bản quyền.")
            self.entry.focus_set()
            return
        self.key_var.set("")
        self._on_activate(key)

    def _close(self) -> None:
        if self._required:
            self.master.destroy()
        else:
            self.destroy()
