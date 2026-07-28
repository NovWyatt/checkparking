from __future__ import annotations

import hashlib
import os
import queue
import subprocess
import threading
import time
from copy import deepcopy
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

from . import __version__
from .config import SETTINGS_VERSION, clear_saved_api_key, load_settings, save_settings, settings_path
from .excel_export import export_results
from .gemini_vision import DEFAULT_GEMINI_MODEL, GEMINI_MODEL_CHOICES, GeminiVisionEngine
from .gpt_vision import DEFAULT_GPT_MODEL, GPT_MODEL_CHOICES, GptVisionEngine
from .image_io import collect_images, load_image
from .models import ImageResult, PlateCandidate
from .ocr import TesseractOcrEngine, find_tesseract, normalize_plate_text, plate_text_metadata
from .paddle_ocr_engine import PaddleOcrEngine
from .plate_recognizer import DEFAULT_PLATE_RECOGNIZER_REGION, PlateRecognizerEngine
from .processor import process_image
from .providers import OpenAICompatibleProvider, ProviderConfig, ProviderStatus, redact_provider_error
from .services.progress_service import BatchProgress, BatchStatus
from .services.worker_manager import WorkItem, WorkerManager, WorkerSettings
from .telegram_notify import AsyncTelegramNotifier, TelegramSettings
from .ui import ApplicationShell
from .ui.state import AppUiState
from .ui.theme import colors as ui_colors, configure_styles
from .updater import UpdateManifest, compare_versions, download_verified, fetch_manifest


THEMES = {
    "light": {
        "bg": "#edf2f7",
        "panel": "#ffffff",
        "panel_alt": "#f8fafc",
        "field": "#ffffff",
        "text": "#0f172a",
        "subtle": "#64748b",
        "line": "#cbd5e1",
        "accent": "#0f766e",
        "accent_hover": "#0b625c",
        "accent_soft": "#dff7f3",
        "accent_text": "#0f5f59",
        "on_accent": "#ffffff",
        "warn": "#b45309",
        "danger": "#b91c1c",
        "button": "#ffffff",
        "button_hover": "#f1f5f9",
        "disabled": "#e2e8f0",
        "disabled_text": "#94a3b8",
        "preview_bg": "#111827",
        "log_bg": "#f8fafc",
        "tree_bg": "#ffffff",
        "tree_alt": "#f8fafc",
        "selection": "#ccfbf1",
        "selection_text": "#0f172a",
    },
    "dark": {
        "bg": "#0f172a",
        "panel": "#162033",
        "panel_alt": "#111827",
        "field": "#0b1220",
        "text": "#e5e7eb",
        "subtle": "#94a3b8",
        "line": "#334155",
        "accent": "#2dd4bf",
        "accent_hover": "#14b8a6",
        "accent_soft": "#123c43",
        "accent_text": "#99f6e4",
        "on_accent": "#06211f",
        "warn": "#f59e0b",
        "danger": "#f87171",
        "button": "#1e293b",
        "button_hover": "#26364d",
        "disabled": "#1f2937",
        "disabled_text": "#64748b",
        "preview_bg": "#020617",
        "log_bg": "#0b1220",
        "tree_bg": "#111827",
        "tree_alt": "#0f172a",
        "selection": "#134e4a",
        "selection_text": "#e5e7eb",
    },
}

BG = THEMES["light"]["bg"]
PANEL = THEMES["light"]["panel"]
TEXT = THEMES["light"]["text"]
SUBTLE = THEMES["light"]["subtle"]
ACCENT = THEMES["light"]["accent"]
ACCENT_DARK = THEMES["light"]["accent_text"]
LINE = THEMES["light"]["line"]
WARN = THEMES["light"]["warn"]
DANGER = THEMES["light"]["danger"]

ENGINE_CHOICES = ("PaddleOCR Local", "Gemini Vision", "Plate Recognizer", "GPT Vision", "OpenAI Compatible", "Local OCR")
API_ENGINE_CHOICES = {"Plate Recognizer", "Gemini Vision", "GPT Vision", "OpenAI Compatible"}
PADDLE_SCAN_MODE_CHOICES = ("Cân bằng", "Nhanh", "Quét kỹ")
PADDLE_SCAN_MODE_DEFAULT = "Cân bằng"


class _UnavailableEngine:
    def __init__(self, reason: str):
        self.reason = reason

    @property
    def available(self) -> bool:
        return False


