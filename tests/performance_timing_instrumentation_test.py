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


class _FastFallbackPaddle:
    def read_plate_regions(self, crop):
        height, width = crop.shape[:2]
        if (width, height) == (220, 80):
            return []
        return [
            (
                (120, 80, 220, 80),
                OcrAttempt(
                    raw_text="59X112345",
                    text="59X112345",
                    normalized_text="59X112345",
                    confidence=96.0,
                    engine="paddleocr",
                ),
            )
        ]


class _FastCenterRescuePaddle:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, int | None, str | None]] = []

    def read_plate_regions(self, crop, *, detector_limit_side_len=None, detector_limit_type=None):
        height, width = crop.shape[:2]
        self.calls.append((width, height, detector_limit_side_len, detector_limit_type))
        if (width, height) == (518, 384) and detector_limit_side_len == 960 and detector_limit_type == "max":
            return [
                (
                    (80, 60, 220, 80),
                    OcrAttempt(
                        raw_text="59U137185",
                        text="59U137185",
                        normalized_text="59U137185",
                        confidence=96.0,
                        engine="paddleocr",
                    ),
                )
            ]
        return []


class _FastVerificationPaddle:
    def __init__(self) -> None:
        self.verification_calls = 0

    def read_plate_regions(self, _crop):
        return [
            (
                (0, 0, 220, 80),
                OcrAttempt(
                    raw_text="76G1T25503",
                    text="76G1T25503",
                    normalized_text="76G1T25503",
                    confidence=88.0,
                    engine="paddleocr",
                ),
            )
        ]

    def read_plate_regions_fast_verification(self, _crop):
        self.verification_calls += 1
        return [
            (
                (0, 0, 220, 80),
                OcrAttempt(
                    raw_text="76G125509",
                    text="76G125509",
                    normalized_text="76G125509",
                    confidence=99.0,
                    engine="paddleocr-small-verification",
                ),
            )
        ]


class _FastExpandedCropPaddle:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def read_plate_regions(self, crop):
        height, width = crop.shape[:2]
        self.calls.append((width, height))
        expanded = (width, height) == (268, 100)
        raw = "59U137185" if expanded else "59U11137185"
        return [
            (
                (0, 0, width, height),
                OcrAttempt(
                    raw_text=raw,
                    text=raw,
                    normalized_text=raw,
                    confidence=96.0 if expanded else 75.0,
                    engine="paddleocr",
                ),
            )
        ]


