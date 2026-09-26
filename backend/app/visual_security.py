"""Synthetic issuer-template visual feature inspection for BHARATSHIELD v6.6.

This module performs local reference-feature matching only against versioned
*synthetic demo* template assets stored with the application. It is deliberately
not presented as official issuer authentication. Genuine document generations,
printing processes, scans, screenshots and camera captures can vary materially.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np

METHOD = 'LOCAL_SYNTHETIC_ISSUER_VISUAL_FEATURE_MATCH_V1'
ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = ROOT / 'reference_templates'


def _clip_box(box):
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    try:
        x, y, w, h = [float(v) for v in box]
    except (TypeError, ValueError):
        return None
    if not np.isfinite([x, y, w, h]).all() or w <= 0 or h <= 0:
        return None
    x = max(0.0, min(1.0, x)); y = max(0.0, min(1.0, y))
    w = max(0.0, min(1.0 - x, w)); h = max(0.0, min(1.0 - y, h))
    if w <= 0 or h <= 0:
        return None
    return [x, y, w, h]


def _crop(rgb, box, pad=0.018):
    h, w = rgb.shape[:2]
    x, y, bw, bh = box
    x0 = max(0, int(round((x - pad) * w))); y0 = max(0, int(round((y - pad) * h)))
    x1 = min(w, int(round((x + bw + pad) * w))); y1 = min(h, int(round((y + bh + pad) * h)))
    if x1 - x0 < 12 or y1 - y0 < 12:
        return None
    return rgb[y0:y1, x0:x1]


def _load_reference(feature):
    rel = str(feature.get('reference_asset') or '').replace('\\', '/').lstrip('/')
    if not rel or '..' in Path(rel).parts:
        return None, 'INVALID_REFERENCE_PATH'
    path = (REFERENCE_ROOT / rel).resolve()
    if REFERENCE_ROOT.resolve() not in path.parents or not path.is_file():
        return None, 'REFERENCE_ASSET_MISSING'
    data = path.read_bytes()
    expected = str(feature.get('reference_sha256') or '').lower()
    actual = hashlib.sha256(data).hexdigest()
    if expected and expected != actual:
        return None, 'REFERENCE_HASH_MISMATCH'
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None, 'REFERENCE_DECODE_FAILED'
    return image, ''


def _edge_similarity(reference, candidate):
    if reference is None or candidate is None or candidate.size == 0:
        return 0.0
    cand = cv2.cvtColor(candidate, cv2.COLOR_RGB2GRAY) if candidate.ndim == 3 else candidate
    if min(cand.shape[:2]) < 8 or min(reference.shape[:2]) < 8:
        return 0.0
    cand = cv2.resize(cand, (reference.shape[1], reference.shape[0]), interpolation=cv2.INTER_AREA)
    ref_edge = cv2.Canny(reference, 60, 160)
    cand_edge = cv2.Canny(cand, 60, 160)
    # Binary edge agreement is less sensitive to paper tone/brightness than raw pixels.
    union = np.count_nonzero((ref_edge > 0) | (cand_edge > 0))
    if union == 0:
        return 0.0
    inter = np.count_nonzero((ref_edge > 0) & (cand_edge > 0))
    return float(inter / union)


def _orb_similarity(reference, candidate):
    cand = cv2.cvtColor(candidate, cv2.COLOR_RGB2GRAY) if candidate.ndim == 3 else candidate
    detector = cv2.ORB_create(nfeatures=700, scaleFactor=1.2, nlevels=8)
    kp1, d1 = detector.detectAndCompute(reference, None)
    kp2, d2 = detector.detectAndCompute(cand, None)
    if d1 is None or d2 is None or len(kp1) < 6 or len(kp2) < 6:
        return {'score': 0.0, 'good_matches': 0, 'inlier_ratio': 0.0, 'reference_keypoints': len(kp1 or []), 'candidate_keypoints': len(kp2 or [])}
    good = []
    for pair in cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d1, d2, k=2):
        if len(pair) == 2 and pair[0].distance < 0.76 * pair[1].distance:
            good.append(pair[0])
    inlier_ratio = 0.0
    if len(good) >= 6:
        src = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        try:
            _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
            if mask is not None:
                inlier_ratio = float(mask.ravel().mean())
        except cv2.error:
            pass
    match_density = min(1.0, len(good) / max(12.0, len(kp1) * 0.28))
    score = 0.62 * match_density + 0.38 * inlier_ratio
    return {'score': float(score), 'good_matches': len(good), 'inlier_ratio': inlier_ratio, 'reference_keypoints': len(kp1), 'candidate_keypoints': len(kp2)}


def analyze(rgb, profile):
    """Return explainable visual-feature evidence and an overlay image.

    profile is a Registry 2.0 issuer-template profile. Only synthetic templates
    with bundled, hash-verified reference assets are accepted here.
    """
    overlay = rgb.copy()
    if not profile or not profile.get('template'):
        return {
            'method': METHOD, 'status': 'NOT_ASSESSED_NO_REFERENCE', 'template_reference': None,
            'feature_results': [], 'inspection_regions': [], 'visual_anomaly_index': None,
            'reason': 'No matching local synthetic issuer-template reference profile is available.',
            'score_meaning': 'No score. Issuer visual features were not assessed.',
            'limitation': 'Only bundled synthetic reference templates are supported. No official issuer template, hologram, UV/IR or government security-feature database is connected.'
        }, overlay
    template = profile['template']
    features = list(profile.get('visual_features') or [])
    reference_class = profile.get('reference_class') or 'SYNTHETIC_DEMO_TEMPLATE'
    if reference_class != 'SYNTHETIC_DEMO_TEMPLATE' or not features:
        return {
            'method': METHOD, 'status': 'NOT_ASSESSED_NO_REFERENCE', 'template_reference': template,
            'feature_results': [], 'inspection_regions': [], 'visual_anomaly_index': None,
            'reason': 'Template metadata exists, but no bundled synthetic visual reference features are available.',
            'score_meaning': 'No score. Issuer visual features were not assessed.',
            'limitation': 'Only bundled synthetic visual references are matched in v6.6.'
        }, overlay

    results = []; regions = []; hard_failures = 0; required_total = 0; weighted_missing = 0.0
    for feature in features:
        box = _clip_box(feature.get('expected_box'))
        required = bool(feature.get('required', True)); critical = bool(feature.get('critical', False))
        if required:
            required_total += 1
        base = {
            'feature_code': feature.get('feature_code', 'VISUAL_FEATURE'),
            'label': feature.get('feature_label') or feature.get('feature_code') or 'Visual feature',
            'expected_box': box, 'required': required, 'critical': critical,
            'reference_sha256': feature.get('reference_sha256', ''),
            'match_method': 'ORB + edge-shape agreement within versioned expected zone'
        }
        if not box:
            results.append({**base, 'status': 'INCONCLUSIVE', 'score': None, 'reason': 'Invalid expected feature zone metadata.'})
            continue
        ref, error = _load_reference(feature)
        candidate = _crop(rgb, box)
        if error or ref is None or candidate is None:
            results.append({**base, 'status': 'INCONCLUSIVE', 'score': None, 'reason': error or 'EXPECTED_ZONE_UNAVAILABLE'})
            continue
        orb = _orb_similarity(ref, candidate)
        edge = _edge_similarity(ref, candidate)
        # Exact-zone edge agreement complements ORB on small emblems/text bands.
        combined = max(float(orb['score']), min(1.0, 0.35 * float(orb['score']) + 0.65 * min(1.0, edge / 0.62)))
        threshold = float(feature.get('min_score') or 0.48)
        margin = 0.10
        if combined >= threshold:
            status = 'PRESENT_CONSISTENT'
            reason = 'Expected synthetic reference feature produced sufficient local visual agreement.'
        elif combined < max(0.05, threshold - margin) and required:
            status = 'REVIEW_MISSING_OR_INCONSISTENT'
            reason = 'Required synthetic reference feature did not produce sufficient agreement in its expected zone.'
            hard_failures += 1
            weighted_missing += 2.0 if critical else 1.0
            regions.append({'field': base['feature_code'], 'box': box, 'source': METHOD, 'status': 'VISUAL_FEATURE_REVIEW'})
        else:
            status = 'INCONCLUSIVE'
            reason = 'Feature agreement is near the prototype threshold; manual inspection is required.'
            if required:
                weighted_missing += 0.35
        results.append({**base, 'status': status, 'score': round(combined, 4), 'threshold': threshold,
                        'edge_agreement': round(edge, 4), 'orb_score': round(float(orb['score']), 4),
                        'good_matches': orb['good_matches'], 'inlier_ratio': round(float(orb['inlier_ratio']), 4), 'reason': reason})

    critical_fail = any(r['status'] == 'REVIEW_MISSING_OR_INCONSISTENT' and r.get('critical') for r in results)
    review = bool(critical_fail or hard_failures >= 2)
    anomaly = None if required_total == 0 else min(100, round(100 * weighted_missing / max(required_total + 1.0, 1.0)))
    status = 'REVIEW_REQUIRED' if review else ('OBSERVATIONS' if any(r['status'] != 'PRESENT_CONSISTENT' for r in results) else 'REFERENCE_FEATURES_CONSISTENT')

    color = (255, 70, 70) if review else (60, 190, 110)
    h, w = rgb.shape[:2]
    for r in results:
        box = r.get('expected_box')
        if not box:
            continue
        x, y, bw, bh = box
        c = color if r['status'] == 'REVIEW_MISSING_OR_INCONSISTENT' else (50, 170, 230)
        cv2.rectangle(overlay, (int(x*w), int(y*h)), (int((x+bw)*w), int((y+bh)*h)), c, 2)
        cv2.putText(overlay, str(r['feature_code'])[:24], (int(x*w), max(18, int(y*h)-5)), cv2.FONT_HERSHEY_SIMPLEX, .45, c, 1, cv2.LINE_AA)
    cv2.putText(overlay, 'SYNTHETIC TEMPLATE VISUAL REVIEW' if review else 'SYNTHETIC TEMPLATE VISUAL CHECK', (12, 28), cv2.FONT_HERSHEY_SIMPLEX, .62, color, 2, cv2.LINE_AA)

    return {
        'method': METHOD, 'status': status, 'reference_class': reference_class,
        'template_reference': {
            'id': template.get('id'), 'document_type': template.get('document_type'),
            'issuer_country': template.get('issuer_country'), 'issuer_name': template.get('issuer_name'),
            'template_version': template.get('template_version'), 'valid_from': template.get('valid_from'), 'valid_to': template.get('valid_to')
        },
        'feature_results': results, 'inspection_regions': regions, 'visual_anomaly_index': anomaly,
        'reason': ('One critical or multiple required synthetic template features are missing/inconsistent; officer review required.' if review else
                   'Bundled synthetic reference features were checked. A consistent result does not authenticate a real issuer document.'),
        'score_meaning': '0-100 prototype missing/inconsistent-reference index; NOT an authenticity or forgery probability.',
        'limitation': 'Matches only bundled synthetic demo features within versioned expected zones. It does not verify holograms, UV/IR features, paper substrate, official seals or any government/issuer security database.'
    }, overlay
