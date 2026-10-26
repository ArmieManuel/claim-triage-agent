"""Assemble docs/images/demo.gif from screenshots of the demo page (one claim, start to result).

Usage: .venv\\Scripts\\python scripts\\make_demo_gif.py frame1.jpg frame2.jpg ...
Each frame gets a short caption bar so the GIF explains itself without sound.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "docs" / "images" / "demo.gif"
WIDTH = 720
CAPTIONS = [
    ("Demo page: no API key in the browser", 1600),
    ("Pick a synthetic sample claim (Italian letter, kitchen fire)", 1800),
    ("The local model works on the CPU (about 30 to 45 s)", 1800),
    ("Routed to senior handler, with the reason", 3200),
    ("Summary for the handler and the extracted fields", 3200),
    ("Every step with its time and token count", 3600),
]


def font(size: int) -> ImageFont.ImageFont:
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def frame(path: str, caption: str) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image = image.resize((WIDTH, round(image.height * WIDTH / image.width)), Image.LANCZOS)
    bar = 44
    canvas = Image.new("RGB", (WIDTH, image.height + bar), (31, 31, 29))
    canvas.paste(image, (0, bar))
    ImageDraw.Draw(canvas).text((16, 11), caption, fill=(236, 235, 230), font=font(18))
    return canvas


def main(paths: list[str]) -> None:
    if len(paths) != len(CAPTIONS):
        raise SystemExit(f"expected {len(CAPTIONS)} frames, got {len(paths)}")
    frames = [frame(p, c) for p, (c, _) in zip(paths, CAPTIONS, strict=True)]
    height = max(f.height for f in frames)
    padded = []
    for f in frames:
        page = Image.new("RGB", (WIDTH, height), (247, 247, 245))
        page.paste(f, (0, 0))
        padded.append(page.quantize(colors=128, method=Image.Quantize.MEDIANCUT))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    padded[0].save(
        OUT,
        save_all=True,
        append_images=padded[1:],
        duration=[d for _, d in CAPTIONS],
        loop=0,
        optimize=True,
    )
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1:])
