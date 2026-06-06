#!/usr/bin/env python3
"""Convert Aperio .svs whole-slide images to compressed multi-level Zarr stores.

Writes one directory per slide named like the user's convention:
  TCGA-44-2661-01Z-00-DX1.<uuid>.zarr/

Each store contains pyramid levels ``0``, ``1``, ... as uint8 HWC arrays with
512x512 chunks and ZSTD compression for lazy, memory-efficient loading.

Usage:
    python svs_to_zarr.py WSI/<file_id>/*.svs --out-dir ./zarr
    python svs_to_zarr.py --slides TCGA-44-2661 TCGA-55-7815 --wsi-dir ./WSI --out-dir ./zarr
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import zarr
from zarr.codecs import BloscCodec, BloscShuffle

from slide import SlideReader

DEFAULT_SLIDES = [
    "TCGA-44-2661-01Z-00-DX1.20cfa0f8-e3ca-4c26-9dfe-b9d416cd94b1",
    "TCGA-55-7815-01Z-00-DX1.288408e6-f6b3-4de4-a1ce-cb2498d9d46d",
    "TCGA-86-7701-01Z-00-DX1.a8a6e71e-9fa9-42c6-a186-0ac7526e9960",
]

COMPRESSOR = BloscCodec(cname="zstd", clevel=3, shuffle=BloscShuffle.shuffle)


def zarr_name_for_svs(svs_path: Path) -> str:
    """TCGA-...-DX1.<uuid>.svs -> TCGA-...-DX1.<uuid>.zarr"""
    stem = svs_path.name
    if stem.endswith(".svs"):
        stem = stem[: -len(".svs")]
    return f"{stem}.zarr"


def levels_for_mode(slide: SlideReader, *, light: bool, min_downsample: float | None) -> list[int]:
    """Choose pyramid levels to store.

    ``light`` (default for pilot slides) skips native level 0 (~40x) and keeps
    downsampled levels only — much smaller on disk while still lazy-loadable for
    10–20x-style viewing and tiling.
    """
    if min_downsample is not None:
        return [i for i, ds in enumerate(slide.level_downsamples) if ds >= min_downsample]
    if light:
        return [i for i, ds in enumerate(slide.level_downsamples) if ds >= 4.0]
    return list(range(slide.level_count))


def convert_svs_to_zarr(
    svs_path: Path,
    out_dir: Path,
    *,
    chunk_size: int = 512,
    tile_size: int = 2048,
    levels: list[int] | None = None,
    light: bool = True,
    min_downsample: float | None = None,
    force: bool = False,
) -> Path:
    """Write a compressed pyramid Zarr store for one slide."""
    out_dir.mkdir(parents=True, exist_ok=True)
    zarr_path = out_dir / zarr_name_for_svs(svs_path)
    if zarr_path.exists():
        if not force:
            raise FileExistsError(f"Refusing to overwrite existing store: {zarr_path} (use --force)")
        shutil.rmtree(zarr_path)

    t0 = time.time()
    with SlideReader(svs_path) as slide:
        native_levels = (
            levels
            if levels is not None
            else levels_for_mode(slide, light=light, min_downsample=min_downsample)
        )
        if not native_levels:
            raise ValueError(f"No pyramid levels selected for {svs_path}")

        store = zarr.storage.LocalStore(str(zarr_path))
        root = zarr.open_group(store=store, mode="w")
        stored_dims = [list(slide.level_dimensions[i]) for i in native_levels]
        stored_ds = [slide.level_downsamples[i] for i in native_levels]
        root.attrs.update(
            {
                "format": "light-zarr-v1",
                "source_file": svs_path.name,
                "backend": slide._backend,
                "dimensions_l0": list(slide.dimensions),
                "native_level_indices": native_levels,
                "level_dimensions": stored_dims,
                "level_downsamples": stored_ds,
                "mpp_l0": slide.mpp,
                "mpp_by_level": [
                    slide.mpp * ds if slide.mpp else None for ds in stored_ds
                ],
                "light": light,
            }
        )

        for out_level, level_idx in enumerate(native_levels):
            lw, lh = slide.level_dimensions[level_idx]
            ds = slide.level_downsamples[level_idx]
            arr = root.create_array(
                str(out_level),
                shape=(lh, lw, 3),
                chunks=(chunk_size, chunk_size, 3),
                dtype="uint8",
                compressors=[COMPRESSOR],
            )
            n_tiles = ((lh + tile_size - 1) // tile_size) * ((lw + tile_size - 1) // tile_size)
            done = 0
            for ly in range(0, lh, tile_size):
                th = min(tile_size, lh - ly)
                for lx in range(0, lw, tile_size):
                    tw = min(tile_size, lw - lx)
                    x0, y0 = int(lx * ds), int(ly * ds)
                    tile = slide.read_region(x0, y0, tw, th, level=level_idx)
                    if tile.shape[0] != th or tile.shape[1] != tw:
                        padded = np.zeros((th, tw, 3), dtype=np.uint8)
                        padded[: tile.shape[0], : tile.shape[1], :] = tile
                        tile = padded
                    arr[ly : ly + th, lx : lx + tw, :] = tile
                    done += 1
                    if done % 25 == 0 or done == n_tiles:
                        pct = 100.0 * done / n_tiles
                        print(
                            f"  level {level_idx}: {done}/{n_tiles} tiles ({pct:.0f}%)",
                            flush=True,
                        )

    elapsed = time.time() - t0
    print(f"wrote {zarr_path} in {elapsed / 60:.1f} min", flush=True)
    return zarr_path


def find_svs_for_prefix(wsi_dir: Path, prefix: str) -> Path:
    """Match TCGA-44-2661 or full barcode stem under WSI/<file_id>/*.svs."""
    matches: list[Path] = []
    for path in wsi_dir.rglob("*.svs"):
        name = path.name
        if name.startswith(prefix) or prefix in name:
            matches.append(path)
    if not matches:
        raise FileNotFoundError(f"No .svs under {wsi_dir} matching {prefix!r}")
    if len(matches) > 1:
        matches.sort(key=lambda p: len(p.name))
    return matches[0]


def load_slide_stems(metadata_path: Path) -> dict[str, str]:
    rows = json.loads(metadata_path.read_text())
    return {row["file_name"].replace(".svs", ""): row["file_id"] for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("svs", nargs="*", type=Path, help="one or more .svs paths")
    parser.add_argument("--slides", nargs="*", help="TCGA barcode prefixes to resolve under --wsi-dir")
    parser.add_argument("--wsi-dir", type=Path, default=Path("WSI"), help="downloaded slides root")
    parser.add_argument("--out-dir", type=Path, default=Path("zarr"), help="output directory for .zarr stores")
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--tile-size", type=int, default=2048)
    parser.add_argument(
        "--full-res",
        action="store_true",
        help="include native level 0 (large; default is light mode skipping 40x)",
    )
    parser.add_argument(
        "--min-downsample",
        type=float,
        default=None,
        help="only store levels with downsample >= this (overrides --full-res)",
    )
    parser.add_argument("--default-three", action="store_true", help="convert the three requested LUAD slides")
    parser.add_argument("--force", action="store_true", help="overwrite existing .zarr directories")
    args = parser.parse_args()

    targets: list[Path] = list(args.svs)
    prefixes = list(args.slides or [])
    if args.default_three:
        prefixes.extend(stem.split(".")[0] for stem in DEFAULT_SLIDES)
    for prefix in prefixes:
        targets.append(find_svs_for_prefix(args.wsi_dir, prefix))

    # dedupe while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in targets:
        if not isinstance(path, Path):
            continue
        try:
            resolved = path.resolve()
        except FileNotFoundError:
            continue
        if resolved not in seen and resolved.is_file():
            seen.add(resolved)
            unique.append(resolved)

    if not unique:
        print("No input slides found.", file=sys.stderr)
        return 2

    print(f"Converting {len(unique)} slide(s) -> {args.out_dir.resolve()}")
    for svs in unique:
        print(f"\n=== {svs.name} ===")
        convert_svs_to_zarr(
            svs,
            args.out_dir,
            chunk_size=args.chunk_size,
            tile_size=args.tile_size,
            light=not args.full_res,
            min_downsample=args.min_downsample,
            force=args.force,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
