#!/usr/bin/env python3
"""
image_to_ascii.py
-----------------
Converte uma foto (assets/profile.png) em arte ASCII com um numero fixo de
linhas, compensando o fato de que um caractere de fonte monoespacada e mais
alto do que largo (razao ~2.27 no layout do SVG: 20px de entrelinha / 8.8px
de avanco horizontal).

Uso:
    python image_to_ascii.py                 # usa os valores de config.yaml
    python image_to_ascii.py --rows 25 --gamma 1.1 --preview
"""

import argparse
import os

from PIL import Image, ImageEnhance, ImageOps

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))

# Rampa do mais claro (espaco) para o mais escuro (@).
# A ordem importa: indice 0 = pixel mais claro.
RAMPS = {
    # rampa curta: menos ruido, silhueta mais legivel (padrao)
    "mid": " .:-=+*oO#%@",
    # rampa longa: mais niveis de cinza, visual mais "sujo"
    "long": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@",
    "blocks": " .:*#@",
}
RAMP = RAMPS["mid"]


def load_config():
    path = os.path.join(HERE, "config.yaml")
    if yaml is None or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def autocrop_subject(img, bg_tolerance=12):
    """Remove a moldura de fundo uniforme ao redor do retrato."""
    gray = img.convert("L")
    bg = gray.getpixel((0, 0))
    mask = gray.point(lambda p: 255 if abs(p - bg) > bg_tolerance else 0)
    box = mask.getbbox()
    return img.crop(box) if box else img


def fit_aspect(img, target_ratio):
    """Recorta ao centro (horizontal) / ao topo (vertical) para chegar
    na razao largura/altura desejada, sem distorcer o rosto."""
    w, h = img.size
    current = w / h
    if current > target_ratio:  # largo demais -> corta as laterais
        new_w = int(round(h * target_ratio))
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    elif current < target_ratio:  # alto demais -> corta por baixo
        new_h = int(round(w / target_ratio))
        img = img.crop((0, 0, w, new_h))
    return img


def to_ascii(
    image_path,
    rows=25,
    aspect=0.85,
    char_aspect=20 / 8.8,
    gamma=1.0,
    contrast=1.35,
    white_cut=0.93,
    invert=False,
    crop=True,
    keep_bottom=1.0,
    ramp=None,
):
    img = Image.open(image_path)
    if img.mode in ("RGBA", "LA", "P"):
        flat = Image.new("RGB", img.size, (255, 255, 255))
        img = img.convert("RGBA")
        flat.paste(img, mask=img.split()[-1])
        img = flat
    else:
        img = img.convert("RGB")

    if crop:
        img = autocrop_subject(img)
    if keep_bottom < 1.0:  # descarta parte do busto/roupa
        w, h = img.size
        img = img.crop((0, 0, w, int(round(h * keep_bottom))))
    img = fit_aspect(img, aspect)

    cols = int(round(rows * char_aspect * aspect))

    gray = ImageOps.autocontrast(img.convert("L"), cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(contrast)
    small = gray.resize((cols, rows), Image.LANCZOS)

    chars = RAMPS.get(ramp, RAMP) if isinstance(ramp, str) else (ramp or RAMP)
    n = len(chars) - 1
    lines = []
    for y in range(rows):
        line = []
        for x in range(cols):
            v = small.getpixel((x, y)) / 255.0
            if invert:
                v = 1.0 - v
            if v >= white_cut:          # fundo -> espaco
                line.append(" ")
                continue
            v = pow(v / white_cut, gamma)
            line.append(chars[min(n, int(round((1.0 - v) * n)))])
        lines.append("".join(line).rstrip())
    return lines, cols


def main():
    cfg = load_config()
    art_cfg = (cfg.get("ascii") or {})
    p = argparse.ArgumentParser()
    p.add_argument("--image", default=os.path.join(HERE, art_cfg.get("image", "assets/profile.png")))
    p.add_argument("--out", default=os.path.join(HERE, "ascii_art.txt"))
    p.add_argument("--rows", type=int, default=art_cfg.get("rows", 25))
    p.add_argument("--aspect", type=float, default=art_cfg.get("aspect", 0.85))
    p.add_argument("--gamma", type=float, default=art_cfg.get("gamma", 1.0))
    p.add_argument("--contrast", type=float, default=art_cfg.get("contrast", 1.35))
    p.add_argument("--white-cut", type=float, default=art_cfg.get("white_cut", 0.93))
    p.add_argument("--ramp", default=art_cfg.get("ramp", "mid"))
    p.add_argument("--keep-bottom", type=float, default=art_cfg.get("keep_bottom", 1.0))
    p.add_argument("--no-crop", action="store_true")
    p.add_argument("--invert", action="store_true")
    a = p.parse_args()

    lines, cols = to_ascii(
        a.image, rows=a.rows, aspect=a.aspect, gamma=a.gamma,
        contrast=a.contrast, white_cut=a.white_cut,
        invert=a.invert, crop=not a.no_crop, keep_bottom=a.keep_bottom, ramp=a.ramp,
    )
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"{a.out}: {len(lines)} linhas x {cols} colunas")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
