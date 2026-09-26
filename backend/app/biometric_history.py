"""Encrypted local SFace-template history search for officer review.

This module does not make an identity verdict. It ranks locally retained, encrypted
face templates after a passed active-liveness challenge and surfaces high-similarity
candidates when identity/document attributes differ. Thresholds are conservative
prototype retrieval thresholds and require site-specific calibration before use in
any operational decision.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from cryptography.fernet import Fernet, InvalidToken

VERSION = "LOCAL_ENCRYPTED_SFACE_HISTORY_V1"
CANDIDATE_THRESHOLD = 0.45
REVIEW_THRESHOLD = 0.50
STRONG_REVIEW_THRESHOLD = 0.58
MAX_SEARCH = 500
MAX_RESULTS = 10


def normalize_embedding(values) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float32).reshape(-1)
    if arr.size == 0 or not np.all(np.isfinite(arr)):
        raise ValueError("Invalid face embedding")
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-12:
        raise ValueError("Zero face embedding")
    return arr / norm


def similarity(a, b) -> float:
    av = normalize_embedding(a)
    bv = normalize_embedding(b)
    if av.shape != bv.shape:
        raise ValueError("Embedding dimensions differ")
    return float(np.clip(np.dot(av, bv), -1.0, 1.0))


def seal_embedding(values, cipher: Fernet) -> tuple[str, str, int]:
    arr = normalize_embedding(values).astype("<f4", copy=False)
    raw = arr.tobytes()
    digest = hashlib.sha256(raw).hexdigest()
    payload = json.dumps({"dtype":"float32","shape":[int(arr.size)],"data_hex":raw.hex()}, separators=(",", ":")).encode()
    return cipher.encrypt(payload).decode("ascii"), digest, int(arr.size)


def open_embedding(ciphertext: str, cipher: Fernet) -> np.ndarray:
    try:
        payload = json.loads(cipher.decrypt(ciphertext.encode("ascii")).decode("utf-8"))
        raw = bytes.fromhex(payload["data_hex"])
        arr = np.frombuffer(raw, dtype="<f4").copy()
        expected = int((payload.get("shape") or [arr.size])[0])
        if arr.size != expected:
            raise ValueError("Embedding size mismatch")
        return normalize_embedding(arr)
    except (InvalidToken, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Encrypted biometric template could not be opened") from exc


def _norm_text(value: str | None) -> str:
    return " ".join((value or "").upper().split())


def _norm_number(value: str | None) -> str:
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def compare_identity(current: dict, previous: dict) -> list[str]:
    reasons=[]
    current_name=_norm_text(current.get("name")); old_name=_norm_text(previous.get("name"))
    current_dob=_norm_text(current.get("dob")); old_dob=_norm_text(previous.get("dob"))
    current_number=_norm_number(current.get("document_number")); old_number=_norm_number(previous.get("document_number"))
    if current_name and old_name and current_name != old_name: reasons.append("DIFFERENT_NAME")
    if current_dob and old_dob and current_dob != old_dob: reasons.append("DIFFERENT_DOB")
    if current_number and old_number and current_number != old_number: reasons.append("DIFFERENT_DOCUMENT_NUMBER")
    return reasons


def search(current_embedding, current_identity: dict, rows: Iterable[dict], limit: int = MAX_SEARCH) -> dict:
    current = normalize_embedding(current_embedding)
    candidates=[]; searched=0; skipped=0
    for row in list(rows)[:limit]:
        searched += 1
        try:
            score=similarity(current,row["embedding"])
        except (ValueError, KeyError):
            skipped += 1
            continue
        if score < CANDIDATE_THRESHOLD:
            continue
        previous={"name":row.get("person_name", ""),"dob":row.get("date_of_birth", ""),"document_number":row.get("document_number", "")}
        conflicts=compare_identity(current_identity,previous)
        different_identity=bool(conflicts)
        requires_review=score >= REVIEW_THRESHOLD and different_identity
        strength="STRONG_REVIEW_CANDIDATE" if score >= STRONG_REVIEW_THRESHOLD and different_identity else "REVIEW_CANDIDATE" if requires_review else "SIMILAR_TEMPLATE"
        candidates.append({
            "screening_id":row.get("screening_id"),
            "person_name":row.get("person_name") or "Not detected",
            "date_of_birth":row.get("date_of_birth") or "Not detected",
            "document_number":row.get("document_number") or "Not detected",
            "document_type":row.get("document_type") or "Unknown",
            "cosine_similarity":round(score,4),
            "identity_differences":conflicts,
            "candidate_type":strength,
            "requires_review":requires_review,
            "liveness_status":row.get("liveness_status","UNKNOWN"),
            "created_at":row.get("created_at"),
        })
    candidates.sort(key=lambda x:x["cosine_similarity"],reverse=True)
    candidates=candidates[:MAX_RESULTS]
    review=[c for c in candidates if c["requires_review"]]
    return {
        "status":"REVIEW_REQUIRED" if review else "CANDIDATES_FOUND" if candidates else "NO_SIMILAR_TEMPLATE_CANDIDATES",
        "requires_review":bool(review),
        "candidate_count":len(candidates),
        "review_candidate_count":len(review),
        "searched_template_count":searched,
        "skipped_template_count":skipped,
        "candidates":candidates,
        "method":VERSION,
        "candidate_threshold":CANDIDATE_THRESHOLD,
        "review_threshold":REVIEW_THRESHOLD,
        "strong_review_threshold":STRONG_REVIEW_THRESHOLD,
        "meaning":"Local SFace-template retrieval for officer investigation after successful active liveness. A candidate is not an identity verdict.",
        "limitation":"Prototype thresholds are uncalibrated for deployment. Similar-looking people, capture conditions, ageing and model bias can affect similarity. Human review and independent identity evidence are required.",
    }
