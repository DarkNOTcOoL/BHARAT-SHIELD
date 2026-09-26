"""Bounded history investigation signals, never automatic identity conclusions."""
from .local_registry import normalized_field as norm

def compare(fields,document_type,digest,claims,history,limit=1000):
    candidates=[];review=False
    for row in history[:limit]:
        reasons=[];conflict=False
        old=row['fields']
        if row['document_hash']==digest:reasons.append('EXACT_IMAGE_RESCAN')
        same_number=bool(fields.get('document_number') and norm('document_number',fields['document_number'])==norm('document_number',old.get('document_number','')))
        same_issuer=bool(fields.get('issuer_country') and norm('issuer_country',fields['issuer_country'])==norm('issuer_country',old.get('issuer_country','')))
        same_person=all(fields.get(k) and old.get(k) and norm(k,fields[k])==norm(k,old[k]) for k in ['name','dob'])
        if same_number and same_issuer and document_type==row['document_type']:
            conflict=any(fields.get(k) and old.get(k) and norm(k,fields[k])!=norm(k,old[k]) for k in ['name','dob'])
            if conflict:reasons.append('DOCUMENT_IDENTITY_FIELDS_CHANGED')
        if same_person and not same_number:reasons.append('SAME_NAME_DOB_OTHER_NUMBER')
        previous=row.get('claims')
        if claims and previous and all(claims[k]==previous[k] for k in ['key_id','issuer','credential_id']):
            reasons.append('SIGNED_CREDENTIAL_SEEN_BEFORE')
            if claims!=previous:reasons.append('CREDENTIAL_ID_CONTENT_CHANGED');conflict=True
        if reasons:candidates.append({'screening_id':row['screening_id'],'reasons':reasons,'requires_review':conflict});review|=conflict
    return {'status':'CANDIDATES_FOUND' if candidates else 'NO_CANDIDATES_IN_SEARCHED_HISTORY','candidates':candidates[:50],
            'candidate_count':len(candidates),'searched_count':min(len(history),limit),'search_limit':limit,'requires_review':review,
            'limitation':'Latest 1000 screenings only; at most 50 candidates displayed. Rescans, matching names and multiple documents can be legitimate. No biometric identity search.'}
