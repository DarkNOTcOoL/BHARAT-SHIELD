"""Local unsupervised tamper-anomaly assistance.

This module deliberately does NOT return an authenticity/fraud probability. It builds a
per-document patch baseline from forensic features (ELA, noise residual, gradients,
Laplacian and luminance statistics), fits a compact PCA model locally with NumPy, and
surfaces patches that are statistical outliers relative to the rest of the same image.

It is useful for officer triage because it is fully offline and does not require a model
or cloud service, but it must not be described as a trained universal forgery detector.
"""
from __future__ import annotations

import io
import math
from typing import Iterable

import cv2
import numpy as np
from PIL import Image

METHOD = "LOCAL_UNSUPERVISED_PATCH_ANOMALY_V57"
MODEL_TYPE = "ROBUST_PCA_PATCH_ANOMALY"


def _jpeg_residual(rgb: np.ndarray, quality: int = 90) -> np.ndarray:
    image = Image.fromarray(rgb)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality)
    rec = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"), dtype=np.float32)
    return np.abs(rgb.astype(np.float32) - rec).max(axis=2)


def _entropy(gray_patch: np.ndarray) -> float:
    hist = cv2.calcHist([gray_patch], [0], None, [32], [0, 256]).ravel().astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return 0.0
    p = hist[hist > 0] / total
    return float(-(p * np.log2(p)).sum())


def _robust_scale(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    med = np.median(values, axis=0)
    mad = np.median(np.abs(values - med), axis=0)
    scale = np.where(mad > 1e-6, mad * 1.4826, np.std(values, axis=0))
    scale = np.where(scale > 1e-6, scale, 1.0)
    return (values - med) / scale, med, scale


def _sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-x))


def _parse_field_boxes(ocr_notes: str | dict | None) -> list[dict]:
    if not ocr_notes:
        return []
    notes = ocr_notes
    if isinstance(ocr_notes, str):
        import json
        try:
            notes = json.loads(ocr_notes)
        except Exception:
            return []
    if not isinstance(notes, dict):
        return []
    output = []
    for item in (notes.get("field_boxes") or [])[:40]:
        if not isinstance(item, dict) or not isinstance(item.get("box"), list) or len(item["box"]) != 4:
            continue
        try:
            box = [float(v) for v in item["box"]]
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in box) or any(v < 0 or v > 1.00001 for v in box):
            continue
        if box[2] <= 0 or box[3] <= 0 or box[0] + box[2] > 1.0001 or box[1] + box[3] > 1.0001:
            continue
        output.append({"field": str(item.get("field", "field"))[:80], "box": box})
    return output


def _box_overlap(region: list[float], field_box: list[float]) -> float:
    ax, ay, aw, ah = region
    bx, by, bw, bh = field_box
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    return inter / max(bw * bh, 1e-9)


