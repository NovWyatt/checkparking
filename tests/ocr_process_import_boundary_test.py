from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    package_entrypoint = (PROJECT_ROOT / "check_vehicle_ocr" / "__main__.py").read_text(encoding="utf-8")
    assert "freeze_support()" in package_entrypoint
    assert 'if __name__ == "__main__"' in package_entrypoint
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            (
                "import sys; import check_vehicle_ocr.app; "
                "loaded=sorted(name for name in sys.modules if name == 'paddle' or name.startswith('paddle.')); "
                "loaded_ocr=sorted(name for name in sys.modules if name == 'paddleocr' or name.startswith('paddleocr.')); "
                "print(len(loaded), len(loaded_ocr)); "
                "raise SystemExit(1 if loaded or loaded_ocr else 0)"
            ),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "Tkinter/UI import vẫn nạp Paddle native trong main process.\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    assert completed.stdout.strip().endswith("0 0")
    print("ocr_process_import_boundary_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
