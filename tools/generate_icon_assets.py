"""Generate original, local PNG/ICO assets from the Check Vehicle icon palette."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "assets" / "icons"
SIZES = (16, 20, 24, 32, 48, 64, 128, 256)
FUNCTIONAL = (
    "scan", "folder", "images", "results", "review", "export", "settings", "update", "download",
    "telegram-notification", "ai", "local-ocr", "warning", "success", "error", "stop", "search",
    "edit", "delete", "refresh", "install",
)


def _base(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def app_icon(size: int) -> Image.Image:
    image, draw = _base(size)
    scale = size / 256
    box = lambda value: int(round(value * scale))
    draw.rounded_rectangle((box(18), box(18), box(238), box(238)), radius=box(48), fill="#242A5C")
    draw.rounded_rectangle((box(53), box(93), box(203), box(169)), radius=box(16), fill="#F5F7FB")
    for x in (69, 95, 121):
        draw.rounded_rectangle((box(x), box(111), box(x + 17), box(151)), radius=max(1, box(4)), fill="#242A5C")
    draw.line([(box(153), box(132)), (box(165), box(144)), (box(189), box(117))], fill="#16734C", width=max(2, box(11)), joint="curve")
    return image


def functional_icon(name: str, size: int = 24) -> Image.Image:
    image, draw = _base(size)
    stroke = max(2, size // 11)
    accent, dark, success, warning, danger = "#4C5CCB", "#242A5C", "#16734C", "#A6670A", "#B42335"
    margin = max(2, size // 7)
    if name in {"success", "review"}:
        draw.line([(margin, size // 2), (size // 2 - 1, size - margin), (size - margin, margin)], fill=success, width=stroke, joint="curve")
    elif name in {"warning", "error"}:
        color = warning if name == "warning" else danger
        draw.polygon([(size // 2, margin), (size - margin, size - margin), (margin, size - margin)], outline=color, width=stroke)
        draw.line([(size // 2, size // 3), (size // 2, size * 3 // 5)], fill=color, width=stroke)
        draw.ellipse((size // 2 - 1, size * 3 // 4 - 1, size // 2 + 1, size * 3 // 4 + 1), fill=color)
    elif name in {"stop", "delete"}:
        draw.rounded_rectangle((margin, margin, size - margin, size - margin), radius=max(2, margin), fill=danger)
        if name == "delete":
            draw.line([(size // 3, size // 3), (size * 2 // 3, size * 2 // 3)], fill="white", width=stroke)
            draw.line([(size * 2 // 3, size // 3), (size // 3, size * 2 // 3)], fill="white", width=stroke)
    elif name in {"folder", "images"}:
        draw.rounded_rectangle((margin, size // 3, size - margin, size - margin), radius=margin, outline=accent, width=stroke)
        draw.line([(margin, size // 3), (size // 2, size // 3), (size * 3 // 5, size // 4)], fill=accent, width=stroke)
        if name == "images":
            draw.ellipse((size // 3, size // 2 - 2, size // 3 + 4, size // 2 + 2), fill=accent)
    elif name in {"download", "install", "export"}:
        draw.line([(size // 2, margin), (size // 2, size * 2 // 3)], fill=accent, width=stroke)
        draw.line([(size // 3, size // 2), (size // 2, size * 2 // 3), (size * 2 // 3, size // 2)], fill=accent, width=stroke)
        draw.line([(margin, size - margin), (size - margin, size - margin)], fill=accent, width=stroke)
    elif name in {"refresh", "update"}:
        draw.arc((margin, margin, size - margin, size - margin), 35, 320, fill=accent, width=stroke)
        draw.polygon([(size - margin, size // 3), (size - margin - 5, size // 3 - 1), (size - margin - 1, size // 3 + 5)], fill=accent)
    elif name == "search":
        draw.ellipse((margin, margin, size * 2 // 3, size * 2 // 3), outline=accent, width=stroke)
        draw.line([(size * 3 // 5, size * 3 // 5), (size - margin, size - margin)], fill=accent, width=stroke)
    elif name == "edit":
        draw.polygon([(margin, size - margin), (margin + 3, size - margin - 7), (size - margin - 3, margin), (size - margin, margin + 3), (margin + 7, size - margin - 3)], outline=accent, fill=None)
    elif name == "settings":
        draw.ellipse((size // 3, size // 3, size * 2 // 3, size * 2 // 3), outline=dark, width=stroke)
        for x, y in ((size // 2, margin), (size // 2, size - margin), (margin, size // 2), (size - margin, size // 2)):
            draw.line([(size // 2, size // 2), (x, y)], fill=dark, width=stroke)
    elif name in {"scan", "local-ocr", "ai", "telegram-notification", "results"}:
        draw.rounded_rectangle((margin, size // 3, size - margin, size * 2 // 3), radius=max(2, margin), outline=accent, width=stroke)
        for x in (size // 3, size // 2, size * 2 // 3):
            draw.line([(x, size // 3 + 3), (x, size * 2 // 3 - 3)], fill=accent, width=max(1, stroke - 1))
        if name == "scan":
            draw.line([(margin, margin), (margin + 5, margin)], fill=success, width=stroke)
    else:
        draw.ellipse((margin, margin, size - margin, size - margin), outline=accent, width=stroke)
    return image


def svg_for(name: str) -> str:
    # The PNG is used by Tkinter.  Keep a matching small SVG for packaging and
    # future UI surfaces that can render vector assets directly.
    color = "#B42335" if name in {"error", "stop", "delete"} else "#A6670A" if name == "warning" else "#4C5CCB"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="7" width="18" height="10" rx="2"/><path d="M8 10v4M12 10v4M16 10v4"/></svg>\n'''


def main() -> int:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    icon = app_icon(256)
    for size in SIZES:
        icon.resize((size, size), Image.Resampling.LANCZOS).save(DESTINATION / f"app-icon-{size}.png")
    icon.save(DESTINATION / "app-icon.ico", sizes=[(size, size) for size in SIZES])
    for name in FUNCTIONAL:
        functional_icon(name).save(DESTINATION / f"{name}.png")
        (DESTINATION / f"{name}.svg").write_text(svg_for(name), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
