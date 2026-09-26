import io
import json
import os
import tempfile
from pathlib import Path
import socket
import pytest
from PIL import Image,ImageDraw
from fastapi.testclient import TestClient

# Test state and authenticated fixtures are isolated in conftest.py.
from app import main,local_security,local_analysis,local_registry

def image_bytes(blank=False):
    image=Image.new('RGB',(1000,700),'white');draw=ImageDraw.Draw(image)
    if not blank:
        for y in range(10,690,20):
            draw.text((10,y),'SYNTHETIC DOCUMENT ABCDE1234F SAMPLE TEST ONLY '*3,fill='black')
    buf=io.BytesIO();image.save(buf,format='PNG');return buf.getvalue()

def upload(client,**updates):
    meta={'type':'PAN Card','name':'SAMPLE PERSON','dob':'01/01/1990','document_number':'ABCDE1234F','nationality':'IND','issuer_country':'IND','ocr_text':'SAMPLE PERSON ABCDE1234F','ocr_confidence':95}
    meta.update(updates)
    return client.post('/api/screening/batch',headers={'X-Local-Request':'1'},data={'documents_json':json.dumps([meta])},files=[('files',('sample.png',image_bytes(),'image/png'))])

def test_auth_required():
    with TestClient(main.app) as anon:
        for path in ['/api/screenings','/api/system/status','/api/audit-logs','/api/screening/foo/image']:
            assert anon.get(path).status_code==401
        assert anon.get('/uploads/test.png').status_code==404
        assert anon.post('/api/auth/login',json={'username':'unknown','password':'wrong'}).status_code==403
        assert anon.post('/api/auth/login',headers={'X-Local-Request':'1'},json={'username':'unknown','password':'wrong'}).status_code==401

def test_foreign_origin(client):
    r=client.post('/api/auth/logout',headers={'X-Local-Request':'1','Origin':'https://example.com'})
    assert r.status_code==403

def test_clean_has_missing_checks_not_fake(client):
    r=upload(client);assert r.status_code==200,r.text
    s=r.json()['screenings'][0]
    assert s['risk']=='LOW'
    assert s['recommendation']=='REVIEW_COMPLETE_CHECKS'
    assert s['status']!='Verified'
    assert s['confidence']<100
    assert s['result']['ai_analysis']['checks']['tampering'] in {'COMPLETE','INCONCLUSIVE'}
    assert s['result']['watchlist_status']=='NOT_CONNECTED'

def test_blur_is_recapture():
    with main.SessionLocal() as db:
        result=main.verify_document(db,{'name':'Sample','document_number':'ABCDE1234F','dob':'01/01/1990'},'PAN Card',95,'Sample',image_bytes(True),'SINGLE_DOCUMENT')
    assert result['risk']=='UNASSESSED'
    assert result['recommendation']=='RECAPTURE'

def test_missing_ocr_does_not_mean_fraud(client):
    s=upload(client,ocr_confidence=0,ocr_text='').json()['screenings'][0]
    assert s['risk']=='UNASSESSED' and s['recommendation']=='RECAPTURE'

def test_bad_metadata_rejected(client):
    for meta in ['{}','[null]','[{"ocr_confidence":NaN}]','[{"ocr_confidence":101}]']:
        r=client.post('/api/screening/batch',headers={'X-Local-Request':'1'},data={'documents_json':meta},files=[('files',('a.png',image_bytes(),'image/png'))])
        assert r.status_code==400

def test_invalid_image_rejected(client):
    r=client.post('/api/screening/batch',headers={'X-Local-Request':'1'},data={'documents_json':'[{}]'},files=[('files',('a.png',b'not image','image/png'))])
    assert r.status_code==400

def test_dates_and_expiry(client):
    assert main.parse_date('31/02/2020') is None
    assert main.parse_date('2020-02-29')==(2020,2,29)
    r=upload(client,type='Visa',expiry='01/01/2000')
    assert r.status_code==200
    s=r.json()['screenings'][0]
    assert any(f['code']=='DOCUMENT_EXPIRED' for f in s['result']['findings'])
    assert s['recommendation']=='MANUAL_REVIEW'

