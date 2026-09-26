"""Explainable local document-type routing from OCR text.

This module is intentionally deterministic and local. It routes the OCR/parser/check pipeline;
it is not an issuer-authenticity classifier and it must not be presented as a fraud probability.
"""
from __future__ import annotations
import re

TYPES=('Passport','Visa','Aadhaar Card','Voter ID (EPIC)','Driving Licence','PAN Card','National ID','Permit','Travel Authorization')
METHOD='LOCAL_EXPLAINABLE_DOCUMENT_TYPE_ROUTER_V1'


def _text(value:str)->str:
    return (value or '').upper().replace('\r','')

def assess(ocr_text:str)->dict:
    text=_text(ocr_text)
    compact=re.sub(r'[^A-Z0-9<]+',' ',text)
    scores={t:0 for t in TYPES}; evidence={t:[] for t in TYPES}
    def add(t,p,label):
        scores[t]+=p;evidence[t].append({'label':label,'points':p})
    def hit(pattern): return re.search(pattern,text,re.I|re.M) is not None

    if re.search(r'(?:^|\n)P<[A-Z0-9<]{3}',text,re.M): add('Passport',12,'TD3 passport MRZ')
    if hit(r'\bPASSPORT\b'): add('Passport',5,'PASSPORT label')
    if hit(r'\bREPUBLIC\s+OF\s+INDIA\b|\bPASSPORT\s+NO\b|\bPLACE\s+OF\s+BIRTH\b'): add('Passport',3,'passport-specific labels')
    if hit(r'\bNATIONALITY\b'): add('Passport',1,'nationality field')

    if hit(r'\bE[- ]?VISA\b|\bVISA\b'): add('Visa',7,'VISA label')
    if hit(r'\b(?:NO\.?\s+OF\s+)?ENTRIES\b'): add('Visa',4,'entries field')
    if hit(r'\bDURATION\s+OF\s+(?:EACH\s+)?STAY\b|\bMAX(?:IMUM)?\s+STAY\b'): add('Visa',4,'duration-of-stay field')
    if hit(r'\bVALID\s+FROM\b|\bVISA\s+(?:TYPE|CLASS|CATEGORY)\b'): add('Visa',3,'visa validity/type field')
    if hit(r'\bPASSPORT\s*(?:NO\.?|NUMBER)\b') and hit(r'\bVISA\b'): add('Visa',2,'passport reference on visa')

    if hit(r'\bAADHAAR\b|\bAADHAR\b|\bUIDAI\b|UNIQUE\s+IDENTIFICATION\s+AUTHORITY\s+OF\s+INDIA'): add('Aadhaar Card',10,'UIDAI/Aadhaar identifier')
    if re.search(r'\b\d{4}\s*\d{4}\s*\d{4}\b',text): add('Aadhaar Card',5,'12-digit Aadhaar-like number')
    if hit(r'\bGOVERNMENT\s+OF\s+INDIA\b|\bYEAR\s+OF\s+BIRTH\b|\bYOB\b'): add('Aadhaar Card',1,'common Aadhaar labels')

    if hit(r'PERMANENT\s+ACCOUNT\s+NUMBER'): add('PAN Card',10,'Permanent Account Number label')
    if hit(r'INCOME\s+TAX\s+DEPARTMENT'): add('PAN Card',5,'Income Tax Department label')
    if re.search(r'\b[A-Z]{5}\d{4}[A-Z]\b',compact): add('PAN Card',7,'PAN-format identifier')
    if hit(r"\bFATHER'?S\s+NAME\b") and hit(r'\bPAN\b|PERMANENT\s+ACCOUNT'): add('PAN Card',2,'PAN identity labels')

    if hit(r'ELECTION\s+COMMISSION\s+OF\s+INDIA'): add('Voter ID (EPIC)',9,'Election Commission label')
    if hit(r"ELECTOR(?:'S)?\s+PHOTO\s+IDENTITY\s+CARD|\bEPIC\b"): add('Voter ID (EPIC)',8,'EPIC/card label')
    if re.search(r'\b[A-Z]{3}\d{7}\b',compact): add('Voter ID (EPIC)',5,'EPIC-format identifier')

    if hit(r"\bDRIVING\s+LICEN[CS]E\b|\bDRIVER'?S\s+LICEN[CS]E\b"): add('Driving Licence',9,'Driving Licence label')
    if hit(r'\bDL\s*(?:NO\.?|NUMBER)\b'): add('Driving Licence',5,'DL number label')
    if hit(r'\bTRANSPORT\s+DEPARTMENT\b|\bVALID\s+TILL\b|\bCOV\b'): add('Driving Licence',2,'licence-specific labels')
    if re.search(r'\b[A-Z]{2}\s*[- ]?\s*\d{2}\s*[- ]?\s*\d{4,13}\b',compact): add('Driving Licence',4,'licence-format identifier')

    if hit(r'\bNATIONAL\s+(?:IDENTITY|ID)\s+(?:CARD|DOCUMENT)\b'): add('National ID',8,'National ID label')
    if hit(r'\bIDENTITY\s+NUMBER\b') and not hit(r'\bAADHAAR\b|\bPAN\b|\bEPIC\b'): add('National ID',2,'generic identity-number label')
    if hit(r'\bPERMIT\b'): add('Permit',8,'Permit label')
    if hit(r'\bPERMIT\s*(?:NO\.?|NUMBER)\b'): add('Permit',3,'Permit number label')
    if hit(r'\bTRAVEL\s+AUTHORI[ZS]ATION\b|\bELECTRONIC\s+TRAVEL\s+AUTHORI[ZS]ATION\b|\bETA\b'): add('Travel Authorization',9,'Travel Authorization label')

    ranked=sorted(({'type':t,'score':scores[t],'evidence':evidence[t]} for t in TYPES),key=lambda x:(-x['score'],x['type']))
    best,second=ranked[0],ranked[1]; margin=best['score']-second['score']
    status='DETECTED' if best['score']>=8 and margin>=3 else 'AMBIGUOUS' if best['score']>=6 else 'UNDETERMINED'
    confidence=0 if status=='UNDETERMINED' else max(0,min(100,round(best['score']/(best['score']+max(second['score'],2))*100)))
    return {'status':status,'detected_type':best['type'] if status!='UNDETERMINED' else '', 'confidence':confidence,
            'score':best['score'],'margin':margin,'runner_up':second['type'],'runner_up_score':second['score'],
            'evidence':best['evidence'],'ranked':[x for x in ranked if x['score']>0][:4],
            'method':METHOD,'limitation':'Rule-weighted OCR evidence for routing only; not an issuer-authenticity model. Officer override remains available.'}


