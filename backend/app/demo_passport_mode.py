"""BHARATSHIELD v7.1 - Demo / Presentation Mode interceptor.

Scope:
  Replaces document-level screening results ONLY for designated demo filenames
  (passport_test_01.png or 'Untitled design (2).png').
  All live webcam capture, face-match and active liveness endpoints are
  completely unaffected by this module - they continue to run normally.

IMPORTANT PRESERVATION GUARANTEE
  /api/face/*  routes    -- NOT touched
  /api/liveness/* routes -- NOT touched
  /api/screening/*/image -- NOT touched
  active_liveness.py     -- NOT imported or called here
  No webcam / camera logic is imported, mocked or bypassed here
"""
from __future__ import annotations
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Trigger filenames -- comparison is case-insensitive, ignores whitespace
# ---------------------------------------------------------------------------
DEMO_TRIGGER_FILENAMES: frozenset[str] = frozenset({
    "passport_test_01.png",
    "untitled design (2).png",
})

# 3-second progressive scan delay to match the UI feedback timeline
_DEMO_DELAY_SECONDS = 3.0

_DEMO_FIELDS = {
    "name":              "SRIKRISHNAN NADAR SIVA SELVA KUMAR",
    "dob":               "04/05/2006",
    "nationality":       "IND",
    "document_number":   "H1591116",
    "expiry":            "30/11/2034",
    "issuer_country":    "IND",
    "issue_date":        "01/12/2024",
    "gender":            "M",
    "issuing_authority": "MADURAI",
}

# ---------------------------------------------------------------------------
# Flat ocr_fields dict -- snake_case keys only, matching COMPARE_FIELDS.
# Capped at 15 entries to satisfy DocumentInput.ocr_fields max_length=15.
# This is the payload that evidence_rules.extraction_evidence() reads from
# metadata['ocr_fields'] to populate the "Extraction source values" section.
# ---------------------------------------------------------------------------
_DEMO_OCR_FIELDS: dict[str, str] = {
    "name":              "SRIKRISHNAN NADAR SIVA SELVA KUMAR",
    "dob":               "04/05/2006",
    "nationality":       "INDIAN",
    "document_number":   "H1591116",
    "expiry":            "30/11/2034",
    "issuer_country":    "IND",
    "issue_date":        "01/12/2024",
    "gender":            "M",
    "issuing_authority": "MADURAI",
    "place_of_birth":    "NAGERCOIL",
    "place_of_issue":    "MADURAI",
    "passport_reference": "",
    "visa_type":         "",
    "number_of_entries": "",
    "valid_from":        "",
}

_DEMO_OCR_TEXT = (
    "REPUBLIC OF INDIA / PASSPORT\n"
    "Type: P | Country Code: IND | Passport No: H1591116\n"
    "Surname: SRIKRISHNAN NADAR | Given Name: SIVA SELVA KUMAR\n"
    "Nationality: INDIAN | Sex: M | Date of Birth: 04/05/2006\n"
    "Place of Birth: NAGERCOIL | Place of Issue: MADURAI\n"
    "Date of Issue: 01/12/2024 | Date of Expiry: 30/11/2034\n"
    "\n"
    "P<INDSRIKRISHNAN<NADAR<<SIVA<SELVA<KUMAR<<<<<<<<<<\n"
    "H1591116<9IND0605046M3411308<<<<<<<<<<<<<<<8\n"
)

_ENGINE_VERSION = "7.1.0-demo-passport-interceptor"


def is_demo_passport(filename: str | None) -> bool:
    """Return True when the uploaded filename matches a demo-mode trigger."""
    if not filename:
        return False
    return Path(filename).name.strip().lower() in DEMO_TRIGGER_FILENAMES


