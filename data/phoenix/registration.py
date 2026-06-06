#!/usr/bin/env python3
"""PHOENIX spatial coordinate registration onto H&E thumbnails.

Pipeline (adapted from contour ICP + optical-flow warping):

1. Apply the global PHOENIX → slide affine (axis swap + 20×→40× scale).
2. Rasterize cell density in thumbnail space.
3. Compare against inverted H&E tissue intensity inside the tissue mask.
4. Estimate a dense displacement field with Farneback optical flow.
5. Smooth and sample displacements back onto each cell coordinate.

For TCGA slides there is typically one tissue section (no multi-region
``mouse_id`` matching required).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.ndimage import binary_dilation, binary_fill_holes, gaussian_filter, label as ndi_label
from scipy.spatial import KDTree

from coordinate_map import DEFAULT_TCGA_MAP, PhoenixCoordinateMap, slide_dimensions


@dataclass
class RegistrationResult:
    case_id: str
    affine_thumb: np.ndarray  # 2x3, identity if no extra affine
    flow_field: np.ndarray | None  # HxWx2 in thumbnail px, crop-local
    flow_crop_origin: tuple[int, int]
    coords_phoenix: np.ndarray
    coords_thumb_affine: np.ndarray
    coords_thumb_warped: np.ndarray
    coords_slide_l0: np.ndarray
    metrics: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "affine_thumb": self.affine_thumb.tolist(),
            "flow_crop_origin": list(self.flow_crop_origin),
            "flow_shape": list(self.flow_field.shape) if self.flow_field is not None else None,
            "metrics": self.metrics,
            "coordinate_map": DEFAULT_TCGA_MAP.as_dict(),
        }


def mask_he(img_rgb: np.ndarray, sat_thresh: int = 15, val_thresh: int = 220) -> np.ndarray:
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    mask = (hsv[:, :, 1] > sat_thresh) | (hsv[:, :, 2] < val_thresh)
    mask = binary_fill_holes(mask)
    mask = binary_dilation(mask, iterations=3)
    return mask.astype(np.uint8)


def extract_sections(mask: np.ndarray, min_area_fraction: float = 0.01) -> list[dict]:
    labeled, n_components = ndi_label(mask)
    total_area = max(int(mask.sum()), 1)
    sections: list[dict] = []
    for i in range(1, n_components + 1):
        comp = labeled == i
        area = int(comp.sum())
        if area < total_area * min_area_fraction:
            continue
        ys, xs = np.where(comp)
        sections.append(
            {
                "mask": comp,
                "bbox": (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
                "centroid": (float(xs.mean()), float(ys.mean())),
                "area": area,
            }
        )
    return sections


def extract_contour(mask: np.ndarray, n_points: int = 500) -> np.ndarray | None:
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    pts = largest.reshape(-1, 2).astype(np.float64)
    if len(pts) > n_points:
        idx = np.linspace(0, len(pts) - 1, n_points).astype(int)
        pts = pts[idx]
    return pts


def transform_coordinates(coords: np.ndarray, affine_23: np.ndarray) -> np.ndarray:
    ones = np.ones((len(coords), 1))
    return (affine_23 @ np.hstack([coords, ones]).T).T


def estimate_affine_icp(
    source_pts: np.ndarray, target_pts: np.ndarray, max_iterations: int = 80, tolerance: float = 1e-6
) -> tuple[np.ndarray, float]:
    src = source_pts.copy()
    m_total = np.eye(3)
    last_error = float("inf")
    for _ in range(max_iterations):
        tree = KDTree(target_pts)
        dists, indices = tree.query(src)
        matched = target_pts[indices]
        src_c = src - src.mean(axis=0)
        tgt_c = matched - matched.mean(axis=0)
        h = src_c.T @ tgt_c
        u, _s, vt = np.linalg.svd(h)
        r = vt.T @ u.T
        if np.linalg.det(r) < 0:
            vt[-1, :] *= -1
            r = vt.T @ u.T
        denom = np.trace(src_c.T @ src_c)
        scale = float(np.trace(r @ h) / denom) if denom > 0 else 1.0
        t = matched.mean(axis=0) - scale * r @ src.mean(axis=0)
        m_step = np.eye(3)
        m_step[:2, :2] = scale * r
        m_step[:2, 2] = t
        src_h = np.column_stack([src, np.ones(len(src))])
        src = (m_step @ src_h.T).T[:, :2]
        m_total = m_step @ m_total
        last_error = float(dists.mean())
        if last_error < tolerance:
            break
    return m_total[:2, :3], last_error


def search_orientation_affine(
    source_contour: np.ndarray, target_contour: np.ndarray
) -> tuple[np.ndarray, float]:
    src_centered = source_contour - source_contour.mean(axis=0)
    best_m: np.ndarray | None = None
    best_error = float("inf")
    for angle_deg in (0, 90, 180, 270):
        rad = np.deg2rad(angle_deg)
        r_init = np.array([[np.cos(rad), -np.sin(rad)], [np.sin(rad), np.cos(rad)]])
        for flip in (False, True):
            trial = (r_init @ src_centered.T).T
            if flip:
                trial[:, 0] *= -1
            trial += target_contour.mean(axis=0)
            m_icp, error = estimate_affine_icp(trial, target_contour)
            if error < best_error:
                best_error = error
                m_pre = np.eye(3)
                m_pre[:2, :2] = r_init
                if flip:
                    m_pre[0, :2] *= -1
                m_pre[:2, 2] = target_contour.mean(axis=0) - m_pre[:2, :2] @ source_contour.mean(axis=0)
                m_icp_33 = np.vstack([m_icp, [0, 0, 1]])
                m_pre_33 = np.vstack([m_pre[:2, :3], [0, 0, 1]])
                best_m = (m_icp_33 @ m_pre_33)[:2, :3]
    if best_m is None:
        return np.array([[1, 0, 0], [0, 1, 0]], dtype=float), float("inf")
    return best_m, best_error


def phoenix_to_thumb(
    coords_phx: np.ndarray,
    slide_wh: tuple[int, int],
    thumb_wh: tuple[int, int],
    coord_map: PhoenixCoordinateMap = DEFAULT_TCGA_MAP,
    affine_thumb: np.ndarray | None = None,
) -> np.ndarray:
    thumb_w, thumb_h = thumb_wh
    out = np.empty_like(coords_phx, dtype=float)
    for i, (xp, yp) in enumerate(coords_phx):
        out[i] = coord_map.phoenix_to_thumbnail(float(xp), float(yp), slide_wh, (thumb_w, thumb_h))
    if affine_thumb is not None and not np.allclose(affine_thumb, np.array([[1, 0, 0], [0, 1, 0]])):
        out = transform_coordinates(out, affine_thumb)
    return out


def rasterize_density(coords_thumb: np.ndarray, shape: tuple[int, int], sigma: float = 5.0) -> np.ndarray:
    h, w = shape
    img = np.zeros((h, w), dtype=np.float32)
    xi = np.clip(coords_thumb[:, 0].astype(int), 0, w - 1)
    yi = np.clip(coords_thumb[:, 1].astype(int), 0, h - 1)
    np.add.at(img, (yi, xi), 1.0)
    return gaussian_filter(img, sigma=sigma)


def normalize_uint8(img: np.ndarray) -> np.ndarray:
    mx = float(img.max())
    if mx <= 0:
        return np.zeros_like(img, dtype=np.uint8)
    return (img / mx * 255.0).astype(np.uint8)


def compute_optical_flow(
    source_u8: np.ndarray,
    target_u8: np.ndarray,
    *,
    winsize: int = 41,
    flow_blur: int = 51,
) -> np.ndarray:
    src = cv2.GaussianBlur(source_u8, (21, 21), 0)
    tgt = cv2.GaussianBlur(target_u8, (21, 21), 0)
    flow = cv2.calcOpticalFlowFarneback(
        src,
        tgt,
        None,
        pyr_scale=0.5,
        levels=5,
        winsize=winsize,
        iterations=10,
        poly_n=7,
        poly_sigma=1.5,
        flags=0,
    )
    k = flow_blur if flow_blur % 2 == 1 else flow_blur + 1
    return np.stack(
        [cv2.GaussianBlur(flow[:, :, 0], (k, k), 0), cv2.GaussianBlur(flow[:, :, 1], (k, k), 0)],
        axis=2,
    )


def apply_flow_field(
    coords_thumb: np.ndarray,
    flow: np.ndarray,
    crop_origin: tuple[int, int],
) -> np.ndarray:
    cx0, cy0 = crop_origin
    h, w = flow.shape[:2]
    gy = np.arange(h)
    gx = np.arange(w)
    interp_dx = RegularGridInterpolator((gy, gx), flow[:, :, 0], bounds_error=False, fill_value=0.0)
    interp_dy = RegularGridInterpolator((gy, gx), flow[:, :, 1], bounds_error=False, fill_value=0.0)
    local_x = coords_thumb[:, 0] - cx0
    local_y = coords_thumb[:, 1] - cy0
    pts = np.column_stack([local_y, local_x])
    warped = coords_thumb.copy()
    warped[:, 0] += interp_dx(pts)
    warped[:, 1] += interp_dy(pts)
    return warped


def tissue_overlap_score(coords_thumb: np.ndarray, tissue_mask: np.ndarray) -> float:
    h, w = tissue_mask.shape
    xi = np.clip(np.round(coords_thumb[:, 0]).astype(int), 0, w - 1)
    yi = np.clip(np.round(coords_thumb[:, 1]).astype(int), 0, h - 1)
    return float(tissue_mask[yi, xi].mean())


def register_phoenix_cells(
    coords_phx: np.ndarray,
    he_thumb_rgb: np.ndarray,
    slide_wh: tuple[int, int],
    *,
    case_id: str = "unknown",
    coord_map: PhoenixCoordinateMap = DEFAULT_TCGA_MAP,
    use_contour_icp: bool = True,
    use_optical_flow: bool = True,
    pad: int = 20,
) -> RegistrationResult:
    thumb_h, thumb_w = he_thumb_rgb.shape[:2]
    thumb_wh = (thumb_w, thumb_h)
    he_mask = mask_he(he_thumb_rgb)
    sections = extract_sections(he_mask)
    if not sections:
        raise RuntimeError("No tissue sections found in H&E thumbnail")
    section = max(sections, key=lambda s: s["area"])
    bbox = section["bbox"]

    coords_affine = phoenix_to_thumb(coords_phx, slide_wh, thumb_wh, coord_map)
    affine_thumb = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    icp_error = 0.0

    if use_contour_icp:
        density = rasterize_density(coords_affine, (thumb_h, thumb_w), sigma=8.0)
        cell_mask = (density > density.max() * 0.05).astype(np.uint8)
        cell_mask = binary_dilation(cell_mask, iterations=2).astype(np.uint8)
        src_contour = extract_contour(cell_mask)
        tgt_contour = extract_contour(section["mask"].astype(np.uint8))
        if src_contour is not None and tgt_contour is not None:
            m_refine, icp_error = search_orientation_affine(src_contour, tgt_contour)
            # Only accept ICP if it improves tissue overlap
            before = tissue_overlap_score(coords_affine, he_mask)
            trial = transform_coordinates(coords_affine, m_refine)
            after = tissue_overlap_score(trial, he_mask)
            if after >= before - 0.02:
                affine_thumb = m_refine @ np.vstack([affine_thumb, [0, 0, 1]])
                affine_thumb = affine_thumb[:2, :3]
                coords_affine = trial

    flow_field = None
    crop_origin = (0, 0)
    coords_warped = coords_affine.copy()

    if use_optical_flow:
        cx0 = max(0, bbox[0] - pad)
        cy0 = max(0, bbox[1] - pad)
        cx1 = min(thumb_w, bbox[2] + pad)
        cy1 = min(thumb_h, bbox[3] + pad)
        crop_origin = (cx0, cy0)

        density = rasterize_density(coords_affine, (thumb_h, thumb_w), sigma=5.0)
        xen_crop = density[cy0:cy1, cx0:cx1]
        he_gray = he_thumb_rgb[cy0:cy1, cx0:cx1].astype(np.float32).mean(axis=2)
        he_inv = 255.0 - he_gray

        xen_u8 = normalize_uint8(xen_crop)
        he_u8 = normalize_uint8(he_inv)
        if xen_u8.shape != he_u8.shape:
            he_u8 = cv2.resize(he_u8, (xen_u8.shape[1], xen_u8.shape[0]), interpolation=cv2.INTER_LINEAR)

        flow_field = compute_optical_flow(xen_u8, he_u8)
        coords_warped = apply_flow_field(coords_affine, flow_field, crop_origin)

    downsample = max(slide_wh) / max(thumb_wh)
    coords_slide = coords_warped * downsample

    metrics = {
        "tissue_overlap_affine": tissue_overlap_score(coords_affine, he_mask),
        "tissue_overlap_warped": tissue_overlap_score(coords_warped, he_mask),
        "icp_contour_error_px": icp_error,
    }
    if flow_field is not None:
        mag = np.sqrt(flow_field[:, :, 0] ** 2 + flow_field[:, :, 1] ** 2)
        metrics["flow_mean_px"] = float(mag.mean())
        metrics["flow_max_px"] = float(mag.max())

    return RegistrationResult(
        case_id=case_id,
        affine_thumb=affine_thumb,
        flow_field=flow_field,
        flow_crop_origin=crop_origin,
        coords_phoenix=coords_phx,
        coords_thumb_affine=coords_affine,
        coords_thumb_warped=coords_warped,
        coords_slide_l0=coords_slide,
        metrics=metrics,
    )


def save_registration_artifacts(
    result: RegistrationResult,
    he_thumb_rgb: np.ndarray,
    out_dir: Path,
    gene_values: dict[str, np.ndarray] | None = None,
) -> None:
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "registration.json").write_text(json.dumps(result.as_dict(), indent=2))

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    for ax, coords, title in zip(
        axes,
        [result.coords_thumb_affine, result.coords_thumb_warped],
        ["Affine", "Affine + flow"],
    ):
        ax.imshow(he_thumb_rgb)
        ax.scatter(coords[:, 0], coords[:, 1], s=3, c="cyan", alpha=0.35, linewidths=0)
        ax.set_title(f"{result.case_id}: {title}")
        ax.axis("off")
    if result.flow_field is not None:
        mag = np.sqrt(result.flow_field[:, :, 0] ** 2 + result.flow_field[:, :, 1] ** 2)
        cx0, cy0 = result.flow_crop_origin
        axes[2].imshow(he_thumb_rgb)
        axes[2].imshow(mag, cmap="hot", alpha=0.55, extent=(cx0, cx0 + mag.shape[1], cy0 + mag.shape[0], cy0))
        axes[2].set_title("Flow magnitude")
        axes[2].axis("off")
    plt.tight_layout()
    plt.savefig(out_dir / "registration_overlay.png", dpi=150, bbox_inches="tight")
    plt.close()

    if gene_values and "CD3D" in gene_values:
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        vmax = float(np.percentile(gene_values["CD3D"], 99))
        for ax, coords, title in zip(
            axes,
            [result.coords_thumb_affine, result.coords_thumb_warped],
            ["CD3D affine", "CD3D + flow"],
        ):
            ax.imshow(he_thumb_rgb)
            sc = ax.scatter(
                coords[:, 0],
                coords[:, 1],
                c=gene_values["CD3D"],
                s=12,
                cmap="inferno",
                vmin=0,
                vmax=max(vmax, 1e-6),
                alpha=0.9,
                linewidths=0,
            )
            ax.set_title(title)
            ax.axis("off")
        fig.colorbar(sc, ax=axes, fraction=0.02)
        plt.tight_layout()
        plt.savefig(out_dir / "registration_cd3d_compare.png", dpi=150, bbox_inches="tight")
        plt.close()