def compare(submitted_type:str, ocr_text:str, source:str='OFFICER_SELECTED')->dict:
    result=assess(ocr_text); result['submitted_type']=submitted_type;result['source']=source
    result['matches_submitted']=bool(result.get('detected_type') and result['detected_type']==submitted_type)
    if result['status']=='DETECTED' and result['detected_type']!=submitted_type:
        result['review_required']=True
        result['finding']={'code':'DOCUMENT_TYPE_CONFLICT','severity':'MEDIUM','status':'REVIEW_REQUIRED','message':f"OCR routing evidence favors {result['detected_type']} while the screening is configured as {submitted_type}. Confirm document type before relying on type-specific checks."}
    elif result['status']=='DETECTED':
        result['review_required']=False
        result['finding']={'code':'DOCUMENT_TYPE_DETECTED','severity':'INFO','message':f"Local OCR routing evidence supports {submitted_type}. This routes parsers/checks; it does not authenticate the document."}
    else:
        result['review_required']=source=='AUTO_DETECTED'
        result['finding']={'code':'DOCUMENT_TYPE_UNCERTAIN','severity':'INFO' if source!='AUTO_DETECTED' else 'MEDIUM','status':'REVIEW_REQUIRED' if source=='AUTO_DETECTED' else 'INFO','message':'Document type routing evidence is '+result['status'].lower()+'. Officer-selected type remains in use; confirm the original document.'}
    return result

_DATE_RE=re.compile(r'\b(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{1,2}\s+[A-Z]{3,9}\s+\d{4})\b',re.I)