def analyze(rgb: np.ndarray, ocr_notes: str | dict | None = None) -> tuple[dict, np.ndarray]:
    """Return (JSON-safe result, uint8 heatmap overlay RGB)."""
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("Expected RGB image")
    h, w = rgb.shape[:2]
    if min(h, w) < 180:
        blank = rgb.copy()
        return ({
            "method": METHOD, "model_type": MODEL_TYPE, "status": "INCONCLUSIVE",
            "reason": "Image is too small for patch anomaly analysis.",
            "max_anomaly_score": None, "inspection_regions": [], "patch_count": 0,
            "limitation": "Unsupervised anomaly localization is not an authenticity or fraud probability."
        }, blank)

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    ela = _jpeg_residual(rgb)
    smooth = cv2.GaussianBlur(gray, (0, 0), 1.2)
    noise = cv2.absdiff(gray, smooth).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(gx, gy)
    lap = np.abs(cv2.Laplacian(gray, cv2.CV_32F, ksize=3))

    min_dim = min(h, w)
    patch = int(np.clip(round(min_dim / 10), 40, 96))
    stride = max(24, patch // 2)
    rows = list(range(0, max(1, h - patch + 1), stride))
    cols = list(range(0, max(1, w - patch + 1), stride))
    if not rows or rows[-1] != h - patch:
        rows.append(max(0, h - patch))
    if not cols or cols[-1] != w - patch:
        cols.append(max(0, w - patch))

    features: list[list[float]] = []
    locations: list[tuple[int, int, int, int]] = []
    evidence: list[dict] = []
    for y in rows:
        for x in cols:
            y1, x1 = min(h, y + patch), min(w, x + patch)
            g = gray[y:y1, x:x1]
            e = ela[y:y1, x:x1]
            n = noise[y:y1, x:x1]
            gr = grad[y:y1, x:x1]
            lp = lap[y:y1, x:x1]
            if g.size < 400:
                continue
            edge_density = float((gr > 35).mean())
            feat = [
                float(g.mean()), float(g.std()), _entropy(g),
                float(e.mean()), float(e.std()), float(np.percentile(e, 95)),
                float(n.mean()), float(n.std()), float(np.percentile(n, 95)),
                float(gr.mean()), float(gr.std()), edge_density,
                float(lp.mean()), float(lp.std()),
            ]
            features.append(feat)
            locations.append((x, y, x1, y1))
            evidence.append({"ela_mean": feat[3], "noise_mean": feat[6], "gradient_mean": feat[9], "edge_density": edge_density})

    if len(features) < 20:
        return ({
            "method": METHOD, "model_type": MODEL_TYPE, "status": "INCONCLUSIVE",
            "reason": "Too few patches for a stable local anomaly baseline.",
            "max_anomaly_score": None, "inspection_regions": [], "patch_count": len(features),
            "limitation": "Unsupervised anomaly localization is not an authenticity or fraud probability."
        }, rgb.copy())

    matrix = np.asarray(features, dtype=np.float64)
    scaled, _, _ = _robust_scale(matrix)
    # Cap extreme feature values before PCA so a single patch cannot define the basis.
    clipped = np.clip(scaled, -8.0, 8.0)
    centered = clipped - clipped.mean(axis=0, keepdims=True)
    try:
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
        components = vt[: min(5, max(2, vt.shape[0] // 3))]
        recon = (centered @ components.T) @ components
        reconstruction_error = np.mean((centered - recon) ** 2, axis=1)
    except np.linalg.LinAlgError:
        reconstruction_error = np.mean(centered ** 2, axis=1)

    # Blend PCA reconstruction error with robust feature-distance. This is intentionally
    # a within-document anomaly score, not a probability of manipulation.
    robust_distance = np.sqrt(np.mean(np.clip(scaled, -12, 12) ** 2, axis=1))
    raw = 0.65 * reconstruction_error + 0.35 * robust_distance
    med = float(np.median(raw))
    mad = float(np.median(np.abs(raw - med)) * 1.4826)
    spread = mad if mad > 1e-6 else max(float(np.std(raw)), 1e-6)
    z = (raw - med) / spread
    scores = (_sigmoid((z - 1.8) * 1.35) * 100.0).astype(np.float32)

    heat_sum = np.zeros((h, w), dtype=np.float32)
    heat_count = np.zeros((h, w), dtype=np.float32)
    supported_scores=[]
    for score, feat, scaled_feat, (x0, y0, x1, y1) in zip(scores, matrix, scaled, locations):
        # Require a second forensic cue before a statistical outlier can become a strong
        # tamper region. This suppresses ordinary high-contrast text that is unusual only
        # because most of the page is blank, while still surfacing compression/noise
        # discontinuities. It remains intentionally conservative and uncalibrated.
        ela_supported = bool(feat[5] >= 12.0 and scaled_feat[3] >= 2.5)
        noise_supported = bool(feat[11] >= 0.45 and feat[6] >= 18.0 and scaled_feat[6] >= 3.0)
        supported = ela_supported or noise_supported
        weighted = float(score) if supported else float(score) * 0.35
        if supported:
            supported_scores.append(float(score))
        heat_sum[y0:y1, x0:x1] += weighted
        heat_count[y0:y1, x0:x1] += 1.0
    heat = np.divide(heat_sum, np.maximum(heat_count, 1.0))

    # Use both an absolute score and an image-relative percentile. This keeps the output
    # selective while still surfacing local outliers on heterogeneous documents.
    nonzero = heat[heat_count > 0]
    relative = float(np.percentile(nonzero, 96)) if nonzero.size else 100.0
    threshold = max(72.0, relative)
    mask = np.uint8((heat >= threshold) * 255)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = max(80, int(h * w * 0.0008))
    max_area = int(h * w * 0.28)
    field_boxes = _parse_field_boxes(ocr_notes)
    regions = []
    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        area = int(cv2.contourArea(contour))
        if area < min_area or area > max_area:
            continue
        x, y, rw, rh = cv2.boundingRect(contour)
        local = heat[y:y+rh, x:x+rw]
        region_score = float(np.percentile(local, 90)) if local.size else 0.0
        box = [x / w, y / h, rw / w, rh / h]
        affected = [b["field"] for b in field_boxes if _box_overlap(box, b["box"]) >= 0.18]
        regions.append({
            "field": affected[0] if affected else "tamper_anomaly",
            "box": [round(float(v), 6) for v in box],
            "source": MODEL_TYPE,
            "status": "AI_ANOMALY_REVIEW",
            "anomaly_score": round(region_score, 1),
            "affected_fields": affected[:6],
        })
        if len(regions) >= 10:
            break

    max_score = max(supported_scores) if supported_scores else 0.0
    strong_regions = [r for r in regions if r["anomaly_score"] >= 82.0]
    status = "REVIEW_REQUIRED" if strong_regions else "NO_STRONG_ANOMALY"
    reason = (
        f"{len(strong_regions)} strong statistical anomaly region(s) found; inspect highlighted pixels and source fields."
        if strong_regions else
        "No strong within-document patch anomaly crossed the review threshold."
    )

    mapped = np.uint8(np.clip(heat / 100.0 * 255.0, 0, 255))
    heat_bgr = cv2.applyColorMap(mapped, cv2.COLORMAP_INFERNO)
    overlay = cv2.addWeighted(rgb, 0.58, cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB), 0.42, 0)
    for region in regions:
        bx, by, bw, bh = region["box"]
        p0 = (int(bx * w), int(by * h))
        p1 = (int((bx + bw) * w), int((by + bh) * h))
        cv2.rectangle(overlay, p0, p1, (255, 255, 255), 2)

    result = {
        "method": METHOD,
        "model_type": MODEL_TYPE,
        "status": status,
        "reason": reason,
        "max_anomaly_score": round(max_score, 1),
        "threshold": round(threshold, 1),
        "patch_count": len(features),
        "patch_size": patch,
        "stride": stride,
        "strong_region_count": len(strong_regions),
        "inspection_regions": regions,
        "affected_fields": sorted({f for r in strong_regions for f in r.get("affected_fields", [])}),
        "score_meaning": "0-100 within-document anomaly index; NOT a probability that the document is forged.",
        "limitation": "This self-calibrating unsupervised model detects unusual forensic patches. Photos, holograms, stamps, QR codes, logos, folds, glare and complex security backgrounds can also be anomalous. A clean result does not establish authenticity.",
    }
    return result, overlay
