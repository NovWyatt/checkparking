from __future__ import annotations

import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.services.progress_service import BatchProgress, BatchStatus


def main() -> int:
    progress = BatchProgress(total=4, configured_workers={"image": 4, "local_ocr": 1, "api": 2})
    progress.preparing_model()
    assert progress.status is BatchStatus.PREPARING_MODEL and progress.queued == 4
    progress.start()
    progress.started_at = time.monotonic() - 120.0
    progress.mark_started("a.jpg", "local_ocr")
    progress.mark_finished("a.jpg", "local_ocr", "success")
    progress.mark_started("b.jpg", "local_ocr")
    progress.mark_finished("b.jpg", "local_ocr", "review")
    snapshot = progress.snapshot()
    assert snapshot["completed"] == 2 and snapshot["succeeded"] == 1 and snapshot["needs_review"] == 1
    assert snapshot["elapsed_seconds"] >= 120.0 and snapshot["images_per_minute"] > 0
    assert snapshot["eta_seconds"] is not None and snapshot["eta_seconds"] >= 0
    assert snapshot["current_files"] == [] and snapshot["active"] == 0
    progress.mark_started("c.jpg", "local_ocr")
    progress.mark_finished("c.jpg", "local_ocr", "failed")
    progress.finish()
    assert progress.status is BatchStatus.COMPLETED_WITH_ERRORS and progress.finished_at is not None
    progress = BatchProgress(total=1, configured_workers={})
    assert progress.eta_seconds is None and progress.images_per_minute == 0
    progress.preparing_model()
    progress.request_stop()
    progress.finish(cancelled=True)
    assert progress.status is BatchStatus.CANCELLED
    print("progress_state_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