def _label_value(text:str, labels:str)->str:
    # Same-line first, then the immediate following non-empty line. Conservative by design.
    same=re.search(rf'(?:{labels})\s*[:#.-]?\s*([^\n|]{{2,180}})',text,re.I)
    if same:
        return same.group(1).strip(' .,:;|-')
    lines=[x.strip() for x in text.splitlines()]
    marker=re.compile(rf'^\s*(?:{labels})(?:\s|[:#.-]|$)',re.I)
    for i,line in enumerate(lines[:-1]):
        if marker.search(line):
            value=lines[i+1].strip(' .,:;|-')
            if value:return value[:180]
    return ''

def extract_fields(ocr_text:str, doc_type:str)->dict:
    """Conservative server-side reparse used only when automatic routing changes type.

    It never uses registry/reference values. Officer-edited fields are preserved by reroute_metadata().
    """
    text=(ocr_text or '').replace('\r','')
    upper=text.upper()
    out={k:'' for k in ('name','dob','nationality','document_number','expiry','passport_reference','issuer_country','gender','issue_date','issuing_authority','visa_type','number_of_entries','valid_from','duration_of_stay')}
    # Name labels. Avoid taking a field label as the value.
    name=_label_value(text,r'FULL\s+NAME|NAME')
    if name and not re.match(r'^(?:DATE|DOB|NATIONALITY|DOCUMENT|PASSPORT|VISA|PAN|EPIC|DL)\b',name,re.I): out['name']=name[:180]
    if not out['name']:
        surname=_label_value(text,r'SURNAME|FAMILY\s+NAME');given=_label_value(text,r'GIVEN\s+NAMES?|FIRST\s+NAME')
        out['name']=' '.join(x for x in (surname,given) if x).strip()[:180]
    def date_after(labels):
        value=_label_value(text,labels); m=_DATE_RE.search(value or '')
        return (m.group(0) if m else value)[:40] if value else ''
    out['dob']=date_after(r'DATE\s+OF\s+BIRTH|BIRTH\s+DATE|D\.?O\.?B\.?')
    out['expiry']=date_after(r'DATE\s+OF\s+EXPIRY|EXPIRY(?:\s+DATE)?|EXPIRATION(?:\s+DATE)?|VALID\s+(?:UNTIL|UPTO|UP\s+TO)|EXPIRES(?:\s+ON)?')
    out['issue_date']=date_after(r'ISSUE\s+DATE|DATE\s+OF\s+ISSUE|ISSUED\s+ON')
    out['nationality']=_label_value(text,r'NATIONALITY|COUNTRY\s+CODE')[:80]
    out['issuer_country']=_label_value(text,r'ISSUING\s+COUNTRY|ISSUER\s+COUNTRY')[:80]
    out['gender']=_label_value(text,r'GENDER|SEX')[:40]
    out['issuing_authority']=_label_value(text,r'ISSUING\s+AUTHORITY')[:180]

    if doc_type=='Aadhaar Card':
        m=re.search(r'\b(\d{4}\s*\d{4}\s*\d{4})\b',text);out['document_number']=re.sub(r'\s+','',m.group(1)) if m else ''
    elif doc_type=='PAN Card':
        m=re.search(r'\b([A-Z]{5}\d{4}[A-Z])\b',upper);out['document_number']=m.group(1) if m else ''
    elif doc_type=='Voter ID (EPIC)':
        m=re.search(r'\b([A-Z]{3}\d{7})\b',upper);out['document_number']=m.group(1) if m else ''
    elif doc_type=='Driving Licence':
        value=_label_value(text,r'DL\s*(?:NO\.?|NUMBER)|LICEN[CS]E\s*(?:NO\.?|NUMBER)')
        if value: out['document_number']=re.sub(r'[^A-Z0-9]','',value.upper())[:80]
        else:
            m=re.search(r'\b([A-Z]{2}\s*[- ]?\s*\d{2}\s*[- ]?\s*\d{4,13})\b',upper);out['document_number']=re.sub(r'[-\s]','',m.group(1)) if m else ''
    elif doc_type=='Passport':
        value=_label_value(text,r'PASSPORT\s*(?:NO\.?|NUMBER)')
        out['document_number']=re.sub(r'[^A-Z0-9]','',value.upper())[:80] if value else ''
        lines=[re.sub(r'[^A-Z0-9<]','',x.upper()) for x in text.splitlines()]
        for i,line in enumerate(lines):
            if line.startswith('P<') and i+1<len(lines):
                l2=lines[i+1]
                if len(l2)>=27:
                    if not out['document_number']:out['document_number']=l2[:9].replace('<','')
                    if not out['nationality']:out['nationality']=l2[10:13].replace('<','')
                break
    elif doc_type=='Visa':
        value=_label_value(text,r'VISA\s*(?:NO\.?|NUMBER)|DOCUMENT\s*(?:NO\.?|NUMBER)')
        out['document_number']=re.sub(r'[^A-Z0-9]','',value.upper())[:80] if value else ''
        ref=_label_value(text,r'PASSPORT\s*(?:NO\.?|NUMBER)');out['passport_reference']=re.sub(r'[^A-Z0-9]','',ref.upper())[:80] if ref else ''
        out['visa_type']=_label_value(text,r'VISA\s*(?:TYPE|CLASS|CATEGORY)|TYPE\s+OF\s+VISA')[:80]
        out['number_of_entries']=_label_value(text,r'NUMBER\s+OF\s+ENTRIES|NO\.?\s+OF\s+ENTRIES|ENTRIES')[:30]
        out['valid_from']=date_after(r'VALID\s+FROM|VALIDITY\s+FROM')
        out['duration_of_stay']=_label_value(text,r'DURATION\s+OF\s+(?:EACH\s+)?STAY|MAX(?:IMUM)?\s+STAY')[:80]
    else:
        value=_label_value(text,r'DOCUMENT\s*(?:NO\.?|NUMBER|ID)|IDENTITY\s+NUMBER|PERMIT\s*(?:NO\.?|NUMBER)|ID\s*(?:NO\.?|NUMBER)')
        out['document_number']=re.sub(r'[^A-Z0-9]','',value.upper())[:80] if value else ''
    return {k:(v or '').strip() for k,v in out.items()}

