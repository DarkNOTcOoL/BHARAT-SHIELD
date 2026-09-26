"""Local active-liveness challenge for the optional person check.

This is a prototype replay-resistance aid, not certified presentation-attack detection (PAD).
It uses bundled YuNet face landmarks over three live-camera frames and never sends images
outside the local process. Challenge state is short-lived and kept only in memory.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from . import local_analysis

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
DETECTOR_PATH = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
CHALLENGE_TTL_SECONDS = 120
_LOCK = threading.Lock()
_CHALLENGES: dict[str, dict] = {}


def _cleanup(now: float | None = None) -> None:
    now = time.time() if now is None else now
    for key in [k for k, v in _CHALLENGES.items() if v["expires_epoch"] < now or v.get("used")]:
        _CHALLENGES.pop(key, None)


def create_challenge(screening_id: str, username: str) -> dict:
    now = time.time()
    challenge_id = secrets.token_urlsafe(24)
    # Front is always first so there is a stable neutral reference. The turn order is random,
    # which adds replay resistance without making the challenge hard to perform.
    turns = ["TURN_LEFT", "TURN_RIGHT"]
    if secrets.randbelow(2):
        turns.reverse()
    steps = ["FRONT", *turns]
    with _LOCK:
        _cleanup(now)
        _CHALLENGES[challenge_id] = {
            "screening_id": screening_id,
            "username": username,
            "steps": steps,
            "created_epoch": now,
            "expires_epoch": now + CHALLENGE_TTL_SECONDS,
            "used": False,
        }
    return {
        "challenge_id": challenge_id,
        "steps": steps,
        "expires_in_seconds": CHALLENGE_TTL_SECONDS,
        "instructions": {
            "FRONT": "Face the camera naturally and keep your head still.",
            "TURN_LEFT": "Turn your head to your left, keeping both eyes visible if possible.",
            "TURN_RIGHT": "Turn your head to your right, keeping both eyes visible if possible.",
        },
        "purpose": "Active head-turn liveness challenge for local replay resistance.",
        "limitation": "This is not certified presentation-attack detection. A sophisticated video replay, mask or virtual camera may still bypass it.",
    }


def consume_challenge(challenge_id: str, screening_id: str, username: str) -> dict | None:
    now = time.time()
    with _LOCK:
        _cleanup(now)
        value = _CHALLENGES.get(challenge_id)
        if not value or value["screening_id"] != screening_id or value["username"] != username or value.get("used"):
            return None
        if value["expires_epoch"] < now:
            _CHALLENGES.pop(challenge_id, None)
            return None
        value["used"] = True
        result = dict(value)
        _CHALLENGES.pop(challenge_id, None)
        return result


def _face_metrics(data: bytes, detector) -> dict:
    image = local_analysis.decode(data)
    image.thumbnail((1280, 1280))
    rgb = np.asarray(image)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    detector.setInputSize((bgr.shape[1], bgr.shape[0]))
    _, faces = detector.detect(bgr)
    count = 0 if faces is None else len(faces)
    if count != 1:
        return {"ok": False, "reason": f"Detected {count} faces; exactly one person must be visible.", "face_count": count}
    face = faces[0]
    x, y, w, h = [float(v) for v in face[:4]]
    if min(w, h) < 90:
        return {"ok": False, "reason": "Face is too small for the active challenge. Move closer and retry.", "face_count": count}
    # YuNet returns five landmarks after the box: right eye, left eye, nose, right mouth, left mouth.
    re = np.array([face[4], face[5]], dtype=np.float64)
    le = np.array([face[6], face[7]], dtype=np.float64)
    nose = np.array([face[8], face[9]], dtype=np.float64)
    eye_mid = (re + le) / 2.0
    eye_dist = max(float(np.linalg.norm(le - re)), 1.0)
    yaw_proxy = float((nose[0] - eye_mid[0]) / eye_dist)
    roll_proxy = float(np.degrees(np.arctan2(le[1] - re[1], le[0] - re[0])))
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(bgr.shape[1], int(x + w)), min(bgr.shape[0], int(y + h))
    crop = bgr[y0:y1, x0:x1]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.size else np.empty((0, 0), np.uint8)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var()) if gray.size else 0.0
    brightness = float(gray.mean()) if gray.size else 0.0
    face_fraction = float((w * h) / max(bgr.shape[0] * bgr.shape[1], 1))
    detection_confidence = float(face[14]) if len(face) > 14 else None
    quality_issues = []
    if blur < 28:
        quality_issues.append("BLUR_OR_LOW_DETAIL")
    if brightness < 35:
        quality_issues.append("UNDEREXPOSED")
    if brightness > 235:
        quality_issues.append("OVEREXPOSED")
    if face_fraction < 0.025:
        quality_issues.append("FACE_TOO_SMALL")
    if abs(roll_proxy) > 24:
        quality_issues.append("EXCESSIVE_ROLL")
    return {
        "ok": not quality_issues,
        "reason": "Usable face frame." if not quality_issues else "Capture quality requires retry: " + ", ".join(quality_issues),
        "face_count": count,
        "yaw_proxy": round(yaw_proxy, 4),
        "roll_degrees": round(roll_proxy, 2),
        "blur": round(blur, 2),
        "brightness": round(brightness, 2),
        "face_fraction": round(face_fraction, 4),
        "detection_confidence": round(detection_confidence, 4) if detection_confidence is not None else None,
        "quality_issues": quality_issues,
    }


def evaluate_motion(samples: dict[str, dict]) -> dict:
    """Evaluate landmark motion independently from image decoding so it can be regression-tested."""
    if any(not samples.get(step, {}).get("ok") for step in ("FRONT", "TURN_LEFT", "TURN_RIGHT")):
        return {
            "status": "RETRY_REQUIRED",
            "reason": "One or more challenge frames failed face/quality checks. Recapture all three steps.",
            "motion_checks": {},
        }
    front = float(samples["FRONT"]["yaw_proxy"])
    left = float(samples["TURN_LEFT"]["yaw_proxy"])
    right = float(samples["TURN_RIGHT"]["yaw_proxy"])
    d1, d2 = left - front, right - front
    separation = abs(left - right)
    opposite = d1 * d2 < -0.035
    enough_each = abs(d1) >= 0.16 and abs(d2) >= 0.16
    front_reasonable = abs(front) <= 0.55
    enough_separation = separation >= 0.38
    passed = opposite and enough_each and front_reasonable and enough_separation
    return {
        "status": "PASSED_ACTIVE_CHALLENGE" if passed else "RETRY_REQUIRED",
        "reason": (
            "Opposite head-turn motion was observed around a neutral frame. This adds replay resistance but is not certified liveness/PAD."
            if passed else
            "Required opposite head-turn motion was not clear enough. Retry slowly with the face centered for the first frame."
        ),
        "motion_checks": {
            "front_reasonable": front_reasonable,
            "opposite_turns": opposite,
            "minimum_turn_each_side": enough_each,
            "turn_separation": enough_separation,
            "yaw_front": round(front, 4),
            "yaw_turn_left": round(left, 4),
            "yaw_turn_right": round(right, 4),
            "yaw_separation": round(separation, 4),
        },
    }


def analyze_sequence(frames: dict[str, bytes]) -> dict:
    if not DETECTOR_PATH.is_file():
        return {
            "status": "MODEL_UNAVAILABLE",
            "reason": "Bundled YuNet detector is unavailable. No download was attempted.",
            "model": "YuNet active head-turn challenge",
        }
    try:
        detector = cv2.FaceDetectorYN.create(str(DETECTOR_PATH), "", (320, 320), 0.85)
        metrics = {step: _face_metrics(frames[step], detector) for step in ("FRONT", "TURN_LEFT", "TURN_RIGHT")}
        result = evaluate_motion(metrics)
        result.update({
            "frames": metrics,
            "model": "YuNet face_detection_yunet_2023mar.onnx",
            "model_sha256": hashlib.sha256(DETECTOR_PATH.read_bytes()).hexdigest(),
            "method": "RANDOMIZED_ACTIVE_HEAD_TURN_V1",
            "presentation_attack_screen": "ACTIVE_CHALLENGE_ONLY",
            "performed_at_model": datetime.now(timezone.utc).isoformat(),
            "image_retention": "NOT_STORED",
            "limitation": "Prototype active liveness only. It is not certified PAD and does not reliably detect sophisticated video replay, masks or virtual-camera attacks.",
        })
        return result
    except cv2.error:
        return {
            "status": "MODEL_ERROR",
            "reason": "YuNet could not run with the installed OpenCV build.",
            "model": "YuNet active head-turn challenge",
        }
