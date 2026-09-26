"""Offline AI-assisted portrait/photo-substitution inspection.

YuNet is used only to localize a portrait face. The surrounding portrait/photo region is
then inspected with deterministic local forensic cues (boundary edges, JPEG residual and
noise mismatch) plus overlap with the v5.7 tamper-anomaly regions.

The output is deliberately an *inspection index*, not a fraud probability or biometric
identity verdict. It is designed to route suspicious portrait regions to a human officer.
"""
from __future__ import annotations

import io
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
DETECTOR_PATH = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
METHOD = "YUNET_LOCAL_PHOTO_INTEGRITY_V58"
MODEL = "YuNet + local portrait-region forensics"


def _jpeg_residual(rgb: np.ndarray, quality: int = 90) -> np.ndarray:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality)
    rec = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"), dtype=np.float32)
    return np.abs(rgb.astype(np.float32) - rec).max(axis=2)


def _clip_box(box: tuple[int, int, int, int], w: int, h: int) -> tuple[int, int, int, int]:
    x, y, bw, bh = box
    x = max(0, min(int(x), w - 1)); y = max(0, min(int(y), h - 1))
    bw = max(1, min(int(bw), w - x)); bh = max(1, min(int(bh), h - y))
    return x, y, bw, bh


def _normalized(box: tuple[int, int, int, int], w: int, h: int) -> list[float]:
    x, y, bw, bh = box
    return [round(x / w, 6), round(y / h, 6), round(bw / w, 6), round(bh / h, 6)]


def _intersection(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _find_photo_frame(gray: np.ndarray, face_box: tuple[int, int, int, int]) -> tuple[tuple[int, int, int, int], bool]:
    """Find a plausible rectangular portrait frame around the detected face.

    If no frame is visible, return a conservative padded crop around the face. A frame
    is only localization evidence; it is not itself suspicious.
    """
    h, w = gray.shape[:2]
    fx, fy, fw, fh = face_box
    cx, cy = fx + fw / 2.0, fy + fh / 2.0
    face_area = max(float(fw * fh), 1.0)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 45, 135)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[float, tuple[int, int, int, int]]] = []
    image_area = float(w * h)
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < face_area * 1.35 or area > image_area * 0.28:
            continue
        if not (x <= cx <= x + bw and y <= cy <= y + bh):
            continue
        aspect = bw / max(float(bh), 1.0)
        if not 0.48 <= aspect <= 1.45:
            continue
        face_ratio = face_area / area
        if not 0.07 <= face_ratio <= 0.72:
            continue
        # Prefer the smallest plausible frame that leaves some room around the face.
        margin = min(cx - x, x + bw - cx, cy - y, y + bh - cy)
        if margin < min(fw, fh) * 0.08:
            continue
        candidates.append((area, (x, y, bw, bh)))
    if candidates:
        candidates.sort(key=lambda item: item[0])
        return _clip_box(candidates[0][1], w, h), True

    # Fallback portrait region. Keep enough context to inspect the photo boundary while
    # avoiding an enormous region that would absorb most of the document.
    x0 = fx - int(round(fw * 0.45)); y0 = fy - int(round(fh * 0.35))
    x1 = fx + fw + int(round(fw * 0.45)); y1 = fy + fh + int(round(fh * 0.50))
    return _clip_box((x0, y0, x1 - x0, y1 - y0), w, h), False