class CheckVehicleApp(tk.Tk):
    def __init__(self) -> None:
        self.settings = load_settings()
        super().__init__()
        self.title(f"Check Vehicle OCR {__version__}")
        self.geometry("1280x720")
        self.minsize(1024, 640)
        self.dark_mode_var = tk.BooleanVar(value=bool(self.settings.get("dark_mode", False)))
        self.colors = _theme_colors(self.dark_mode_var.get())
        self.configure(bg=self.colors["bg"])

        self.images: list[Path] = []
        self.results: list[ImageResult] = []
        self.image_row_map: dict[str, Path] = {}
        self._result_sort_column = "file"
        self._result_sort_descending = False
        self.detail_row_vars: list[tuple[PlateCandidate, tk.StringVar, tk.BooleanVar]] = []
        self.current_detail_result: ImageResult | None = None
        self.selected_image_path: Path | None = None
        self.preview_photo = None
        self.crop_preview_photo = None
        self.event_queue: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.export_worker: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.retry_failed_before_count = 0
        self._save_after_id: str | None = None
        self._drain_after_id: str | None = None
        self._layout_after_ids: list[str] = []
        self._settings_ready = False
        self._theme_initialized = False
        self._theme_text_var = tk.StringVar()
        self.ui_state = AppUiState()
        self.notification_var = tk.StringVar(value="Sẵn sàng")
        self.header_status_var = tk.StringVar(value="Local • engine chưa khởi tạo")
        self.input_summary_var = tk.StringVar(value="Chưa có ảnh nào được chọn.")
        self.session_search_var = tk.StringVar()
        self.progress_primary_var = tk.StringVar(value="Chưa có batch đang chạy")
        self.progress_timing_var = tk.StringVar(value="")
        self.progress_workers_var = tk.StringVar(value="")
        self.progress_detail_var = tk.StringVar(value="")
        self.local_ocr_hint_var = tk.StringVar()
        self.export_status_var = tk.StringVar(value="Chưa có dữ liệu để xuất.")
        self.provider_status_var = tk.StringVar(value="Chưa kiểm tra kết nối.")
        self.telegram_status_var = tk.StringVar(value="Telegram đang tắt.")
        self.update_status_var = tk.StringVar(value="Chưa kiểm tra cập nhật.")
        self.update_notes_var = tk.StringVar(value="")
        self.update_version_var = tk.StringVar(value=f"Phiên bản hiện tại: {__version__} • Build source: không xác định")
        self.batch_progress: BatchProgress | None = None
        self.worker_manager: WorkerManager | None = None
        self.telegram_notifier: AsyncTelegramNotifier | None = None
        self.telegram_percent_sent: set[int] = set()
        self.current_update_manifest: UpdateManifest | None = None
        self.custom_secret_entries: list[ttk.Entry] = []
        self.custom_model_combo: ttk.Combobox | None = None
        self.provider_refresh_button: ttk.Button | None = None
        self.provider_test_button: ttk.Button | None = None
        self.update_check_button: ttk.Button | None = None
        self.update_download_button: ttk.Button | None = None
        self._last_progress_render_at = 0.0
        self.cpu_count = max(1, os.cpu_count() or 1)
        self.engine_choices = ENGINE_CHOICES
        self.paddle_scan_choices = PADDLE_SCAN_MODE_CHOICES

        output_dir = Path(str(self.settings.get("output_dir") or _default_output_dir())).expanduser()
        settings_version = _safe_settings_version(self.settings)
        saved_engine = str(self.settings.get("engine") or "PaddleOCR Local")
        if settings_version < 4 and saved_engine == "Plate Recognizer":
            saved_engine = "Gemini Vision"
        if settings_version < 6 and saved_engine == "Gemini Vision":
            saved_engine = "PaddleOCR Local"
        if saved_engine not in ENGINE_CHOICES:
            saved_engine = "PaddleOCR Local"

        self.output_var = tk.StringVar(value=str(output_dir / f"vehicle_plates_{datetime.now():%Y%m%d_%H%M%S}.xlsx"))
        self.embed_excel_images_var = tk.BooleanVar(value=bool(self.settings.get("embed_excel_images", True)))
        self.engine_var = tk.StringVar(value=saved_engine)
        self.openai_api_key_var = tk.StringVar(value=str(self.settings.get("api_key") or os.environ.get("OPENAI_API_KEY", "")))
        self.gemini_api_key_var = tk.StringVar(value=str(self.settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")))
        self.plate_recognizer_token_var = tk.StringVar(
            value=str(self.settings.get("plate_recognizer_token") or os.environ.get("PLATE_RECOGNIZER_TOKEN", ""))
        )
        has_any_key = any(
            value.get().strip()
            for value in (self.openai_api_key_var, self.gemini_api_key_var, self.plate_recognizer_token_var)
        )
        self.remember_key_var = tk.BooleanVar(value=bool(self.settings.get("remember_key", True) or has_any_key))
        self.show_key_var = tk.BooleanVar(value=False)

        saved_model = str(self.settings.get("gpt_model") or DEFAULT_GPT_MODEL)
        if _safe_settings_version(self.settings) < 2 and saved_model.startswith("gpt-5."):
            saved_model = DEFAULT_GPT_MODEL
        if saved_model not in GPT_MODEL_CHOICES:
            saved_model = DEFAULT_GPT_MODEL
        self.gpt_model_var = tk.StringVar(value=saved_model)

        saved_gemini_model = str(self.settings.get("gemini_model") or DEFAULT_GEMINI_MODEL)
        if _safe_settings_version(self.settings) < 5 and saved_gemini_model == "gemini-2.5-pro":
            saved_gemini_model = DEFAULT_GEMINI_MODEL
        if saved_gemini_model not in GEMINI_MODEL_CHOICES:
            saved_gemini_model = DEFAULT_GEMINI_MODEL
        self.gemini_model_var = tk.StringVar(value=saved_gemini_model)
        self.plate_recognizer_region_var = tk.StringVar(
            value=str(self.settings.get("plate_recognizer_region") or DEFAULT_PLATE_RECOGNIZER_REGION)
        )

        self.tesseract_var = tk.StringVar(value=str(self.settings.get("tesseract_path") or find_tesseract() or ""))
        self.recursive_var = tk.BooleanVar(value=bool(self.settings.get("recursive", True)))
        self.blur_threshold_var = tk.DoubleVar(value=float(self.settings.get("blur_threshold", 80.0)))
        self.conf_threshold_var = tk.DoubleVar(value=float(self.settings.get("conf_threshold", 35.0)))
        # Keep the old single setting as a migration fallback, but persist/use
        # separate pools from this point onward.
        legacy_workers = int(self.settings.get("worker_count", _default_worker_count()))
        self.worker_count_var = tk.IntVar(value=legacy_workers)
        self.worker_mode_var = tk.StringVar(value=str(self.settings.get("worker_mode") or "AUTO").upper())
        self.image_workers_var = tk.IntVar(value=int(self.settings.get("image_workers") or legacy_workers))
        self.local_ocr_workers_var = tk.IntVar(value=int(self.settings.get("local_ocr_workers") or 1))
        self.api_workers_var = tk.IntVar(value=int(self.settings.get("api_workers") or 2))
        self.queue_capacity_var = tk.IntVar(value=int(self.settings.get("queue_capacity") or 32))
        saved_paddle_mode = str(self.settings.get("paddle_scan_mode") or PADDLE_SCAN_MODE_DEFAULT)
        if saved_paddle_mode not in PADDLE_SCAN_MODE_CHOICES:
            saved_paddle_mode = PADDLE_SCAN_MODE_DEFAULT
        self.paddle_scan_mode_var = tk.StringVar(value=saved_paddle_mode)

        provider_configs = self.settings.get("provider_configs") if isinstance(self.settings.get("provider_configs"), dict) else {}
        custom_provider = provider_configs.get("custom_openai") if isinstance(provider_configs.get("custom_openai"), dict) else {}
        self.custom_provider_enabled_var = tk.BooleanVar(value=bool(custom_provider.get("enabled", False)))
        self.custom_provider_name_var = tk.StringVar(value=str(custom_provider.get("name") or "Custom OpenAI"))
        self.custom_base_url_var = tk.StringVar(value=str(custom_provider.get("base_url") or ""))
        self.custom_api_key_var = tk.StringVar(value=str(custom_provider.get("api_key") or ""))
        self.custom_model_var = tk.StringVar(value=str(custom_provider.get("model") or ""))
        self.custom_model_values = list(custom_provider.get("cached_models") or [])
        saved_api_mode = str(custom_provider.get("api_mode") or "auto").strip().lower()
        self.custom_api_mode_var = tk.StringVar(value=saved_api_mode if saved_api_mode in {"auto", "responses", "chat_completions"} else "auto")
        self.provider_cached_api_mode = str(custom_provider.get("cached_api_mode") or "").strip().lower()
        self.provider_timeout_var = tk.IntVar(value=int(custom_provider.get("timeout") or 45))
        self.provider_last_refresh = float(custom_provider.get("last_refreshed_at") or 0.0)

        telegram_settings = self.settings.get("telegram") if isinstance(self.settings.get("telegram"), dict) else {}
        self.telegram_enabled_var = tk.BooleanVar(value=bool(telegram_settings.get("enabled", False)))
        self.telegram_bot_token_var = tk.StringVar(value=str(telegram_settings.get("bot_token") or ""))
        self.telegram_chat_id_var = tk.StringVar(value=str(telegram_settings.get("chat_id") or ""))
        self.telegram_notify_start_var = tk.BooleanVar(value=bool(telegram_settings.get("notify_start", True)))
        self.telegram_notify_progress_var = tk.BooleanVar(value=bool(telegram_settings.get("notify_progress", True)))
        self.telegram_notify_complete_var = tk.BooleanVar(value=bool(telegram_settings.get("notify_complete", True)))
        self.telegram_notify_error_var = tk.BooleanVar(value=bool(telegram_settings.get("notify_error", True)))
        self.telegram_progress_step_var = tk.IntVar(value=int(telegram_settings.get("progress_percent_step") or 10))
        self.telegram_min_interval_var = tk.IntVar(value=int(telegram_settings.get("minimum_interval_seconds") or 60))
        self.telegram_mask_plate_var = tk.BooleanVar(value=bool(telegram_settings.get("mask_plate_number", False)))

        update_settings = self.settings.get("updates") if isinstance(self.settings.get("updates"), dict) else {}
        self.update_manifest_url_var = tk.StringVar(value=str(update_settings.get("manifest_url") or ""))

        self.status_var = tk.StringVar(value="Sẵn sàng")
        self.key_status_var = tk.StringVar()
        self.total_var = tk.StringVar(value="0")
        self.scanned_var = tk.StringVar(value="0")
        self.plates_var = tk.StringVar(value="0")
        self.review_var = tk.StringVar(value="0")
        self.detail_title_var = tk.StringVar(value="Chưa chọn ảnh")
        self.detail_meta_var = tk.StringVar(value="")

        self._build_ui()
        self._bind_settings()
        self._settings_ready = True
        self.status_var.trace_add("write", lambda *_args: self._update_header_status())
        self.engine_var.trace_add("write", lambda *_args: self._update_header_status())
        self.engine_var.trace_add("write", lambda *_args: self._sync_local_ocr_control())
        self.gpt_model_var.trace_add("write", lambda *_args: self._update_header_status())
        self.gemini_model_var.trace_add("write", lambda *_args: self._update_header_status())
        self.custom_model_var.trace_add("write", lambda *_args: self._update_header_status())
        self._update_header_status()
        self._sync_local_ocr_control()
        self._update_key_status()
        self._update_stats()
        self.show_page("scan")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._drain_after_id = self.after(100, self._drain_events)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self._configure_style()
        self.shell = ApplicationShell(self, self)
        self._bind_shortcuts()

    def _configure_style(self) -> None:
        configure_styles(self, self.colors, initialize_theme=not self._theme_initialized)
        self._theme_initialized = True

    def _build_workflow_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        canvas = tk.Canvas(parent, bg=self.colors["bg"], highlightthickness=0, borderwidth=0, width=360)
        self.workflow_canvas = canvas
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)
        workflow = ttk.Frame(canvas, style="App.TFrame")
        workflow_window = canvas.create_window((0, 0), window=workflow, anchor="nw")
        workflow.columnconfigure(0, weight=1)

        workflow.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(workflow_window, width=event.width))
        canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))

        import_box = self._section(workflow, "1. Chọn ảnh", 0)
        import_box.columnconfigure(0, weight=1)
        row = ttk.Frame(import_box, style="Panel.TFrame")
        row.grid(row=0, column=0, sticky="ew")
        row.columnconfigure((0, 1), weight=1)
        ttk.Button(row, text="Chọn file ảnh", command=self.add_files).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(row, text="Chọn thư mục", command=self.add_folder).grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ttk.Checkbutton(import_box, text="Quét cả thư mục con", variable=self.recursive_var).grid(row=1, column=0, sticky="w", pady=(8, 2))
        row = ttk.Frame(import_box, style="Panel.TFrame")
        row.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        row.columnconfigure((0, 1), weight=1)
        ttk.Button(row, text="Bỏ ảnh chọn", command=self.remove_selected).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(row, text="Xóa danh sách", command=self.clear_all).grid(row=0, column=1, sticky="ew", padx=(5, 0))

        ai_box = self._section(workflow, "2. Nhận diện", 1)
        ai_box.columnconfigure(1, weight=1)
        self._form_combo(ai_box, 0, "Engine", self.engine_var, ENGINE_CHOICES, readonly=True)
        self._form_combo(ai_box, 1, "Model Gemini", self.gemini_model_var, GEMINI_MODEL_CHOICES)
        self._form_entry(ai_box, 2, "Gemini API key", self.gemini_api_key_var, secret=True)
        self._form_entry(ai_box, 3, "PlateRec token", self.plate_recognizer_token_var, secret=True)
        self._form_entry(ai_box, 4, "PlateRec region", self.plate_recognizer_region_var)
        self._form_combo(ai_box, 5, "Model GPT", self.gpt_model_var, GPT_MODEL_CHOICES)
        self._form_entry(ai_box, 6, "OpenAI API key", self.openai_api_key_var, secret=True)
        ttk.Checkbutton(ai_box, text="Hiện key", variable=self.show_key_var, command=self._toggle_key_visibility).grid(
            row=7, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Checkbutton(ai_box, text="Lưu key cho lần sau", variable=self.remember_key_var).grid(
            row=7, column=1, sticky="w", pady=(4, 0)
        )
        row = ttk.Frame(ai_box, style="Panel.TFrame")
        row.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        row.columnconfigure((0, 1), weight=1)
        ttk.Button(row, text="Lưu API keys", command=self.save_api_key_now, style="Accent.TButton").grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )
        ttk.Button(row, text="Xóa key đã lưu", command=self.clear_saved_key).grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ttk.Label(ai_box, textvariable=self.key_status_var, style="PanelSubtle.TLabel", wraplength=300).grid(
            row=9, column=0, columnspan=2, sticky="w"
        )

        scan_box = self._section(workflow, "3. Tốc độ và lọc lỗi", 2)
        scan_box.columnconfigure(1, weight=1)
        self._form_spin(scan_box, 0, "Tin cậy tối thiểu", self.conf_threshold_var, 10, 95, 5)
        self._form_spin(scan_box, 1, "Ngưỡng ảnh mờ", self.blur_threshold_var, 10, 500, 5)
        self._form_spin(scan_box, 2, "Luồng xử lý", self.worker_count_var, 1, max(1, os.cpu_count() or 4), 1)
        self._form_combo(scan_box, 3, "Chế độ quét", self.paddle_scan_mode_var, PADDLE_SCAN_MODE_CHOICES, readonly=True)
        self._form_entry(scan_box, 4, "Tesseract", self.tesseract_var)
        ttk.Button(scan_box, text="Chọn tesseract.exe", command=self.choose_tesseract).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=(4, 0)
        )

        output_box = self._section(workflow, "4. File Excel", 3)
        output_box.columnconfigure(0, weight=1)
        ttk.Entry(output_box, textvariable=self.output_var, width=34).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(output_box, text="Chọn nơi lưu Excel", command=self.choose_output).grid(row=1, column=0, sticky="ew")
        ttk.Checkbutton(output_box, text="Nhúng ảnh vào Excel (chậm hơn)", variable=self.embed_excel_images_var).grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )

        log_box = self._section(workflow, "Nhật ký", 4)
        log_box.columnconfigure(0, weight=1)
        self.log_text = tk.Text(
            log_box,
            height=5,
            wrap="word",
            borderwidth=0,
            bg=self.colors["log_bg"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            font=("Segoe UI", 9),
        )
        self.log_text.grid(row=0, column=0, sticky="ew")

    def _form_entry(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, secret: bool = False) -> ttk.Entry:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=0, sticky="w", pady=3)
        entry = ttk.Entry(parent, textvariable=variable, show="*" if secret and not self.show_key_var.get() else "", width=26)
        entry.grid(row=row, column=1, sticky="ew", pady=3)
        if secret:
            entry.bind("<FocusOut>", lambda _event: self.save_api_key_now(silent=True))
            if not hasattr(self, "_secret_entries"):
                self._secret_entries: list[ttk.Entry] = []
            self._secret_entries.append(entry)
        return entry

    @staticmethod
    def _form_combo(parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, values, readonly: bool = False) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=0, sticky="w", pady=3)
        state = "readonly" if readonly else "normal"
        ttk.Combobox(parent, textvariable=variable, values=values, state=state, width=24).grid(row=row, column=1, sticky="ew", pady=3)

    @staticmethod
    def _form_spin(parent: ttk.Frame, row: int, label: str, variable, from_: int, to: int, increment: int) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=0, sticky="w", pady=3)
        ttk.Spinbox(parent, from_=from_, to=to, increment=increment, textvariable=variable, width=8).grid(
            row=row, column=1, sticky="w", pady=3
        )

    def _build_results_area(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        metrics = ttk.Frame(parent, padding=(0, 0, 0, 8), style="App.TFrame")
        metrics.grid(row=0, column=0, sticky="ew")
        metrics.columnconfigure((0, 1, 2, 3), weight=1)
        self._metric(metrics, "Ảnh đã nhập", self.total_var, 0)
        self._metric(metrics, "Ảnh đã quét", self.scanned_var, 1)
        self._metric(metrics, "Biển số tìm được", self.plates_var, 2)
        self._metric(metrics, "Cần kiểm tra", self.review_var, 3)

        content = ttk.Frame(parent, style="App.TFrame")
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=3, minsize=360)
        content.columnconfigure(1, weight=2, minsize=260)
        content.rowconfigure(0, weight=1)
        list_panel = ttk.Frame(content, padding=(10, 10), style="Panel.TFrame")
        detail_panel = ttk.Frame(content, padding=(10, 10), style="Panel.TFrame")
        list_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        detail_panel.grid(row=0, column=1, sticky="nsew")
        self._build_image_list(list_panel)
        self._build_detail_panel(detail_panel)

    def _build_image_list(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        ttk.Label(parent, text="Danh sách ảnh", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        columns = ("file", "plates", "status")
        self.image_tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="extended")
        headings = {"file": "Tên ảnh", "plates": "Biển số trong ảnh", "status": "Trạng thái"}
        widths = {"file": 220, "plates": 280, "status": 125}
        for column in columns:
            self.image_tree.heading(column, text=headings[column])
            self.image_tree.column(column, width=widths[column], anchor="w")
        self._configure_tree_tags()
        self.image_tree.grid(row=1, column=0, sticky="nsew")
        self.image_tree.bind("<<TreeviewSelect>>", self._on_image_selected)
        self.image_tree.bind("<Double-1>", lambda _event: self.open_visual_review())
        scroll_y = ttk.Scrollbar(parent, orient="vertical", command=self.image_tree.yview)
        scroll_y.grid(row=1, column=1, sticky="ns")
        scroll_x = ttk.Scrollbar(parent, orient="horizontal", command=self.image_tree.xview)
        scroll_x.grid(row=2, column=0, sticky="ew")
        self.image_tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

    def _build_detail_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        ttk.Label(parent, textvariable=self.detail_title_var, style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(parent, textvariable=self.detail_meta_var, style="PanelSubtle.TLabel", wraplength=430).grid(
            row=1, column=0, sticky="w", pady=(3, 8)
        )
        self.preview_label = tk.Label(
            parent,
            bg=self.colors["preview_bg"],
            fg=self.colors["on_accent"],
            text="Chọn một ảnh để xem",
            compound="center",
        )
        self.preview_label.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        ttk.Label(parent, text="Biển số của ảnh đang chọn", style="Section.TLabel").grid(row=3, column=0, sticky="w", pady=(0, 6))
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.grid(row=4, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        self.plate_canvas = tk.Canvas(frame, height=105, bg=self.colors["panel"], highlightthickness=0)
        self.plate_canvas.grid(row=0, column=0, sticky="ew")
        plate_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.plate_canvas.yview)
        plate_scroll.grid(row=0, column=1, sticky="ns")
        self.plates_frame = ttk.Frame(self.plate_canvas, style="Panel.TFrame")
        self.plate_canvas_window = self.plate_canvas.create_window((0, 0), window=self.plates_frame, anchor="nw")
        self.plate_canvas.configure(yscrollcommand=plate_scroll.set)
        self.plates_frame.bind("<Configure>", lambda _event: self.plate_canvas.configure(scrollregion=self.plate_canvas.bbox("all")))
        self.plate_canvas.bind("<Configure>", lambda event: self.plate_canvas.itemconfigure(self.plate_canvas_window, width=event.width))
        buttons = ttk.Frame(parent, padding=(0, 10, 0, 0), style="Panel.TFrame")
        buttons.grid(row=5, column=0, sticky="ew")
        buttons.columnconfigure((0, 1), weight=1)
        ttk.Button(buttons, text="Lưu sửa", command=self.save_detail_edits).grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=(0, 6))
        ttk.Button(buttons, text="Tick đúng hết", command=self.approve_current_image).grid(
            row=0, column=1, sticky="ew", padx=(4, 0), pady=(0, 6)
        )
        ttk.Button(buttons, text="Thêm biển số", command=self.add_manual_plate).grid(row=1, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Mở ảnh gốc", command=self.open_current_image).grid(row=1, column=1, sticky="ew", padx=(4, 0))

    @staticmethod
    def _section(parent: ttk.Frame, title: str, row: int) -> ttk.LabelFrame:
        section = ttk.LabelFrame(parent, text=title, padding=(10, 8))
        section.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        return section

    @staticmethod
    def _metric(parent: ttk.Frame, label: str, variable: tk.StringVar, column: int) -> None:
        card = ttk.Frame(parent, padding=(12, 10), style="Panel.TFrame")
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
        ttk.Label(card, textvariable=variable, style="MetricValue.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, text=label, style="MetricName.TLabel").grid(row=1, column=0, sticky="w")

    def add_files(self) -> None:
        files = filedialog.askopenfilenames(
            title="Chọn ảnh",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp *.heic *.heif"), ("All files", "*.*")],
        )
        self._add_paths([Path(file) for file in files])

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Chọn thư mục ảnh")
        if not folder:
            return
        try:
            paths = collect_images([Path(folder)], recursive=bool(self.recursive_var.get()))
        except Exception as exc:
            messagebox.showerror("Lỗi đọc thư mục", str(exc), parent=self)
            return
        self._add_paths(paths)

    def remove_selected(self) -> None:
        selected = self._selected_paths()
        if not selected:
            return
        self.images = [path for path in self.images if path not in selected]
        self.results = [result for result in self.results if result.image_path not in selected]
        if self.selected_image_path in selected:
            self.selected_image_path = None
            self.current_detail_result = None
        self._refresh_table()
        self.input_summary_var.set(f"Đã chọn {len(self.images)} ảnh.")

    def clear_all(self) -> None:
        self.images.clear()
        self.results.clear()
        self.image_row_map.clear()
        self.selected_image_path = None
        self.current_detail_result = None
        self.detail_row_vars.clear()
        if hasattr(self, "image_tree"):
            self.image_tree.delete(*self.image_tree.get_children())
        if hasattr(self, "review_tree"):
            self.review_tree.delete(*self.review_tree.get_children())
        self._render_detail(None)
        self._update_stats()
        self.input_summary_var.set("Chưa có ảnh nào được chọn.")

    def choose_tesseract(self) -> None:
        selected = filedialog.askopenfilename(title="Chọn tesseract.exe", filetypes=[("tesseract.exe", "tesseract.exe"), ("All files", "*.*")])
        if selected:
            self.tesseract_var.set(selected)

    def choose_output(self) -> None:
        selected = filedialog.asksaveasfilename(
            title="Chọn file Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("All files", "*.*")],
            initialfile=Path(self.output_var.get()).name,
        )
        if selected:
            self.output_var.set(selected)
            self._schedule_settings_save()

    def start_processing(self) -> None:
        self._start_processing(list(self.images), retry_failed=False)

    def retry_failed_images(self) -> None:
        failed_images = self._failed_image_paths()
        if not failed_images:
            messagebox.showinfo("Khong co anh loi", "Khong con anh nao chua doc duoc de quet lai.", parent=self)
            return
        self._start_processing(failed_images, retry_failed=True)

    def _start_processing(self, target_images: list[Path], retry_failed: bool = False) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not target_images:
            self._notify("Hãy thêm ảnh hoặc thư mục trước khi bắt đầu quét.", "warning")
            return

        self._save_detail_edits()
        self._save_settings()
        engine_mode = self.engine_var.get()
        tesseract_path = self.tesseract_var.get().strip() or None
        openai_api_key = self.openai_api_key_var.get().strip()
        gemini_api_key = self.gemini_api_key_var.get().strip()
        plate_token = self.plate_recognizer_token_var.get().strip()
        gpt_model = self.gpt_model_var.get().strip() or DEFAULT_GPT_MODEL
        gemini_model = self.gemini_model_var.get().strip() or DEFAULT_GEMINI_MODEL
        plate_region = self.plate_recognizer_region_var.get().strip() or DEFAULT_PLATE_RECOGNIZER_REGION
        paddle_scan_mode = self.paddle_scan_mode_var.get().strip() or PADDLE_SCAN_MODE_DEFAULT
        if retry_failed and engine_mode == "PaddleOCR Local":
            paddle_scan_mode = "thorough"
        confidence_threshold = float(self.conf_threshold_var.get())
        if retry_failed:
            confidence_threshold = min(confidence_threshold, 30.0)

        if not retry_failed:
            self.retry_failed_before_count = 0
        else:
            self.retry_failed_before_count = len(target_images)
        self.progress.configure(maximum=len(target_images), value=0)
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.retry_failed_button.configure(state="disabled")
        self._set_export_buttons_state("disabled")
        if hasattr(self, "export_reviewed_button"):
            self.export_reviewed_button.configure(state="disabled")
        self._set_review_buttons(False)
        self.stop_event.clear()

        worker_settings = self._worker_settings(engine_mode, len(target_images))
        self.batch_progress = BatchProgress(total=len(target_images), configured_workers={})
        self.batch_progress.preparing_model()
        self.telegram_percent_sent.clear()
        self._start_telegram_lifecycle(len(target_images), engine_mode)

        self.status_var.set(f"Đang chuẩn bị {engine_mode}...")
        self._log(f"Đang chuẩn bị {engine_mode} trong worker nền.")
        args = (
            list(target_images),
            Path(self.output_var.get()).expanduser(),
            engine_mode,
            tesseract_path,
            openai_api_key,
            gpt_model,
            gemini_api_key,
            gemini_model,
            plate_token,
            plate_region,
            float(self.blur_threshold_var.get()),
            confidence_threshold,
            worker_settings,
            paddle_scan_mode,
            retry_failed,
            self._custom_provider_snapshot(),
        )
        self.worker = threading.Thread(target=self._worker_process, args=args, daemon=True)
        self.worker.start()

    def stop_processing(self) -> None:
        if not self.worker or not self.worker.is_alive():
            return
        self.stop_event.set()
        if self.worker_manager:
            self.worker_manager.stop()
        if self.batch_progress:
            self.batch_progress.request_stop()
        self.stop_button.configure(state="disabled")
        self.status_var.set("Đang dừng sau ảnh hiện tại...")
        self._log("Đã yêu cầu dừng quét. App sẽ dừng sau ảnh đang xử lý.")

    def _worker_process(
        self,
        images: list[Path],
        output_path: Path,
        engine_mode: str,
        tesseract_path: str | None,
        openai_api_key: str | None,
        gpt_model: str,
        gemini_api_key: str | None,
        gemini_model: str,
        plate_token: str | None,
        plate_region: str,
        blur_threshold: float,
        confidence_threshold: float,
        worker_settings: WorkerSettings | int,
        paddle_scan_mode: str,
        retry_failed: bool = False,
        custom_provider: dict[str, object] | None = None,
    ) -> None:
        crop_dir = output_path.with_suffix("").parent / f"{output_path.stem}_crops"
        try:
            engine = self._make_engine(
                engine_mode,
                tesseract_path,
                openai_api_key,
                gpt_model,
                gemini_api_key,
                gemini_model,
                plate_token,
                plate_region,
                custom_provider,
            )
            if not engine.available:
                self.event_queue.put(("engine_unavailable", engine.reason))
                return
            settings = worker_settings if isinstance(worker_settings, WorkerSettings) else WorkerSettings(
                mode="MANUAL",
                image_workers=max(1, int(worker_settings)),
                local_ocr_workers=1,
                api_workers=max(1, int(worker_settings)),
                queue_capacity=max(2, len(images)),
            )
            manager = WorkerManager(settings, engine_mode, self.stop_event)
            self.worker_manager = manager
            progress = BatchProgress(total=len(images), configured_workers=manager.configured_workers)
            self.batch_progress = progress
            progress.preparing_model()
            self.event_queue.put(("engine_ready", engine_mode, len(images), manager.configured_workers, retry_failed))
            progress.start()
            last_progress_event = 0.0

            def emit_progress(*, force: bool = False) -> None:
                nonlocal last_progress_event
                now = time.monotonic()
                if force or now - last_progress_event >= 0.15:
                    self.event_queue.put(("progress", progress.snapshot()))
                    last_progress_event = now

            def prepare(image: Path):
                # Decode/exif conversion is independent from inference.  Passing
                # the decoded frame to the local processor avoids a second read.
                if engine_mode in {"PaddleOCR Local", "Local OCR"}:
                    image_bgr, image_size = load_image(image)
                    return image, image_bgr, image_size
                if not image.is_file():
                    raise FileNotFoundError(f"Không tìm thấy ảnh: {image}")
                return image, None, None

            def infer(prepared):
                image, image_bgr, image_size = prepared
                return self._process_one(
                    0,
                    image,
                    crop_dir,
                    engine_mode,
                    engine,
                    tesseract_path,
                    blur_threshold,
                    confidence_threshold,
                    paddle_scan_mode,
                    image_bgr=image_bgr,
                    image_size=image_size,
                )

            def on_started(item: WorkItem[Path], pool: str) -> None:
                progress.mark_started(item.value.name, pool)
                emit_progress()

            def on_finished(item: WorkItem[Path], outcome: ImageResult | Exception, pool: str) -> None:
                if isinstance(outcome, Exception):
                    result = ImageResult(
                        image_path=item.value,
                        status="ERROR",
                        reason="Không thể xử lý ảnh",
                        error=str(outcome),
                    )
                    outcome_name = "failed"
                else:
                    result = outcome
                    outcome_name = "success" if result.status == "OK" else ("failed" if result.status == "ERROR" else "review")
                progress.mark_finished(item.value.name, pool, outcome_name)
                snapshot = progress.snapshot()
                self.event_queue.put(("retry_result" if retry_failed else "result", progress.completed, len(images), result, snapshot))

            ordered_results = manager.run_pipeline(images, prepare, infer, on_started=on_started, on_finished=on_finished)
            completed_results = [result for result in ordered_results if isinstance(result, ImageResult)]
            progress.finish(cancelled=self.stop_event.is_set())
            emit_progress(force=True)
            if engine_mode == "OpenAI Compatible" and getattr(engine, "last_api_mode", ""):
                self.event_queue.put(("provider_capability", engine.last_api_mode))
            if retry_failed:
                event_name = "done_retry_stopped" if self.stop_event.is_set() else "done_retry"
            else:
                event_name = "done_scan_stopped" if self.stop_event.is_set() else "done_scan"
            self.event_queue.put((event_name, completed_results, progress.snapshot()))
        except Exception as exc:
            if self.batch_progress:
                self.batch_progress.finish(fatal=True)
                self.event_queue.put(("progress", self.batch_progress.snapshot()))
            self.event_queue.put(("error", str(exc)))

    @staticmethod
    def _make_engine(
        engine_mode: str,
        tesseract_path: str | None,
        openai_api_key: str | None,
        gpt_model: str,
        gemini_api_key: str | None,
        gemini_model: str,
        plate_token: str | None,
        plate_region: str,
        custom_provider: dict[str, object] | None = None,
    ):
        if engine_mode == "GPT Vision":
            return GptVisionEngine(openai_api_key, gpt_model)
        if engine_mode == "OpenAI Compatible":
            provider = custom_provider or {}
            if not provider.get("enabled"):
                return _UnavailableEngine("Provider custom chưa được bật.")
            if not str(provider.get("base_url") or "").strip():
                return _UnavailableEngine("Provider custom chưa có Base URL.")
            return GptVisionEngine(
                str(provider.get("api_key") or ""),
                str(provider.get("model") or gpt_model),
                timeout=float(provider.get("timeout") or 45.0),
                base_url=str(provider.get("base_url") or ""),
                api_mode=str(provider.get("api_mode") or "auto"),
                cached_api_mode=str(provider.get("cached_api_mode") or ""),
            )
        if engine_mode == "Gemini Vision":
            return GeminiVisionEngine(gemini_api_key, gemini_model)
        if engine_mode == "Plate Recognizer":
            return PlateRecognizerEngine(plate_token, plate_region)
        if engine_mode == "PaddleOCR Local":
            return PaddleOcrEngine(25.0)
        return TesseractOcrEngine(tesseract_path, 35.0)

    @staticmethod
    def _process_one(
        index: int,
        image: Path,
        crop_dir: Path,
        engine_mode: str,
        engine,
        tesseract_path: str | None,
        blur_threshold: float,
        confidence_threshold: float,
        paddle_scan_mode: str = PADDLE_SCAN_MODE_DEFAULT,
        image_bgr=None,
        image_size: tuple[int, int] | None = None,
    ) -> ImageResult:
        _ = index
        if engine_mode == "GPT Vision":
            return engine.analyze_image(image, blur_threshold)
        if engine_mode == "Gemini Vision":
            gemini_result = engine.analyze_image(image, blur_threshold)
            if _needs_local_fallback(gemini_result):
                local_engine = TesseractOcrEngine(tesseract_path, confidence_threshold)
                if local_engine.available:
                    local_result = process_image(image, crop_dir, local_engine, blur_threshold, max(20.0, confidence_threshold - 10.0))
                    return _merge_gemini_local_result(gemini_result, local_result)
                gemini_result.warnings.append(f"Không fallback Local OCR được: {local_engine.reason}")
            return gemini_result
        if engine_mode == "Plate Recognizer":
            return engine.analyze_image(image, blur_threshold)
        if engine_mode == "PaddleOCR Local":
            return process_image(
                image,
                crop_dir,
                engine,
                blur_threshold,
                max(20.0, confidence_threshold - 10.0),
                paddle_scan_mode=paddle_scan_mode,
                image_bgr=image_bgr,
                image_size=image_size,
            )
        return process_image(image, crop_dir, engine, blur_threshold, confidence_threshold, image_bgr=image_bgr, image_size=image_size)

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.event_queue.get_nowait()
                kind = event[0]
                if kind == "engine_ready":
                    _, engine_mode, total, workers, retry_failed = event
                    if not retry_failed:
                        self.results = []
                        self.current_detail_result = None
                        self.detail_row_vars.clear()
                        self._refresh_table()
                    worker_text = self._format_worker_summary(workers)
                    self.status_var.set(f"Đang quét {total} ảnh bằng {engine_mode}. {worker_text}")
                    self._log(f"Engine sẵn sàng. Bắt đầu quét {total} ảnh bằng {engine_mode}.")
                elif kind == "engine_unavailable":
                    _, reason = event
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self._set_export_buttons_state("normal" if self.results else "disabled")
                    self._set_review_buttons(bool(self.results))
                    self._update_retry_button()
                    self.status_var.set("Engine chưa sẵn sàng")
                    self._log(f"Engine chưa sẵn sàng: {reason}")
                    self._notify(f"Engine chưa sẵn sàng: {reason}", "error")
                elif kind == "result":
                    _, completed, total, result, *rest = event
                    snapshot = rest[0] if rest else None
                    self.results.append(result)
                    self.progress.configure(value=completed)
                    self._upsert_image_row(result.image_path)
                    self._update_stats()
                    if snapshot:
                        self._apply_progress_snapshot(snapshot)
                    if self.selected_image_path == result.image_path:
                        self._render_detail(result)
                    self.status_var.set(f"Đã xử lý {completed}/{total}: {result.image_path.name}")
                    self._notify_telegram_progress(snapshot)
                elif kind == "retry_result":
                    _, completed, total, result, *rest = event
                    snapshot = rest[0] if rest else None
                    self._replace_result(result)
                    self.progress.configure(value=completed)
                    self._upsert_image_row(result.image_path)
                    self._update_stats()
                    if snapshot:
                        self._apply_progress_snapshot(snapshot)
                    if self.selected_image_path == result.image_path:
                        self._render_detail(result)
                    self.status_var.set(f"Da quet lai {completed}/{total}: {result.image_path.name}")
                elif kind == "progress":
                    _, snapshot = event
                    self._apply_progress_snapshot(snapshot)
                elif kind == "done_scan":
                    _, results, *rest = event
                    self.results = results
                    self.progress.configure(value=len(results))
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self._set_export_buttons_state("normal")
                    self._set_review_buttons(bool(results))
                    self._refresh_table()
                    self.status_var.set("Quét xong")
                    self._log(f"Quét xong {len(results)} ảnh, tìm thấy {self.plates_var.get()} biển số/candidate.")
                    if rest:
                        self._apply_progress_snapshot(rest[0], force=True)
                    self._finish_telegram_lifecycle("completed")
                    self._notify("Quét xong. Mở Phiên hiện tại để xem kết quả hoặc Xuất Excel để tạo báo cáo.", "success")
                elif kind == "done_retry":
                    _, results, *rest = event
                    for result in results:
                        self._replace_result(result)
                    self.progress.configure(value=len(results))
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self._set_export_buttons_state("normal" if self.results else "disabled")
                    self._set_review_buttons(bool(self.results))
                    self._refresh_table()
                    remaining = len(self._failed_image_paths())
                    recovered = max(0, self.retry_failed_before_count - remaining)
                    self.status_var.set(f"Quet lai xong, doc them {recovered} anh, con {remaining} anh chua doc duoc")
                    self._log(f"Quet lai xong {len(results)} anh bang che do ky. Doc them {recovered} anh, con {remaining} anh chua doc duoc.")
                    if rest:
                        self._apply_progress_snapshot(rest[0], force=True)
                    self._finish_telegram_lifecycle("completed")
                    self._notify(f"Quét lại xong: phục hồi {recovered} ảnh, còn {remaining} ảnh cần kiểm tra.", "success")
                elif kind == "done_scan_stopped":
                    _, results, *rest = event
                    self.results = results
                    self.progress.configure(value=len(results))
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self._set_export_buttons_state("normal" if results else "disabled")
                    self._set_review_buttons(bool(results))
                    self._refresh_table()
                    self.status_var.set(f"Đã dừng, giữ {len(results)} ảnh đã quét")
                    self._log(f"Đã dừng quét. Giữ {len(results)} ảnh đã xử lý, tìm thấy {self.plates_var.get()} biển số/candidate.")
                    if rest:
                        self._apply_progress_snapshot(rest[0], force=True)
                    self._finish_telegram_lifecycle("cancelled")
                elif kind == "done_retry_stopped":
                    _, results, *rest = event
                    for result in results:
                        self._replace_result(result)
                    self.progress.configure(value=len(results))
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self._set_export_buttons_state("normal" if self.results else "disabled")
                    self._set_review_buttons(bool(self.results))
                    self._refresh_table()
                    self.status_var.set(f"Da dung quet lai, cap nhat {len(results)} anh")
                    self._log(f"Da dung quet lai. Cap nhat {len(results)} anh da xu ly.")
                    if rest:
                        self._apply_progress_snapshot(rest[0], force=True)
                    self._finish_telegram_lifecycle("cancelled")
                elif kind == "error":
                    _, message = event
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self._update_retry_button()
                    self.status_var.set("Có lỗi khi quét")
                    self._log(f"Lỗi: {message}")
                    self._finish_telegram_lifecycle("error", message)
                    self._notify(f"Batch gặp lỗi: {message}", "error")
                elif kind == "export_done":
                    _, reviewed, exported_path, exported_count = event
                    self._set_export_buttons_state("normal" if self.results else "disabled")
                    self.output_var.set(str(exported_path))
                    mode_label = "đã duyệt" if reviewed else "đọc được"
                    self.status_var.set("Đã xuất Excel")
                    self._log(f"Đã xuất Excel: {exported_path}")
                    self.export_status_var.set(f"Đã xuất {exported_count} biển số {mode_label}: {exported_path}")
                    self._notify("Xuất Excel hoàn tất. File đã được lưu an toàn.", "success")
                elif kind == "export_error":
                    _, message = event
                    self._set_export_buttons_state("normal" if self.results else "disabled")
                    self.status_var.set("Có lỗi xuất Excel")
                    self._log(f"Lỗi xuất Excel: {message}")
                    self.export_status_var.set(message)
                    self._notify(f"Không xuất được Excel: {message}", "error")
                elif kind == "provider_status":
                    _, status, values = event
                    self._apply_provider_status(status, values)
                elif kind == "provider_capability":
                    _, api_mode = event
                    self.provider_cached_api_mode = str(api_mode)
                    self.provider_status_var.set(f"Provider inference đã xác nhận API mode: {api_mode}.")
                    self._schedule_settings_save()
                elif kind == "telegram_delivery":
                    _, sent, error = event
                    if sent:
                        self.telegram_status_var.set("Đã gửi Telegram thành công.")
                    elif error:
                        self.telegram_status_var.set(f"Telegram không gửi được: {error}")
                elif kind == "update_checked":
                    _, manifest = event
                    comparison = compare_versions(manifest.version, __version__)
                    self.current_update_manifest = manifest if comparison > 0 else None
                    if comparison > 0:
                        self.update_status_var.set(f"Có bản mới {manifest.version}. Chưa tải file.")
                    elif comparison == 0:
                        self.update_status_var.set(f"Đang dùng đúng phiên bản {__version__}; không cần tải lại.")
                    else:
                        self.update_status_var.set(f"Manifest có bản {manifest.version} cũ hơn phiên bản hiện tại {__version__}.")
                    self.update_notes_var.set(manifest.release_notes)
                    if self.update_download_button:
                        self.update_download_button.configure(state="normal" if comparison > 0 else "disabled")
                    if self.update_check_button:
                        self.update_check_button.configure(state="normal")
                elif kind == "update_downloaded":
                    _, downloaded = event
                    self.update_status_var.set(f"Đã tải và xác minh SHA-256: {downloaded}. Sẵn sàng cài đặt thủ công.")
                elif kind == "update_error":
                    _, message = event
                    self.update_status_var.set(message)
                    if self.update_check_button:
                        self.update_check_button.configure(state="normal")
                    if self.update_download_button:
                        self.update_download_button.configure(state="normal" if self.current_update_manifest else "disabled")
        except queue.Empty:
            pass
        self._drain_after_id = self.after(100, self._drain_events)

    def show_page(self, page_name: str) -> None:
        self.shell.show_page(page_name)

    def _bind_shortcuts(self) -> None:
        self.bind_all("<Control-o>", lambda _event: self.add_files())
        self.bind_all("<Control-Shift-O>", lambda _event: self.add_folder())
        self.bind_all("<Control-Return>", lambda _event: self.start_processing())
        self.bind_all("<Control-e>", lambda _event: self.export_all_results())
        self.bind_all("<Control-comma>", lambda _event: self.show_page("settings"))
        self.bind_all("<F5>", lambda _event: self.refresh_provider_models())
        self.bind_all("<Control-f>", lambda _event: (self.show_page("session"), self.focus_session_search()))
        self.bind_all("<Escape>", lambda _event: self.stop_processing())

    def focus_session_search(self) -> None:
        entry = getattr(self, "session_search_entry", None)
        if entry is not None:
            entry.focus_set()

    def _worker_settings(self, engine_mode: str, image_count: int) -> WorkerSettings:
        mode = self.worker_mode_var.get().strip().upper()
        settings = WorkerSettings(
            mode=mode if mode in {"AUTO", "MANUAL"} else "AUTO",
            image_workers=max(1, self._safe_int_var(self.image_workers_var, _default_worker_count())),
            local_ocr_workers=max(1, self._safe_int_var(self.local_ocr_workers_var, 1)),
            api_workers=max(1, self._safe_int_var(self.api_workers_var, 2)),
            queue_capacity=max(1, self._safe_int_var(self.queue_capacity_var, 32)),
        ).resolved(engine_mode)
        # WorkerManager resolves AUTO itself. Return the already resolved
        # values as MANUAL so the per-batch image-count cap is not discarded.
        return WorkerSettings(
            mode="MANUAL",
            image_workers=min(settings.image_workers, max(1, image_count)),
            local_ocr_workers=min(settings.local_ocr_workers, max(1, image_count)),
            api_workers=min(settings.api_workers, max(1, image_count)),
            queue_capacity=min(max(settings.queue_capacity, 1), max(1, image_count)),
        )

    @staticmethod
    def _format_worker_summary(workers: dict[str, int] | int) -> str:
        if isinstance(workers, dict):
            return f"Ảnh {workers.get('image', 0)} • OCR local {workers.get('local_ocr', 0)} • API {workers.get('api', 0)}"
        return f"{workers} worker"

    def _apply_progress_snapshot(self, snapshot: dict[str, object], *, force: bool = False) -> None:
        now = datetime.now().timestamp()
        if not force and now - self._last_progress_render_at < 0.12:
            self.ui_state.batch_snapshot = dict(snapshot)
            return
        self._last_progress_render_at = now
        self.ui_state.batch_snapshot = dict(snapshot)
        total = int(snapshot.get("total") or 0)
        completed = int(snapshot.get("completed") or 0)
        self.progress.configure(maximum=max(1, total), value=completed)
        status = str(snapshot.get("status") or "")
        percent = int(snapshot.get("percent") or 0)
        self.progress_primary_var.set(f"{status}: {completed}/{total} ảnh ({percent}%)")
        elapsed = float(snapshot.get("elapsed_seconds") or 0.0)
        rate = float(snapshot.get("images_per_minute") or 0.0)
        eta = snapshot.get("eta_seconds")
        eta_text = "ETA đang tính" if eta is None else f"ETA {self._format_duration(float(eta))}"
        self.progress_timing_var.set(f"Đã chạy {self._format_duration(elapsed)} • {rate:.1f} ảnh/phút • {eta_text}")
        active_workers = snapshot.get("active_workers") if isinstance(snapshot.get("active_workers"), dict) else {}
        configured = snapshot.get("configured_workers") if isinstance(snapshot.get("configured_workers"), dict) else {}
        self.progress_workers_var.set(f"Đang chạy {active_workers} / cấu hình {configured}")
        current = ", ".join(str(value) for value in list(snapshot.get("current_files") or [])[:3]) or "Đang chờ task tiếp theo"
        self.progress_detail_var.set(
            f"{current} • Thành công {snapshot.get('succeeded', 0)} • Review {snapshot.get('needs_review', 0)} • Lỗi {snapshot.get('failed', 0)}"
        )

    @staticmethod
    def _format_duration(value: float) -> str:
        seconds = max(0, int(round(value)))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _telegram_settings_snapshot(self) -> TelegramSettings:
        return TelegramSettings(
            enabled=bool(self.telegram_enabled_var.get()),
            bot_token=self.telegram_bot_token_var.get().strip(),
            chat_id=self.telegram_chat_id_var.get().strip(),
            notify_start=bool(self.telegram_notify_start_var.get()),
            notify_progress=bool(self.telegram_notify_progress_var.get()),
            notify_complete=bool(self.telegram_notify_complete_var.get()),
            notify_error=bool(self.telegram_notify_error_var.get()),
            progress_percent_step=max(5, min(100, self._safe_int_var(self.telegram_progress_step_var, 10))),
            minimum_interval_seconds=max(0, self._safe_int_var(self.telegram_min_interval_var, 60)),
            mask_plate_number=bool(self.telegram_mask_plate_var.get()),
        )

    def _start_telegram_lifecycle(self, total: int, engine_mode: str) -> None:
        if self.telegram_notifier:
            self.telegram_notifier.close()
            self.telegram_notifier = None
        settings = self._telegram_settings_snapshot()
        if not settings.enabled:
            self.telegram_status_var.set("Telegram đang tắt.")
            return
        if not settings.bot_token or not settings.chat_id:
            self.telegram_status_var.set("Telegram bật nhưng thiếu Bot token hoặc Chat ID; batch vẫn tiếp tục.")
            return
        self.telegram_notifier = AsyncTelegramNotifier(
            settings,
            timeout=8.0,
            retries=1,
            on_delivery=lambda sent, error: self.event_queue.put(("telegram_delivery", sent, error)),
        )
        self.telegram_status_var.set("Telegram đang gửi thông báo nền.")
        if settings.notify_start:
            self.telegram_notifier.send_later(f"Check Vehicle OCR bắt đầu quét {total} ảnh bằng {engine_mode}.", force=True)

    def _notify_telegram_progress(self, snapshot: dict[str, object] | None) -> None:
        if not snapshot or not self.telegram_notifier:
            return
        settings = self._telegram_settings_snapshot()
        if not settings.notify_progress:
            return
        percent = int(snapshot.get("percent") or 0)
        step = max(5, settings.progress_percent_step)
        milestone = percent - (percent % step)
        if milestone <= 0 or milestone >= 100 or milestone in self.telegram_percent_sent:
            return
        self.telegram_percent_sent.add(milestone)
        self.telegram_notifier.send_later(
            f"Check Vehicle OCR: {milestone}% ({snapshot.get('completed', 0)}/{snapshot.get('total', 0)} ảnh)."
        )

    def _finish_telegram_lifecycle(self, outcome: str, error: str = "") -> None:
        notifier = self.telegram_notifier
        if not notifier:
            return
        settings = self._telegram_settings_snapshot()
        snapshot = self.ui_state.batch_snapshot
        if outcome == "completed" and settings.notify_complete:
            notifier.send_later(f"Check Vehicle OCR hoàn tất: {snapshot.get('completed', 0)}/{snapshot.get('total', 0)} ảnh.", force=True)
        elif outcome == "cancelled" and settings.notify_error:
            notifier.send_later(f"Check Vehicle OCR đã dừng: giữ {snapshot.get('completed', 0)} ảnh đã xử lý.", force=True)
        elif outcome == "error" and settings.notify_error:
            notifier.send_later(f"Check Vehicle OCR gặp lỗi batch: {redact_provider_error(error, settings.bot_token)}", force=True)

    def send_telegram_test(self) -> None:
        settings = self._telegram_settings_snapshot()
        if not settings.enabled or not settings.bot_token or not settings.chat_id:
            self.telegram_status_var.set("Cần bật Telegram, nhập Bot token và Chat ID trước khi gửi tin thử.")
            return
        if self.telegram_notifier:
            self.telegram_notifier.close()
        notifier = AsyncTelegramNotifier(settings, timeout=8.0, retries=1, on_delivery=lambda sent, error: self.event_queue.put(("telegram_delivery", sent, error)))
        notifier.send_later("Check Vehicle OCR: kiểm tra Telegram thành công nếu bạn nhận được tin này.", force=True)
        # Test delivery is detached from OCR. Keep a reference only until the
        # app closes; its daemon worker exits after the queue drains.
        self.telegram_notifier = notifier
        self.telegram_status_var.set("Đã xếp hàng gửi tin thử.")

    def _custom_provider_snapshot(self) -> dict[str, object]:
        return {
            "enabled": bool(self.custom_provider_enabled_var.get()),
            "name": self.custom_provider_name_var.get().strip() or "Custom OpenAI",
            "base_url": self.custom_base_url_var.get().strip().rstrip("/"),
            "api_key": self.custom_api_key_var.get().strip(),
            "model": self.custom_model_var.get().strip(),
            "api_mode": self.custom_api_mode_var.get().strip().lower(),
            "cached_api_mode": self.provider_cached_api_mode,
            "timeout": max(3, self._safe_int_var(self.provider_timeout_var, 45)),
            "cached_models": list(self.custom_model_values),
            "last_refreshed_at": self.provider_last_refresh,
        }

    def refresh_provider_models(self) -> None:
        self._run_provider_action("refresh")

    def test_provider_connection(self) -> None:
        self._run_provider_action("test")

    def _run_provider_action(self, action: str) -> None:
        config = self._custom_provider_snapshot()
        if not config["base_url"]:
            self.provider_status_var.set("Cần nhập Base URL trước khi kiểm tra hoặc làm mới model.")
            return
        if self.provider_refresh_button:
            self.provider_refresh_button.configure(state="disabled")
        if self.provider_test_button:
            self.provider_test_button.configure(state="disabled")
        self.provider_status_var.set("Đang kết nối provider ở nền…")

        def worker() -> None:
            provider = OpenAICompatibleProvider(
                ProviderConfig(
                    name=str(config["name"]),
                    api_key=str(config["api_key"]),
                    base_url=str(config["base_url"]),
                    model=str(config["model"]),
                    manual_models=[str(config["model"])] if config["model"] else [],
                    api_mode=str(config["api_mode"]),
                    cached_api_mode=str(config["cached_api_mode"]),
                ),
                timeout=float(config["timeout"]),
            )
            status = provider.refresh_models() if action == "refresh" else provider.test_connection()
            self.event_queue.put(("provider_status", status, list(status.models)))

        threading.Thread(target=worker, name="check_vehicle_provider", daemon=True).start()

    def _apply_provider_status(self, status: ProviderStatus, values: list[str]) -> None:
        message = status.message
        if status.ok:
            self.provider_last_refresh = status.refreshed_at
            current_model = self.custom_model_var.get().strip()
            if current_model and current_model not in values:
                message += f" Model đang chọn '{current_model}' không có trong danh sách nhưng vẫn được giữ."
            self.custom_model_values = list(dict.fromkeys([*values, current_model]))
            if self.custom_model_combo:
                self.custom_model_combo.configure(values=self.custom_model_values)
            message += f" Làm mới lúc {datetime.fromtimestamp(status.refreshed_at):%H:%M:%S}."
        self.provider_status_var.set(message)
        if self.provider_refresh_button:
            self.provider_refresh_button.configure(state="normal")
        if self.provider_test_button:
            self.provider_test_button.configure(state="normal")
        self._schedule_settings_save()

    def check_for_updates(self) -> None:
        manifest_url = self.update_manifest_url_var.get().strip()
        if not manifest_url:
            self.update_status_var.set("Chưa cấu hình manifest URL. Nhập URL release/manifest trước khi kiểm tra.")
            return
        if self.update_check_button:
            self.update_check_button.configure(state="disabled")
        self.update_status_var.set("Đang tải manifest ở nền…")

        def worker() -> None:
            try:
                manifest = fetch_manifest(manifest_url, timeout=15.0)
            except Exception as exc:
                self.event_queue.put(("update_error", f"Không kiểm tra được cập nhật: {exc}"))
            else:
                self.event_queue.put(("update_checked", manifest))

        threading.Thread(target=worker, name="check_vehicle_update_check", daemon=True).start()

    def download_update(self) -> None:
        manifest = self.current_update_manifest
        if not manifest:
            self.update_status_var.set("Hãy kiểm tra manifest trước khi tải cập nhật.")
            return
        if self.update_download_button:
            self.update_download_button.configure(state="disabled")
        self.update_status_var.set("Đang tải và xác minh SHA-256 ở nền…")

        def worker() -> None:
            try:
                destination = settings_path().parent / "updates"
                downloaded = download_verified(manifest, destination, timeout=60.0)
            except Exception as exc:
                self.event_queue.put(("update_error", f"Không tải được cập nhật: {exc}"))
            else:
                self.event_queue.put(("update_downloaded", downloaded))

        threading.Thread(target=worker, name="check_vehicle_update_download", daemon=True).start()

    def _notify(self, message: str, level: str = "info") -> None:
        self.ui_state.notify(message, level)
        self.notification_var.set(message)

    def _update_header_status(self) -> None:
        engine = self.engine_var.get()
        if engine == "GPT Vision":
            model = self.gpt_model_var.get().strip() or DEFAULT_GPT_MODEL
        elif engine == "Gemini Vision":
            model = self.gemini_model_var.get().strip() or DEFAULT_GEMINI_MODEL
        elif engine == "OpenAI Compatible":
            model = self.custom_model_var.get().strip() or "chưa chọn model"
        else:
            model = "local" if engine in {"PaddleOCR Local", "Local OCR"} else "API"
        self.header_status_var.set(f"{engine} • {model} • {self.status_var.get()}")

    def _sync_local_ocr_control(self) -> None:
        is_paddle = self.engine_var.get() == "PaddleOCR Local"
        if is_paddle:
            self.local_ocr_workers_var.set(1)
            self.local_ocr_hint_var.set("PaddleOCR local chạy một inference worker để đảm bảo ổn định; image worker vẫn có thể song song.")
        else:
            self.local_ocr_hint_var.set("Local OCR dùng giới hạn worker local đã cấu hình.")
        control = getattr(self, "local_ocr_workers_spin", None)
        if control is not None:
            control.configure(state="disabled" if is_paddle else "normal")

    def save_detail_edits(self) -> None:
        self._save_detail_edits()
        if self.current_detail_result:
            self._upsert_image_row(self.current_detail_result.image_path)
            self._update_stats()
            self._log(f"Đã lưu sửa cho ảnh: {self.current_detail_result.image_path.name}")

    def approve_current_image(self) -> None:
        if not self.current_detail_result:
            return
        for _plate, text_var, approved_var in self.detail_row_vars:
            if text_var.get().strip():
                approved_var.set(True)
        self.save_detail_edits()
        self._select_next_result(self.current_detail_result.image_path)

    def add_manual_plate(self) -> None:
        result = self.current_detail_result
        if result is None:
            messagebox.showwarning("Chưa chọn ảnh", "Chọn ảnh đã quét trước khi thêm biển số.", parent=self)
            return
        self._save_detail_edits()
        result.plates.append(
            PlateCandidate(
                bbox=(0, 0, result.width, result.height),
                score=0.0,
                source="manual_review",
                text="",
                readable=True,
                reason="Thêm thủ công",
            )
        )
        self._render_detail(result)

    def export_reviewed_results(self) -> None:
        self._export_results(reviewed=True)

    def export_all_results(self) -> None:
        self._export_results(reviewed=False)

    def _export_results(self, reviewed: bool) -> None:
        if not self.results:
            messagebox.showwarning("Chưa có dữ liệu", "Hãy quét ảnh trước khi xuất Excel.", parent=self)
            return
        if self.export_worker and self.export_worker.is_alive():
            return
        self._save_detail_edits()
        self._save_settings()
        output_path = Path(self.output_var.get()).expanduser().resolve()
        results_snapshot = deepcopy(self.results)
        exported_count = sum(
            1
            for result in results_snapshot
            for plate in result.plates
            if plate.final_text and (plate.review_approved if reviewed else plate.readable)
        )
        self._set_export_buttons_state("disabled")
        self.status_var.set("Đang xuất Excel ở nền...")
        self._log("Đang xuất Excel ở worker nền.")
        self.export_worker = threading.Thread(
            target=self._worker_export,
            args=(
                results_snapshot,
                output_path,
                float(self.blur_threshold_var.get()),
                reviewed,
                bool(self.embed_excel_images_var.get()),
                exported_count,
            ),
            daemon=True,
        )
        self.export_worker.start()

    def _worker_export(
        self,
        results: list[ImageResult],
        output_path: Path,
        blur_threshold: float,
        reviewed: bool,
        include_images: bool,
        exported_count: int,
    ) -> None:
        try:
            exported_path = export_results(
                results,
                output_path,
                blur_threshold,
                reviewed=reviewed,
                include_images=include_images,
            )
        except Exception as exc:
            self.event_queue.put(("export_error", str(exc)))
            return
        self.event_queue.put(("export_done", reviewed, exported_path, exported_count))

    def open_visual_review(self) -> None:
        if not self.results:
            messagebox.showwarning("Chưa có dữ liệu", "Hãy quét ảnh trước khi review.", parent=self)
            return
        self._save_detail_edits()
        start_index = 0
        if self.selected_image_path:
            for index, result in enumerate(self.results):
                if result.image_path == self.selected_image_path:
                    start_index = index
                    break
        VisualReviewWindow(self, self.results, start_index=start_index, on_change=self._refresh_table, on_export=self.export_reviewed_results)

    def approve_auto_results(self) -> int:
        count = 0
        for result in self.results:
            if result.status != "OK" or result.warnings:
                continue
            for plate in result.plates:
                if plate.final_text and plate.readable and plate.confidence >= float(self.conf_threshold_var.get()):
                    plate.review_approved = True
                    count += 1
        self._refresh_table()
        return count

    def save_api_key_now(self, silent: bool = False) -> None:
        if not any(value.get().strip() for value in (self.openai_api_key_var, self.gemini_api_key_var, self.plate_recognizer_token_var)):
            self._update_key_status()
            if not silent:
                messagebox.showwarning("Thiếu API key", "Nhập ít nhất một API key/token trước khi lưu.", parent=self)
            return
        if not self.remember_key_var.get():
            self.remember_key_var.set(True)
        self._save_settings()
        if not silent:
            messagebox.showinfo("Đã lưu API keys", f"Lần sau mở app sẽ tự dùng key đã lưu.\n{settings_path()}", parent=self)

    def clear_saved_key(self) -> None:
        if not messagebox.askyesno("Xóa API keys", "Xóa tất cả API key/token đã lưu trên máy này?", parent=self):
            return
        self.openai_api_key_var.set("")
        self.gemini_api_key_var.set("")
        self.plate_recognizer_token_var.set("")
        self.custom_api_key_var.set("")
        self.telegram_bot_token_var.set("")
        self.remember_key_var.set(False)
        clear_saved_api_key()
        self._update_key_status()

    def open_current_image(self) -> None:
        path = self.selected_image_path
        if not path:
            return
        try:
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror("Không mở được ảnh", str(exc), parent=self)

    def _show_scan_finished_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Quét xong")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=self.colors["bg"])
        total_images = len(self.results)
        total_plates = sum(1 for result in self.results for plate in result.plates if plate.final_text)
        needs_review = self._review_count()
        failed_count = len(self._failed_image_paths())
        ttk.Label(dialog, text="Đã quét xong", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", padx=18, pady=(16, 6))
        ttk.Label(
            dialog,
            text=f"{total_images} ảnh, {total_plates} biển số/candidate, {needs_review} ảnh cần xem lại.",
            style="Subtle.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=18, pady=(0, 14))
        ttk.Button(dialog, text="Duyệt bằng ảnh", command=lambda: (dialog.destroy(), self.open_visual_review())).grid(
            row=2, column=0, padx=(18, 8), pady=(0, 16)
        )
        ttk.Button(dialog, text="Xuất luôn", command=lambda: (dialog.destroy(), self.export_all_results())).grid(
            row=2, column=1, padx=8, pady=(0, 16)
        )
        ttk.Button(dialog, text="Đóng", command=dialog.destroy).grid(row=2, column=2, padx=(8, 18), pady=(0, 16))
        if failed_count:
            ttk.Button(dialog, text=f"Quet lai loi ({failed_count})", command=lambda: (dialog.destroy(), self.retry_failed_images())).grid(
                row=3, column=0, columnspan=3, sticky="ew", padx=18, pady=(0, 16)
            )
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _show_retry_finished_dialog(self, processed: int, recovered: int, remaining: int) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Quet lai xong")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=self.colors["bg"])
        ttk.Label(dialog, text="Quet lai xong", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", padx=18, pady=(16, 6))
        ttk.Label(
            dialog,
            text=f"Da quet lai {processed} anh loi, doc them {recovered} anh, con {remaining} anh chua doc duoc.",
            style="Subtle.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=18, pady=(0, 14))
        if remaining:
            ttk.Button(dialog, text=f"Quet lai loi tiep ({remaining})", command=lambda: (dialog.destroy(), self.retry_failed_images())).grid(
                row=2, column=0, padx=(18, 8), pady=(0, 16)
            )
            ttk.Button(dialog, text="Duyet bang anh", command=lambda: (dialog.destroy(), self.open_visual_review())).grid(
                row=2, column=1, padx=8, pady=(0, 16)
            )
            ttk.Button(dialog, text="Dong", command=dialog.destroy).grid(row=2, column=2, padx=(8, 18), pady=(0, 16))
        else:
            ttk.Button(dialog, text="Duyet bang anh", command=lambda: (dialog.destroy(), self.open_visual_review())).grid(
                row=2, column=0, padx=(18, 8), pady=(0, 16)
            )
            ttk.Button(dialog, text="Xuat luon", command=lambda: (dialog.destroy(), self.export_all_results())).grid(
                row=2, column=1, padx=8, pady=(0, 16)
            )
            ttk.Button(dialog, text="Dong", command=dialog.destroy).grid(row=2, column=2, padx=(8, 18), pady=(0, 16))
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _add_paths(self, paths: list[Path]) -> None:
        existing = {str(path.resolve()).lower() for path in self.images}
        added = 0
        for path in paths:
            resolved = path.resolve()
            key = str(resolved).lower()
            if key not in existing:
                existing.add(key)
                self.images.append(resolved)
                added += 1
        self.images.sort(key=lambda item: str(item).lower())
        self._refresh_table()
        self.input_summary_var.set(f"Đã chọn {len(self.images)} ảnh.")
        if added and not self.selected_image_path:
            self._select_path(self.images[0])
        self._log(f"Đã thêm {added} ảnh. Tổng: {len(self.images)}")

    def _refresh_table(self) -> None:
        self._save_detail_edits()
        has_image_tree = hasattr(self, "image_tree")
        has_review_tree = hasattr(self, "review_tree")
        if has_image_tree:
            self.image_tree.delete(*self.image_tree.get_children())
        if has_review_tree:
            self.review_tree.delete(*self.review_tree.get_children())
        self.image_row_map.clear()
        if not has_image_tree and not has_review_tree:
            self._update_stats()
            return
        for path in self._filtered_sorted_images():
            self._upsert_image_row(path)
        self._update_stats()
        if self.selected_image_path and self.selected_image_path in self.images:
            self._select_path(self.selected_image_path)
        elif self.images:
            self._select_path(self.images[0])

    def _upsert_image_row(self, path: Path) -> None:
        result = self._result_for_path(path)
        item_id = _image_iid(path)
        self.image_row_map[item_id] = path
        values = self._image_row_values(path, result)
        tags = (_row_tag(result, self._all_final_plates_approved(result) if result else False),)
        if hasattr(self, "image_tree"):
            if self.image_tree.exists(item_id):
                self.image_tree.item(item_id, values=values, tags=tags)
            else:
                self.image_tree.insert("", "end", iid=item_id, values=values, tags=tags)
        if hasattr(self, "review_tree"):
            review_id = f"review_{item_id}"
            if self._is_review_result(result):
                review_values = self._review_row_values(path, result)
                if self.review_tree.exists(review_id):
                    self.review_tree.item(review_id, values=review_values)
                else:
                    self.review_tree.insert("", "end", iid=review_id, values=review_values)
            elif self.review_tree.exists(review_id):
                self.review_tree.delete(review_id)

    def _image_row_values(self, path: Path, result: ImageResult | None) -> tuple[str, str, str, str, str, str, str]:
        if result is None:
            return ("Chờ quét", path.name, "", "", "", "", "")
        plates = [plate.final_text for plate in result.plates if plate.final_text]
        first = result.plates[0] if result.plates else None
        plate_text = "; ".join(plates[:2])
        status = "Đã duyệt" if self._all_final_plates_approved(result) else _display_status(result.status)
        raw = first.raw_text if first else ""
        confidence = f"{first.confidence:.0f}%" if first else ""
        review = "Cần review" if self._is_review_result(result) else "Không"
        source = first.source if first else ""
        return (status, path.name, raw, plate_text, confidence, review, source)

    @staticmethod
    def _is_review_result(result: ImageResult | None) -> bool:
        if result is None:
            return False
        return result.status != "OK" or bool(result.warnings) or any(plate.needs_review or (plate.final_text and not plate.review_approved) for plate in result.plates)

    def _review_row_values(self, path: Path, result: ImageResult | None) -> tuple[str, str, str]:
        if result is None:
            return path.name, "", "Chờ quét"
        plate_text = "; ".join(plate.final_text for plate in result.plates if plate.final_text)
        return path.name, plate_text, result.reason

    def refresh_result_tables(self) -> None:
        self._refresh_table()

    def sort_result_table(self, column: str) -> None:
        if column == self._result_sort_column:
            self._result_sort_descending = not self._result_sort_descending
        else:
            self._result_sort_column = column
            self._result_sort_descending = False
        self._refresh_table()

    def _filtered_sorted_images(self) -> list[Path]:
        query = self.session_search_var.get().strip().casefold()

        def searchable(path: Path) -> str:
            result = self._result_for_path(path)
            values = [path.name]
            if result:
                values.extend([result.status, result.reason])
                for plate in result.plates:
                    values.extend([plate.final_text, plate.raw_text, plate.source])
            return " ".join(values).casefold()

        paths = [path for path in self.images if not query or query in searchable(path)]

        def sort_key(path: Path):
            result = self._result_for_path(path)
            first = result.plates[0] if result and result.plates else None
            if self._result_sort_column == "status":
                return _display_status(result.status) if result else "Chờ quét"
            if self._result_sort_column == "raw":
                return first.raw_text if first else ""
            if self._result_sort_column == "plate":
                return first.final_text if first else ""
            if self._result_sort_column == "confidence":
                return first.confidence if first else 0.0
            if self._result_sort_column == "review":
                return int(self._is_review_result(result))
            if self._result_sort_column == "source":
                return first.source if first else ""
            return path.name.casefold()

        return sorted(paths, key=sort_key, reverse=self._result_sort_descending)

    def _on_image_selected(self, _event=None) -> None:
        self._save_detail_edits()
        selected = self.image_tree.selection()
        if not selected:
            return
        path = self.image_row_map.get(selected[0])
        if not path:
            return
        self.selected_image_path = path
        self._render_detail(self._result_for_path(path), fallback_path=path)

    def _on_review_selected(self, _event=None) -> None:
        selected = self.review_tree.selection()
        if not selected:
            return
        key = selected[0].removeprefix("review_")
        path = self.image_row_map.get(key)
        if path:
            self.selected_image_path = path
            self._render_detail(self._result_for_path(path), fallback_path=path)

    def _select_path(self, path: Path) -> None:
        item_id = _image_iid(path)
        if hasattr(self, "image_tree") and self.image_tree.exists(item_id):
            self.image_tree.selection_set(item_id)
            self.image_tree.focus(item_id)
            self.image_tree.see(item_id)
        review_id = f"review_{item_id}"
        if hasattr(self, "review_tree") and self.review_tree.exists(review_id):
            self.review_tree.selection_set(review_id)
            self.review_tree.focus(review_id)
            self.review_tree.see(review_id)

    def _render_detail(self, result: ImageResult | None, fallback_path: Path | None = None) -> None:
        path = result.image_path if result else fallback_path
        self.current_detail_result = result
        self.detail_row_vars.clear()
        if not hasattr(self, "plates_frame"):
            return
        for child in self.plates_frame.winfo_children():
            child.destroy()
        if not path:
            self.detail_title_var.set("Chưa chọn ảnh")
            self.detail_meta_var.set("")
            self.preview_photo = None
            self.preview_label.configure(image="", text="Chọn một ảnh để xem")
            self.crop_preview_photo = None
            if hasattr(self, "crop_preview_label"):
                self.crop_preview_label.configure(image="", text="Chưa có crop")
            return
        self.detail_title_var.set(path.name)
        if result is None:
            self.detail_meta_var.set(f"Chờ quét | {path}")
            self._load_preview(path)
            self._load_crop_preview(None)
            ttk.Label(self.plates_frame, text="Ảnh chưa quét", style="SurfaceMuted.TLabel").grid(row=0, column=0, sticky="w")
            return
        self.detail_meta_var.set(f"{_display_status(result.status)} | Độ mờ {result.blur_score:.1f} | {result.reason}")
        self._load_preview(path)
        self._load_crop_preview(result)
        if not result.plates:
            ttk.Label(
                self.plates_frame,
                text="Chưa có biển số nào. Nếu nhìn thấy biển trong ảnh, bấm Thêm biển số để nhập tay.",
                style="SurfaceMuted.TLabel",
                wraplength=360,
            ).grid(row=0, column=0, sticky="w")
            return
        self._render_plate_rows(result)

    def _load_preview(self, image_path: Path) -> None:
        try:
            image = Image.open(image_path)
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((500, 360), Image.Resampling.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(image)
            self.preview_label.configure(image=self.preview_photo, text="")
        except Exception as exc:
            self.preview_photo = None
            self.preview_label.configure(image="", text=f"Không hiển thị được ảnh\n{exc}")

    def _load_crop_preview(self, result: ImageResult | None) -> None:
        label = getattr(self, "crop_preview_label", None)
        if label is None:
            return
        crop_path = next((plate.crop_path for plate in (result.plates if result else []) if plate.crop_path and plate.crop_path.exists()), None)
        if not crop_path:
            self.crop_preview_photo = None
            label.configure(image="", text="Chưa có crop")
            return
        try:
            image = Image.open(crop_path)
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((210, 120), Image.Resampling.LANCZOS)
            self.crop_preview_photo = ImageTk.PhotoImage(image)
            label.configure(image=self.crop_preview_photo, text="")
        except Exception as exc:
            self.crop_preview_photo = None
            label.configure(image="", text=f"Không mở được crop\n{exc}")

    def _render_plate_rows(self, result: ImageResult) -> None:
        headers = ("OK", "Kết quả chọn", "OCR thô / gợi ý / tin cậy", "")
        for column, header in enumerate(headers):
            ttk.Label(self.plates_frame, text=header, style="SurfaceMuted.TLabel").grid(row=0, column=column, sticky="w", padx=(0, 8), pady=(0, 4))
        for row_index, plate in enumerate(result.plates, start=1):
            approved_var = tk.BooleanVar(value=plate.review_approved)
            text_var = tk.StringVar(value=plate.final_text)
            self.detail_row_vars.append((plate, text_var, approved_var))
            ttk.Checkbutton(self.plates_frame, variable=approved_var).grid(row=row_index, column=0, sticky="n", padx=(0, 8), pady=4)
            ttk.Entry(self.plates_frame, textvariable=text_var, width=24).grid(row=row_index, column=1, sticky="ew", pady=4)
            detail = f"Raw: {plate.raw_text or plate.text or '—'}\n{plate.confidence:.0f}% | {plate.source}"
            if plate.suggested_texts:
                detail += f"\nGợi ý: {', '.join(plate.suggested_texts[:5])}"
            if plate.ambiguity_flags:
                detail += f"\nMơ hồ: {', '.join(plate.ambiguity_flags)}"
            if plate.reason:
                detail += f" | {plate.reason}"
            ttk.Label(self.plates_frame, text=detail, style="SurfaceMuted.TLabel", wraplength=240).grid(
                row=row_index, column=2, sticky="w", padx=(8, 0), pady=4
            )
            ttk.Button(self.plates_frame, text="Xóa", command=lambda plate=plate: self.delete_current_plate(plate)).grid(
                row=row_index, column=3, sticky="ew", padx=(8, 0), pady=4
            )
        self.plates_frame.columnconfigure(1, weight=1)

    def delete_current_plate(self, plate: PlateCandidate) -> None:
        result = self.current_detail_result
        if result is None:
            return
        self._save_detail_edits()
        result.plates = [item for item in result.plates if item is not plate]
        self._render_detail(result)
        self._upsert_image_row(result.image_path)
        self._update_stats()
        self._log(f"Đã xóa 1 biển số khỏi ảnh: {result.image_path.name}")

    def _save_detail_edits(self) -> None:
        result = self.current_detail_result
        if not result or not self.detail_row_vars:
            return
        for plate, text_var, approved_var in self.detail_row_vars:
            value = text_var.get().strip().upper()
            if value and value != plate.text:
                plate.corrected_text = value
            elif not value:
                plate.corrected_text = ""
            plate.review_approved = bool(approved_var.get() and value)
            if value and not plate.text:
                plate.text = value
                plate.normalized_text = normalize_plate_text(value)
                plate.readable = True
            elif value:
                plate.normalized_text = normalize_plate_text(value)
            plate.cleaned_text, plate.suggested_texts, plate.ambiguity_flags, plate.needs_review = plate_text_metadata(value)
            if plate.review_approved:
                plate.needs_review = False

    def _selected_paths(self) -> set[Path]:
        if not hasattr(self, "image_tree"):
            return set()
        return {self.image_row_map[item_id] for item_id in self.image_tree.selection() if item_id in self.image_row_map}

    def _result_for_path(self, path: Path) -> ImageResult | None:
        for result in self.results:
            if result.image_path == path:
                return result
        return None

    def _replace_result(self, new_result: ImageResult) -> None:
        for index, result in enumerate(self.results):
            if result.image_path == new_result.image_path:
                self.results[index] = new_result
                return
        self.results.append(new_result)

    def _failed_image_paths(self) -> list[Path]:
        failed: list[Path] = []
        for path in self.images:
            result = self._result_for_path(path)
            if result is None:
                continue
            if not self._result_has_readable_plate(result):
                failed.append(path)
        return failed

    @staticmethod
    def _result_has_readable_plate(result: ImageResult) -> bool:
        return any(plate.readable and plate.final_text for plate in result.plates)

    def _select_next_result(self, current_path: Path) -> None:
        for index, result in enumerate(self.results):
            if result.image_path == current_path and index + 1 < len(self.results):
                self._select_path(self.results[index + 1].image_path)
                return

    @staticmethod
    def _all_final_plates_approved(result: ImageResult) -> bool:
        plates = [plate for plate in result.plates if plate.final_text]
        return bool(plates) and all(plate.review_approved for plate in plates)

    def _review_count(self) -> int:
        threshold = float(self.blur_threshold_var.get())
        count = 0
        for result in self.results:
            if result.status != "OK" or result.blur_score < threshold or result.warnings:
                count += 1
                continue
            if not any(plate.final_text for plate in result.plates):
                count += 1
                continue
            if any(plate.final_text and not plate.review_approved for plate in result.plates):
                count += 1
        return count

    def _export_plate_count(self, reviewed: bool) -> int:
        if reviewed:
            return sum(1 for result in self.results for plate in result.plates if plate.review_approved and plate.final_text)
        return sum(1 for result in self.results for plate in result.plates if plate.readable and plate.final_text)

    def _reveal_exported_file(self, output_path: Path) -> None:
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", "/select,", str(output_path)])
            else:
                os.startfile(str(output_path.parent))
        except Exception as exc:
            self._log(f"Không mở được thư mục Excel: {exc}")

    def _update_stats(self) -> None:
        self.total_var.set(str(len(self.images)))
        self.scanned_var.set(str(len(self.results)))
        self.plates_var.set(str(sum(1 for result in self.results for plate in result.plates if plate.final_text)))
        self.review_var.set(str(self._review_count()))
        if hasattr(self, "start_button") and not (self.worker and self.worker.is_alive()):
            self.start_button.configure(state="normal" if self.images else "disabled")
        self._set_export_buttons_state("normal" if self.results and not (self.export_worker and self.export_worker.is_alive()) else "disabled")
        self._update_retry_button()

    def _update_retry_button(self) -> None:
        button = getattr(self, "retry_failed_button", None)
        if button is None:
            return
        has_failed = bool(self._failed_image_paths())
        is_busy = bool(self.worker and self.worker.is_alive())
        button.configure(state="normal" if has_failed and not is_busy else "disabled")

    def _set_review_buttons(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        if hasattr(self, "review_button"):
            self.review_button.configure(state=state)

    def _set_export_buttons_state(self, state: str) -> None:
        for button_name in ("export_button", "export_reviewed_button"):
            button = getattr(self, button_name, None)
            if button is not None:
                button.configure(state=state)

    def _toggle_key_visibility(self) -> None:
        show = "" if self.show_key_var.get() else "*"
        for entry in [*getattr(self, "_secret_entries", []), *self.custom_secret_entries]:
            entry.configure(show=show)

    def _on_theme_toggle(self) -> None:
        self._apply_theme()
        self._schedule_settings_save()

    def _apply_theme(self) -> None:
        self.colors = _theme_colors(self.dark_mode_var.get())
        self._configure_style()
        self._update_theme_toggle_text()
        for widget_name, option_map in (
            ("workflow_canvas", {"bg": self.colors["bg"]}),
            ("log_text", {"bg": self.colors["log_bg"], "fg": self.colors["text"], "insertbackground": self.colors["text"]}),
            ("preview_label", {"bg": self.colors["preview_bg"], "fg": self.colors["on_accent"]}),
            ("crop_preview_label", {"bg": self.colors["preview_bg"], "fg": self.colors["on_accent"]}),
            ("plate_canvas", {"bg": self.colors["surface"]}),
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.configure(**option_map)
        if hasattr(self, "image_tree"):
            self._configure_tree_tags()

    def _update_theme_toggle_text(self) -> None:
        self._theme_text_var.set("Giao diện tối" if self.dark_mode_var.get() else "Giao diện sáng")

    def _configure_tree_tags(self) -> None:
        for tree_name in ("image_tree", "review_tree"):
            tree = getattr(self, tree_name, None)
            if tree is None:
                continue
            tree.tag_configure("ok", foreground=self.colors["success"])
            tree.tag_configure("review", foreground=self.colors["warning"])
            tree.tag_configure("error", foreground=self.colors["danger"])
            tree.tag_configure("pending", foreground=self.colors["text_secondary"])

    def _bind_settings(self) -> None:
        for variable in (
            self.engine_var,
            self.remember_key_var,
            self.gpt_model_var,
            self.gemini_model_var,
            self.plate_recognizer_region_var,
            self.tesseract_var,
            self.recursive_var,
            self.blur_threshold_var,
            self.conf_threshold_var,
            self.worker_count_var,
            self.worker_mode_var,
            self.image_workers_var,
            self.local_ocr_workers_var,
            self.api_workers_var,
            self.queue_capacity_var,
            self.paddle_scan_mode_var,
            self.embed_excel_images_var,
            self.dark_mode_var,
            self.custom_provider_enabled_var,
            self.custom_provider_name_var,
            self.custom_base_url_var,
            self.custom_model_var,
            self.custom_api_mode_var,
            self.provider_timeout_var,
            self.telegram_enabled_var,
            self.telegram_chat_id_var,
            self.telegram_notify_start_var,
            self.telegram_notify_progress_var,
            self.telegram_notify_complete_var,
            self.telegram_notify_error_var,
            self.telegram_progress_step_var,
            self.telegram_min_interval_var,
            self.telegram_mask_plate_var,
            self.update_manifest_url_var,
        ):
            variable.trace_add("write", lambda *_args: self._schedule_settings_save())
        for variable in (
            self.openai_api_key_var,
            self.gemini_api_key_var,
            self.plate_recognizer_token_var,
            self.custom_api_key_var,
            self.telegram_bot_token_var,
        ):
            variable.trace_add("write", lambda *_args: self._on_api_key_changed())
        self.remember_key_var.trace_add("write", lambda *_args: self._update_key_status())

    def _on_api_key_changed(self) -> None:
        has_any_key = any(
            value.get().strip()
            for value in (
                self.openai_api_key_var,
                self.gemini_api_key_var,
                self.plate_recognizer_token_var,
                self.custom_api_key_var,
                self.telegram_bot_token_var,
            )
        )
        if self._settings_ready and has_any_key and not self.remember_key_var.get():
            self.remember_key_var.set(True)
        self._update_key_status()
        self._schedule_settings_save()

    def _schedule_settings_save(self) -> None:
        if not self._settings_ready:
            return
        if self._save_after_id:
            self.after_cancel(self._save_after_id)
        self._save_after_id = self.after(700, self._save_settings)

    def _save_settings(self) -> None:
        self._save_after_id = None
        try:
            output_dir = str(Path(self.output_var.get()).expanduser().parent)
            payload = {
                "version": SETTINGS_VERSION,
                "engine": self.engine_var.get(),
                "remember_key": bool(self.remember_key_var.get()),
                "gpt_model": self.gpt_model_var.get().strip() or DEFAULT_GPT_MODEL,
                "gemini_model": self.gemini_model_var.get().strip() or DEFAULT_GEMINI_MODEL,
                "plate_recognizer_region": self.plate_recognizer_region_var.get().strip() or DEFAULT_PLATE_RECOGNIZER_REGION,
                "tesseract_path": self.tesseract_var.get().strip(),
                "recursive": bool(self.recursive_var.get()),
                "blur_threshold": float(self.blur_threshold_var.get()),
                "conf_threshold": float(self.conf_threshold_var.get()),
                "worker_count": self._safe_int_var(self.worker_count_var, _default_worker_count()),
                "worker_mode": self.worker_mode_var.get().strip().upper(),
                "image_workers": self._safe_int_var(self.image_workers_var, _default_worker_count()),
                "local_ocr_workers": self._safe_int_var(self.local_ocr_workers_var, 1),
                "api_workers": self._safe_int_var(self.api_workers_var, 2),
                "queue_capacity": self._safe_int_var(self.queue_capacity_var, 32),
                "paddle_scan_mode": self.paddle_scan_mode_var.get().strip() or PADDLE_SCAN_MODE_DEFAULT,
                "embed_excel_images": bool(self.embed_excel_images_var.get()),
                "dark_mode": bool(self.dark_mode_var.get()),
                "output_dir": output_dir,
                "provider_configs": {"custom_openai": self._custom_provider_snapshot()},
                "telegram": {
                    "enabled": bool(self.telegram_enabled_var.get()),
                    "chat_id": self.telegram_chat_id_var.get().strip(),
                    "notify_start": bool(self.telegram_notify_start_var.get()),
                    "notify_progress": bool(self.telegram_notify_progress_var.get()),
                    "notify_complete": bool(self.telegram_notify_complete_var.get()),
                    "notify_error": bool(self.telegram_notify_error_var.get()),
                    "progress_percent_step": self._safe_int_var(self.telegram_progress_step_var, 10),
                    "minimum_interval_seconds": self._safe_int_var(self.telegram_min_interval_var, 60),
                    "mask_plate_number": bool(self.telegram_mask_plate_var.get()),
                },
                "updates": {"manifest_url": self.update_manifest_url_var.get().strip(), "channel": "stable", "auto_install": False},
            }
            save_settings(
                payload,
                api_key=self.openai_api_key_var.get().strip() if self.remember_key_var.get() else "",
                gemini_api_key=self.gemini_api_key_var.get().strip() if self.remember_key_var.get() else "",
                plate_recognizer_token=self.plate_recognizer_token_var.get().strip() if self.remember_key_var.get() else "",
                provider_api_keys={"custom_openai": self.custom_api_key_var.get().strip()},
                telegram_bot_token=self.telegram_bot_token_var.get().strip(),
            )
        except Exception as exc:
            self._log(f"Không lưu được cấu hình: {exc}")
        self._update_key_status()

    def _update_key_status(self) -> None:
        saved = []
        if self.gemini_api_key_var.get().strip():
            saved.append("Gemini")
        if self.plate_recognizer_token_var.get().strip():
            saved.append("PlateRec")
        if self.openai_api_key_var.get().strip():
            saved.append("OpenAI")
        if self.custom_api_key_var.get().strip():
            saved.append("Provider custom")
        if self.telegram_bot_token_var.get().strip():
            saved.append("Telegram")
        if self.remember_key_var.get() and saved:
            self.key_status_var.set(f"Đã lưu/tải key: {', '.join(saved)} | {settings_path()}")
        elif any(os.environ.get(name) for name in ("PLATE_RECOGNIZER_TOKEN", "GEMINI_API_KEY", "OPENAI_API_KEY")):
            self.key_status_var.set("Đang dùng API key từ biến môi trường")
        else:
            self.key_status_var.set("Chưa có API key đã lưu")

    def _on_close(self) -> None:
        self._save_detail_edits()
        self._save_settings()
        self.destroy()

    def destroy(self) -> None:
        if self.worker_manager:
            self.worker_manager.stop()
        if self.telegram_notifier:
            self.telegram_notifier.close()
            self.telegram_notifier = None
        for after_id in [self._save_after_id, self._drain_after_id, *self._layout_after_ids]:
            if after_id:
                try:
                    self.after_cancel(after_id)
                except tk.TclError:
                    pass
        self._save_after_id = None
        self._drain_after_id = None
        self._layout_after_ids.clear()
        super().destroy()

    def _log(self, message: str) -> None:
        log = getattr(self, "log_text", None)
        if log is not None:
            log.insert("end", f"{datetime.now():%H:%M:%S}  {message}\n")
            log.see("end")

    @staticmethod
    def _safe_int(value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError, tk.TclError):
            return default

    def _safe_int_var(self, variable: tk.IntVar, default: int) -> int:
        try:
            return int(variable.get())
        except (TypeError, ValueError, tk.TclError):
            variable.set(default)
            return default


class VisualReviewWindow(tk.Toplevel):
    def __init__(self, master: CheckVehicleApp, results: list[ImageResult], start_index: int = 0, on_change=None, on_export=None) -> None:
        super().__init__(master)
        self.results = results
        self.index = max(0, min(start_index, len(results) - 1))
        self.on_change = on_change
        self.on_export = on_export
        self.photo = None
        self.row_vars: list[tuple[PlateCandidate, tk.StringVar, tk.BooleanVar]] = []
        self.colors = master.colors
        self.title("Duyệt kết quả")
        self.geometry("1180x720")
        self.minsize(980, 600)
        self.configure(bg=self.colors["bg"])
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=(12, 10), style="App.TFrame")
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        top.columnconfigure(0, weight=1)
        self.title_var = tk.StringVar()
        ttk.Label(top, textvariable=self.title_var, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(top, text="Quay lại", command=self.prev).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(top, text="Ảnh sau", command=self.next).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(top, text="Xuất Excel", command=self._export).grid(row=0, column=3)

        self.image_label = tk.Label(self, bg=self.colors["preview_bg"], fg=self.colors["on_accent"])
        self.image_label.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))
        side = ttk.Frame(self, padding=(10, 10), style="Panel.TFrame")
        side.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        side.columnconfigure(0, weight=1)
        side.rowconfigure(2, weight=1)
        self.meta_var = tk.StringVar()
        ttk.Label(side, textvariable=self.meta_var, style="PanelSubtle.TLabel", wraplength=360).grid(row=0, column=0, sticky="w")
        self.rows = ttk.Frame(side, style="Panel.TFrame")
        self.rows.grid(row=2, column=0, sticky="nsew", pady=(10, 10))
        buttons = ttk.Frame(side, style="Panel.TFrame")
        buttons.grid(row=3, column=0, sticky="ew")
        buttons.columnconfigure((0, 1), weight=1)
        ttk.Button(buttons, text="Lưu", command=self.save_current).grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=(0, 6))
        ttk.Button(buttons, text="Tick đúng hết", command=self.approve_all).grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=(0, 6))
        ttk.Button(buttons, text="Thêm biển số", command=self.add_plate).grid(row=1, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(buttons, text="Mở ảnh gốc", command=self.open_image).grid(row=1, column=1, sticky="ew", padx=(5, 0))
        self.render()

    def render(self) -> None:
        self.save_current()
        if not self.results:
            return
        result = self.results[self.index]
        self.title_var.set(f"{self.index + 1}/{len(self.results)} - {result.image_path.name}")
        self.meta_var.set(f"{_display_status(result.status)} | Độ mờ {result.blur_score:.1f} | {result.reason}")
        try:
            image = Image.open(result.image_path)
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((700, 560), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(image)
            self.image_label.configure(image=self.photo, text="")
        except Exception as exc:
            self.photo = None
            self.image_label.configure(image="", text=f"Không hiển thị được ảnh\n{exc}")
        for child in self.rows.winfo_children():
            child.destroy()
        self.row_vars.clear()
        if not result.plates:
            ttk.Label(
                self.rows,
                text="Chưa có biển số nào. Nếu nhìn thấy biển trong ảnh, bấm Thêm biển số để nhập tay.",
                style="PanelSubtle.TLabel",
                wraplength=330,
            ).grid(row=0, column=0, sticky="w")
            return
        ttk.Label(self.rows, text="OK", style="PanelSubtle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self.rows, text="Biển số", style="PanelSubtle.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(self.rows, text="Nguồn", style="PanelSubtle.TLabel").grid(row=0, column=2, sticky="w")
        ttk.Label(self.rows, text="", style="PanelSubtle.TLabel").grid(row=0, column=3, sticky="w")
        for row, plate in enumerate(result.plates, start=1):
            approved = tk.BooleanVar(value=plate.review_approved)
            text = tk.StringVar(value=plate.final_text)
            self.row_vars.append((plate, text, approved))
            ttk.Checkbutton(self.rows, variable=approved).grid(row=row, column=0, sticky="n", padx=(0, 8), pady=4)
            ttk.Entry(self.rows, textvariable=text, width=24).grid(row=row, column=1, sticky="ew", pady=4)
            ttk.Label(self.rows, text=f"{plate.confidence:.0f}% | {plate.source}", style="PanelSubtle.TLabel", wraplength=170).grid(
                row=row, column=2, sticky="w", padx=(8, 0), pady=4
            )
            ttk.Button(self.rows, text="Xóa", command=lambda plate=plate: self.delete_plate(plate)).grid(
                row=row, column=3, sticky="ew", padx=(8, 0), pady=4
            )
        self.rows.columnconfigure(1, weight=1)

    def save_current(self) -> None:
        for plate, text_var, approved_var in self.row_vars:
            value = text_var.get().strip().upper()
            if value and value != plate.text:
                plate.corrected_text = value
            elif not value:
                plate.corrected_text = ""
            plate.review_approved = bool(approved_var.get() and value)
            if value:
                if not plate.text:
                    plate.text = value
                    plate.readable = True
                plate.normalized_text = normalize_plate_text(value)
            plate.cleaned_text, plate.suggested_texts, plate.ambiguity_flags, plate.needs_review = plate_text_metadata(value)
            if plate.review_approved:
                plate.needs_review = False
        if self.on_change:
            self.on_change()

    def approve_all(self) -> None:
        for _plate, text_var, approved_var in self.row_vars:
            if text_var.get().strip():
                approved_var.set(True)
        self.save_current()
        if self.index + 1 < len(self.results):
            self.index += 1
        self.render()

    def add_plate(self) -> None:
        result = self.results[self.index]
        result.plates.append(
            PlateCandidate(
                bbox=(0, 0, result.width, result.height),
                score=0.0,
                source="manual_review",
                readable=True,
                reason="Thêm thủ công",
            )
        )
        self.render()

    def delete_plate(self, plate: PlateCandidate) -> None:
        if not self.results:
            return
        self.save_current()
        result = self.results[self.index]
        result.plates = [item for item in result.plates if item is not plate]
        self.render()

    def open_image(self) -> None:
        try:
            os.startfile(str(self.results[self.index].image_path))
        except Exception as exc:
            messagebox.showerror("Không mở được ảnh", str(exc), parent=self)

    def prev(self) -> None:
        self.save_current()
        self.index = max(0, self.index - 1)
        self.render()

    def next(self) -> None:
        self.save_current()
        self.index = min(len(self.results) - 1, self.index + 1)
        self.render()

    def _export(self) -> None:
        self.save_current()
        if self.on_export:
            self.on_export()


def _default_output_dir() -> Path:
    docs = Path.home() / "Documents"
    return docs if docs.exists() else Path.home()


def _default_worker_count() -> int:
    return min(2, max(1, os.cpu_count() or 2))


def _safe_settings_version(settings: dict) -> int:
    try:
        return int(settings.get("version", 0))
    except (TypeError, ValueError):
        return 0


def _image_iid(path: Path) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8", errors="ignore")).hexdigest()
    return f"img_{digest}"


def _theme_colors(dark_mode: bool) -> dict[str, str]:
    palette = ui_colors(dark_mode)
    # Legacy names keep the review dialog and small compatibility methods
    # working while all new pages consume the semantic token names.
    palette.update(
        {
            "bg": palette["background"],
            "panel": palette["surface"],
            "panel_alt": palette["surface_hover"],
            "field": palette["surface"],
            "text": palette["text_primary"],
            "subtle": palette["text_secondary"],
            "line": palette["border"],
            "accent_hover": palette["accent_hover"],
            "accent_soft": palette["surface_selected"],
            "accent_text": palette["accent"],
            "warn": palette["warning"],
            "danger": palette["danger"],
            "button": palette["surface"],
            "button_hover": palette["surface_hover"],
            "disabled": palette["border"],
            "disabled_text": palette["text_muted"],
            "preview_bg": palette["preview"],
            "log_bg": palette["surface"],
            "tree_bg": palette["surface"],
            "tree_alt": palette["surface_hover"],
            "selection": palette["surface_selected"],
            "selection_text": palette["text_primary"],
        }
    )
    return palette


def _display_status(status: str) -> str:
    mapping = {
        "OK": "OK",
        "BLURRY": "Ảnh mờ",
        "UNREADABLE": "Chưa đọc được",
        "ERROR": "Lỗi",
    }
    return mapping.get(status, status)


def _row_tag(result: ImageResult | None, approved: bool) -> str:
    if result is None:
        return "pending"
    if approved or result.status == "OK":
        return "ok"
    if result.status in {"BLURRY", "UNREADABLE"}:
        return "review"
    return "error"


def _needs_local_fallback(result: ImageResult) -> bool:
    if result.status == "ERROR":
        return True
    if not any(plate.final_text for plate in result.plates):
        return True
    return result.status in {"UNREADABLE", "BLURRY"}


def _merge_gemini_local_result(gemini_result: ImageResult, local_result: ImageResult) -> ImageResult:
    gemini_plates = [plate for plate in gemini_result.plates if plate.final_text]
    local_plates = [plate for plate in local_result.plates if plate.final_text]
    seen = {plate.normalized_text for plate in gemini_plates if plate.normalized_text}
    merged_plates = [*gemini_plates]
    for plate in local_plates:
        if plate.normalized_text and plate.normalized_text in seen:
            continue
        if plate.normalized_text:
            seen.add(plate.normalized_text)
        if plate.source == "detected":
            plate.source = "local_ocr_fallback"
        else:
            plate.source = f"local_ocr_fallback:{plate.source}"
        if plate.final_text and plate.confidence < 72.0:
            plate.readable = False
            if not plate.reason:
                plate.reason = "Cần review vì là kết quả fallback"
        merged_plates.append(plate)

    local_found_text = any(plate.final_text for plate in merged_plates)
    warnings = [*gemini_result.warnings]
    if gemini_result.error:
        warnings.append(f"Gemini lỗi: {gemini_result.error[:220]}")
    elif gemini_result.reason:
        warnings.append(f"Gemini: {gemini_result.reason}")
    warnings.extend(local_result.warnings)

    if local_found_text:
        status = "OK"
        reason = "Local OCR fallback tìm được biển số sau khi Gemini không chắc"
    else:
        status = local_result.status if local_result.status != "OK" else gemini_result.status
        reason = f"Gemini và Local OCR đều cần review; {local_result.reason}"

    return ImageResult(
        image_path=gemini_result.image_path,
        status=status,
        reason=reason,
        blur_score=gemini_result.blur_score or local_result.blur_score,
        width=gemini_result.width or local_result.width,
        height=gemini_result.height or local_result.height,
        candidate_count=max(gemini_result.candidate_count, local_result.candidate_count),
        plates=merged_plates,
        warnings=_dedupe_text(warnings),
        error=gemini_result.error,
    )


def _dedupe_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def main() -> None:
    app = CheckVehicleApp()
    app.mainloop()


if __name__ == "__main__":
    main()
