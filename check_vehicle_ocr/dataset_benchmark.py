from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import ImageResult
from .ocr import normalize_plate_text


@dataclass(frozen=True)
class BenchmarkItem:
    image_path: Path
    expected_plate: str = ""


def load_benchmark_items(folder: Path, manifest_path: Path | None = None) -> list[BenchmarkItem]:
    if manifest_path is None:
        from .image_io import collect_images

        return [BenchmarkItem(path) for path in collect_images(folder, recursive=True)]

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Manifest benchmark phải là một mảng JSON.")
    items: list[BenchmarkItem] = []
    seen: set[Path] = set()
    for index, entry in enumerate(payload, start=1):
        if not isinstance(entry, dict) or not isinstance(entry.get("image"), str):
            raise ValueError(f"Manifest dòng {index} thiếu image.")
        relative = Path(entry["image"])
        if relative.is_absolute():
            raise ValueError(f"Manifest dòng {index} phải dùng đường dẫn ảnh tương đối.")
        image_path = (manifest_path.parent / relative).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy ảnh ở manifest dòng {index}: {relative}")
        if image_path in seen:
            continue
        seen.add(image_path)
        items.append(BenchmarkItem(image_path, str(entry.get("expected_plate") or "")))
    return items


def evaluate_result(result: ImageResult, expected_plate: str) -> dict[str, object]:
    expected = normalize_plate_text(expected_plate)
    predictions = [normalize_plate_text(plate.final_text) for plate in result.plates if plate.readable and plate.final_text]
    predictions = [value for value in dict.fromkeys(predictions) if value]
    exact = bool(expected and expected in predictions)
    character_accuracy = max((_character_accuracy(expected, value) for value in predictions), default=0.0) if expected else None
    unreadable = not bool(predictions)
    needs_review = result.status != "OK" or any(plate.needs_review for plate in result.plates)
    false_positive = bool(expected and predictions and not exact)
    return {
        "image": str(result.image_path),
        "expected_plate": expected_plate,
        "predictions": predictions,
        "exact_match": exact,
        "character_accuracy": character_accuracy,
        "unreadable": unreadable,
        "needs_review": needs_review,
        "false_positive": false_positive,
        "status": result.status,
        "reason": result.reason,
    }


def summarise(rows: list[dict[str, object]], elapsed_seconds: float, scan_mode: str) -> dict[str, object]:
    labelled = [row for row in rows if str(row.get("expected_plate") or "").strip()]
    character_values = [float(row["character_accuracy"]) for row in labelled if row.get("character_accuracy") is not None]
    total = len(rows)
    return {
        "scan_mode": scan_mode,
        "total_images": total,
        "labelled_images": len(labelled),
        "exact_match": sum(bool(row["exact_match"]) for row in labelled),
        "exact_match_rate": sum(bool(row["exact_match"]) for row in labelled) / len(labelled) if labelled else None,
        "character_accuracy": sum(character_values) / len(character_values) if character_values else None,
        "unreadable": sum(bool(row["unreadable"]) for row in rows),
        "needs_review": sum(bool(row["needs_review"]) for row in rows),
        "false_positive": sum(bool(row["false_positive"]) for row in labelled),
        "elapsed_seconds": max(0.0, elapsed_seconds),
        "images_per_minute": total / elapsed_seconds * 60.0 if elapsed_seconds > 0 else 0.0,
        "rows": rows,
    }


def _character_accuracy(expected: str, prediction: str) -> float:
    if not expected:
        return 0.0
    distance = _levenshtein(expected, prediction)
    return max(0.0, 1.0 - distance / max(len(expected), len(prediction), 1))


def _levenshtein(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(min(current[-1] + 1, previous[right_index] + 1, previous[right_index - 1] + (left_character != right_character)))
        previous = current
    return previous[-1]