def test_visa_own_number_not_passport():
    docs=[{'type':'Passport','document_number':'P1234567','name':'SAMPLE'},{'type':'Visa','document_number':'V7654321','name':'SAMPLE'}]
    _,_,findings=main.cross_verify(docs)
    assert not any(f['code']=='CROSS_PASSPORT_LINK' and f['severity']=='HIGH' for f in findings)
    docs[1]['passport_reference']='P1234567'
    assert any(f['code']=='CROSS_PASSPORT_LINK' and f['severity']=='PASS' for f in main.cross_verify(docs)[2])
    docs[1]['passport_reference']='OTHER'
    assert any(f['code']=='CROSS_PASSPORT_LINK' and f['severity']=='HIGH' for f in main.cross_verify(docs)[2])

def test_empty_cross_is_insufficient():
    assert main.cross_verify([{},{}])[1]=='INSUFFICIENT_EVIDENCE'

def test_mrz_failure_and_dates():
    mrz='P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F1204159ZE184226B<<<<<10'
    # Standard TD3 test vector; the line finder requires >= 40 characters.
    result=main.validate_passport_mrz(mrz,{'dob':'13/08/1974'})
    assert any(f['code']=='MRZ_VIZ_DOB_CONFLICT' for f in result['findings'])
    bad=main.validate_passport_mrz(mrz.replace('L898902C36','L898902C30'),{})
    assert bad['detected'] and not bad['valid']

def test_encrypted_original_and_evidence(client):
    s=upload(client).json()['screenings'][0]
    with main.SessionLocal() as db:
        row=db.scalar(main.select(main.Screening).where(main.Screening.screening_id==s['id']))
        raw=Path(row.stored_path).read_bytes()
        assert raw!=image_bytes()
        assert main.DOCUMENT_CIPHER.decrypt(raw)==image_bytes()
    evidence=client.get('/api/screening/'+s['id']+'/evidence')
    assert evidence.status_code==200 and evidence.json()['hash_integrity_ok']
    assert client.get('/api/screening/'+s['id']+'/image?view=residual').headers['content-type']=='image/png'

def test_decision_reason_and_actor(client):
    s=upload(client).json()['screenings'][0]
    path='/api/screening/'+s['id']+'/decision?action=ACCEPT'
    assert client.post(path,headers={'X-Local-Request':'1'},data={'reason':'short'}).status_code==400
    assert client.post(path,headers={'X-Local-Request':'1'},data={'reason':'Manually checked the document.'}).status_code==200
    new=client.get('/api/screening/'+s['id']).json()
    assert new['status']=='Verified' and new['recommendation']=='REVIEW_COMPLETE_CHECKS'
    logs=client.get('/api/audit-logs').json()
    assert logs[0]['officer']=='tester'

def test_review_override_requires_supervisor(client):
    s=upload(client,ocr_confidence=0).json()['screenings'][0]
    path='/api/screening/'+s['id']+'/decision?action=ACCEPT'
    assert client.post(path,headers={'X-Local-Request':'1'},data={'reason':'Manually reviewed original.'}).status_code==403

def test_face_empty_returns_inconclusive(client):
    s=upload(client).json()['screenings'][0]
    r=client.post('/api/screening/'+s['id']+'/face',headers={'X-Local-Request':'1'},files={'photo':('blank.png',image_bytes(True),'image/png')})
    assert r.status_code==200,r.text
    assert r.json()['status'] in {'NOT_RUN','INCONCLUSIVE'}
    assert r.json()['liveness']=='NOT_RUN'

def test_status_and_dashboard(client):
    assert client.get('/api/system/status').json()['external_ai']=='REMOVED'
    for path in ['/api/dashboard/summary','/api/cases','/api/watchlist','/api/reference/summary']:
        assert client.get(path).status_code==200

def test_logout_invalidates_session():
    with TestClient(main.app) as c:
        c.post('/api/auth/login',headers={'X-Local-Request':'1'},json={'username':'supervisor','password':'test-password-12345'})
        assert c.get('/api/auth/me').status_code==200
        c.post('/api/auth/logout',headers={'X-Local-Request':'1'})
        assert c.get('/api/auth/me').status_code==401
