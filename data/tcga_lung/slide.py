#!/usr/bin/env python3
"""Read, preview, and tile pathology whole-slide images (`.svs`, pyramidal TIFF).

This is the slide-IO layer for the pathology foundation-model dashboard. It
gives you a small, dependency-light reader over Aperio `.svs` slides plus the
operations the dashboard and feature-extraction pipeline need:

    * fast whole-slide thumbnails (from the lowest pyramid level),
    * windowed region reads at any pyramid level (no loading 8 GP into RAM),
    * H&E tissue detection (saturation-based, ignores ink/pen/background),
    * tissue-aware tile extraction for ML, and
    * a labelled "tissue overview" preview (thumbnail + sampled tile boxes).

Backends: prefers OpenSlide if installed (`openslide-python`), otherwise falls
back to `tifffile` + `zarr` (which is what works out of the box here). The two
backends share one API so callers don't care which is used.

CLI:
    python slide.py thumbnail SLIDE.svs                 -> SLIDE.thumbnail.png
    python slide.py crop SLIDE.svs                      -> auto tissue crop
    python slide.py crop SLIDE.svs --x 30000 --y 27000 --size 2048
    python slide.py overview SLIDE.svs                  -> thumbnail w/ tile boxes
    python slide.py tiles SLIDE.svs --out-dir tiles/    -> extract tissue tiles
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

try:  # optional, best backend if present
    import openslide  # type: ignore

    _HAS_OPENSLIDE = True
except Exception:  # pragma: no cover - openslide is optional
    _HAS_OPENSLIDE = False


def _require_pil():
    from PIL import Image  # local import keeps numpy-only callers light

    Image.MAX_IMAGE_PIXELS = None  # these are big on purpose
    return Image


# --------------------------------------------------------------------------- #
# Reader                                                                       #
# --------------------------------------------------------------------------- #
@dataclass
class TileSpec:
    """Coordinates of a tile in level-0 (full-resolution) pixel space."""

    x: int
    y: int
    size: int  # square edge length in level-0 pixels


class SlideReader:
    """Unified reader over a pyramidal `.svs` slide.

    Coordinates follow the OpenSlide convention: ``read_region`` takes an
    (x, y) **location in level-0 pixels** and a ``level`` to read from, plus a
    width/height **in that level's pixels**.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self._backend = "openslide" if _HAS_OPENSLIDE else "tifffile"
        if self._backend == "openslide":
            self._os = openslide.OpenSlide(str(self.path))
            self.level_dimensions = list(self._os.level_dimensions)  # [(W,H), ...]
            self.level_downsamples = [float(d) for d in self._os.level_downsamples]
        else:
            self._open_tifffile()

    # -- tifffile backend ---------------------------------------------------- #
    def _open_tifffile(self) -> None:
        import tifffile
        import zarr

        self._tf = tifffile.TiffFile(str(self.path))
        # The pyramidal image is the first series named "Baseline".
        series = self._tf.series[0]
        self._levels = series.levels
        # zarr handles per-level coords without decoding the whole image.
        self._zarr_levels = []
        for lvl in self._levels:
            z = zarr.open(lvl.aszarr(), mode="r")
            # tifffile may expose a single level as a group keyed "0".
            arr = z["0"] if hasattr(z, "keys") and "0" in z else z
            self._zarr_levels.append(arr)
        self.level_dimensions = [(lv.shape[1], lv.shape[0]) for lv in self._levels]
        w0 = self.level_dimensions[0][0]
        self.level_downsamples = [w0 / w for (w, _h) in self.level_dimensions]

    # -- common -------------------------------------------------------------- #
    @property
    def dimensions(self) -> tuple[int, int]:
        """(width, height) at level 0."""
        return self.level_dimensions[0]

    @property
    def level_count(self) -> int:
        return len(self.level_dimensions)

    @property
    def mpp(self) -> float | None:
        """Microns per pixel at level 0, if recorded in slide metadata."""
        try:
            if self._backend == "openslide":
                v = self._os.properties.get("openslide.mpp-x")
                return float(v) if v else None
            # Aperio stores "MPP=" in the ImageDescription of the first page.
            desc = self._tf.pages[0].description or ""
            for part in desc.replace("\n", "|").split("|"):
                if part.strip().startswith("MPP"):
                    return float(part.split("=")[1])
        except Exception:
            return None
        return None

    def best_level_for_downsample(self, downsample: float) -> int:
        diffs = [abs(d - downsample) for d in self.level_downsamples]
        # prefer the largest level whose downsample does not exceed target
        candidates = [i for i, d in enumerate(self.level_downsamples) if d <= downsample]
        return max(candidates) if candidates else int(np.argmin(diffs))

    def read_region(self, x: int, y: int, w: int, h: int, level: int = 0) -> np.ndarray:
        """Read a region. (x, y) are level-0 px; (w, h) are level-``level`` px."""
        if self._backend == "openslide":
            img = self._os.read_region((x, y), level, (w, h)).convert("RGB")
            return np.asarray(img)
        ds = self.level_downsamples[level]
        lx, ly = int(x / ds), int(y / ds)
        arr = self._zarr_levels[level]
        H, W = arr.shape[0], arr.shape[1]
        x1, y1 = min(lx + w, W), min(ly + h, H)
        region = np.asarray(arr[ly:y1, lx:x1])
        if region.ndim == 2:  # grayscale safety
            region = np.stack([region] * 3, axis=-1)
        return region[..., :3]

    def thumbnail(self, max_dim: int = 1024) -> np.ndarray:
        """RGB thumbnail with the longest edge <= ``max_dim``."""
        w0, h0 = self.dimensions
        downsample = max(w0, h0) / max_dim
        level = self.best_level_for_downsample(downsample)
        lw, lh = self.level_dimensions[level]
        full = self.read_region(0, 0, lw, lh, level=level)
        Image = _require_pil()
        img = Image.fromarray(full)
        img.thumbnail((max_dim, max_dim))
        return np.asarray(img)

    # -- tissue detection ---------------------------------------------------- #
    def tissue_mask(
        self, level: int | None = None, tint_thresh: float = 5.0
    ) -> tuple[np.ndarray, int]:
        """Boolean H&E tissue mask at a low level. Returns (mask, level).

        Tissue is detected by **stain tint** rather than raw darkness: H&E
        stain is purple/pink, so the green channel sits below the red/blue
        average (``(R + B) / 2 - G > 0``). This single rule:

          * keeps pale, hematoxylin-rich (lavender) tissue that has low
            saturation but a clear purple tint,
          * keeps strongly eosinophilic (pink) tissue,
          * rejects white glass background (excluded as near-white), and
          * rejects gray/black ink, pen marks and scanner smudges, whose
            channels are roughly equal so their tint is ~0.
        """
        if level is None:
            level = self.level_count - 1  # smallest level
        lw, lh = self.level_dimensions[level]
        img = self.read_region(0, 0, lw, lh, level=level).astype(np.float32)
        r, g, b = img[..., 0], img[..., 1], img[..., 2]
        brightness = img.mean(axis=2)
        tint = (r + b) / 2.0 - g
        near_white = brightness > 220
        mask = (~near_white) & (brightness > 40) & (tint > tint_thresh)
        return mask, level

    def find_tissue_regions(
        self, size: int = 2048, top_k: int = 1, stride_frac: float = 0.5
    ) -> list[TileSpec]:
        """Return the ``top_k`` most tissue-dense square windows (level-0 px)."""
        mask, level = self.tissue_mask()
        ds = self.level_downsamples[level]
        wl = max(1, int(size / ds))  # window edge in mask pixels
        m = mask.astype(np.float32)
        if m.shape[0] <= wl or m.shape[1] <= wl:
            # slide smaller than one tile; just return the center.
            w0, h0 = self.dimensions
            return [TileSpec((w0 - size) // 2, (h0 - size) // 2, size)]
        ii = np.pad(m, ((1, 0), (1, 0))).cumsum(0).cumsum(1)

        def win(yy: int, xx: int) -> float:
            return float(
                ii[yy + wl, xx + wl] - ii[yy, xx + wl] - ii[yy + wl, xx] + ii[yy, xx]
            )

        step = max(1, int(wl * stride_frac))
        scored: list[tuple[float, int, int]] = []
        for yy in range(0, m.shape[0] - wl, step):
            for xx in range(0, m.shape[1] - wl, step):
                scored.append((win(yy, xx), yy, xx))
        scored.sort(reverse=True)
        out: list[TileSpec] = []
        chosen: list[tuple[int, int]] = []
        for _s, yy, xx in scored:
            # simple non-max suppression so tiles don't all overlap
            if any(abs(yy - cy) < wl and abs(xx - cx) < wl for cy, cx in chosen):
                continue
            chosen.append((yy, xx))
            out.append(TileSpec(int(xx * ds), int(yy * ds), size))
            if len(out) >= top_k:
                break
        return out or [TileSpec(0, 0, size)]

    def iter_tissue_tiles(
        self, size: int = 256, level: int = 0, tissue_frac: float = 0.35
    ) -> Iterator[TileSpec]:
        """Yield tiles (level-0 px) on a grid that contain >= ``tissue_frac`` tissue."""
        mask, mlevel = self.tissue_mask()
        ds_mask = self.level_downsamples[mlevel]
        ds_level = self.level_downsamples[level]
        step0 = size * ds_level  # tile step in level-0 px
        wl = max(1, int(step0 / ds_mask))  # tile footprint in mask px
        w0, h0 = self.dimensions
        ny = int(h0 // step0)
        nx = int(w0 // step0)
        for j in range(ny):
            for i in range(nx):
                my, mx = int(j * wl), int(i * wl)
                patch = mask[my : my + wl, mx : mx + wl]
                if patch.size and patch.mean() >= tissue_frac:
                    yield TileSpec(int(i * step0), int(j * step0), int(step0))

    def close(self) -> None:
        if self._backend == "openslide":
            self._os.close()
        else:
            self._tf.close()

    def __enter__(self) -> "SlideReader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# High-level helpers (used by CLI + dashboard)                                 #
# --------------------------------------------------------------------------- #
def save_thumbnail(slide_path: str | Path, out: str | Path, max_dim: int = 1536) -> Path:
    Image = _require_pil()
    with SlideReader(slide_path) as s:
        arr = s.thumbnail(max_dim=max_dim)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(out)
    return out


def save_crop(
    slide_path: str | Path,
    out: str | Path,
    x: int | None = None,
    y: int | None = None,
    size: int = 2048,
    level: int = 0,
) -> Path:
    Image = _require_pil()
    with SlideReader(slide_path) as s:
        if x is None or y is None:
            spec = s.find_tissue_regions(size=size, top_k=1)[0]
            x, y = spec.x, spec.y
        arr = s.read_region(x, y, size, size, level=level)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(out)
    return out


def save_overview(
    slide_path: str | Path, out: str | Path, n_boxes: int = 6, tile_size: int = 2048
) -> Path:
    """Thumbnail with the top tissue tiles drawn as boxes (sanity-check view)."""
    Image = _require_pil()
    from PIL import ImageDraw

    with SlideReader(slide_path) as s:
        max_dim = 1536
        thumb = s.thumbnail(max_dim=max_dim)
        w0, h0 = s.dimensions
        scale = max(thumb.shape[1] / w0, thumb.shape[0] / h0)
        specs = s.find_tissue_regions(size=tile_size, top_k=n_boxes)
    img = Image.fromarray(thumb).convert("RGB")
    draw = ImageDraw.Draw(img)
    for k, sp in enumerate(specs, 1):
        x0, y0 = sp.x * scale, sp.y * scale
        x1, y1 = (sp.x + sp.size) * scale, (sp.y + sp.size) * scale
        draw.rectangle([x0, y0, x1, y1], outline=(0, 180, 0), width=3)
        draw.text((x0 + 4, y0 + 2), str(k), fill=(0, 120, 0))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def extract_tiles(
    slide_path: str | Path,
    out_dir: str | Path,
    size: int = 256,
    level: int = 0,
    tissue_frac: float = 0.35,
    limit: int | None = None,
) -> int:
    """Write tissue tiles as PNGs named ``<x>_<y>.png`` (level-0 coords)."""
    Image = _require_pil()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    with SlideReader(slide_path) as s:
        for spec in s.iter_tissue_tiles(size=size, level=level, tissue_frac=tissue_frac):
            arr = s.read_region(spec.x, spec.y, size, size, level=level)
            Image.fromarray(arr).save(out_dir / f"{spec.x}_{spec.y}.png")
            n += 1
            if limit is not None and n >= limit:
                break
    return n


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def _default_out(slide: Path, suffix: str) -> Path:
    return slide.with_suffix("").with_suffix(f".{suffix}.png")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("thumbnail", help="save a whole-slide thumbnail PNG")
    pt.add_argument("slide", type=Path)
    pt.add_argument("--out", type=Path)
    pt.add_argument("--max-dim", type=int, default=1536)

    pc = sub.add_parser("crop", help="save a high-mag crop (auto tissue or coords)")
    pc.add_argument("slide", type=Path)
    pc.add_argument("--out", type=Path)
    pc.add_argument("--x", type=int)
    pc.add_argument("--y", type=int)
    pc.add_argument("--size", type=int, default=2048)
    pc.add_argument("--level", type=int, default=0)

    po = sub.add_parser("overview", help="thumbnail annotated with tissue tile boxes")
    po.add_argument("slide", type=Path)
    po.add_argument("--out", type=Path)
    po.add_argument("--n-boxes", type=int, default=6)
    po.add_argument("--tile-size", type=int, default=2048)

    px = sub.add_parser("tiles", help="extract tissue tiles for ML")
    px.add_argument("slide", type=Path)
    px.add_argument("--out-dir", type=Path, required=True)
    px.add_argument("--size", type=int, default=256)
    px.add_argument("--level", type=int, default=0)
    px.add_argument("--tissue-frac", type=float, default=0.35)
    px.add_argument("--limit", type=int)

    pi = sub.add_parser("info", help="print slide dimensions / levels / mpp")
    pi.add_argument("slide", type=Path)

    args = p.parse_args()

    if args.cmd == "thumbnail":
        out = save_thumbnail(args.slide, args.out or _default_out(args.slide, "thumbnail"), args.max_dim)
        print(f"wrote {out}")
    elif args.cmd == "crop":
        out = save_crop(args.slide, args.out or _default_out(args.slide, "crop"), args.x, args.y, args.size, args.level)
        print(f"wrote {out}")
    elif args.cmd == "overview":
        out = save_overview(args.slide, args.out or _default_out(args.slide, "overview"), args.n_boxes, args.tile_size)
        print(f"wrote {out}")
    elif args.cmd == "tiles":
        n = extract_tiles(args.slide, args.out_dir, args.size, args.level, args.tissue_frac, args.limit)
        print(f"wrote {n} tiles to {args.out_dir}")
    elif args.cmd == "info":
        with SlideReader(args.slide) as s:
            print(f"path        : {s.path}")
            print(f"backend     : {s._backend}")
            print(f"dimensions  : {s.dimensions[0]} x {s.dimensions[1]} (W x H)")
            gp = s.dimensions[0] * s.dimensions[1] / 1e9
            print(f"gigapixels  : {gp:.2f}")
            print(f"levels      : {s.level_count}")
            for i, (dim, ds) in enumerate(zip(s.level_dimensions, s.level_downsamples)):
                print(f"  level[{i}] {dim[0]:>7} x {dim[1]:<7}  downsample {ds:.1f}x")
            mpp = s.mpp
            print(f"mpp (level0): {mpp:.4f} um/px" if mpp else "mpp (level0): unknown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
