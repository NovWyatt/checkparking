from __future__ import annotations

import os
import queue
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from check_vehicle_ocr.app import CheckVehicleApp
from check_vehicle_ocr.models import BatchSession, ImageResult, PlateCandidate
from check_vehicle_ocr.plate_formatting import PlateType
from check_vehicle_ocr.services.progress_service import BatchStatus
from check_vehicle_ocr.services.worker_manager import WorkerSettings


def plate(text: str, *, review: bool = False) -> PlateCandidate:
    return PlateCandidate(bbox=(0, 0, 1, 1), score=90, text=text, raw_text=text, readable=bool(text), confidence=90, needs_review=review)


def local_result(path: Path) -> ImageResult:
    if path.name == "clear.jpg":
        return ImageResult(path, "OK", "", plates=[plate("59X112345")])
    if path.name == "special.jpg":
        return ImageResult(path, "OK", "", plates=[plate("49MD112345")])
    return ImageResult(path, "UNREADABLE", "Không đọc được", plates=[plate("")])


class Online:
    available = True
    last_api_mode = "chat_completions"

    def __init__(self) -> None:
        self.calls: list[Path] = []

    def analyze_image(self, path: Path, _blur: float) -> ImageResult:
        self.calls.append(path)
        if path.name == "unreadable.jpg":
            raise TimeoutError("mock timeout")
        return ImageResult(path, "OK", "", plates=[plate("59X112345")])


def main() -> int:
    previous_appdata = os.environ.get("APPDATA")
    with tempfile.TemporaryDirectory() as temporary:
        os.environ["APPDATA"] = temporary
        app = CheckVehicleApp()
        try:
            app.ai_review_policy_var.set("Khi kết quả cần kiểm tra — Khuyên dùng")
            paths = [Path(temporary) / name for name in ("clear.jpg", "special.jpg", "unreadable.jpg")]
            online = Online()
            engine = SimpleNamespace(local_engine=object(), online_engine=online)
            session = BatchSession("batch", PlateType.MOTORCYCLE, "2026-07-29T00:00:00+07:00", len(paths))
            with patch("check_vehicle_ocr.app.load_image", return_value=(None, (1, 1))), patch("check_vehicle_ocr.app.process_image", side_effect=lambda image, *_args, **_kwargs: local_result(image)):
                app._run_hybrid_pipeline(
                    images=paths,
                    engine=engine,
                    crop_dir=Path(temporary) / "crops",
                    output_path=Path(temporary) / "output.xlsx",
                    settings=WorkerSettings(mode="MANUAL", image_workers=2, local_ocr_workers=1, api_workers=2, queue_capacity=4),
                    blur_threshold=80,
                    confidence_threshold=35,
                    paddle_scan_mode="Cân bằng — Khuyên dùng",
                    retry_failed=False,
                    batch_session=session,
                )
            assert [path.name for path in online.calls] == ["special.jpg", "unreadable.jpg"], [path.name for path in online.calls]
            assert app.batch_progress is not None
            snapshot = app.batch_progress.snapshot()
            assert app.batch_progress.status is BatchStatus.COMPLETED_WITH_ERRORS
            assert snapshot["local_completed"] == 3 and snapshot["completed"] == 3
            assert snapshot["ai_completed"] == 2 and snapshot["ai_failed"] == 1
            events = []
            while True:
                try:
                    events.append(app.event_queue.get_nowait())
                except queue.Empty:
                    break
            assert len([event for event in events if event[0] == "done_scan"]) == 1
            assert not any(event[0] == "done_scan_stopped" for event in events)
        finally:
            app.destroy()
    if previous_appdata is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = previous_appdata
    print("hybrid_pipeline_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