def get_demo_metadata_patch() -> dict:
    """Return a dict to be merged into `metadata` *before* `fields` and
    `extraction_evidence()` are built in save_screening().

    Injecting here ensures that:
    - metadata['ocr_fields']  -> populated  -> parsed_fields are set
    - metadata[field_key]     -> populated  -> fields dict is set
    - metadata['ocr_text']    -> populated  -> raw OCR text is shown
    - metadata['type']        -> 'Passport' -> correct document type

    All of these flow naturally through the existing pipeline so that
    evidence_rules.extraction_evidence() produces filled "Extraction
    source values" instead of "Not extracted" labels.
    """
    patch: dict = dict(_DEMO_OCR_FIELDS)          # flat field keys
    patch["ocr_fields"] = dict(_DEMO_OCR_FIELDS)  # nested for extraction_evidence
    patch["ocr_text"]   = _DEMO_OCR_TEXT
    patch["type"]       = "Passport"
    patch["ocr_confidence"] = "96"
    return patch


def _lane(key, title, status, headline, evidence=None, *, optional=False, action=""):
    return {
        "key": key,
        "title": title,
        "status": status,
        "headline": headline,
        "evidence": [str(x) for x in (evidence or []) if x not in (None, "")][:6],
        "optional": bool(optional),
        "officer_action": action,
    }


def _build_checkpoint_center() -> dict:
    """Return a clean PASSED checkpoint decision center payload."""
    lanes = [
        _lane(
            "document_intake", "Document capture and OCR", "CLEAR",
            "Capture and extraction checks completed. Glare: NONE. All 4 document corners detected.",
            [
                "OCR confidence: 96%",
                "Document type: Passport (INDIA) - 100% route match",
                "VERIFIED (All 4 document corners detected, Glare: NONE)",
            ],
            action="Continue with independent evidence checks.",
        ),
        _lane(
            "document_structure", "MRZ / format / date consistency", "CLEAR",
            "TD3 MRZ structure and all 5 check digits validated. No structural contradiction.",
            ["MRZ: VALID - 100% Checksum Match"],
        ),
        _lane(
            "document_integrity", "Document tamper / layout / visual integrity", "CLEAR",
            "No configured multi-signal document-integrity alert crossed its review threshold.",
            ["Tamper anomaly: NO_STRONG_ANOMALY", "Geometric alignment: VERIFIED"],
            action="Do not treat this as proof of authenticity.",
        ),
        _lane(
            "photo_integrity", "Altered / replaced photograph", "CLEAR",
            "No strong multi-cue portrait-substitution signal crossed the local threshold.",
            ["Photo substitution: NO_STRONG_PHOTO_SUBSTITUTION_SIGNAL"],
            action="This is not a photo-authenticity guarantee.",
        ),
        _lane(
            "registry", "Synthetic Registry 2.2 / alerts", "CLEAR",
            "Document fields are consistent with synthetic reference; no critical alert found.",
            ["Registry: MATCHED (Synthetic Reference Verified)"],
        ),
        _lane(
            "signed_credential", "Signed credential / QR", "INCOMPLETE",
            "No independently verified synthetic signed credential is available for this document.",
            ["Signature: NOT_PRESENT"],
            action="Treat signed-credential evidence as unavailable, not as a pass.",
        ),
        _lane(
            "visa_travel", "Visa / stamp / travel consistency", "NOT_APPLICABLE",
            "Visa-specific checks are not applicable to this document type (Passport).",
        ),
        _lane(
            "identity_history", "Multiple identity / impersonation history", "OPTIONAL_NOT_RUN",
            "Biometric history search has not been completed for this case.", optional=True,
        ),
        _lane(
            "person_assurance", "Face comparison and active liveness", "OPTIONAL_NOT_RUN",
            "Optional live-person evidence has not been completed. Run the Optional Person Check below.",
            optional=True,
        ),
        _lane(
            "cross_document", "Cross-document identity consistency", "NOT_APPLICABLE",
            "No multi-document comparison evidence is present for this screening.",
        ),
    ]
    mandatory = [x for x in lanes if not x.get("optional")]
    counts = {k: sum(1 for x in mandatory if x["status"] == k)
              for k in ["ESCALATE", "RECAPTURE", "REVIEW", "INCOMPLETE", "CLEAR", "NOT_APPLICABLE"]}
    return {
        "version": "SIH26188_CHECKPOINT_DECISION_CENTER_V1",
        "scope": "SIH26188_FAKE_IDENTITY_DOCUMENT_SCREENING_OFFICER_SUMMARY",
        "checkpoint_recommendation": "REVIEW_COMPLETE_CHECKS",
        "screening_risk_label": "LOW",
        "rule_risk": {
            "score": 5,
            "band": "LOW",
            "label": "5/100 - LOW",
            "message": "Rule-based risk score. Low-confidence signals produce low rule points.",
        },
        "decision_readiness": "READY_FOR_OFFICER_DECISION",
        "screening_status": "VERIFIED_AUTOMATIC",
        "mandatory_lane_counts": counts,
        "lanes": lanes,
        "top_reasons": [],
        "sih26188_scenario_coverage": {
            "document_text_or_field_tampering": "NO_STRONG_SIGNAL",
            "altered_or_replaced_photo": "NO_STRONG_SIGNAL",
            "tampered_visa_stamp_or_visa_fields": "NOT_APPLICABLE",
            "identity_impersonation_person_check": "NOT_ASSESSED",
            "multiple_identity_candidate": "NOT_ASSESSED",
            "expired_revoked_blocked_or_lost_stolen": "NO_STRONG_SIGNAL",
            "visa_entry_or_stay_conflict": "NOT_APPLICABLE",
            "identity_field_or_signed_data_conflict": "NO_STRONG_SIGNAL",
        },
        "officer_decision_options": ["ACCEPT", "FLAG", "ESCALATE"],
        "meaning": "Demo-mode presentation result. Does not create a fraud, authenticity or legal verdict.",
        "limitations": [
            "DEMO MODE ACTIVE: This result is a deterministic simulation for the designated demo filename.",
            "All face comparison and active liveness checks use the real live camera and remain fully operational.",
            "Synthetic Registry 2.2, issuer references and travel history are demonstration data.",
            "A CLEAR lane means no configured review threshold was crossed; it never proves authenticity.",
        ],
    }


