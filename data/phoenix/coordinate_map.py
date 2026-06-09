#!/usr/bin/env python3
"""Map PHOENIX atlas spatial coordinates onto TCGA whole-slide images.

PHOENIX TCGA atlas cells (``tcga-atlas-nest-multi-cell-20x-discrete.h5ad``)
store integer ``obsm['spatial']`` coordinates in **20× microscope pixel
space**. TCGA diagnostic ``.svs`` files in this repo are read at **40×
(level 0)** via OpenSlide / ``slide.py`` (e.g. mpp ≈ 0.252 µm/px for
TCGA-56-5898).

Empirical alignment for TCGA-56-5898 shows two required fixes:

1. **Axis swap** — PHOENIX column 0 is *not* slide X. Map
   ``slide_x = phoenix_y``, ``slide_y = phoenix_x``.
2. **Magnification scale** — multiply both axes by ``2.0`` to convert
   20× PHOENIX pixels → 40× level-0 slide pixels.

No Y-flip is needed when rendering with PIL/matplotlib ``origin='upper'``
(OpenSlide uses a top-left origin matching the thumbnail from ``slide.py``).

Thumbnail mapping (``slide.py`` uses ``max(W,H) / max_dim`` downsample):

    thumb_x = slide_x / downsample
    thumb_y = slide_y / downsample
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PhoenixCoordinateMap:
    """Affine map from PHOENIX atlas coords to slide level-0 pixels."""

    # 20x PHOENIX grid → 40x OpenSlide level-0
    magnification_scale: float = 2.0
    swap_axes: bool = True
    offset_x: float = 0.0
    offset_y: float = 0.0
    flip_x: bool = False
    flip_y: bool = False

    def phoenix_to_slide_l0(self, x_phx: float, y_phx: float, slide_wh: tuple[int, int]) -> tuple[float, float]:
        slide_w, slide_h = slide_wh
        if self.swap_axes:
            sx, sy = y_phx, x_phx
        else:
            sx, sy = x_phx, y_phx
        sx = sx * self.magnification_scale + self.offset_x
        sy = sy * self.magnification_scale + self.offset_y
        if self.flip_x:
            sx = slide_w - sx
        if self.flip_y:
            sy = slide_h - sy
        return sx, sy

    def phoenix_to_thumbnail(
        self,
        x_phx: float,
        y_phx: float,
        slide_wh: tuple[int, int],
        thumb_wh: tuple[int, int],
    ) -> tuple[float, float]:
        slide_w, slide_h = slide_wh
        thumb_w, thumb_h = thumb_wh
        downsample = max(slide_w, slide_h) / max(thumb_w, thumb_h)
        sx, sy = self.phoenix_to_slide_l0(x_phx, y_phx, slide_wh)
        return sx / downsample, sy / downsample

    def as_dict(self) -> dict:
        return {
            "magnification_scale": self.magnification_scale,
            "swap_axes": self.swap_axes,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
            "notes": (
                "PHOENIX obsm spatial is 20x pixels with axes swapped vs OpenSlide "
                "level-0: slide_x=phoenix_y*2, slide_y=phoenix_x*2"
            ),
        }


# Validated on TCGA-56-5898 (TCGA-LUSC diagnostic slide).
DEFAULT_TCGA_MAP = PhoenixCoordinateMap()


def slide_dimensions(svs_path: str | Path) -> tuple[int, int]:
    import sys

    tcga_lung = Path(__file__).resolve().parents[1] / "tcga_lung"
    if str(tcga_lung) not in sys.path:
        sys.path.insert(0, str(tcga_lung))
    from slide import SlideReader

    with SlideReader(svs_path) as s:
        return s.dimensions
