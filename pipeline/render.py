"""Hillshade rendering for target and Earth patches at an identical scale."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from features import fill_gaps, hillshade

OUT_PX = 256


def hillshade_image(z: np.ndarray, res: float, out_px: int = OUT_PX, scale_bar_m: float = 1000.0,
                    stretch: bool = True) -> Image.Image:
    """Greyscale hillshade (azimuth 315, altitude 45, no exaggeration) with a scale bar.

    With ``stretch`` the shading is linearly contrast-stretched between its 1st
    and 99th percentiles for display. Geometry and features are unaffected; a
    uniformly steep slope facing the light would otherwise render near-white.

    The patch is shaded at its native resolution and enlarged with bilinear
    interpolation, so every image of a ``patch_px`` window covers the same
    ground distance and the scale bar has the same length in every image.
    """
    shade = hillshade(fill_gaps(z), res)
    if stretch:
        lo, hi = np.percentile(shade, [1, 99])
        if hi - lo > 1e-6:
            shade = np.clip((shade - lo) / (hi - lo), 0.0, 1.0)
    img = Image.fromarray(np.uint8(np.round(shade * 255)), mode="L").resize((out_px, out_px), Image.BILINEAR)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    metres_per_px = res * z.shape[1] / out_px
    bar_px = int(round(scale_bar_m / metres_per_px))
    x0, y0 = 10, out_px - 14
    draw.rectangle([x0 - 4, y0 - 16, x0 + bar_px + 6, y0 + 7], fill=(255, 255, 255))
    draw.rectangle([x0, y0, x0 + bar_px, y0 + 3], fill=(20, 20, 20))
    try:
        font = ImageFont.load_default(size=12)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    label = f"{scale_bar_m / 1000:.0f} km" if scale_bar_m >= 1000 else f"{scale_bar_m:.0f} m"
    draw.text((x0, y0 - 15), label, fill=(20, 20, 20), font=font)
    return img


def save_hillshade(z: np.ndarray, res: float, path: Path, stretch: bool = True) -> None:
    """Render and save an optimised PNG."""
    path.parent.mkdir(parents=True, exist_ok=True)
    hillshade_image(z, res, stretch=stretch).save(path, optimize=True)
