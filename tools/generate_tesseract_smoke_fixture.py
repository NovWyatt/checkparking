"""Generate the tiny, deterministic plate image used to smoke-test Tesseract.

The fixture contains no user imagery or actual registration number.  It is a
synthetic alphanumeric plate rendered locally and is bundled with the app so
component verification never needs network access.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("arialbd.ttf", "arial.ttf", "segoeuib.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    image = Image.new("RGB", (900, 260), "#f8fafc")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((95, 48, 805, 212), radius=16, fill="#ffffff", outline="#0f172a", width=8)
    label = "59X112345"
    font = _font(92)
    bounds = draw.textbbox((0, 0), label, font=font)
    x = (image.width - (bounds[2] - bounds[0])) // 2
    y = (image.height - (bounds[3] - bounds[1])) // 2 - bounds[1]
    draw.text((x, y), label, font=font, fill="#111827")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, format="PNG", optimize=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
