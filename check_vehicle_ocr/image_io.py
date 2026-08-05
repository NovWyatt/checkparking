from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:
    pass


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".gif",
    ".heic",
    ".heif",
    ".avif",
    ".jp2",
    ".j2k",
    ".ppm",
    ".pgm",
    ".pbm",
}


def is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def collect_images(paths: Path | str | Iterable[Path | str], recursive: bool = True) -> list[Path]:
    images: list[Path] = []
    seen: set[str] = set()

    if isinstance(paths, (str, Path)):
        input_paths = [Path(paths)]
    else:
        input_paths = [Path(path) for path in paths]

    for input_path in input_paths:
        path = input_path.expanduser()
        if path.is_file() and is_image_file(path):
            resolved = str(path.resolve()).lower()
            if resolved not in seen:
                seen.add(resolved)
                images.append(path.resolve())
            continue

        if path.is_dir():
            iterator = path.rglob("*") if recursive else path.glob("*")
            for child in iterator:
                if is_image_file(child):
                    resolved = str(child.resolve()).lower()
                    if resolved not in seen:
                        seen.add(resolved)
                        images.append(child.resolve())

    return sorted(images, key=lambda item: str(item).lower())


def load_image(
    path: Path,
    *,
    stage_timings: dict[str, float] | None = None,
) -> tuple[np.ndarray, tuple[int, int]]:
    opened_at = time.perf_counter()
    image_file = Image.open(path)
    if stage_timings is not None:
        stage_timings["file_read_ms"] = stage_timings.get("file_read_ms", 0.0) + (time.perf_counter() - opened_at) * 1000

    with image_file as image:
        image.seek(0)
        exif_started = time.perf_counter()
        image = ImageOps.exif_transpose(image)
        if stage_timings is not None:
            stage_timings["exif_ms"] = stage_timings.get("exif_ms", 0.0) + (time.perf_counter() - exif_started) * 1000

        decode_started = time.perf_counter()
        image = image.convert("RGB")
        width, height = image.size
        rgb = np.array(image)

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    if stage_timings is not None:
        stage_timings["decode_ms"] = stage_timings.get("decode_ms", 0.0) + (time.perf_counter() - decode_started) * 1000
    return bgr, (width, height)


def save_crop(crop_bgr: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    Image.fromarray(rgb).save(path, quality=94)
