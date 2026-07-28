"""Synthetic PaddleOCR smoke test for a staged, versioned model bundle."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detection-dir", type=Path, required=True)
    parser.add_argument("--recognition-dir", type=Path, required=True)
    args = parser.parse_args()
    if not (args.detection_dir / "inference.yml").is_file() or not (args.recognition_dir / "inference.yml").is_file():
        return 2
    try:
        import numpy as np
        from paddleocr import PaddleOCR

        engine = PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_detection_model_dir=str(args.detection_dir),
            text_recognition_model_name="en_PP-OCRv5_mobile_rec",
            text_recognition_model_dir=str(args.recognition_dir),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_rec_score_thresh=0.1,
        )
        # Initializing the exact staged model and predicting one compact image
        # catches bad archives and incompatible weights without touching the
        # active engine or downloading a replacement model.
        image = np.full((96, 320, 3), 255, dtype=np.uint8)
        list(engine.predict(image))
        return 0
    except Exception as exc:
        print(type(exc).__name__, file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
