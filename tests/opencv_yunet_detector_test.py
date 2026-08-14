from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from check_vehicle_ocr.opencv_yunet_detector import (
    _candidate_from_points,
    bundled_yunet_model_path,
    detect_plate_candidates_yunet,
)


EXPECTED_SHA256 = "6d4978a7b6d25514d5e24811b82bfb511d166bdd8ca3b03aa63c1623d4d039c7"


def main() -> int:
    model_path = bundled_yunet_model_path()
    assert model_path is not None and model_path.is_file()
    assert hashlib.sha256(model_path.read_bytes()).hexdigest() == EXPECTED_SHA256
    assert (model_path.parent / "LICENSE").is_file()
    assert (model_path.parent / "NOTICE.md").is_file()
    assert (model_path.parent / "manifest.json").is_file()

    upright = _candidate_from_points(
        np.asarray(((20, 20), (140, 20), (140, 70), (20, 70)), dtype=np.float32),
        0.99,
        320,
        180,
    )
    assert upright is not None and upright.source == "opencv_yunet_plate"
    rotated = _candidate_from_points(
        np.asarray(((40, 20), (105, 85), (85, 145), (20, 80)), dtype=np.float32),
        0.99,
        320,
        180,
    )
    assert rotated is not None and rotated.source.endswith("_high_rotation")

    blank = np.zeros((640, 480, 3), dtype=np.uint8)
    assert detect_plate_candidates_yunet(blank, confidence_threshold=1.1) == []
    print("opencv_yunet_detector_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
