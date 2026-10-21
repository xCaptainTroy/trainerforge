"""Regenerate the TrainerForge icon set.

Requires Pillow:  python -m pip install pillow
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "trainerforge" / "assets"
DOCS = ROOT / "docs"
S = 1024


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = 56
    radius = 200
    draw.rounded_rectangle(
        (margin, margin, S - margin, S - margin),
        radius=radius,
        fill=(19, 25, 35, 255),
        outline=(48, 62, 84, 255),
        width=18,
    )
    draw.rounded_rectangle(
        (margin + 44, margin + 44, S - margin - 44, S - margin - 44),
        radius=radius - 40,
        fill=(25, 33, 47, 255),
    )

    accent = (91, 140, 255, 255)
    green = (61, 220, 151, 255)
    inset = 236
    length = 118
    width = 30
    corners = (
        (inset, inset, 1, 1),
        (S - inset, inset, -1, 1),
        (inset, S - inset, 1, -1),
        (S - inset, S - inset, -1, -1),
    )
    for x, y, dx, dy in corners:
        draw.line((x, y, x + dx * length, y), fill=accent, width=width)
        draw.line((x, y, x, y + dy * length), fill=accent, width=width)

    font = _font(400)
    text = "T"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((S - tw) / 2 - bbox[0], (S - th) / 2 - bbox[1] - 10),
        text,
        font=font,
        fill=(235, 241, 250, 255),
    )
    dot = 82
    draw.ellipse(
        (S - 300, S - 306, S - 300 + dot, S - 306 + dot),
        fill=green,
    )

    png_path = ASSETS / "icon.png"
    image.save(png_path)
    image.save(DOCS / "icon.png")

    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [image.resize((size, size), Image.Resampling.LANCZOS) for size in sizes]
    ico_path = ASSETS / "icon.ico"
    frames[-1].save(
        ico_path,
        format="ICO",
        sizes=[(size, size) for size in sizes],
        append_images=frames[:-1],
    )
    print(f"wrote {ico_path}")
    print(f"wrote {png_path}")
    print(f"wrote {DOCS / 'icon.png'}")
    return 0


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
    ):
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                pass
    return ImageFont.load_default()


if __name__ == "__main__":
    raise SystemExit(main())
