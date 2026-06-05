#!/usr/bin/env python3
"""Download lung TCGA H&E (FFPE diagnostic) whole-slide images from a GDC manifest.

Two backends are supported:

1. ``gdc-client`` (preferred if installed) - the official GDC Data Transfer Tool,
   which handles parallel multipart transfers and resume natively.
2. A built-in direct-HTTP downloader (no extra install) that streams each slide
   from ``https://api.gdc.cancer.gov/data/<file_id>`` in parallel, resumes
   partial files, and verifies md5 checksums against the manifest.

All lung TCGA diagnostic slides are *open access*, so no token is required.

NOTE ON SIZE: the full lung set is ~1,053 slides totalling ~820 GB. Make sure
the target volume has room. Use ``--dry-run`` to preview, ``--limit N`` to grab
a small pilot subset first, and re-run any time to resume.

Usage:
    # Preview what would be downloaded
    python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --dry-run

    # Pilot: first 3 slides
    python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI --limit 3

    # Full download (auto-uses gdc-client if available)
    python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI

    # Force the built-in HTTP downloader with 8 parallel workers
    python download.py --manifest gdc_manifest.tcga_lung.txt --out-dir ./WSI \
        --backend http --workers 8
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

GDC_DATA_ENDPOINT = "https://api.gdc.cancer.gov/data"
CHUNK = 1024 * 1024  # 1 MiB streaming chunk


@dataclass
class Entry:
    file_id: str
    file_name: str
    md5: str
    size: int


def parse_manifest(path: Path) -> list[Entry]:
    """Parse a gdc-client manifest (TSV: id, filename, md5, size, state)."""
    entries: list[Entry] = []
    lines = path.read_text().splitlines()
    if not lines:
        return entries
    header = lines[0].lower().split("\t")
    try:
        i_id = header.index("id")
        i_name = header.index("filename")
        i_md5 = header.index("md5")
        i_size = header.index("size")
    except ValueError as err:  # pragma: no cover - malformed manifest
        raise SystemExit(f"Unexpected manifest header in {path}: {header}") from err
    for line in lines[1:]:
        if not line.strip():
            continue
        cols = line.split("\t")
        entries.append(
            Entry(
                file_id=cols[i_id],
                file_name=cols[i_name],
                md5=cols[i_md5],
                size=int(cols[i_size]),
            )
        )
    return entries


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def already_complete(dest: Path, entry: Entry, *, verify_md5: bool) -> bool:
    """True if ``dest`` exists, has the right size, and (optionally) md5."""
    if not dest.exists() or dest.stat().st_size != entry.size:
        return False
    if verify_md5:
        return md5_of(dest) == entry.md5
    return True


def human(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f} {unit}"
        f /= 1024
    return f"{f:.1f} TB"


# --------------------------------------------------------------------------- #
# Backend: official gdc-client                                                 #
# --------------------------------------------------------------------------- #
def download_with_gdc_client(manifest: Path, out_dir: Path, workers: int) -> int:
    cmd = [
        "gdc-client",
        "download",
        "-m",
        str(manifest),
        "-d",
        str(out_dir),
        "-n",
        str(workers),
        "--retry-amount",
        "5",
    ]
    print(f"Running: {' '.join(cmd)}")
    return subprocess.call(cmd)


# --------------------------------------------------------------------------- #
# Backend: built-in HTTP downloader (resume + md5 verify)                      #
# --------------------------------------------------------------------------- #
def _download_one(entry: Entry, out_dir: Path, verify_md5: bool, retries: int = 4) -> tuple[str, str]:
    """Download a single slide. Returns (file_name, status)."""
    # gdc-client lays files out as <out_dir>/<file_id>/<file_name>; mirror that
    # so the two backends are interchangeable.
    dest_dir = out_dir / entry.file_id
    dest = dest_dir / entry.file_name
    if already_complete(dest, entry, verify_md5=verify_md5):
        return entry.file_name, "skip (complete)"

    dest_dir.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    url = f"{GDC_DATA_ENDPOINT}/{entry.file_id}"

    for attempt in range(retries):
        try:
            resume_from = part.stat().st_size if part.exists() else 0
            headers = {}
            mode = "wb"
            if resume_from:
                headers["Range"] = f"bytes={resume_from}-"
                mode = "ab"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=300) as resp, part.open(mode) as fh:
                # If the server ignored our Range request, restart cleanly.
                if resume_from and resp.status == 200:
                    fh.close()
                    part.unlink(missing_ok=True)
                    fh = part.open("wb")
                while True:
                    block = resp.read(CHUNK)
                    if not block:
                        break
                    fh.write(block)

            if part.stat().st_size != entry.size:
                raise OSError(
                    f"size mismatch: got {part.stat().st_size}, want {entry.size}"
                )
            if verify_md5 and md5_of(part) != entry.md5:
                part.unlink(missing_ok=True)
                raise OSError("md5 mismatch")
            part.replace(dest)
            return entry.file_name, "ok"
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            wait = 4 * (2**attempt)
            if attempt == retries - 1:
                return entry.file_name, f"FAILED: {err}"
            time.sleep(wait)
    return entry.file_name, "FAILED: exhausted retries"


def download_with_http(
    entries: list[Entry], out_dir: Path, workers: int, verify_md5: bool
) -> int:
    total = len(entries)
    done = 0
    failures: list[str] = []
    print(f"Downloading {total} slides via built-in HTTP backend ({workers} workers)")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_download_one, e, out_dir, verify_md5): e for e in entries
        }
        for fut in concurrent.futures.as_completed(futures):
            name, status = fut.result()
            done += 1
            if status.startswith("FAILED"):
                failures.append(name)
            print(f"  [{done}/{total}] {name}: {status}")
    if failures:
        print(f"\n{len(failures)} slide(s) failed:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("\nAll slides downloaded successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="GDC manifest file")
    parser.add_argument("--out-dir", type=Path, default=Path("./WSI"), help="Output dir")
    parser.add_argument(
        "--backend",
        choices=["auto", "gdc-client", "http"],
        default="auto",
        help="auto (default): use gdc-client if installed, else built-in HTTP",
    )
    parser.add_argument("--workers", type=int, default=4, help="Parallel transfers")
    parser.add_argument("--limit", type=int, default=None, help="Only first N slides")
    parser.add_argument(
        "--no-verify-md5",
        action="store_true",
        help="Skip md5 verification (faster, http backend only)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview, do not download")
    args = parser.parse_args()

    if not args.manifest.exists():
        raise SystemExit(f"Manifest not found: {args.manifest}")

    entries = parse_manifest(args.manifest)
    if args.limit is not None:
        entries = entries[: args.limit]
    total_bytes = sum(e.size for e in entries)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Manifest : {args.manifest}")
    print(f"Slides   : {len(entries)}")
    print(f"Size     : {human(total_bytes)}")
    print(f"Out dir  : {args.out_dir.resolve()}")

    if args.dry_run:
        for e in entries[:10]:
            print(f"  would download {e.file_name} ({human(e.size)})")
        if len(entries) > 10:
            print(f"  ... and {len(entries) - 10} more")
        return 0

    has_gdc_client = shutil.which("gdc-client") is not None
    backend = args.backend
    if backend == "auto":
        backend = "gdc-client" if has_gdc_client else "http"
    if backend == "gdc-client" and not has_gdc_client:
        print("gdc-client not found; falling back to built-in HTTP backend.")
        backend = "http"

    print(f"Backend  : {backend}\n")

    if backend == "gdc-client":
        if args.limit is not None:
            # gdc-client needs a manifest file; write a trimmed temp manifest.
            tmp = args.manifest.with_suffix(".limit.txt")
            header = args.manifest.read_text().splitlines()[0]
            body = args.manifest.read_text().splitlines()[1 : args.limit + 1]
            tmp.write_text("\n".join([header, *body]) + "\n")
            rc = download_with_gdc_client(tmp, args.out_dir, args.workers)
            tmp.unlink(missing_ok=True)
            return rc
        return download_with_gdc_client(args.manifest, args.out_dir, args.workers)

    return download_with_http(
        entries, args.out_dir, args.workers, verify_md5=not args.no_verify_md5
    )


if __name__ == "__main__":
    raise SystemExit(main())