class _FastHighRotationVerificationPaddle:
    def __init__(self) -> None:
        self.verification_calls = 0

    def read_plate_regions(self, _crop):
        return [
            (
                (0, 0, 220, 80),
                OcrAttempt(
                    raw_text="59C301122",
                    text="59C301122",
                    normalized_text="59C301122",
                    confidence=99.0,
                    engine="paddleocr",
                ),
            )
        ]

    def read_plate_regions_fast_verification(self, _crop):
        self.verification_calls += 1
        return [
            (
                (0, 0, 220, 80),
                OcrAttempt(
                    raw_text="59C304122",
                    text="59C304122",
                    normalized_text="59C304122",
                    confidence=99.0,
                    engine="paddleocr-small-verification",
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

        previous = processor.detect_plate_candidates_onnx
        processor.detect_plate_candidates_onnx = lambda *_args, **_kwargs: [
            PlateCandidate(
                bbox=(120, 80, 220, 80),
                score=95.0,
                detector_confidence=95.0,
                source="test-detector",
            )
        ]
        try:
            fast_rescue = processor.process_image(
                image_path,
                root / "fast_rescue_crops",
                _FastFallbackPaddle(),
                blur_threshold=0,
                confidence_threshold=70,
                paddle_scan_mode="fast",
                image_bgr=np.full((520, 900, 3), 210, dtype=np.uint8),
                image_size=(900, 520),
                selected_plate_type=PlateType.MOTORCYCLE,
            )
        finally:
            processor.detect_plate_candidates_onnx = previous

        assert fast_rescue.status == "OK"
        assert fast_rescue.primary_plate is not None
        assert fast_rescue.primary_plate.normalized_text == "59X112345"
        assert fast_rescue.pipeline_metrics["full_scene_ocr_calls"] == 1

        previous = processor.detect_plate_candidates_onnx
        processor.detect_plate_candidates_onnx = lambda *_args, **_kwargs: []
        center_engine = _FastCenterRescuePaddle()
        try:
            fast_center_rescue = processor.process_image(
                image_path,
                root / "fast_center_rescue_crops",
                center_engine,
                blur_threshold=0,
                confidence_threshold=70,
                paddle_scan_mode="fast",
                image_bgr=np.full((1280, 960, 3), 210, dtype=np.uint8),
                image_size=(960, 1280),
                selected_plate_type=PlateType.MOTORCYCLE,
            )
        finally:
            processor.detect_plate_candidates_onnx = previous

        assert fast_center_rescue.status == "OK"
        assert fast_center_rescue.primary_plate is not None
        assert fast_center_rescue.primary_plate.normalized_text == "59U137185"
        assert center_engine.calls == [
            (960, 1280, None, None),
            (518, 358, 960, "max"),
            (518, 384, 960, "max"),
        ]

        previous = processor.detect_plate_candidates_onnx
        processor.detect_plate_candidates_onnx = lambda *_args, **_kwargs: [
            PlateCandidate(
                bbox=(40, 30, 220, 80),
                score=95.0,
                detector_confidence=95.0,
                source="test-detector",
            )
        ]
        verification_engine = _FastVerificationPaddle()
        try:
            fast_verification = processor.process_image(
                image_path,
                root / "fast_verification_crops",
                verification_engine,
                blur_threshold=0,
                confidence_threshold=70,
                paddle_scan_mode="fast",
                image_bgr=np.full((180, 320, 3), 210, dtype=np.uint8),
                image_size=(320, 180),
                selected_plate_type=PlateType.NONE,
            )
        finally:
            processor.detect_plate_candidates_onnx = previous

        assert fast_verification.status == "OK"
        assert fast_verification.primary_plate is not None
        assert fast_verification.primary_plate.normalized_text == "76G125509"
        assert verification_engine.verification_calls == 1
        assert fast_verification.pipeline_metrics["small_verification_ocr_calls"] == 1

        previous = processor.detect_plate_candidates_onnx
        processor.detect_plate_candidates_onnx = lambda *_args, **_kwargs: [
            PlateCandidate(
                bbox=(40, 30, 220, 80),
                score=95.0,
                detector_confidence=95.0,
                source="opencv_yunet_plate",
            )
        ]
        expanded_engine = _FastExpandedCropPaddle()
        try:
            fast_expanded_crop = processor.process_image(
                image_path,
                root / "fast_expanded_crop",
                expanded_engine,
                blur_threshold=0,
                confidence_threshold=70,
                paddle_scan_mode="fast",
                image_bgr=np.full((180, 320, 3), 210, dtype=np.uint8),
                image_size=(320, 180),
                selected_plate_type=PlateType.NONE,
            )
        finally:
            processor.detect_plate_candidates_onnx = previous

        assert fast_expanded_crop.primary_plate is not None
        assert fast_expanded_crop.primary_plate.normalized_text == "59U137185"
        assert expanded_engine.calls == [(220, 80), (268, 100)]
        assert fast_expanded_crop.pipeline_metrics["small_verification_ocr_calls"] == 0

        previous = processor.detect_plate_candidates_onnx
        processor.detect_plate_candidates_onnx = lambda *_args, **_kwargs: [
            PlateCandidate(
                bbox=(40, 30, 220, 80),
                score=95.0,
                detector_confidence=95.0,
                source="opencv_yunet_plate_high_rotation",
            )
        ]
        high_rotation_engine = _FastHighRotationVerificationPaddle()
        try:
            high_rotation = processor.process_image(
                image_path,
                root / "fast_high_rotation",
                high_rotation_engine,
                blur_threshold=0,
                confidence_threshold=70,
                paddle_scan_mode="fast",
                image_bgr=np.full((180, 320, 3), 210, dtype=np.uint8),
                image_size=(320, 180),
                selected_plate_type=PlateType.NONE,
            )
        finally:
            processor.detect_plate_candidates_onnx = previous

        assert high_rotation.primary_plate is not None
        assert high_rotation.primary_plate.normalized_text == "59C304122"
        assert high_rotation_engine.verification_calls == 1
        assert high_rotation.pipeline_metrics["small_verification_ocr_calls"] == 1

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
