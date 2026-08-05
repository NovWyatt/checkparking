from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_vehicle_ocr import processor
from check_vehicle_ocr.image_io import load_image
from check_vehicle_ocr.models import OcrAttempt, PlateCandidate
from check_vehicle_ocr.plate_formatting import PlateType


EXPECTED_STAGE_KEYS = {
    "file_read_ms",
    "exif_ms",
    "decode_ms",
    "resize_ms",
    "detector_ms",
    "detector_postprocess_ms",
    "crop_ms",
    "paddle_det_ms",
    "paddle_rec_ms",
    "paddle_total_ms",
    "formatting_ms",
    "tesseract_ms",
    "candidate_filter_ms",
    "scoring_ms",
    "thumbnail_ms",
    "result_event_ms",
    "ui_render_ms",
    "total_ms",
}


class _TimedDetector:
    def __call__(self, _image, *, max_candidates: int, confidence_threshold: float):
        del max_candidates, confidence_threshold
        time.sleep(0.002)
        return [
            PlateCandidate(
                bbox=(40, 30, 220, 80),
                score=95.0,
                detector_confidence=95.0,
                source="timed-detector",
            )
        ]


class _TimedPaddle:
    def read_plate_regions(self, _crop):
        time.sleep(0.002)
        return [
            (
                (0, 0, 220, 80),
                OcrAttempt(
                    raw_text="59X112345",
                    text="59X112345",
                    normalized_text="59X112345",
                    confidence=96.0,
                    engine="paddleocr",
                ),
            )
        ]


class _ShapeDetector:
    def __init__(self) -> None:
        self.shapes: list[tuple[int, int]] = []

    def __call__(self, image, *, max_candidates: int, confidence_threshold: float):
        del max_candidates, confidence_threshold
        self.shapes.append((image.shape[1], image.shape[0]))
        return [
            PlateCandidate(
                bbox=(100, 200, 300, 100),
                score=95.0,
                detector_confidence=95.0,
                source="shape-detector",
            )
        ]


class _ShapePaddle:
    def __init__(self) -> None:
        self.shapes: list[tuple[int, int]] = []

    def read_plate_regions(self, crop):
        self.shapes.append((crop.shape[1], crop.shape[0]))
        return [
            (
                (0, 0, crop.shape[1], crop.shape[0]),
                OcrAttempt(
                    raw_text="59X112345",
                    text="59X112345",
                    normalized_text="59X112345",
                    confidence=96.0,
                    engine="paddleocr",
                ),
            )
        ]


def _run_shape_case(root: Path, frame: np.ndarray, image_path: Path, mode: str):
    detector = _ShapeDetector()
    engine = _ShapePaddle()
    previous = processor.detect_plate_candidates_onnx
    processor.detect_plate_candidates_onnx = detector
    try:
        timings: dict[str, float] = {}
        result = processor.process_image(
            image_path,
            root / f"{mode}_crops",
            engine,
            blur_threshold=0,
            confidence_threshold=70,
            paddle_scan_mode=mode,
            image_bgr=frame,
            image_size=(frame.shape[1], frame.shape[0]),
            selected_plate_type=PlateType.MOTORCYCLE,
            stage_timings=timings,
        )
        return result, timings, detector, engine
    finally:
        processor.detect_plate_candidates_onnx = previous


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        image_path = root / "timing.jpg"
        Image.new("RGB", (320, 180), "white").save(image_path, quality=90)

        load_timings: dict[str, float] = {}
        frame, size = load_image(image_path, stage_timings=load_timings)
        assert size == (320, 180)
        assert {"file_read_ms", "exif_ms", "decode_ms"} <= load_timings.keys()
        assert all(load_timings[key] >= 0 for key in ("file_read_ms", "exif_ms", "decode_ms"))

        detector = _TimedDetector()
        previous = processor.detect_plate_candidates_onnx
        processor.detect_plate_candidates_onnx = detector
        try:
            stage_timings = dict(load_timings)
            result = processor.process_image(
                image_path,
                root / "crops",
                _TimedPaddle(),
                blur_threshold=0,
                confidence_threshold=70,
                paddle_scan_mode="fast",
                image_bgr=frame,
                image_size=size,
                selected_plate_type=PlateType.MOTORCYCLE,
                stage_timings=stage_timings,
            )
        finally:
            processor.detect_plate_candidates_onnx = previous

        assert result.status == "OK"
        assert result.pipeline_metrics["detector_calls"] == 1
        assert result.pipeline_metrics["crop_ocr_calls"] == 1
        assert EXPECTED_STAGE_KEYS <= stage_timings.keys()
        assert stage_timings["detector_ms"] >= 1.0
        assert stage_timings["paddle_total_ms"] >= 1.0
        assert stage_timings["total_ms"] >= stage_timings["detector_ms"]
        assert all(value >= 0 for value in stage_timings.values())

        large_frame = np.full((2560, 1920, 3), 210, dtype=np.uint8)
        for mode in ("fast", "balanced"):
            resized, resized_timings, resized_detector, resized_engine = _run_shape_case(root, large_frame, image_path, mode)
            assert resized_detector.shapes == [(960, 1280)]
            assert resized_engine.shapes == [(300, 100)]
            assert resized_timings["resize_ms"] > 0
            assert (resized.width, resized.height) == (1920, 2560)
            assert resized.primary_plate is not None
            assert resized.primary_plate.bbox == (200, 400, 600, 200)
            assert resized.primary_plate.raw_text == "59X112345"
            assert resized.primary_plate.final_text == "59X1-12345"
            assert resized.pipeline_metrics["detector_calls"] == 1
            assert resized.pipeline_metrics["crop_ocr_calls"] == 1
            assert resized.pipeline_metrics["full_scene_ocr_calls"] == 0
            assert resized.pipeline_metrics["candidates_before_filter"] == 1
            assert resized.pipeline_metrics["candidates_after_filter"] == 1

        thorough, thorough_timings, thorough_detector, thorough_engine = _run_shape_case(root, large_frame, image_path, "thorough")
        assert thorough_detector.shapes == [(1920, 2560)]
        assert thorough_engine.shapes == [(300, 100)]
        assert thorough_timings["resize_ms"] == 0
        assert (thorough.width, thorough.height) == (1920, 2560)
        assert thorough.primary_plate is not None
        assert thorough.primary_plate.bbox == (100, 200, 300, 100)
        assert thorough.primary_plate.raw_text == "59X112345"
        assert thorough.primary_plate.final_text == "59X1-12345"
        assert thorough.pipeline_metrics["detector_calls"] == 1
        assert thorough.pipeline_metrics["crop_ocr_calls"] == 1
        assert thorough.pipeline_metrics["full_scene_ocr_calls"] == 0

    print("performance_timing_instrumentation_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
