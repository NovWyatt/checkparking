from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from check_vehicle_ocr.ui.theme import TOKENS


def _contrast(first: str, second: str) -> float:
    def luminance(value: str) -> float:
        channels = [int(value[index : index + 2], 16) / 255.0 for index in (1, 3, 5)]
        normalized = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
        return 0.2126 * normalized[0] + 0.7152 * normalized[1] + 0.0722 * normalized[2]

    first_luminance, second_luminance = luminance(first), luminance(second)
    return (max(first_luminance, second_luminance) + 0.05) / (min(first_luminance, second_luminance) + 0.05)


def main() -> int:
    for mode, palette in TOKENS.items():
        for foreground, background in (
            ("text_primary", "surface"),
            ("text_secondary", "surface"),
            ("text_muted", "surface"),
            ("text_secondary", "background"),
            ("text_secondary", "border"),
            ("on_accent", "accent"),
            ("success", "surface"),
            ("warning", "surface"),
            ("danger", "surface"),
            ("info", "surface"),
        ):
            value = _contrast(palette[foreground], palette[background])
            assert value >= 4.5, f"{mode} {foreground}/{background} chỉ đạt {value:.2f}:1"
    print("theme_contrast_test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
