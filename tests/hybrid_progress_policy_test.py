from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from check_vehicle_ocr.hybrid_review import AiReviewPolicy, should_send_to_ai
from check_vehicle_ocr.models import ImageResult, PlateCandidate
from check_vehicle_ocr.plate_formatting import PlateFormatStatus
from check_vehicle_ocr.services.progress_service import BatchProgress, BatchStatus


def result(*, readable: bool = True, confidence: float = 92.0, status: str = "OK", unmatched: bool = False, review: bool = False) -> ImageResult:
    plate = PlateCandidate(
        bbox=(0, 0, 1, 1),
        score=1.0,
        text="59X1-12345" if readable else "",
        raw_text="59X112345" if readable else "",
        export_text="59X1-12345" if readable else "",
        readable=readable,
        confidence=confidence,
        needs_review=review,
        format_status=PlateFormatStatus.UNMATCHED if unmatched else PlateFormatStatus.FORMATTED,
    )
    return ImageResult(Path("image.jpg"), status, "", plates=[plate])


def test_policy() -> None:
    clear = result()
    assert should_send_to_ai(clear, AiReviewPolicy.NEEDS_REVIEW, confidence_threshold=35)[0] is False
    assert should_send_to_ai(clear, AiReviewPolicy.UNREADABLE_ONLY, confidence_threshold=35)[0] is False
    assert should_send_to_ai(clear, AiReviewPolicy.ALL_IMAGES, confidence_threshold=35)[0] is True
    assert should_send_to_ai(result(readable=False), AiReviewPolicy.UNREADABLE_ONLY, confidence_threshold=35)[0] is True
    assert should_send_to_ai(result(unmatched=True), AiReviewPolicy.NEEDS_REVIEW, confidence_threshold=35)[0] is True
    assert should_send_to_ai(result(confidence=20), AiReviewPolicy.NEEDS_REVIEW, confidence_threshold=35)[0] is True
    assert should_send_to_ai(result(review=True), AiReviewPolicy.NEEDS_REVIEW, confidence_threshold=35)[0] is True


def test_hybrid_progress_lifecycle() -> None:
    progress = BatchProgress(total=3, configured_workers={"local_ocr": 1, "api": 2})
    progress.preparing_model()
    progress.start()
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        progress.hybrid_local_started(name)
        progress.hybrid_local_finished(name)
    progress.hybrid_queue_ai(3)
    snapshot = progress.snapshot()
    assert snapshot["local_completed"] == 3 and snapshot["completed"] == 0 and snapshot["percent"] == 0
    progress.hybrid_finish_result("success")
    progress.hybrid_ai_started("a.jpg")
    progress.hybrid_ai_finished("a.jpg", improved=True)
    progress.hybrid_finish_result("success", used_ai=True)
    progress.hybrid_ai_started("b.jpg")
    progress.hybrid_ai_finished("b.jpg", improved=False, failed=True)
    progress.hybrid_finish_result("review", used_ai=True, ai_failed=True)
    assert progress.snapshot()["completed"] == 3
    progress.finish()
    snapshot = progress.snapshot()
    assert progress.status is BatchStatus.COMPLETED_WITH_ERRORS
    assert snapshot["active_workers"] == {} and snapshot["current_files"] == []
    assert snapshot["ai_completed"] == 2 and snapshot["ai_failed"] == 1


def test_local_only_and_stop() -> None:
    progress = BatchProgress(total=2, configured_workers={})
    progress.preparing_model()
    progress.start()
    for name in ("a.jpg", "b.jpg"):
        progress.hybrid_local_started(name)
        progress.hybrid_local_finished(name)
        progress.hybrid_finish_result("success")
    progress.finish()
    assert progress.status is BatchStatus.COMPLETED
    stopped = BatchProgress(total=2, configured_workers={})
    stopped.preparing_model()
    stopped.start()
    stopped.hybrid_local_started("a.jpg")
    stopped.hybrid_local_finished("a.jpg")
    stopped.hybrid_finish_result("success")
    stopped.request_stop()
    stopped.finish(cancelled=True)
    assert stopped.status is BatchStatus.CANCELLED


def main() -> int:
    test_policy()
    test_hybrid_progress_lifecycle()
    test_local_only_and_stop()
    print("hybrid_progress_policy_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
