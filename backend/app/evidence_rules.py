"""Deterministic local evidence checks; no network or identity verdicts."""
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from .local_registry import normalized_field, normalized_number, normalized_text, normalized_date, COMPARE_FIELDS, VISA_COMPARE_FIELDS

ALIASES={'document_number':'documentNumber','passport_reference':'passportReference','issuer_country':'issuerCountry','issue_date':'issueDate','issuing_authority':'issuingAuthority','visa_type':'visaType','number_of_entries':'numberOfEntries','valid_from':'validFrom','duration_of_stay':'durationOfStay'}

def extraction_evidence(metadata, reviewed, actor):
    original=metadata.get('ocr_fields',{})
    keys=COMPARE_FIELDS + VISA_COMPARE_FIELDS
    parsed={k:original.get(k,original.get(ALIASES.get(k,k),'')) for k in keys}
    return {'raw_text':metadata.get('ocr_text',''), 'ocr_fields':original, 'parsed_fields':parsed,
            'intake_notes_browser_supplied':metadata.get('ocr_notes',''),
            'reviewed_fields':reviewed,'reviewed_by':actor,'reviewed_at':datetime.now(timezone.utc).isoformat(),
            'parsed_fields_supplied':bool(original),
            'corrections':[{'field':k,'before':parsed[k],'after':reviewed.get(k,'')} for k in keys if parsed[k]!=reviewed.get(k,'')] if original else [],
            'source':'AUTHENTICATED_BROWSER_OCR_AND_OFFICER_REVIEW',
            'limitation':'OCR and parsed fields are browser-supplied, not independently attested. Server records the submitting account and time.'}

def cross_checks(documents):
    if len(documents)<2:return 0,'NOT_APPLICABLE',[]
    findings=[];checked=0;matches=0
    def add(code,status,message):
        nonlocal checked,matches
        findings.append({'code':code,'status':status,'severity':'HIGH' if status=='CONFLICT' else 'MEDIUM' if status=='REVIEW_REQUIRED' else 'PASS' if status=='MATCH' else 'INFO','message':message})
        if status in {'MATCH','CONFLICT','REVIEW_REQUIRED'}:checked+=1;matches+=int(status=='MATCH')
    for key in ['name','dob','nationality']:
        raw=[d.get(key,'').strip() for d in documents]
        values=[normalized_field(key,v) if v else None for v in raw]
        available=[v for v in values if v]
        if len(available)>=2:
            same=all(v==available[0] for v in available[1:])
            close=key=='name' and all(sorted(v.split())==sorted(available[0].split()) or SequenceMatcher(None,available[0],v).ratio()>=.85 for v in available[1:])
            status='MATCH' if same else 'REVIEW_REQUIRED' if close else 'CONFLICT'
            add('CROSS_'+key.upper(),status,f'{key.title()}: {status.lower().replace("_"," ")} across extracted document fields.')
        if len(available)!=len(documents):
            add('CROSS_'+key.upper()+'_MISSING','MISSING',f'{key.title()} is missing or unreadable on at least one document; comparison is incomplete.')
    passports=[d for d in documents if d.get('type')=='Passport']
    for i,d in enumerate(documents,1):
        if d.get('type')=='Visa':
            ref=normalized_number(d.get('passport_reference',''))
            if not passports or not ref or not any(p.get('document_number') for p in passports):
                add('CROSS_LINK_UNAVAILABLE','MISSING',f'Document {i}: supplied passport or visa passport reference missing; relationship not verified.')
            else:
                linked=[p for p in passports if normalized_number(p.get('document_number',''))==ref]
                add('CROSS_PASSPORT_LINK','MATCH' if len(linked)==1 else 'REVIEW_REQUIRED' if len(linked)>1 else 'CONFLICT',f'Document {i}: visa passport reference has {len(linked)} matching supplied passports. The visa number is a separate identifier.')
                if len(linked)==1:
                    expiry=normalized_date(linked[0].get('expiry',''));issue=normalized_date(d.get('issue_date',''))
                    if expiry and issue:
                        add('CROSS_VISA_ISSUE_AFTER_PASSPORT_EXPIRY','CONFLICT' if issue>expiry else 'MATCH',f'Document {i}: visa issue date compared with referenced passport expiry. Conflicts require review, not a forgery conclusion.')
        if d.get('type')=='Visa':
            vf=normalized_date(d.get('valid_from',''));vx=normalized_date(d.get('expiry',''))
            if vf and vx:add('CROSS_VISA_VALIDITY_ORDER','CONFLICT' if vf>vx else 'MATCH',f'Document {i}: visa valid-from must not follow valid-until/expiry.')
            entries=normalized_field('number_of_entries',d.get('number_of_entries',''))
            if d.get('number_of_entries') and entries not in {'1','2','multiple'}:add('CROSS_VISA_ENTRIES_REVIEW','REVIEW_REQUIRED',f'Document {i}: visa number-of-entries value requires manual review.')
        parsed={k:normalized_date(d.get(k,'')) for k in ['dob','issue_date','expiry']}
        for a,b in [('dob','issue_date'),('issue_date','expiry')]:
            if parsed[a] and parsed[b]:add('CROSS_DATE_ORDER','CONFLICT' if parsed[a]>parsed[b] else 'MATCH',f'Document {i}: {a} must not follow {b}.')
        if d.get('type') in {'Passport','Visa','Permit','Driving Licence','Travel Authorization'}:
            if not parsed['expiry']:add('CROSS_EXPIRY_MISSING','MISSING',f'Document {i}: expiry missing or unreadable.')
            elif parsed['expiry']<date.today().isoformat():add('CROSS_DOCUMENT_EXPIRED','CONFLICT',f'Document {i}: extracted expiry is in the past.')
    statuses={f['status'] for f in findings}
    status='CONFLICT' if 'CONFLICT' in statuses else 'REVIEW_REQUIRED' if 'REVIEW_REQUIRED' in statuses else 'INSUFFICIENT_EVIDENCE' if not checked else 'PARTIAL' if 'MISSING' in statuses else 'CONSISTENT'
    return round(matches/checked*100,1) if checked else 0,status,findings
