"""BHARATSHIELD v6.8 SIH26188 Checkpoint Decision Center.

This module only summarizes already-produced evidence.  It does not create a new
fraud/authenticity verdict and it does not override the officer workflow.
"""
from __future__ import annotations

VERSION = "SIH26188_CHECKPOINT_DECISION_CENTER_V1"

_REVIEW_CODES = {
    "AI_TAMPER_ANOMALY", "PHOTO_SUBSTITUTION_REVIEW", "STAMP_SEAL_TAMPER_REVIEW",
    "LAYOUT_SECURITY_ZONE_REVIEW", "ISSUER_VISUAL_FEATURE_REVIEW",
    "BIOMETRIC_IDENTITY_HISTORY_CANDIDATE", "DOCUMENT_TYPE_CONFLICT",
    "VISA_VALIDITY_ORDER_CONFLICT", "VISA_ENTRIES_UNRECOGNIZED", "VISA_ISSUE_AFTER_VALID_FROM",
    "TRAVEL_VISA_ENTRY_LIMIT_CONFLICT", "TRAVEL_ENTRY_BEFORE_VISA_VALID_FROM",
    "TRAVEL_ENTRY_AFTER_VISA_EXPIRY", "TRAVEL_ENTRY_BEFORE_VISA_ISSUE",
    "TRAVEL_VISA_ISSUED_AFTER_ENTRY", "TRAVEL_STAY_DURATION_EXCEEDED",
    "TRAVEL_EVENT_IN_FUTURE", "HISTORY_IDENTITY_CONFLICT", "SIGNED_DATA_CONFLICT",
}


def _code_set(findings):
    return {str(x.get("code", "")) for x in (findings or [])}


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


def _finding_priority(f):
    sev = str(f.get("severity", "")).upper()
    status = str(f.get("status", "")).upper()
    if sev == "CRITICAL": return 100
    if sev == "HIGH": return 90
    if status == "REVIEW_REQUIRED": return 80
    if sev == "MEDIUM": return 70
    if sev == "QUALITY": return 60
    return 0