def _masks(shape: tuple[int, int], box: tuple[int, int, int, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    h, w = shape
    x, y, bw, bh = box
    border = max(3, int(round(min(bw, bh) * 0.045)))
    ring = max(border + 2, int(round(min(bw, bh) * 0.10)))
    photo = np.zeros((h, w), dtype=bool); photo[y:y+bh, x:x+bw] = True
    inner = np.zeros_like(photo)
    ix0, iy0 = min(x + border, x + bw), min(y + border, y + bh)
    ix1, iy1 = max(ix0, x + bw - border), max(iy0, y + bh - border)
    inner[iy0:iy1, ix0:ix1] = True
    expanded = np.zeros_like(photo)
    ex0, ey0 = max(0, x-ring), max(0, y-ring)
    ex1, ey1 = min(w, x+bw+ring), min(h, y+bh+ring)
    expanded[ey0:ey1, ex0:ex1] = True
    outside_ring = expanded & ~photo
    boundary = (photo & ~inner) | outside_ring
    return inner, outside_ring, boundary


def _ratio_score(a: float, b: float, start: float = 1.45, full: float = 2.8) -> tuple[float, float]:
    lo, hi = min(a, b), max(a, b)
    ratio = (hi + 1e-6) / (lo + 1e-6)
    score = float(np.clip((ratio - start) / max(full - start, 1e-6) * 100.0, 0, 100))
    return ratio, score


def analyze_region(
    rgb: np.ndarray,
    photo_box: tuple[int, int, int, int],
    *,
    face_box: tuple[int, int, int, int] | None = None,
    frame_detected: bool = False,
    tamper_regions: list[dict] | None = None,
) -> tuple[dict, np.ndarray]:
    """Analyze a supplied portrait/photo region. Exposed separately for deterministic tests."""
    h, w = rgb.shape[:2]
    photo_box = _clip_box(photo_box, w, h)
    x, y, bw, bh = photo_box
    if min(bw, bh) < 55:
        return ({
            "method": METHOD, "model": MODEL, "status": "INCONCLUSIVE",
            "reason": "Detected portrait region is too small for local photo-integrity analysis.",
            "photo_integrity_index": None, "inspection_regions": [], "frame_detected": frame_detected,
            "limitation": "Photo-integrity analysis is an inspection aid, not proof of substitution."
        }, rgb.copy())

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    ela = _jpeg_residual(rgb)
    smooth = cv2.GaussianBlur(gray, (0, 0), 1.1)
    noise = cv2.absdiff(gray, smooth).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(gx, gy)
    inner, outside, boundary = _masks(gray.shape, photo_box)
    if inner.sum() < 600 or outside.sum() < 250:
        return ({
            "method": METHOD, "model": MODEL, "status": "INCONCLUSIVE",
            "reason": "Not enough surrounding document pixels to compare the portrait region.",
            "photo_integrity_index": None, "inspection_regions": [], "frame_detected": frame_detected,
            "limitation": "Photo-integrity analysis is an inspection aid, not proof of substitution."
        }, rgb.copy())

    edge_threshold = max(28.0, float(np.percentile(grad, 82)))
    boundary_edge_coverage = float((grad[boundary] >= edge_threshold).mean())
    inner_edge_coverage = float((grad[inner] >= edge_threshold).mean())
    outside_edge_coverage = float((grad[outside] >= edge_threshold).mean())
    baseline_edges = max(inner_edge_coverage, outside_edge_coverage, 0.035)
    seam_ratio = boundary_edge_coverage / baseline_edges
    relative_seam_score = float(np.clip((seam_ratio - 1.55) / 2.1 * 100.0, 0, 100))
    absolute_seam_score = float(np.clip((boundary_edge_coverage - 0.08) / 0.20 * 100.0, 0, 100))
    seam_score = max(relative_seam_score, absolute_seam_score)

    ela_inside = float(np.mean(ela[inner])); ela_outside = float(np.mean(ela[outside]))
    noise_inside = float(np.mean(noise[inner])); noise_outside = float(np.mean(noise[outside]))
    ela_ratio, ela_score = _ratio_score(ela_inside, ela_outside, 1.55, 3.4)
    noise_ratio, noise_score = _ratio_score(noise_inside, noise_outside, 1.55, 3.2)

    photo_norm = _normalized(photo_box, w, h)
    overlap_fraction = 0.0; overlap_max_score = 0.0
    photo_area = max(photo_norm[2] * photo_norm[3], 1e-9)
    for region in tamper_regions or []:
        box = region.get("box")
        if not isinstance(box, list) or len(box) != 4:
            continue
        try:
            vals = [float(v) for v in box]
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in vals):
            continue
        inter = _intersection(photo_norm, vals)
        overlap_fraction = max(overlap_fraction, inter / photo_area)
        if inter > 0:
            overlap_max_score = max(overlap_max_score, float(region.get("anomaly_score") or 0.0))
    overlap_score = float(np.clip(max(overlap_fraction / 0.35 * 100.0, (overlap_max_score - 72.0) / 18.0 * 100.0), 0, 100))

    # Individual cues intentionally require strong evidence. The review state is only
    # emitted when multiple independent cues agree, limiting false alerts on legitimate
    # printed portrait boxes and security backgrounds.
    hard_seam = seam_score >= 62.0
    compression_mismatch = ela_score >= 62.0
    noise_mismatch = noise_score >= 62.0
    tamper_overlap = overlap_score >= 60.0
    cue_count = sum([hard_seam, compression_mismatch, noise_mismatch, tamper_overlap])
    content_mismatch = compression_mismatch or noise_mismatch
    base = 0.30 * seam_score + 0.24 * ela_score + 0.24 * noise_score + 0.22 * overlap_score
    synergy = 0.0
    if tamper_overlap and content_mismatch: synergy += 16.0
    if tamper_overlap and hard_seam and content_mismatch: synergy += 18.0
    if hard_seam and compression_mismatch and noise_mismatch: synergy += 12.0
    index = float(np.clip(base + synergy, 0, 100))
    if not content_mismatch:
        index = min(index, 49.0)
    review = bool(
        (content_mismatch and (tamper_overlap or hard_seam) and cue_count >= 2 and index >= 55.0)
        or (hard_seam and compression_mismatch and noise_mismatch and index >= 65.0)
    )
    status = "REVIEW_REQUIRED" if review else "NO_STRONG_PHOTO_SUBSTITUTION_SIGNAL"
    cues = []
    if hard_seam: cues.append("HARD_RECTANGULAR_BOUNDARY")
    if compression_mismatch: cues.append("JPEG_RESIDUAL_MISMATCH")
    if noise_mismatch: cues.append("NOISE_PATTERN_MISMATCH")
    if tamper_overlap: cues.append("OVERLAPPING_TAMPER_ANOMALY")

    canvas = rgb.copy()
    color = (255, 80, 80) if review else (255, 200, 60)
    cv2.rectangle(canvas, (x, y), (x+bw, y+bh), color, 3)
    if face_box:
        fx, fy, fw, fh = _clip_box(face_box, w, h)
        cv2.rectangle(canvas, (fx, fy), (fx+fw, fy+fh), (80, 220, 255), 2)
    label = "PHOTO REVIEW" if review else "PHOTO REGION"
    cv2.putText(canvas, label, (x, max(18, y-8)), cv2.FONT_HERSHEY_SIMPLEX, 0.58, color, 2, cv2.LINE_AA)

    region = {
        "field": "document_photo", "box": photo_norm, "source": METHOD,
        "status": "PHOTO_SUBSTITUTION_REVIEW" if review else "PHOTO_REGION_INSPECTED",
        "photo_integrity_index": round(index, 1),
    }
    result = {
        "method": METHOD, "model": MODEL, "status": status,
        "reason": (
            "Multiple independent forensic cues overlap the AI-localized portrait region; inspect the original document and compare the person."
            if review else
            "No multi-cue portrait-substitution signal crossed the review threshold. A clean result does not establish authenticity."
        ),
        "photo_integrity_index": round(index, 1),
        "score_meaning": "0-100 local portrait-integrity anomaly index; NOT a probability that the photograph was replaced.",
        "frame_detected": bool(frame_detected),
        "photo_region": photo_norm,
        "face_region": _normalized(face_box, w, h) if face_box else None,
        "cues": cues,
        "metrics": {
            "boundary_edge_coverage": round(boundary_edge_coverage, 4),
            "seam_ratio": round(seam_ratio, 3), "seam_score": round(seam_score, 1),
            "jpeg_residual_inside": round(ela_inside, 3), "jpeg_residual_outside": round(ela_outside, 3),
            "jpeg_residual_ratio": round(ela_ratio, 3), "jpeg_residual_score": round(ela_score, 1),
            "noise_inside": round(noise_inside, 3), "noise_outside": round(noise_outside, 3),
            "noise_ratio": round(noise_ratio, 3), "noise_score": round(noise_score, 1),
            "tamper_overlap_fraction": round(overlap_fraction, 4), "tamper_overlap_score": round(overlap_score, 1),
        },
        "inspection_regions": [region],
        "limitation": "YuNet localizes a face, but the replacement decision is not a trained or calibrated universal classifier. Legitimate photo frames, scans, laminates, holograms, resaving and printer/scanner differences can change these cues. Human review is required.",
    }
    return result, canvas


def analyze(rgb: np.ndarray, tamper_regions: list[dict] | None = None) -> tuple[dict, np.ndarray]:
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("Expected RGB image")
    h, w = rgb.shape[:2]
    if not DETECTOR_PATH.is_file():
        return ({
            "method": METHOD, "model": MODEL, "status": "MODEL_UNAVAILABLE",
            "reason": "Bundled YuNet face detector is unavailable; photo-substitution analysis was not run.",
            "photo_integrity_index": None, "inspection_regions": [], "face_count": None,
            "limitation": "Missing analysis is not evidence of authenticity or fraud."
        }, rgb.copy())
    if min(h, w) < 180:
        return ({
            "method": METHOD, "model": MODEL, "status": "INCONCLUSIVE",
            "reason": "Image is too small for portrait-substitution analysis.",
            "photo_integrity_index": None, "inspection_regions": [], "face_count": None,
            "limitation": "Recapture at higher resolution."
        }, rgb.copy())
    try:
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        detector = cv2.FaceDetectorYN.create(str(DETECTOR_PATH), "", (320, 320), 0.72, 0.3, 5000)
        detector.setInputSize((w, h))
        _, faces = detector.detect(bgr)
    except cv2.error:
        return ({
            "method": METHOD, "model": MODEL, "status": "MODEL_ERROR",
            "reason": "Bundled YuNet model could not run with the installed OpenCV build.",
            "photo_integrity_index": None, "inspection_regions": [], "face_count": None,
            "limitation": "Model failure is not evidence of authenticity or fraud."
        }, rgb.copy())
    count = 0 if faces is None else len(faces)
    if count == 0:
        return ({
            "method": METHOD, "model": MODEL, "status": "NO_PORTRAIT_DETECTED",
            "reason": "No portrait face was detected in the document image. Photo substitution was not assessed.",
            "photo_integrity_index": None, "inspection_regions": [], "face_count": 0,
            "limitation": "Documents without a detectable portrait require manual photo inspection if a portrait is expected."
        }, rgb.copy())
    # Security documents can contain ghost portraits. Do not treat multiple faces as fraud.
    if count > 2:
        return ({
            "method": METHOD, "model": MODEL, "status": "INCONCLUSIVE_MULTIPLE_PORTRAITS",
            "reason": f"YuNet detected {count} face-like regions. Multiple/ghost portraits require manual inspection.",
            "photo_integrity_index": None, "inspection_regions": [], "face_count": count,
            "limitation": "Multiple detected portraits can be legitimate security features and are not a substitution verdict."
        }, rgb.copy())

    # Analyze the largest face as the principal document portrait. A second smaller ghost
    # portrait, if present, is preserved as context but does not trigger an alert by itself.
    principal = max(faces, key=lambda f: float(f[2] * f[3]))
    fx, fy, fw, fh = [int(round(float(v))) for v in principal[:4]]
    face_box = _clip_box((fx, fy, fw, fh), w, h)
    if min(face_box[2], face_box[3]) < 38:
        return ({
            "method": METHOD, "model": MODEL, "status": "INCONCLUSIVE",
            "reason": "Detected document portrait is too small. Recapture closer for photo-integrity analysis.",
            "photo_integrity_index": None, "inspection_regions": [], "face_count": count,
            "face_region": _normalized(face_box, w, h),
            "limitation": "A small face cannot support reliable local forensic inspection."
        }, rgb.copy())
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    photo_box, frame_detected = _find_photo_frame(gray, face_box)
    result, overlay = analyze_region(rgb, photo_box, face_box=face_box, frame_detected=frame_detected, tamper_regions=tamper_regions)
    result["face_count"] = count
    result["detector"] = "YuNet face_detection_yunet_2023mar.onnx"
    result["detector_confidence"] = round(float(principal[-1]), 4) if len(principal) >= 15 else None
    if count == 2:
        result["note"] = "Two face-like regions were detected; the largest was analyzed as the principal portrait. The second may be a legitimate ghost/security portrait."
    return result, overlay
