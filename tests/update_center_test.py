from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.update_center import PaddleRelease, build_paddle_staging_plan, fetch_paddle_release, parse_model_manifest, stage_model_archive


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def main() -> int:
    source = b'{"info":{"version":"9.9.9","project_urls":{"Release notes":"https://example.invalid/notes"}}}'
    release = fetch_paddle_release("https://example.invalid/pypi", opener=lambda *_args, **_kwargs: _Response(source))
    assert release == PaddleRelease("9.9.9", "https://example.invalid/pypi", "https://example.invalid/notes")

    plan = build_paddle_staging_plan("9.9.9", "3.1.0")
    assert plan.stage_dir.as_posix().endswith("update-staging/paddleocr-9.9.9")
    assert any("môi trường thử nghiệm" in step for step in plan.steps)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("PP-OCRv5_mobile_det/inference.yml", "model: det")
        archive.writestr("en_PP-OCRv5_mobile_rec/inference.yml", "model: rec")
    payload = buffer.getvalue()
    manifest = parse_model_manifest(
        json.dumps(
            {
                "version": "2026.07",
                "detection_model": "PP-OCRv5_mobile_det",
                "recognition_model": "en_PP-OCRv5_mobile_rec",
                "download_url": "https://example.invalid/models.zip",
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    )
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        result = stage_model_archive(manifest, root, opener=lambda *_args, **_kwargs: _Response(payload))
        assert result.verified and (result.stage_dir / "PP-OCRv5_mobile_det" / "inference.yml").exists()
        assert not list(root.glob("*.tmp"))
        try:
            stage_model_archive(manifest, root, opener=lambda *_args, **_kwargs: _Response(payload))
        except FileExistsError:
            pass
        else:
            raise AssertionError("Không được ghi đè model staging đã có")
    print("update_center_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
