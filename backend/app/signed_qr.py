"""BS52 synthetic credentials only. Never fetch keys, URLs, or issuer metadata."""
import base64
import hashlib
import json
import re
from pathlib import Path
from datetime import date
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from pydantic import BaseModel,ConfigDict,Field,ValidationError
from .local_registry import COMPARE_FIELDS,normalized_field,normalized_date

TRUST=Path(__file__).resolve().parents[1]/'trust'/'demo_issuers.json'
PREFIX='BS52.'
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
def b64(data):return base64.urlsafe_b64encode(data).decode().rstrip('=')
def unb64(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',value):raise ValueError('Invalid encoding')
    return base64.urlsafe_b64decode(value+'='*((-len(value))%4))
def no_duplicates(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Repeated JSON key')
        result[key]=value
    return result
class Claims(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    schema_version:str=Field(alias='schema',pattern=r'^BS52-DEMO-1$')
    issuer:str=Field(min_length=1,max_length=80)
    key_id:str=Field(pattern=r'^[A-Za-z0-9_-]{1,60}$')
    credential_id:str=Field(pattern=r'^[A-Za-z0-9-]{8,80}$')
    registry_id:str=Field(min_length=1,max_length=80)
    registry_version:int=Field(ge=1)
    document_type:str=Field(min_length=1,max_length=60)
    fields:dict[str,str]

def verify_text(value,trust=None):
    result={'signature_status':'UNSUPPORTED_QR','claims':None,'key_fingerprint':None,'message':'QR does not use the synthetic BS52 format.'}
    if not value.startswith(PREFIX):return result
    try:
        if len(value)>6000:raise ValueError('QR too large')
        _,payload,signature=value.split('.')
        raw=unb64(payload);sig=unb64(signature)
        obj=json.loads(raw,object_pairs_hook=no_duplicates)
        c=Claims.model_validate(obj)
        if raw!=canonical(obj) or len(sig)!=64:raise ValueError('Noncanonical credential')
        if set(c.fields)!=set(COMPARE_FIELDS) or any(len(v)>180 for v in c.fields.values()):raise ValueError('Invalid fields')
        for key in ['dob','issue_date','expiry']:
            if not c.fields[key] or normalized_date(c.fields[key])!=c.fields[key]:raise ValueError('Dates must be ISO and present')
        if not c.fields['dob']<=c.fields['issue_date']<=c.fields['expiry']:raise ValueError('Invalid date order')
        result['credential_hash']=hashlib.sha256(raw).hexdigest()
        try:keys=trust if trust is not None else json.loads(TRUST.read_text())
        except (OSError,ValueError):
            result.update(signature_status='TRUST_UNAVAILABLE',message='Local demo trust file unavailable. Signature not verified.');return result
        if not isinstance(keys,dict):raise ValueError('Invalid trust configuration')
        entry=keys.get(c.key_id)
        if entry is not None and not isinstance(entry,dict):raise ValueError('Invalid trust entry')
        if not entry:
            result.update(signature_status='UNKNOWN_DEMO_ISSUER',message='No locally trusted demo key for this credential.');return result
        if not entry.get('enabled',False):
            result.update(signature_status='DEMO_KEY_DISABLED',message='This local demo issuer key is disabled.');return result
        key=unb64(entry['public_key']);fingerprint=hashlib.sha256(key).hexdigest()
        if fingerprint!=entry['sha256']:raise ValueError('Trust key fingerprint mismatch')
        result['key_fingerprint']=fingerprint
        try:Ed25519PublicKey.from_public_bytes(key).verify(sig,raw)
        except InvalidSignature:
            result.update(signature_status='SIGNATURE_INVALID',message='The synthetic QR signature does not verify. Review required.');return result
        if c.issuer!=entry['issuer']:raise ValueError('Issuer name inconsistent with configured key')
        result.update(signature_status='SIGNATURE_VALID',claims=obj,message='Signature valid under the configured synthetic demo issuer key. Printed fields and person require separate checks.')
        return result
    except (ValueError,TypeError,KeyError,ValidationError,UnicodeError):
        result.update(signature_status='MALFORMED_SIGNED_QR',claims=None,message='Malformed or unsupported synthetic signed payload. No trusted identity extracted.');return result

def scan_image(data):
    result={'signature_status':'NO_SIGNED_QR','claims':None,'message':'No QR code detected. Absence does not establish fraud.'}
    try:
        import numpy as np
        from .local_analysis import decode
        image=decode(data);image.thumbnail((2800,2800));array=np.asarray(image)
        try:
            import zxingcpp
            codes=zxingcpp.read_barcodes(array,formats=zxingcpp.BarcodeFormat.QRCode)
            valid=[c.text for c in codes if c.valid and c.text]
            if len(valid)>1:return result|{'signature_status':'MULTIPLE_QR_CODES','message':'Multiple readable QR codes found; none selected automatically.'}
            if valid:return verify_text(valid[0])
            if codes:return result|{'signature_status':'QR_UNREADABLE','message':'QR detected but decoding failed.'}
            return result
        except ImportError:
            # OpenCV fallback keeps the package functional when the optional zxing-cpp
            # wheel is unavailable. No network/download is attempted.
            import cv2
            detector=cv2.QRCodeDetector()
            try:
                ok,decoded,points,_=detector.detectAndDecodeMulti(array)
                readable=[x for x in (decoded or ()) if x]
                if len(readable)>1:return result|{'signature_status':'MULTIPLE_QR_CODES','message':'Multiple readable QR codes found; none selected automatically.'}
                if len(readable)==1:return verify_text(readable[0])
                if ok or points is not None:return result|{'signature_status':'QR_UNREADABLE','message':'QR detected but decoding failed.'}
            except cv2.error:
                pass
            text,points,_=detector.detectAndDecode(array)
            if text:return verify_text(text)
            if points is not None:return result|{'signature_status':'QR_UNREADABLE','message':'QR detected but decoding failed.'}
            return result
    except Exception:return result|{'signature_status':'QR_UNREADABLE','message':'Local QR decoding failed. Recapture or review required.'}

def compare(qr,document_type,fields,registry):
    result=dict(qr);result['comparisons']=[];result['findings']=[]
    record=registry.get('record') or {};claims=qr.get('claims')
    required=bool(record.get('requires_signed_qr'))
    result['required_by_registry']=required
    if not claims:
        result['comparison_status']='UNVERIFIED'
        result['requires_review']=required or qr['signature_status'] not in {'NO_SIGNED_QR','UNSUPPORTED_QR'}
        if result['requires_review']:result['findings']=[{'code':'SIGNED_QR_UNVERIFIED','severity':'MEDIUM','message':qr['message']}]
        return result
    statuses=[]
    for key in COMPARE_FIELDS:
        signed=claims['fields'].get(key,'');observed=fields.get(key,'');reference=record.get(key,'')
        def match(a,b):
            if not a and not b:return 'NOT_APPLICABLE'
            if not a or not b:return 'MISSING'
            lhs=normalized_field(key,a);rhs=normalized_field(key,b)
            return 'MATCH' if lhs and rhs and lhs==rhs else 'CONFLICT'
        printed=match(observed,signed);registered=match(reference,signed) if record else 'MISSING'
        statuses.extend([printed,registered]);result['comparisons'].append({'field':key,'reviewed':observed,'signed':signed,'registry':reference,'printed_vs_signed':printed,'registry_vs_signed':registered})
    identity=claims['document_type']==document_type and claims['registry_id']==record.get('id')
    version=claims['registry_version']==record.get('version')
    result['reference_status']='MATCH' if identity and version else 'REFERENCE_VERSION_CHANGED' if identity else 'REFERENCE_CONFLICT'
    if not identity:statuses.append('CONFLICT' if record else 'MISSING')
    if not version:statuses.append('MISSING')
    if claims['fields']['expiry']<date.today().isoformat():statuses.append('CONFLICT');result['findings'].append({'code':'SIGNED_CREDENTIAL_EXPIRED','severity':'HIGH','message':'Signed demo credential expiry is in the past.'})
    result['comparison_status']='SIGNED_DATA_CONFLICT' if 'CONFLICT' in statuses else 'PARTIAL' if 'MISSING' in statuses else 'CONSISTENT'
    result['requires_review']=result['comparison_status']!='CONSISTENT'
    if result['requires_review']:result['findings'].append({'code':result['comparison_status'],'severity':'HIGH' if 'CONFLICT' in statuses else 'MEDIUM','message':'Signed/printed/reference comparison: '+result['comparison_status']+'. Signature validity does not resolve this discrepancy.'})
    return result
