"""Synthetic travel/immigration consistency intelligence for SIH26188.

This module reasons only over the local Registry 2.x demo graph and OCR-visible
stamp text. It does not connect to government, immigration, airline or border
systems and it never treats missing travel history as proof of fraud.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Iterable

from . import local_registry

VERSION = 'TRAVEL_IMMIGRATION_INTELLIGENCE_V1'
METHOD = 'REGISTRY2_VISA_ENTRY_SEQUENCE_V1'

COUNTRY_NAMES = {
    'INDIA': 'IND', 'IND': 'IND',
    'UNITED STATES': 'USA', 'USA': 'USA', 'US': 'USA',
    'UNITED KINGDOM': 'GBR', 'UK': 'GBR', 'GBR': 'GBR',
    'FRANCE': 'FRA', 'FRA': 'FRA',
    'GERMANY': 'DEU', 'DEU': 'DEU',
    'JAPAN': 'JPN', 'JPN': 'JPN',
    'AUSTRALIA': 'AUS', 'AUS': 'AUS',
    'CANADA': 'CAN', 'CAN': 'CAN',
}


def _date(value: str | None) -> str:
    return local_registry.normalized_date(value or '') or ''


def _allowed_entries(value: str | None):
    norm = local_registry.normalized_field('number_of_entries', value or '')
    if norm in {'1', 'single'}:
        return 1
    if norm in {'2', 'double'}:
        return 2
    if norm in {'multiple', 'mult', 'm', 'unlimited'}:
        return None
    if norm.isdigit():
        n = int(norm)
        return n if 1 <= n <= 99 else None
    return None


def _duration_days(value: str | None):
    if not value:
        return None
    m = re.search(r'\b(\d{1,3})\s*(?:DAY|DAYS|D)\b', str(value), re.I)
    if not m:
        return None
    n = int(m.group(1))
    return n if 1 <= n <= 366 else None


def _parse_any_date(text: str) -> str:
    candidates = re.findall(
        r'\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b',
        text,
    )
    for raw in candidates:
        normalized = _date(raw)
        if normalized:
            return normalized
    return ''


def extract_observed_stamp_mentions(ocr_text: str) -> list[dict]:
    """Extract conservative ENTRY/EXIT stamp mentions from OCR-visible lines.

    The result is evidence only. OCR absence is never interpreted as absence of a
    stamp because most screenings contain only a document bio/visa page.
    """
    out = []
    seen = set()
    for line_no, raw in enumerate((ocr_text or '').splitlines(), 1):
        line = ' '.join(raw.strip().split())
        upper = line.upper()
        if not line or not re.search(r'\b(ENTRY|ENTERED|ARRIVAL|EXIT|DEPARTURE|DEPARTED)\b', upper):
            continue
        event_type = 'ENTRY' if re.search(r'\b(ENTRY|ENTERED|ARRIVAL)\b', upper) else 'EXIT'
        event_date = _parse_any_date(line)
        country = ''
        for name, code in COUNTRY_NAMES.items():
            if re.search(r'(?<![A-Z])' + re.escape(name) + r'(?![A-Z])', upper):
                country = code
                break
        key = (event_type, event_date, country, upper)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            'event_type': event_type,
            'event_date': event_date,
            'country_code': country,
            'ocr_line': line[:240],
            'line_number': line_no,
            'confidence_class': 'STRUCTURED_TEXT_CUE' if event_date else 'PARTIAL_TEXT_CUE',
        })
    return out[:20]


def _event_key(event: dict):
    return (event.get('event_date') or '', event.get('created_at') or '', event.get('id') or '')


def _paired_stays(events: Iterable[dict], country: str):
    """Pair ENTRY with the next EXIT in the same country, conservatively."""
    events = sorted(
        [e for e in events if e.get('event_type') in {'ENTRY', 'EXIT'} and (not country or e.get('country_code') == country)],
        key=_event_key,
    )
    open_entry = None
    pairs = []
    gaps = []
    for e in events:
        if e.get('event_type') == 'ENTRY':
            if open_entry is not None:
                gaps.append({'code': 'TRAVEL_SEQUENCE_ENTRY_WITHOUT_EXIT', 'event': e, 'previous_entry': open_entry})
            open_entry = e
        elif e.get('event_type') == 'EXIT':
            if open_entry is None:
                gaps.append({'code': 'TRAVEL_SEQUENCE_EXIT_WITHOUT_ENTRY', 'event': e})
            else:
                pairs.append((open_entry, e))
                open_entry = None
    if open_entry is not None:
        pairs.append((open_entry, None))
    return pairs, gaps


def _visa_assessment(visa: dict, events: list[dict], today_iso: str) -> dict:
    country = (visa.get('issuer_country') or '').upper()
    valid_from = _date(visa.get('valid_from')) or _date(visa.get('issue_date'))
    expiry = _date(visa.get('expiry'))
    issue_date = _date(visa.get('issue_date'))
    allowed = _allowed_entries(visa.get('number_of_entries'))
    duration = _duration_days(visa.get('duration_of_stay'))
    entries = [e for e in events if e.get('event_type') == 'ENTRY' and (not country or e.get('country_code') == country)]
    findings = []

    for e in entries:
        d = _date(e.get('event_date'))
        if not d:
            continue
        if valid_from and d < valid_from:
            findings.append({'code': 'TRAVEL_ENTRY_BEFORE_VISA_VALID_FROM', 'severity': 'HIGH', 'status': 'REVIEW_REQUIRED',
                             'message': f"Synthetic travel history records an entry on {d} before visa validity starts on {valid_from}."})
        if expiry and d > expiry:
            findings.append({'code': 'TRAVEL_ENTRY_AFTER_VISA_EXPIRY', 'severity': 'HIGH', 'status': 'REVIEW_REQUIRED',
                             'message': f"Synthetic travel history records an entry on {d} after visa expiry on {expiry}."})
        if issue_date and d < issue_date:
            findings.append({'code': 'TRAVEL_ENTRY_BEFORE_VISA_ISSUE', 'severity': 'HIGH', 'status': 'REVIEW_REQUIRED',
                             'message': f"Synthetic travel history records an entry on {d} before visa issue on {issue_date}."})

    if allowed is not None and len(entries) > allowed:
        findings.append({'code': 'TRAVEL_VISA_ENTRY_LIMIT_CONFLICT', 'severity': 'HIGH', 'status': 'REVIEW_REQUIRED',
                         'message': f"Synthetic travel history shows {len(entries)} entry event(s) for a visa allowing {allowed}."})

    pairs, gaps = _paired_stays(events, country)
    stay_summaries = []
    for start, end in pairs:
        sd = _date(start.get('event_date'))
        ed = _date(end.get('event_date')) if end else ''
        days = None
        if sd and ed:
            days = (date.fromisoformat(ed) - date.fromisoformat(sd)).days
        elif sd and not ed and sd <= today_iso:
            days = (date.fromisoformat(today_iso) - date.fromisoformat(sd)).days
        stay_summaries.append({'entry_date': sd, 'exit_date': ed, 'days': days, 'open_stay': end is None})
        if duration is not None and days is not None and days > duration:
            findings.append({'code': 'TRAVEL_STAY_DURATION_EXCEEDED', 'severity': 'HIGH', 'status': 'REVIEW_REQUIRED',
                             'message': f"Synthetic travel history indicates a stay of {days} day(s), exceeding the visa duration-of-stay value of {duration} day(s)."})

    for gap in gaps:
        findings.append({'code': gap['code'], 'severity': 'MEDIUM', 'status': 'REVIEW_REQUIRED',
                         'message': 'Synthetic entry/exit history contains an incomplete sequence. Review source records; this can also reflect missing historical data.'})

    status = 'REVIEW_REQUIRED' if findings else 'CONSISTENT'
    return {
        'document_record_id': visa.get('id', ''),
        'document_number': visa.get('document_number', ''),
        'issuer_country': country,
        'visa_type': visa.get('visa_type', ''),
        'number_of_entries': visa.get('number_of_entries', ''),
        'allowed_entries': 'MULTIPLE_OR_UNLIMITED' if allowed is None and local_registry.normalized_field('number_of_entries', visa.get('number_of_entries', '')) == 'multiple' else allowed,
        'entries_observed_in_registry': len(entries),
        'valid_from': valid_from,
        'expiry': expiry,
        'duration_of_stay': visa.get('duration_of_stay', ''),
        'duration_days': duration,
        'stays': stay_summaries[:20],
        'status': status,
        'findings': findings,
    }


def _compare_ocr_mentions(mentions: list[dict], events: list[dict]) -> list[dict]:
    comparisons = []
    for mention in mentions:
        candidates = []
        for e in events:
            if e.get('event_type') != mention.get('event_type'):
                continue
            score = 1
            if mention.get('event_date') and e.get('event_date') == mention.get('event_date'):
                score += 3
            elif mention.get('event_date'):
                continue
            if mention.get('country_code') and e.get('country_code') == mention.get('country_code'):
                score += 2
            elif mention.get('country_code'):
                continue
            candidates.append((score, e))
        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0][1] if candidates else None
        comparisons.append({
            'observed': mention,
            'registry_match': {k: best.get(k) for k in ('id','event_type','country_code','port','event_date','authority','stamp_reference','source')} if best else None,
            'status': 'MATCHED_SYNTHETIC_EVENT' if best else 'NOT_FOUND_IN_SYNTHETIC_HISTORY',
            'interpretation': 'A missing synthetic-history match is an evidence gap, not proof that the OCR-visible stamp is false.',
        })
    return comparisons


def assess(registry: dict, document_type: str, fields: dict, ocr_text: str, today: date | None = None) -> dict:
    """Assess visa/travel consistency from the saved Registry 2.x graph.

    Only positive contradictions produce review findings. Missing history is kept as
    an evidence gap because a demo/local registry can be incomplete.
    """
    today_iso = (today or date.today()).isoformat()
    if document_type not in {'Visa','Passport','Travel Authorization','Permit'}:
        return {
            'version': VERSION, 'method': METHOD, 'status': 'NOT_APPLICABLE_DOCUMENT_TYPE',
            'requires_review': False, 'visa_assessments': [], 'travel_event_count': 0,
            'ocr_stamp_mentions': [], 'stamp_comparisons': [], 'findings': [], 'gaps': [],
            'limitation': 'Travel/immigration consistency is only applied to travel-document screening in this prototype.'
        }
    r2 = (registry or {}).get('registry2') or {}
    if r2.get('status') in {'UNAVAILABLE', 'NOT_LINKED'} or not r2.get('identity'):
        return {
            'version': VERSION, 'method': METHOD, 'status': 'NOT_ASSESSED_NO_LINKED_IDENTITY',
            'requires_review': False, 'visa_assessments': [], 'travel_event_count': 0,
            'ocr_stamp_mentions': extract_observed_stamp_mentions(ocr_text), 'stamp_comparisons': [],
            'findings': [], 'gaps': ['No linked Registry 2.x identity graph was available.'],
            'limitation': 'Synthetic local evidence only; no government or immigration system is connected.'
        }

    events = list(r2.get('travel_events') or [])
    docs = list(r2.get('linked_documents') or [])
    current_record = (registry or {}).get('record') or {}
    # enrich_reference now carries visa details in linked_documents, but retain the
    # current record in case an older saved graph omitted those fields.
    visa_docs = [dict(d) for d in docs if d.get('document_type') == 'Visa']
    if document_type == 'Visa' and current_record:
        if not any(v.get('id') == current_record.get('id') for v in visa_docs):
            visa_docs.append(dict(current_record))
        else:
            visa_docs = [({**v, **current_record} if v.get('id') == current_record.get('id') else v) for v in visa_docs]

    assessments = [_visa_assessment(v, events, today_iso) for v in visa_docs]
    findings = [f for a in assessments for f in a.get('findings', [])]

    # Registry chronology checks independent of a particular visa.
    for e in events:
        d = _date(e.get('event_date'))
        if d and d > today_iso:
            findings.append({'code': 'TRAVEL_EVENT_IN_FUTURE', 'severity': 'HIGH', 'status': 'REVIEW_REQUIRED',
                             'message': f"Synthetic travel history contains a future-dated {e.get('event_type','event').lower()} event on {d}."})

    # Visa-issued events should not come after an already recorded entry when both
    # concern the same issuer country. This is deterministic chronology, not profiling.
    issued_by_country = {}
    for e in events:
        if e.get('event_type') == 'VISA_ISSUED' and _date(e.get('event_date')):
            issued_by_country.setdefault(e.get('country_code', ''), []).append(_date(e.get('event_date')))
    for e in events:
        if e.get('event_type') != 'ENTRY':
            continue
        ed = _date(e.get('event_date'))
        for issued in issued_by_country.get(e.get('country_code', ''), []):
            if ed and issued > ed:
                findings.append({'code': 'TRAVEL_VISA_ISSUED_AFTER_ENTRY', 'severity': 'HIGH', 'status': 'REVIEW_REQUIRED',
                                 'message': f"Synthetic history records visa issuance on {issued} after an entry on {ed} for the same country."})
                break

    mentions = extract_observed_stamp_mentions(ocr_text)
    comparisons = _compare_ocr_mentions(mentions, events)
    gaps = []
    if not events:
        gaps.append('No synthetic travel/stamp history is recorded for this identity.')
    if not visa_docs and document_type in {'Visa', 'Passport', 'Travel Authorization'}:
        gaps.append('No linked visa record is available for visa-entry entitlement checks.')
    unmatched = [x for x in comparisons if x['status'] == 'NOT_FOUND_IN_SYNTHETIC_HISTORY']
    if unmatched:
        gaps.append(f"{len(unmatched)} OCR-visible entry/exit stamp mention(s) were not found in the synthetic travel history; review manually because the local history may be incomplete.")

    # de-duplicate findings that can arise from overlapping visa/history rules.
    dedup = []
    seen = set()
    for f in findings:
        key = (f.get('code'), f.get('message'))
        if key not in seen:
            seen.add(key); dedup.append(f)
    findings = dedup
    requires_review = bool(findings)
    if requires_review:
        status = 'REVIEW_REQUIRED'
    elif events or assessments:
        status = 'CONSISTENT_WITH_SYNTHETIC_HISTORY'
    else:
        status = 'INCONCLUSIVE_NO_HISTORY'

    entry_total = sum(1 for e in events if e.get('event_type') == 'ENTRY')
    exit_total = sum(1 for e in events if e.get('event_type') == 'EXIT')
    return {
        'version': VERSION,
        'method': METHOD,
        'status': status,
        'requires_review': requires_review,
        'identity_id': (r2.get('identity') or {}).get('id', ''),
        'travel_event_count': len(events),
        'entry_count': entry_total,
        'exit_count': exit_total,
        'visa_assessments': assessments,
        'ocr_stamp_mentions': mentions,
        'stamp_comparisons': comparisons,
        'findings': findings,
        'gaps': gaps,
        'reason': (f"{len(findings)} travel/visa consistency issue(s) require review." if findings else
                   f"No contradiction was found across {len(events)} synthetic travel event(s) and {len(assessments)} linked visa assessment(s)." if (events or assessments) else
                   'No linked synthetic travel history was available for consistency checking.'),
        'limitation': 'This checks only the local synthetic Registry 2.x graph and OCR-visible text. It is not connected to immigration, airline, border-control or government systems and does not establish travel history or admissibility.'
    }