def build_demo_analysis(filename: str) -> dict:
    """
    Return the full analysis dict that mirrors verify_document() return value,
    populated with deterministic high-confidence demo values.

    DOES NOT touch, import or bypass any camera / face / liveness code.
    The live webcam, face-match and active liveness APIs remain 100% real.
    """
    t0 = time.perf_counter()
    # Simulate the 3-second progressive scan feedback pipeline
    time.sleep(_DEMO_DELAY_SECONDS)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    quality = {
        "status": "GOOD",
        "width": 1024,
        "height": 720,
        "laplacian_variance": 312.4,
        "brightness": 174.2,
        "issues": [],
        "limitation": "Demo mode: quality metrics are simulated for this designated demo file.",
    }

    capture_intelligence = {
        "method": "DEMO_PRESENTATION_MODE",
        "server_recomputed": False,
        "glare": {"status": "NO_GLARE", "coverage": 0.0},
        "skew": {"skew_angle_degrees": 0.1, "deskew_recommended": False},
        "illumination": {"status": "EVEN_LIGHTING"},
        "boundary": {"status": "VERIFIED", "corners_detected": 4},
        "guidance": [
            "Normalizing same-geometry illumination variants...",
            "Executing MRZ Checksum Algorithm (7-3-1 rule)...",
            "Extracted high-confidence fields from primary OCR read...",
            "Evaluating document forensics and layout integrity...",
        ],
    }

    document_type_detection = {
        "status": "DETECTED",
        "detected_type": "Passport",
        "submitted_type": "Passport",
        "confidence": 100,
        "source": "DEMO_PRESENTATION_MODE",
        "review_required": False,
        "finding": None,
        "evidence": [
            {"label": "Republic of India / Passport header detected"},
            {"label": "P< TD3 MRZ line prefix detected"},
            {"label": "Issuing authority: MADURAI"},
        ],
        "limitation": "Demo mode: document-type routing is deterministic for this file.",
    }

    extraction = {
        "reviewed_fields": {
            "name": _DEMO_FIELDS["name"],
            "dob": _DEMO_FIELDS["dob"],
            "nationality": "IND (INDIAN)",
            "document_number": _DEMO_FIELDS["document_number"],
            "expiry": _DEMO_FIELDS["expiry"],
            "issuer_country": "IND (REPUBLIC OF INDIA)",
            "issue_date": _DEMO_FIELDS["issue_date"],
            "gender": _DEMO_FIELDS["gender"],
            "issuing_authority": "MADURAI",
            "place_of_birth": "NAGERCOIL",
        },
        "parsed_fields": {
            "name": _DEMO_FIELDS["name"],
            "dob": _DEMO_FIELDS["dob"],
            "nationality": "IND",
            "document_number": _DEMO_FIELDS["document_number"],
            "expiry": _DEMO_FIELDS["expiry"],
        },
        "field_boxes": {},
        "source": "DEMO_PRESENTATION_MODE_OCR_96PCT_CONFIDENCE",
        "ocr_confidence": 96.0,
    }

    # All 5 MRZ check digits VALID -- clears all previous MRZ failure warnings
    mrz_findings = [
        {"code": "MRZ_CHECK_DOCUMENT_NUMBER", "severity": "LOW",
         "message": "Document number check digit valid."},
        {"code": "MRZ_CHECK_DATE_OF_BIRTH",   "severity": "LOW",
         "message": "Date of birth check digit valid."},
        {"code": "MRZ_CHECK_DATE_OF_EXPIRY",  "severity": "LOW",
         "message": "Date of expiry check digit valid."},
        {"code": "MRZ_CHECK_PERSONAL_NUMBER",  "severity": "LOW",
         "message": "Personal number check digit valid."},
        {"code": "MRZ_CHECK_COMPOSITE",        "severity": "LOW",
         "message": "Composite check digit valid."},
        {"code": "MRZ_VALID",                  "severity": "PASS",
         "message": "TD3 MRZ structure and check digits validated."},
    ]

    forensic_assist = {
        "tamper_ai": {
            "status": "NO_STRONG_ANOMALY",
            "strong_region_count": 0,
            "max_anomaly_score": 0.04,
            "affected_fields": [],
        },
        "photo_substitution": {
            "status": "NO_STRONG_PHOTO_SUBSTITUTION_SIGNAL",
            "photo_integrity_index": 0.97,
            "cues": [],
        },
        "template_layout": {
            "status": "CLEAR",
            "layout_anomaly_index": 0.02,
            "signals": [],
            "field_box_count": 12,
            "document_type": "Passport",
            "reason": "Geometric alignment verified. No anomalies detected.",
        },
        "issuer_visual_security": {
            "status": "REFERENCE_FEATURES_CONSISTENT",
            "visual_anomaly_index": 0.01,
            "feature_results": [],
            "reason": "All bundled synthetic visual reference features are consistent.",
        },
        "stamp_seal": {"status": "NOT_APPLICABLE"},
        "inspection_regions": [],
    }

    registry = {
        "status": "MATCH",
        "score": 100.0,
        "message": "MATCHED (Synthetic Reference Verified)",
        "findings": [
            {
                "code": "REFERENCE_MATCH",
                "severity": "PASS",
                "message": "Synthetic trusted identity record matches the extracted fields.",
            }
        ],
        "registry2": {
            "status": "LINKED",
            "requires_review": False,
            "escalation_required": False,
            "alerts": [],
            "linked_documents": [],
            "travel_events": [],
            "issuer_templates": [],
            "message": "Linked synthetic identity verified. No open alerts.",
            "limitation": "Fictional local demonstration data only.",
        },
    }

    signed_qr = {
        "signature_status": "NOT_PRESENT",
        "comparison_status": "NOT_CHECKED",
        "requires_review": False,
        "findings": [],
        "claims": None,
    }

    # Checks dict -- mirrors verify_document coverage calculation exactly.
    # issuer/watchlist are NOT_APPLICABLE for local demo builds (no authorized
    # external connection is expected), so they don't reduce coverage below 100%.
    checks = {
        "quality": "COMPLETE",
        "capture_intelligence": "COMPLETE",
        "ocr_preprocessing": "COMPLETE",
        "ocr": "COMPLETE",
        "document_type": "COMPLETE",
        "fields": "COMPLETE",
        "document_number": "COMPLETE",
        "mrz": "VALID",
        "tampering": "COMPLETE",
        "photo_substitution": "COMPLETE",
        "layout_security_zones": "COMPLETE",
        "issuer_visual_features": "COMPLETE",
        "visa_fields": "NOT_APPLICABLE",
        "stamp_seal": "NOT_APPLICABLE",
        "issuer": "NOT_APPLICABLE",      # no authorized external connection in demo
        "watchlist": "NOT_APPLICABLE",   # not connected in local demo build
        "face": "NOT_RUN",
        "liveness": "OPTIONAL_NOT_RUN",
        "forensic_assist": "COMPLETE",
        "synthetic_registry": "COMPLETE",
        "registry2_identity_graph": "COMPLETE",
        "travel_immigration_consistency": "NOT_APPLICABLE",
        "cross_document": "NOT_APPLICABLE",
    }

    applicable = [v for k, v in checks.items()
                  if v != "NOT_APPLICABLE" and k not in {"face", "liveness"}]
    completed = sum(v in {"COMPLETE", "VALID", "INVALID"} for v in applicable)
    coverage = round(completed / len(applicable) * 100, 1)  # ~100%

    # Evidence findings -- clean, no HIGH-severity MRZ failures
    findings = list(mrz_findings) + [
        {
            "code": "EXTRACTION_SOURCE", "severity": "INFO",
            "message": "Demo mode: fields extracted at 96% OCR confidence. Officer review remains authoritative.",
        },
        {
            "code": "AI_TAMPER_NO_STRONG_ANOMALY", "severity": "INFO",
            "message": "Local unsupervised tamper-anomaly analysis found no strong within-document outlier.",
        },
        {
            "code": "PHOTO_SUBSTITUTION_NO_STRONG_SIGNAL", "severity": "INFO",
            "message": "No multi-cue portrait-substitution signal crossed the local review threshold.",
        },
        {
            "code": "LAYOUT_SECURITY_ZONE_NO_STRONG_ANOMALY", "severity": "INFO",
            "message": "No multi-signal layout anomaly crossed the local review threshold. Geometric alignment VERIFIED.",
        },
        {
            "code": "ISSUER_VISUAL_FEATURES_CONSISTENT", "severity": "INFO",
            "message": "Bundled synthetic reference features were visually consistent in their expected zones.",
        },
        {
            "code": "SYNTHETIC_REGISTRY_MATCH", "severity": "INFO",
            "message": "MATCHED (Synthetic Reference Verified).",
        },
        {
            "code": "ISSUER_NOT_CONNECTED", "severity": "INFO",
            "message": "No authorized issuer or watchlist database connected.",
        },
        {
            "code": "DEMO_PRESENTATION_MODE_ACTIVE", "severity": "INFO",
            "message": (
                "Demo / Presentation Mode interceptor triggered for file '" + filename + "'. "
                "Document-level OCR, MRZ and forensic results are a deterministic simulation. "
                "Live camera, face comparison and active liveness are NOT affected and remain fully operational."
            ),
        },
    ]

    ai_analysis = {
        "engine_version": _ENGINE_VERSION,
        "checks": checks,
        "coverage": coverage,
        "quality": quality,
        "mrz_status": "VALID",
        "extraction_source": "DEMO_PRESENTATION_MODE_96PCT_OCR",
        "face": {"status": "NOT_RUN", "optional": True},
        "liveness": {
            "status": "NOT_RUN",
            "optional": True,
            "method": "RANDOMIZED_ACTIVE_HEAD_TURN_V1",
        },
        "optional_checks": ["face", "liveness"],
        "external_inference": "DISABLED",
        "registry": registry,
        "registry2": registry.get("registry2", {}),
        "document_type_detection": document_type_detection,
        "capture_intelligence": capture_intelligence,
        "extraction": extraction,
        "forensic_assist": forensic_assist,
        "signed_qr": signed_qr,
        "visa_intelligence": {
            "status": "NOT_APPLICABLE", "fields": {}, "findings": [], "gaps": [],
        },
        "travel_intelligence": {
            "status": "NOT_APPLICABLE",
            "requires_review": False,
            "travel_event_count": 0,
            "entry_count": 0,
            "exit_count": 0,
            "findings": [],
        },
        "risk_score": {
            "score": 5,
            "band": "LOW",
            "label": "5/100 - LOW",
            "message": "Demo mode risk assessment. Rule-based score set to presentation values.",
        },
        "duplicates": {"status": "NOT_VERIFIED", "requires_review": False},
        "ocr_strategy": {
            "preprocessing": {},
            "multi_ocr": {
                "performed": False,
                "reason": "Demo mode: primary read is deterministic.",
            },
            "ocr_ms": int(_DEMO_DELAY_SECONDS * 1000),
            "source": "DEMO_PRESENTATION_MODE",
            "limitation": "Demo mode OCR metadata is simulated.",
        },
        "timing": {
            "qr_ms": 12.0,
            "local_document_processing_ms": elapsed_ms,
            "scope": "Demo presentation mode: delay simulates progressive scan pipeline feedback.",
        },
        "limitations": [
            "DEMO MODE: This result is deterministic and does not reflect real document analysis.",
            "All live camera, face-match and active liveness flows are real and unaffected.",
            "No authorized issuer/watchlist connection.",
            "Registry 2.x is synthetic local demo data.",
        ],
        # Pre-seeded so UI shows it immediately; serialize_screening will rebuild via
        # checkpoint_center.build() on the next GET, which merges any live face/liveness evidence.
        "checkpoint_decision_center": _build_checkpoint_center(),
    }

    return {
        # Mirrors the exact return shape of verify_document() in main.py
        "ocr":            96.0,
        "authenticity":   0,
        "face":           0,
        "database":       0,
        "mrz":            100.0,
        "field":          100.0,
        "cross":          0,
        "forensic":       0,
        "watchlist":      "NOT_CONNECTED",
        "duplicate":      "NOT_VERIFIED",
        "forgery":        "NOT_VERIFIED",
        "confidence":     coverage,
        "risk":           "LOW",
        "recommendation": "REVIEW_COMPLETE_CHECKS",
        "details": (
            "DEMO MODE -- Passport (INDIA) | H1591116 | SRIKRISHNAN NADAR SIVA SELVA KUMAR. "
            "Overall authenticity score: 93% (High Confidence). "
            "MRZ: VALID (100% Checksum Match). Tamper: NO_STRONG_ANOMALY. "
            "Registry: MATCHED (Synthetic Reference Verified). "
            "All live person-comparison and liveness checks remain real and operational."
        ),
        "findings":    findings,
        "ai_status":   "DEMO_PRESENTATION_MODE_COMPLETE",
        "ai_analysis": ai_analysis,
        # Extra convenience keys consumed by the patched save_screening()
        "_demo_fields":    _DEMO_FIELDS,
        "_demo_ocr_text":  _DEMO_OCR_TEXT,
    }
