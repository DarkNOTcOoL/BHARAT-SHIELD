"""BHARATSHIELD v6.9 SIH26188 demo/readiness hardening.

This module does not create new identity or fraud verdicts. It packages the
existing local capabilities into a repeatable SIH demonstration workflow and
performs local-only preflight checks before a live demo.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse

from . import local_registry, local_security, registry_v2, signed_demo, video_demo

VERSION = "SIH26188_DEMO_HARDENING_V1"

SCENARIOS = [
    {
        "key": "clean_active",
        "title": "Clean active document",
        "sample": "demo_samples/video_demo/01_active_match.png",
        "document_type": "Permit",
        "expected": "LOW / READY FOR OFFICER DECISION",
        "why": "Baseline: OCR + registry match with no strong configured review signal.",
        "talking_point": "Shows the normal fast-path before demonstrating negative SIH26188 cases.",
    },
    {
        "key": "dob_tamper",
        "title": "DOB / identity field conflict",
        "sample": "demo_samples/video_demo/03_dob_conflict.png",
        "document_type": "Permit",
        "expected": "MANUAL REVIEW / HIGH",
        "why": "Printed/OCR DOB conflicts with the synthetic reference identity.",
        "talking_point": "Maps directly to modified identity fields such as DOB in SIH26188.",
    },
    {
        "key": "blocked_document",
        "title": "Blocked document",
        "sample": "demo_samples/video_demo/06_blocked.png",
        "document_type": "Permit",
        "expected": "ESCALATE / CRITICAL",
        "why": "Synthetic reference status is BLOCKED.",
        "talking_point": "Demonstrates deterministic blacklist/status escalation without an opaque AI verdict.",
    },
    {
        "key": "poor_capture",
        "title": "Poor capture / recapture",
        "sample": "demo_samples/ocr_capture/02_glare_recapture.png",
        "document_type": "Permit",
        "expected": "RECAPTURE",
        "why": "Capture-quality evidence is intentionally insufficient.",
        "talking_point": "Shows that missing/poor evidence does not become a false clean or fraud result.",
    },
    {
        "key": "visa_stamp_review",
        "title": "Suspicious visa stamp region",
        "sample": "demo_samples/visa_intelligence/03_visa_stamp_suspicious.png",
        "document_type": "Visa",
        "expected": "MANUAL REVIEW",
        "why": "Visa/stamp forensic cues cross the configured review threshold.",
        "talking_point": "Targets the tampered visa/stamp scenario in SIH26188.",
    },
    {
        "key": "entry_limit",
        "title": "Single-entry visa used twice",
        "sample": "demo_samples/travel_intelligence/02_single_entry_overused_visa.png",
        "document_type": "Visa",
        "expected": "MANUAL REVIEW",
        "why": "Synthetic travel history contradicts the visa entry entitlement.",
        "talking_point": "Demonstrates visa intelligence and entry/exit chronology correlation.",
    },
    {
        "key": "lost_stolen",
        "title": "Lost / stolen document alert",
        "sample": "demo_samples/registry2/02_lost_stolen_passport_alert.png",
        "document_type": "Passport",
        "expected": "ESCALATE",
        "why": "Registry 2.2 contains a synthetic critical lost/stolen alert.",
        "talking_point": "Demonstrates the production integration point for authorized government alerts.",
    },
    {
        "key": "visual_security",
        "title": "Moved issuer emblem / template feature",
        "sample": "demo_samples/visual_security/03_emblem_moved.png",
        "document_type": "Passport",
        "expected": "MANUAL REVIEW",
        "why": "A required visual reference is outside its versioned expected zone.",
        "talking_point": "Shows explainable template/security-zone anomaly evidence.",
    },
    {
        "key": "signed_qr_tamper",
        "title": "Tampered signed credential payload",
        "sample": "demo_samples/signed_qr/03_payload_tampered.png",
        "document_type": "Permit",
        "expected": "MANUAL REVIEW / signature problem",
        "why": "Local Ed25519 verification does not validate the modified signed payload.",
        "talking_point": "Shows cryptographic corroboration alongside AI/CV evidence.",
    },
]


def _check(name: str, status: str, detail: str, blocking: bool = False) -> dict:
    return {"name": name, "status": status, "detail": detail, "blocking": bool(blocking)}


def _quick_check(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "WARN", "Database will be created on first use."
    try:
        db = sqlite3.connect(path, timeout=3)
        try:
            result = db.execute("PRAGMA quick_check").fetchone()[0]
        finally:
            db.close()
        return ("PASS", "SQLite quick_check: ok") if result == "ok" else ("BLOCK", f"SQLite quick_check: {result}")
    except Exception as exc:
        return "BLOCK", f"Database check failed: {type(exc).__name__}"


def readiness(backend_root: Path, private_root: Path, main_db: Path) -> dict:
    project_root = backend_root.parent
    dist = project_root / "dist"
    models = backend_root / "models"
    checks: list[dict] = []

    py = sys.version_info
    supported = (3, 11) <= (py.major, py.minor) <= (3, 13)
    checks.append(_check("Python runtime", "PASS" if supported else "BLOCK", f"Python {py.major}.{py.minor}.{py.micro}; supported demo range is 3.11-3.13.", not supported))

    writable = private_root.exists() and os.access(private_root, os.W_OK)
    checks.append(_check("Private data directory", "PASS" if writable else "BLOCK", str(private_root), not writable))

    ocr_assets = [dist / "ocr" / "worker.min.js", dist / "ocr" / "tessdata" / "eng.traineddata.gz"]
    ocr_ok = (dist / "index.html").exists() and all(p.exists() for p in ocr_assets) and any((dist / "ocr" / "core").glob("*.wasm.js"))
    checks.append(_check("Offline OCR assets", "PASS" if ocr_ok else "BLOCK", "Bundled Tesseract worker, English data and WASM are present." if ocr_ok else "One or more bundled OCR assets are missing.", not ocr_ok))

    face_files = [models / "face_detection_yunet_2023mar.onnx", models / "face_recognition_sface_2021dec.onnx"]
    face_ok = all(p.exists() and p.stat().st_size > 1000 for p in face_files)
    checks.append(_check("Local face models", "PASS" if face_ok else "BLOCK", "YuNet + SFace model files are present." if face_ok else "YuNet or SFace model file is missing.", not face_ok))

    zxing = importlib.util.find_spec("zxingcpp") is not None
    checks.append(_check("Native QR decoder", "PASS" if zxing else "WARN", "zxing-cpp available." if zxing else "zxing-cpp is unavailable; OpenCV fallback remains available but dense QR decoding may be less reliable."))

    ref_manifest = backend_root / "reference_templates" / "v66" / "manifest.json"
    checks.append(_check("Synthetic issuer references", "PASS" if ref_manifest.exists() else "WARN", "Versioned synthetic visual-reference manifest is present." if ref_manifest.exists() else "Synthetic visual-reference manifest is missing."))

    try:
        free = shutil.disk_usage(private_root).free
        if free >= 512 * 1024 * 1024:
            ds, detail = "PASS", f"{free // (1024*1024)} MiB free"
        elif free >= 128 * 1024 * 1024:
            ds, detail = "WARN", f"Only {free // (1024*1024)} MiB free"
        else:
            ds, detail = "BLOCK", f"Only {free // (1024*1024)} MiB free"
        checks.append(_check("Free local storage", ds, detail, ds == "BLOCK"))
    except Exception:
        checks.append(_check("Free local storage", "WARN", "Free-space check unavailable."))

    for label, dbpath in [("Screening database", main_db), ("Synthetic registry database", local_registry.DB), ("Accounts database", local_security.DB)]:
        status, detail = _quick_check(Path(dbpath))
        checks.append(_check(label, status, detail, status == "BLOCK"))

    scenario_missing = [s["sample"] for s in SCENARIOS if not (project_root / s["sample"]).exists()]
    checks.append(_check("Curated SIH demo samples", "PASS" if not scenario_missing else "BLOCK", f"{len(SCENARIOS)} curated scenarios available." if not scenario_missing else "Missing: " + ", ".join(scenario_missing[:4]), bool(scenario_missing)))

    blocking = [c for c in checks if c["blocking"] and c["status"] == "BLOCK"]
    warnings = [c for c in checks if c["status"] == "WARN"]
    overall = "READY" if not blocking and not warnings else "READY_WITH_WARNINGS" if not blocking else "NOT_READY"
    return {
        "version": VERSION,
        "overall": overall,
        "checks": checks,
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "scenario_count": len(SCENARIOS),
        "meaning": "Readiness checks local demo dependencies and storage only. It is not a security certification or authenticity assessment.",
    }


def _seed_legacy(db, actor: str) -> dict:
    created, skipped = [], []
    candidates = list(local_registry.demo_records()) + list(local_registry.visa_demo_records())
    for case in video_demo.scenarios():
        if case["reference"] is not None:
            candidates.append(local_registry.RegistryRecordInput.model_validate(case["reference"]))
    for record in candidates:
        found = db.execute(
            "SELECT id FROM registry_records WHERE document_type=? AND issuer_country=? AND document_number=?",
            (record.document_type, record.issuer_country, record.document_number),
        ).fetchone()
        if found:
            skipped.append(record.document_number)
        else:
            saved = local_registry.create_in_transaction(db, record, actor, "Loaded bundled v6.9 SIH26188 all-demo pack.")
            created.append(saved["id"])
    return {"created": created, "skipped": skipped}


def _seed_signed(db, actor: str) -> dict:
    created, skipped = [], []
    for values in signed_demo.records():
        ident = values["id"]
        data = {k: v for k, v in values.items() if k not in {"id", "version"}}
        found = db.execute(
            "SELECT 1 FROM registry_records WHERE id=? OR (document_type=? AND issuer_country=? AND document_number=?)",
            (ident, data["document_type"], data["issuer_country"], data["document_number"]),
        ).fetchone()
        if found:
            skipped.append(ident)
            continue
        record = local_registry.RegistryRecordInput.model_validate(data).model_dump()
        now = local_registry.utcnow()
        db.execute(
            "INSERT INTO registry_records VALUES(?,?,?,?,?,?,1,0,?,?,?)",
            (ident, record["document_type"], record["issuer_country"], record["document_number"], local_registry.normalized_text(record["name"]), json.dumps(record), now, now, actor),
        )
        saved = local_registry.serialize(db.execute("SELECT * FROM registry_records WHERE id=?", (ident,)).fetchone())
        local_registry.audit(db, saved, None, "CREATE", actor, "Loaded bundled v6.9 signed-QR demonstration reference.")
        created.append(ident)
    return {"created": created, "skipped": skipped}


def install(app, *, backend_root: Path, private_root: Path, main_db: Path):
    project_root = backend_root.parent
    scenario_map = {x["key"]: x for x in SCENARIOS}

    @app.get("/api/demo/readiness")
    def demo_readiness(request: Request):
        return readiness(backend_root, private_root, main_db)

    @app.get("/api/demo/scenarios")
    def demo_scenarios(request: Request):
        return {"version": VERSION, "source": "BUNDLED_SYNTHETIC_SIH26188_DEMOS", "scenarios": SCENARIOS,
                "limitation": "All referenced identities, registries, issuers, travel records and alerts are fictional/synthetic demonstration data."}

    @app.get("/api/demo/sample/{key}")
    def demo_sample(key: str, request: Request):
        item = scenario_map.get(key)
        if not item:
            raise HTTPException(404, "Unknown bundled demo scenario.")
        path = (project_root / item["sample"]).resolve()
        if project_root not in path.parents or not path.is_file():
            raise HTTPException(404, "Bundled demo sample is unavailable.")
        return FileResponse(path, media_type="image/png", filename=path.name)

    @app.post("/api/demo/seed-all")
    def seed_all(request: Request):
        actor = local_registry.require_supervisor(request)
        with local_registry.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            legacy = _seed_legacy(db, actor)
            signed = _seed_signed(db, actor)
            registry_base = registry_v2.seed_demo(db, actor)
            visual = registry_v2.seed_visual_demo(db, actor)
            travel = registry_v2.seed_travel_demo_v67(db, actor)
        return {
            "version": VERSION,
            "source": "SYNTHETIC_SIH26188_ALL_DEMO_PACK",
            "legacy": legacy,
            "signed_qr": signed,
            "registry2": registry_base,
            "visual_security": visual,
            "travel_intelligence": travel,
            "message": "All bundled synthetic SIH26188 demo references are ready. Existing records were preserved.",
        }
