from __future__ import annotations

import cProfile
import argparse
import json
import os
import pstats
import queue
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from io import StringIO
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _profile(func) -> dict[str, object]:
    profiler = cProfile.Profile()
    started = time.perf_counter()
    profiler.enable()
    func()
    profiler.disable()
    elapsed = time.perf_counter() - started
    stream = StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(16)
    return {"seconds": elapsed, "top_cumulative": stream.getvalue()}


def _import_seconds() -> float:
    completed = subprocess.run(
        [sys.executable, "-B", "-c", "import time; s=time.perf_counter(); import check_vehicle_ocr.app; print(time.perf_counter()-s)"],
        check=True,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    return float(completed.stdout.strip().splitlines()[-1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    os.environ.setdefault("CHECK_VEHICLE_DISABLE_ONNX_DETECTOR", "1")
    from check_vehicle_ocr.app import CheckVehicleApp
    from check_vehicle_ocr.config import migrate_settings
    from check_vehicle_ocr.excel_export import export_results
    from check_vehicle_ocr.models import ImageResult, PlateCandidate
    from check_vehicle_ocr.paddle_ocr_engine import PaddleOcrEngine
    from check_vehicle_ocr.processor import process_image
    from check_vehicle_ocr.providers import OpenAICompatibleProvider, ProviderConfig
    from check_vehicle_ocr.services.progress_service import BatchProgress
    from check_vehicle_ocr.services.worker_manager import WorkerManager, WorkerSettings
    from check_vehicle_ocr.telegram_notify import TelegramSettings
    from check_vehicle_ocr.updater import parse_manifest

    report: dict[str, object] = {"import_app_seconds": _import_seconds(), "profiles": {}}
    with tempfile.TemporaryDirectory(prefix="profile_regression_appdata_") as appdata, tempfile.TemporaryDirectory(prefix="profile_regression_data_") as temporary:
        previous_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = appdata
        try:
            holder: dict[str, CheckVehicleApp] = {}
            report["profiles"]["app_shell_scan_startup"] = _profile(lambda: holder.setdefault("app", CheckVehicleApp()))
            app = holder["app"]
            report["startup_pages"] = list(app.shell.pages)
            for page in ("session", "review", "export", "providers", "telegram", "updates", "settings"):
                report["profiles"][f"lazy_page_{page}"] = _profile(lambda page=page: app.show_page(page))
            report["profiles"]["theme_setup"] = _profile(app._configure_style)
            report["profiles"]["config_migration_1000"] = _profile(lambda: [migrate_settings({"engine": "PaddleOCR Local"}) for _ in range(1000)])
            report["profiles"]["worker_manager_setup_1000"] = _profile(lambda: [WorkerManager(WorkerSettings(), "PaddleOCR Local") for _ in range(1000)])
            report["profiles"]["provider_telegram_updater_setup_1000"] = _profile(
                lambda: [
                    (
                        OpenAICompatibleProvider(ProviderConfig("Mock", "key", "https://example.invalid/v1")),
                        TelegramSettings(),
                        parse_manifest('{"version":"1.0.0","release_notes":"n","download_url":"file:///x","sha256":"' + "a" * 64 + '"}'),
                    )
                    for _ in range(1000)
                ]
            )
            progress = BatchProgress(total=100, configured_workers={"image": 2, "local_ocr": 1, "api": 2})
            progress.start()
            report["profiles"]["progress_snapshot_1000"] = _profile(lambda: [progress.snapshot() for _ in range(1000)])
            events: queue.Queue = queue.Queue()
            report["profiles"]["event_queue_1000"] = _profile(lambda: [(events.put(("progress", progress.snapshot())), events.get_nowait()) for _ in range(1000)])

            root = Path(temporary)
            image_path = root / "sample.jpg"
            Image.new("RGB", (900, 520), "white").save(image_path)
            result = ImageResult(
                image_path=image_path,
                status="OK",
                reason="ok",
                width=900,
                height=520,
                plates=[PlateCandidate(bbox=(0, 0, 300, 80), score=90, text="30A-123.45", normalized_text="30A12345", confidence=90, readable=True)],
            )
            report["profiles"]["excel_snapshot_compact"] = _profile(lambda: export_results(deepcopy([result] * 3), root / "profile.xlsx", 80, include_images=False))
            engine = PaddleOcrEngine(20)
            started = time.perf_counter()
            if not engine.available:
                raise RuntimeError(engine.reason)
            report["paddle_cold_init_seconds"] = time.perf_counter() - started
            report["profiles"]["process_image"] = _profile(lambda: process_image(image_path, root / "crops", engine, 10, 20))
            app.destroy()
        finally:
            if previous_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = previous_appdata
    payload = json.dumps(report, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
