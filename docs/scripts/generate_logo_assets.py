"""Genera los assets de logo de Prevex a partir de la imagen fuente.

Produce:
- apps/web/public/logo.png        -> logo completo (escudo + texto PREVEX), recortado ajustado
- apps/web/public/logo-mark.png   -> solo el escudo (cuadrado) para sidebar/favicon
- apps/web/public/favicon.png     -> escudo 64x64
"""
from __future__ import annotations

import os
import sys

from PIL import Image

SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    r"~/Downloads/Gemini_Generated_Image_l4qwz7l4qwz7l4qw (1).png"
)
HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.normpath(os.path.join(HERE, "..", "..", "apps", "web", "public"))


def autocrop(im: Image.Image, threshold: int = 8) -> Image.Image:
    """Recorta el margen transparente usando el canal alfa."""
    alpha = im.convert("RGBA").getchannel("A")
    mask = alpha.point(lambda p: 255 if p > threshold else 0)
    bbox = mask.getbbox()
    return im.crop(bbox) if bbox else im


def main() -> None:
    im = Image.open(SRC).convert("RGBA")
    print("source size", im.size)
    w, h = im.size

    # Logo completo: recorte ajustado del contenido con un pequeño padding.
    full = autocrop(im)
    pad = int(max(full.size) * 0.03)
    canvas = Image.new("RGBA", (full.size[0] + pad * 2, full.size[1] + pad * 2), (0, 0, 0, 0))
    canvas.paste(full, (pad, pad), full)
    canvas.save(os.path.join(PUBLIC, "logo.png"))
    print("logo.png", canvas.size)

    # Solo escudo: la mitad superior (aprox) donde vive el escudo, luego autocrop.
    shield = im.crop((0, 0, w, int(h * 0.60)))
    shield = autocrop(shield)
    # Cuadrar sobre lienzo transparente con pequeño padding.
    spad = int(max(shield.size) * 0.10)
    side = max(shield.size) + spad * 2
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(shield, ((side - shield.size[0]) // 2, (side - shield.size[1]) // 2), shield)
    sq.save(os.path.join(PUBLIC, "logo-mark.png"))
    print("logo-mark.png", sq.size)

    fav = sq.resize((64, 64), Image.LANCZOS)
    fav.save(os.path.join(PUBLIC, "favicon.png"))
    print("favicon.png", fav.size)


if __name__ == "__main__":
    main()