def reroute_metadata(meta:dict)->dict:
    """Apply automatic type routing to batch metadata without overwriting officer corrections."""
    result=assess(meta.get('ocr_text',''))
    source=meta.get('document_type_source','OFFICER_SELECTED')
    meta['document_type_detection']=result | {'client_reported':meta.get('document_type_detection') or {}}
    if source!='AUTO_DETECTED' or result.get('status')!='DETECTED':
        return meta
    detected=result['detected_type']; old_type=meta.get('type') or 'Passport'
    meta['type']=detected
    parsed=extract_fields(meta.get('ocr_text',''),detected)
    raw=meta.get('ocr_fields') or {}
    field_map={'document_number':'document_number','passport_reference':'passport_reference','issuer_country':'issuer_country','issue_date':'issue_date','issuing_authority':'issuing_authority','visa_type':'visa_type','number_of_entries':'number_of_entries','valid_from':'valid_from','duration_of_stay':'duration_of_stay','name':'name','dob':'dob','nationality':'nationality','expiry':'expiry','gender':'gender'}
    # Frontend raw keys are camelCase for some fields; include both aliases when checking edits.
    aliases={'document_number':'documentNumber','passport_reference':'passportReference','issuer_country':'issuerCountry','issue_date':'issueDate','issuing_authority':'issuingAuthority','visa_type':'visaType','number_of_entries':'numberOfEntries','valid_from':'validFrom','duration_of_stay':'durationOfStay'}
    for target,key in field_map.items():
        current=str(meta.get(target,'') or '').strip();raw_value=str(raw.get(aliases.get(target,target),raw.get(target,'')) or '').strip();candidate=parsed.get(key,'')
        officer_edited=bool(current and raw_value and current!=raw_value)
        if candidate and not officer_edited:
            meta[target]=candidate
    meta['_auto_routed_from']=old_type
    meta['_auto_routed_to']=detected
    return meta