def build(*, recommendation: str, risk: str, screening_status: str, document_type: str,
          findings: list[dict], evidence: dict, ocr_confidence: float = 0.0) -> dict:
    """Build a dynamic judge/officer summary from saved evidence.

    The result deliberately distinguishes screening recommendation, evidence
    completeness and optional biometric evidence.  No lane labelled CLEAR means
    that a document/person is authentic.
    """
    evidence = evidence or {}
    findings = findings or []
    codes = _code_set(findings)
    checks = evidence.get("checks") or {}
    quality = evidence.get("quality") or {}
    capture = evidence.get("capture_intelligence") or {}
    dtype = evidence.get("document_type_detection") or {}
    registry = evidence.get("registry") or {}
    registry2 = registry.get("registry2") or {}
    qr = evidence.get("signed_qr") or {}
    forensic = evidence.get("forensic_assist") or {}
    tamper = forensic.get("tamper_ai") or {}
    photo = forensic.get("photo_substitution") or {}
    stamp = forensic.get("stamp_seal") or {}
    layout = forensic.get("template_layout") or {}
    visual = forensic.get("issuer_visual_security") or {}
    visa = evidence.get("visa_intelligence") or {}
    travel = evidence.get("travel_intelligence") or {}
    duplicates = evidence.get("duplicates") or {}
    face = evidence.get("face") or {}
    live = evidence.get("liveness") or {}
    identity_history = evidence.get("identity_history") or {}
    risk_score = evidence.get("risk_score") or {}

    lanes = []

    # 1. Intake / OCR / routing
    if quality.get("status") == "RECAPTURE" or (capture.get("glare") or {}).get("status") == "RECAPTURE_RECOMMENDED" or float(ocr_confidence or 0) < 35:
        lanes.append(_lane("document_intake", "Document capture & OCR", "RECAPTURE", "Capture/OCR quality is not reliable enough for screening.",
                           [f"OCR confidence: {round(float(ocr_confidence or 0),1)}%", "Recapture-quality issue detected"], action="Recapture the original document before relying on extracted fields."))
    elif dtype.get("review_required") or checks.get("fields") == "INCOMPLETE" or float(ocr_confidence or 0) < 65:
        lanes.append(_lane("document_intake", "Document capture & OCR", "REVIEW", "OCR/type evidence needs officer confirmation.",
                           [f"OCR confidence: {round(float(ocr_confidence or 0),1)}%", f"Type routing: {dtype.get('status','UNKNOWN')}"], action="Compare extracted fields and document type with the original."))
    else:
        lanes.append(_lane("document_intake", "Document capture & OCR", "CLEAR", "Capture and extraction checks completed without a strong intake warning.",
                           [f"OCR confidence: {round(float(ocr_confidence or 0),1)}%", f"Type: {document_type}"], action="Continue with independent evidence checks."))

    # 2. Structure/MRZ/date
    mrz = str(checks.get("mrz", "NOT_APPLICABLE"))
    date_codes = {"DOCUMENT_EXPIRED", "DOB_IN_FUTURE", "ISSUE_DATE_IN_FUTURE", "DATE_ORDER_CONFLICT", "DATE_UNREADABLE"}
    struct_review = bool(codes & date_codes) or mrz == "INVALID"
    if struct_review:
        lanes.append(_lane("document_structure", "MRZ / format / date consistency", "REVIEW", "Machine-readable or date/format consistency needs review.",
                           [f"MRZ: {mrz}"] + sorted(codes & date_codes), action="Verify machine-readable and visible fields against the original."))
    elif mrz in {"NOT_DETECTED", "INCONCLUSIVE"}:
        lanes.append(_lane("document_structure", "MRZ / format / date consistency", "INCOMPLETE", "Passport MRZ evidence is incomplete.", [f"MRZ: {mrz}"], action="Inspect/recapture the MRZ zone."))
    else:
        lanes.append(_lane("document_structure", "MRZ / format / date consistency", "CLEAR", "No strong structural/date contradiction was produced by configured checks.", [f"MRZ: {mrz}"]))

    # 3. Forensic integrity
    forensic_review = any(x.get("status") == "REVIEW_REQUIRED" for x in [tamper, layout, visual])
    if forensic_review:
        ev=[]
        if tamper.get("status") == "REVIEW_REQUIRED": ev.append(f"Tamper anomaly index: {tamper.get('max_anomaly_score','—')}")
        if layout.get("status") == "REVIEW_REQUIRED": ev.append(f"Layout anomaly index: {layout.get('layout_anomaly_index','—')}")
        if visual.get("status") == "REVIEW_REQUIRED": ev.append(f"Visual-reference anomaly index: {visual.get('visual_anomaly_index','—')}")
        lanes.append(_lane("document_integrity", "Document tamper / layout / visual integrity", "REVIEW", "One or more independent document-integrity aids produced a review signal.", ev, action="Inspect highlighted regions and corroborate with registry/MRZ/signed evidence."))
    elif tamper.get("status") == "INCONCLUSIVE" or layout.get("status") == "INCONCLUSIVE":
        lanes.append(_lane("document_integrity", "Document tamper / layout / visual integrity", "INCOMPLETE", "Document-integrity evidence is inconclusive.", action="Use manual forensic views and original-document inspection."))
    else:
        lanes.append(_lane("document_integrity", "Document tamper / layout / visual integrity", "CLEAR", "No configured multi-signal document-integrity alert crossed its review threshold.", action="Do not treat this as proof of authenticity."))

    # 4. Photo integrity
    if photo.get("status") == "REVIEW_REQUIRED":
        lanes.append(_lane("photo_integrity", "Altered / replaced photograph", "REVIEW", "Portrait-region integrity requires substitution review.",
                           [f"Photo-integrity index: {photo.get('photo_integrity_index','—')}"] + list(photo.get("cues") or []), action="Compare portrait boundaries, face evidence and registry identity."))
    elif photo.get("status") == "NO_PORTRAIT_DETECTED":
        lanes.append(_lane("photo_integrity", "Altered / replaced photograph", "NOT_APPLICABLE", "No document portrait was localized for this check."))
    elif photo.get("status") in {"MODEL_ERROR", "MODEL_UNAVAILABLE", "INCONCLUSIVE", "INCONCLUSIVE_MULTIPLE_PORTRAITS"}:
        lanes.append(_lane("photo_integrity", "Altered / replaced photograph", "INCOMPLETE", "Portrait substitution analysis is inconclusive.", action="Inspect the portrait manually."))
    else:
        lanes.append(_lane("photo_integrity", "Altered / replaced photograph", "CLEAR", "No strong multi-cue portrait-substitution signal crossed the local threshold.", action="This is not a photo-authenticity guarantee."))

    # 5. Synthetic registry / alert status
    reg_status = str(registry.get("status", "NOT_CHECKED"))
    if registry2.get("escalation_required") or reg_status in {"BLOCKED", "REVOKED"}:
        alerts = [f"{a.get('alert_type')}: {a.get('reason')}" for a in registry2.get("alerts", []) if a.get("status") == "OPEN"]
        lanes.append(_lane("registry", "Synthetic Registry 2.2 / alerts", "ESCALATE", "A blocked/revoked/lost-stolen or critical synthetic reference condition requires escalation.", alerts or [f"Registry: {reg_status}"], action="Escalate under the prototype workflow; verify through authorized systems in production."))
    elif registry2.get("requires_review") or reg_status in {"CONFLICT", "REVIEW_REQUIRED", "AMBIGUOUS"}:
        lanes.append(_lane("registry", "Synthetic Registry 2.2 / alerts", "REVIEW", "Synthetic reference identity/document evidence contains a conflict or open review alert.", [f"Registry: {reg_status}"], action="Review linked identity, documents and alerts."))
    elif reg_status in {"NOT_FOUND", "NOT_CHECKED", "UNAVAILABLE", "ARCHIVED"}:
        lanes.append(_lane("registry", "Synthetic Registry 2.2 / alerts", "INCOMPLETE", "A complete synthetic reference match is unavailable.", [f"Registry: {reg_status}"], action="Do not infer authenticity from missing reference data."))
    else:
        lanes.append(_lane("registry", "Synthetic Registry 2.2 / alerts", "CLEAR", "Document fields are consistent with the selected synthetic reference and no critical linked alert was found.", [f"Registry: {reg_status}"]))

    # 6. Signed QR
    sig = str(qr.get("signature_status", "NOT_PRESENT"))
    comp = str(qr.get("comparison_status", "NOT_CHECKED"))
    if sig == "SIGNATURE_INVALID" or comp == "SIGNED_DATA_CONFLICT":
        lanes.append(_lane("signed_credential", "Signed credential / QR", "REVIEW", "Signed credential evidence conflicts or fails cryptographic verification.", [f"Signature: {sig}", f"Comparison: {comp}"], action="Inspect signed payload, printed fields and registry version separately."))
    elif qr.get("requires_review"):
        lanes.append(_lane("signed_credential", "Signed credential / QR", "REVIEW", "Signed credential evidence requires officer review.", [f"Signature: {sig}", f"Comparison: {comp}"]))
    elif sig == "SIGNATURE_VALID":
        lanes.append(_lane("signed_credential", "Signed credential / QR", "CLEAR", "Configured synthetic signature verified; field comparison must still be considered separately.", [f"Signature: {sig}", f"Comparison: {comp}"]))
    else:
        lanes.append(_lane("signed_credential", "Signed credential / QR", "INCOMPLETE", "No independently verified synthetic signed credential is available.", [f"Signature: {sig}"], action="Treat signed-credential evidence as unavailable, not as a pass."))

    # 7. Visa / stamp / travel
    if document_type == "Visa" or visa.get("status") not in {None, "NOT_APPLICABLE"}:
        if stamp.get("status") == "REVIEW_REQUIRED" or visa.get("status") == "REVIEW_REQUIRED" or travel.get("requires_review"):
            e=[]
            if visa.get("status"): e.append("Visa fields: "+str(visa.get("status")))
            if stamp.get("status"): e.append("Stamp/seal: "+str(stamp.get("status")))
            if travel.get("status"): e.append("Travel consistency: "+str(travel.get("status")))
            lanes.append(_lane("visa_travel", "Visa / stamp / travel consistency", "REVIEW", "Visa entitlement, stamp or travel-history evidence requires review.", e, action="Check visa validity, entries, stay duration, stamp evidence and linked passport."))
        elif visa.get("status") == "PARTIAL" or travel.get("status") == "INCONCLUSIVE_NO_HISTORY":
            lanes.append(_lane("visa_travel", "Visa / stamp / travel consistency", "INCOMPLETE", "Visa/travel evidence is incomplete.", [str(visa.get("status","")), str(travel.get("status",""))]))
        else:
            lanes.append(_lane("visa_travel", "Visa / stamp / travel consistency", "CLEAR", "No configured visa/stamp/travel contradiction was found in the synthetic evidence.", [str(travel.get("status",""))]))
    else:
        lanes.append(_lane("visa_travel", "Visa / stamp / travel consistency", "NOT_APPLICABLE", "Visa-specific checks are not applicable to this document."))

    # 8. Local screening history
    if identity_history.get("requires_review") or "BIOMETRIC_IDENTITY_HISTORY_CANDIDATE" in codes:
        lanes.append(_lane("identity_history", "Multiple identity / impersonation history", "REVIEW", "A liveness-passed biometric-history candidate has different identity/document attributes.",
                           [f"Review candidates: {identity_history.get('review_candidate_count',0)}"], optional=True, action="Compare linked screenings and independent identity evidence; similarity is not an identity verdict."))
    elif duplicates.get("requires_review") or "HISTORY_IDENTITY_CONFLICT" in codes:
        lanes.append(_lane("identity_history", "Multiple identity / impersonation history", "REVIEW", "Local document/history evidence contains an identity inconsistency.", optional=True, action="Inspect prior screening candidates."))
    elif identity_history.get("status") in {"NO_SIMILAR_TEMPLATE_CANDIDATES", "CANDIDATES_FOUND"}:
        lanes.append(_lane("identity_history", "Multiple identity / impersonation history", "CLEAR", "No review-level multiple-identity biometric candidate was produced.", [f"Status: {identity_history.get('status')}"] , optional=True))
    else:
        lanes.append(_lane("identity_history", "Multiple identity / impersonation history", "OPTIONAL_NOT_RUN", "Biometric history search has not been completed for this case.", optional=True))

    # 9. Face + liveness (optional identity evidence)
    live_status = str(live.get("status", "NOT_RUN"))
    face_status = str(face.get("status", "NOT_RUN"))
    if live_status == "PASSED_ACTIVE_CHALLENGE" and face_status == "REVIEW_REQUIRED":
        lanes.append(_lane("person_assurance", "Face comparison + active liveness", "OPTIONAL_REVIEW_ONLY", "Quality-gated SFace similarity was measured and active liveness passed; similarity remains uncalibrated.",
                           [f"SFace cosine similarity: {face.get('cosine_similarity','—')}", "Liveness: PASSED_ACTIVE_CHALLENGE"], optional=True, action="Use this only as supporting person evidence; do not convert the similarity into an identity probability."))
    elif live_status in {"RETRY_REQUIRED", "MODEL_ERROR", "MODEL_UNAVAILABLE"} or face_status in {"INCONCLUSIVE", "MODEL_ERROR", "MODEL_UNAVAILABLE"}:
        lanes.append(_lane("person_assurance", "Face comparison + active liveness", "INCOMPLETE", "Optional person evidence is inconclusive or needs recapture.", [f"Face: {face_status}", f"Liveness: {live_status}"], optional=True))
    elif face_status == "SKIPPED":
        lanes.append(_lane("person_assurance", "Face comparison + active liveness", "OPTIONAL_NOT_RUN", "Officer skipped the optional person comparison.", optional=True))
    else:
        lanes.append(_lane("person_assurance", "Face comparison + active liveness", "OPTIONAL_NOT_RUN", "Optional live-person evidence has not been completed.", optional=True))

    # 10. Cross-document consistency
    cross_codes = sorted(c for c in codes if c.startswith("CROSS_"))
    if any((f.get("code","").startswith("CROSS_") and f.get("status") in {"CONFLICT", "REVIEW_REQUIRED"}) for f in findings):
        lanes.append(_lane("cross_document", "Cross-document identity consistency", "REVIEW", "Submitted documents contain cross-document conflicts or close-match review signals.", cross_codes, action="Compare the linked fields across all submitted documents."))
    elif checks.get("cross_document") in {"INCOMPLETE", "INCONCLUSIVE"}:
        lanes.append(_lane("cross_document", "Cross-document identity consistency", "INCOMPLETE", "Cross-document evidence is incomplete."))
    elif cross_codes:
        lanes.append(_lane("cross_document", "Cross-document identity consistency", "CLEAR", "No strong cross-document conflict was produced.", cross_codes))
    else:
        lanes.append(_lane("cross_document", "Cross-document identity consistency", "NOT_APPLICABLE" if evidence.get("checks") and not cross_codes else "INCOMPLETE", "No multi-document comparison evidence is present for this screening."))

    # SIH26188 scenario coverage.  "REVIEW_SIGNAL" means evidence to inspect, never fraud confirmed.
    scenario = {
        "document_text_or_field_tampering": "REVIEW_SIGNAL" if bool(codes & {"AI_TAMPER_ANOMALY","LAYOUT_SECURITY_ZONE_REVIEW","ISSUER_VISUAL_FEATURE_REVIEW"}) else "NO_STRONG_SIGNAL",
        "altered_or_replaced_photo": "REVIEW_SIGNAL" if "PHOTO_SUBSTITUTION_REVIEW" in codes else ("NOT_ASSESSED" if photo.get("status") in {None,"NO_PORTRAIT_DETECTED","INCONCLUSIVE","MODEL_UNAVAILABLE","MODEL_ERROR"} else "NO_STRONG_SIGNAL"),
        "tampered_visa_stamp_or_visa_fields": "REVIEW_SIGNAL" if bool(codes & {"STAMP_SEAL_TAMPER_REVIEW","VISA_VALIDITY_ORDER_CONFLICT","VISA_ENTRIES_UNRECOGNIZED","VISA_ISSUE_AFTER_VALID_FROM"}) else ("NOT_APPLICABLE" if document_type != "Visa" else "NO_STRONG_SIGNAL"),
        "identity_impersonation_person_check": "REVIEW_ONLY" if face_status == "REVIEW_REQUIRED" else ("NOT_ASSESSED" if face_status in {"NOT_RUN","SKIPPED",""} else "INCONCLUSIVE"),
        "multiple_identity_candidate": "REVIEW_SIGNAL" if identity_history.get("requires_review") or "BIOMETRIC_IDENTITY_HISTORY_CANDIDATE" in codes else ("NO_REVIEW_CANDIDATE" if identity_history.get("status") in {"NO_SIMILAR_TEMPLATE_CANDIDATES","CANDIDATES_FOUND"} else "NOT_ASSESSED"),
        "expired_revoked_blocked_or_lost_stolen": "ESCALATION_SIGNAL" if registry2.get("escalation_required") or bool(codes & {"DOCUMENT_EXPIRED","REGISTRY2_ALERT_LOST_STOLEN_DOCUMENT","REGISTRY2_ALERT_DOCUMENT_BLOCKED","REGISTRY2_ALERT_DOCUMENT_REVOKED"}) or reg_status in {"BLOCKED","REVOKED","EXPIRED"} else "NO_STRONG_SIGNAL",
        "visa_entry_or_stay_conflict": "REVIEW_SIGNAL" if any(c.startswith("TRAVEL_") for c in codes) else ("NOT_APPLICABLE" if document_type != "Visa" else "NO_STRONG_SIGNAL"),
        "identity_field_or_signed_data_conflict": "REVIEW_SIGNAL" if reg_status in {"CONFLICT","REVIEW_REQUIRED"} or comp == "SIGNED_DATA_CONFLICT" else "NO_STRONG_SIGNAL",
    }

    priority_findings = sorted([f for f in findings if _finding_priority(f) > 0], key=_finding_priority, reverse=True)
    top_reasons=[]
    seen=set()
    for f in priority_findings:
        item={"code":f.get("code",""),"severity":f.get("severity",""),"message":f.get("message","")}
        key=(item["code"],item["message"])
        if key in seen: continue
        seen.add(key); top_reasons.append(item)
        if len(top_reasons)>=6: break

    recommendation = recommendation or "MANUAL_REVIEW"
    if recommendation == "ESCALATE": readiness="HOLD_FOR_ESCALATION"
    elif recommendation == "RECAPTURE": readiness="RECAPTURE_REQUIRED"
    elif recommendation == "MANUAL_REVIEW": readiness="HUMAN_REVIEW_REQUIRED"
    else: readiness="READY_FOR_OFFICER_DECISION"

    mandatory = [x for x in lanes if not x.get("optional")]
    counts = {k: sum(1 for x in mandatory if x["status"] == k) for k in ["ESCALATE","RECAPTURE","REVIEW","INCOMPLETE","CLEAR","NOT_APPLICABLE"]}
    return {
        "version": VERSION,
        "scope": "SIH26188_FAKE_IDENTITY_DOCUMENT_SCREENING_OFFICER_SUMMARY",
        "checkpoint_recommendation": recommendation,
        "screening_risk_label": risk,
        "rule_risk": risk_score,
        "decision_readiness": readiness,
        "screening_status": screening_status,
        "mandatory_lane_counts": counts,
        "lanes": lanes,
        "top_reasons": top_reasons,
        "sih26188_scenario_coverage": scenario,
        "officer_decision_options": ["ACCEPT","FLAG","ESCALATE"],
        "meaning": "Unified view of already-produced BHARATSHIELD evidence for an authorized officer. It does not create a new fraud, authenticity, identity, admissibility or legal verdict.",
        "limitations": [
            "Synthetic Registry 2.2, issuer references, alerts and travel history are demonstration data, not connected government systems.",
            "AI/forensic signals are prototype review aids; their indices are not fraud probabilities.",
            "SFace similarity and active liveness are supporting biometric evidence, not a calibrated identity decision or certified presentation-attack detection.",
            "A CLEAR lane means no configured review threshold was crossed; it never proves authenticity.",
        ],
    }
