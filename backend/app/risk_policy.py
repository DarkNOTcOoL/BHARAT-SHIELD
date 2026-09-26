"""Prototype rule points, not a fraud probability or government policy."""
VERSION='SYNTHETIC_REFERENCE_RISK_V7_TRAVEL_INTELLIGENCE'

def assess(registry,qr,findings,fields,quality,confidence,mrz):
    factors={};gaps=[]
    def add(group,points,reason):
        if group not in factors or points>factors[group]['points']:
            factors[group]={'group':group,'points':points,'reason':reason}
    status=registry.get('status','NOT_CHECKED')
    if status in {'BLOCKED','REVOKED'}:add('reference_status',100 if status=='BLOCKED' else 90,'Synthetic reference is '+status.lower()+'. Escalation required.')
    if status=='EXPIRED':add('expiry',40,'Synthetic reference is expired.')
    registry2=registry.get('registry2') or {}
    for alert in registry2.get('alerts',[]):
        if alert.get('status')!='OPEN':continue
        kind=alert.get('alert_type','')
        severity=alert.get('severity','REVIEW')
        if kind in {'DOCUMENT_BLOCKED'}:add('registry2_alert',100,'Synthetic Registry 2.0 document-block alert requires escalation.')
        elif kind in {'DOCUMENT_REVOKED','LOST_STOLEN_DOCUMENT'}:add('registry2_alert',90,'Synthetic Registry 2.0 '+kind.lower().replace('_',' ')+' alert requires escalation.')
        elif kind=='WATCHLIST_REVIEW':add('registry2_alert',60,'Synthetic Registry 2.0 review alert requires officer investigation; no external watchlist is connected.')
        elif kind=='DUPLICATE_IDENTITY':add('registry2_alert',35,'Synthetic Registry 2.0 duplicate-identity alert requires investigation.')
        elif severity in {'HIGH','CRITICAL'}:add('registry2_alert',40,'Synthetic Registry 2.0 high-severity alert requires review.')
        elif severity=='REVIEW':add('registry2_alert',20,'Synthetic Registry 2.0 alert requires review.')
    for f in registry.get('fields',[]):
        if f['status']=='CONFLICT':add('identity_fields',40,f['label']+' conflicts with the synthetic reference.')
        elif f['status']=='CLOSE_MATCH':add('similar_name',10,'Similar name requires human review.')
        elif f['status'] in {'NOT_EXTRACTED','NOT_IN_REGISTRY','INVALID_EXTRACTED_VALUE'}:gaps.append(f['label']+': '+f['status'])
    for f in findings:
        code=f.get('code','')
        if code in {'DOCUMENT_EXPIRED','REGISTRY_EXPIRED','SIGNED_CREDENTIAL_EXPIRED'}:add('expiry',40,'Expiry is in the past. Review the original and reference dates.')
        if code in {'DATE_ORDER_CONFLICT','DOB_IN_FUTURE','ISSUE_DATE_IN_FUTURE'}:add('date_logic',35,'Date inconsistency: '+code)
        if code=='DOCUMENT_NUMBER_FORMAT_INVALID':add('number_format',15,'Document number fails a supported format check. Inspect OCR.')
        if code=='HISTORY_IDENTITY_CONFLICT':add('history',35,'Document key has conflicting identity fields in local history.')
        # Generic tamper and portrait-substitution signals share forensic evidence, so use
        # one rule family and keep only the stronger signal rather than double counting.
        if code=='AI_TAMPER_ANOMALY':add('forensic_integrity',20,'Local unsupervised forensic anomaly requires officer inspection; this is not proof of editing.')
        if code=='PHOTO_SUBSTITUTION_REVIEW':add('forensic_integrity',30,'AI-localized portrait region has multiple substitution cues; officer inspection is required. This is not a replacement-photo probability.')
        if code=='STAMP_SEAL_TAMPER_REVIEW':add('forensic_integrity',30,'Stamp/seal-like region overlaps independent forensic anomaly cues. This is not issuer-stamp authentication.')
        if code=='LAYOUT_SECURITY_ZONE_REVIEW':add('forensic_integrity',25,'Multiple layout/security-zone inconsistencies require officer inspection. This is not issuer-template authentication.')
        if code=='ISSUER_VISUAL_FEATURE_REVIEW':add('forensic_integrity',30,'Bundled synthetic issuer-template visual features are missing or inconsistent. This requires officer inspection and is not official issuer authentication.')
        if code in {'VISA_VALIDITY_ORDER_CONFLICT'}:add('visa_consistency',35,'Visa validity dates conflict.')
        if code in {'VISA_ENTRIES_UNRECOGNIZED','VISA_ISSUE_AFTER_VALID_FROM'}:add('visa_consistency',15,'Visa-specific field requires officer review.')
        if code in {'TRAVEL_VISA_ENTRY_LIMIT_CONFLICT','TRAVEL_ENTRY_BEFORE_VISA_VALID_FROM','TRAVEL_ENTRY_AFTER_VISA_EXPIRY','TRAVEL_ENTRY_BEFORE_VISA_ISSUE','TRAVEL_VISA_ISSUED_AFTER_ENTRY','TRAVEL_EVENT_IN_FUTURE'}:add('travel_consistency',35,'Synthetic travel/visa chronology or entry-entitlement conflict requires officer review.')
        if code=='TRAVEL_STAY_DURATION_EXCEEDED':add('travel_consistency',30,'Synthetic travel history exceeds the linked visa duration-of-stay value.')
        if code in {'TRAVEL_SEQUENCE_ENTRY_WITHOUT_EXIT','TRAVEL_SEQUENCE_EXIT_WITHOUT_ENTRY'}:add('travel_consistency',15,'Synthetic entry/exit history has an incomplete sequence. Review source completeness.')
        if code.startswith('CROSS_') and f.get('status')=='CONFLICT':add('cross_document',40,'Submitted documents contain conflicting values.')
        if code=='DATE_UNREADABLE':gaps.append('A date could not be parsed.')
    if mrz=='INVALID':add('mrz',30,'Passport MRZ checks failed; inspect extraction.')
    if mrz in {'NOT_DETECTED','NOT_SUPPORTED'}:gaps.append('MRZ: '+mrz)
    if qr.get('signature_status')=='SIGNATURE_INVALID':add('signed_data',45,'Configured synthetic signature is invalid.')
    if qr.get('comparison_status')=='SIGNED_DATA_CONFLICT':add('signed_data',45,'Signed, printed or reference data conflict.')
    if qr.get('requires_review') and 'signed_data' not in factors:gaps.append('Signed QR requires further review.')
    if status in {'NOT_CHECKED','NOT_FOUND','UNAVAILABLE','AMBIGUOUS','ARCHIVED'}:gaps.append('Synthetic reference: '+status)
    for key in ['name','document_number','dob','nationality','issuer_country']:
        if not fields.get(key):gaps.append('Missing '+key)
    if quality.get('status')!='USABLE':gaps.append('Capture quality requires recapture.')
    if confidence<65:gaps.append('OCR confidence below 65; review required.')
    points=min(100,sum(f['points'] for f in factors.values()));score=None if points==0 and gaps else points
    band='UNASSESSED' if score is None else 'CRITICAL' if points>=70 else 'HIGH' if points>=30 else 'REVIEW' if points else 'LOW'
    return {'policy_version':VERSION,'scope':'SYNTHETIC_REFERENCE_SCREENING','score':score,'observed_points':points,'maximum':100,'band':band,
            'evidence_status':'INCOMPLETE' if gaps else 'SUFFICIENT_FOR_DEMO_RULES','factors':list(factors.values()),'gaps':list(dict.fromkeys(gaps)),
            'method':'Sum of maximum points per rule family, capped at 100. Missing evidence does not add fraud points. Generic tamper, photo-substitution, stamp/seal, layout and synthetic issuer-visual cues share one forensic-integrity family to avoid double counting. Registry 2.x synthetic alerts and travel-consistency signals use separate maximum-per-family rules.',
            'limitation':'Prototype weights, not a calibrated probability, government policy or authenticity verdict. Low risk means no weighted inconsistency detected in these checks. Human decision remains separate.'}
