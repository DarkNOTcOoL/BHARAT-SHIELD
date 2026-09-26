import numpy as np
import cv2
from app import visa_intelligence, risk_policy


def test_visa_field_extraction_and_normalization():
    text='''Visa Type: Tourist\nNumber of Entries: Multiple\nValid From: 01/10/2026\nDuration of Stay: 30 days'''
    parsed=visa_intelligence.extract(text)
    assert parsed['visa_type']=='Tourist'
    assert parsed['number_of_entries']=='Multiple'
    assert parsed['valid_from']=='01/10/2026'
    assert parsed['duration_of_stay']=='30 days'
    checked=visa_intelligence.assess_fields({**parsed,'expiry':'31/12/2026','issue_date':'25/09/2026'},text)
    assert checked['status']=='COMPLETE'
    assert checked['normalized_entries']=='MULTIPLE'


def test_visa_validity_order_conflict():
    checked=visa_intelligence.assess_fields({'visa_type':'Tourist','number_of_entries':'1','valid_from':'2027-01-01','expiry':'2026-12-31','issue_date':'2026-09-25'},'')
    assert checked['status']=='REVIEW_REQUIRED'
    assert any(x['code']=='VISA_VALIDITY_ORDER_CONFLICT' for x in checked['findings'])


def _stamp_fixture():
    img=np.full((700,1000,3),235,np.uint8)
    cv2.rectangle(img,(80,90),(920,610),(190,190,190),2)
    cv2.circle(img,(720,430),85,(30,60,180),8)
    cv2.putText(img,'ENTRY',(655,440),cv2.FONT_HERSHEY_SIMPLEX,1.1,(30,60,180),3,cv2.LINE_AA)
    return img


def test_stamp_candidate_alone_is_not_tamper_verdict():
    img=_stamp_fixture()
    result,_=visa_intelligence.analyze_stamp_seal(img,[],enabled=True)
    assert result['status'] in {'CANDIDATES_FOUND','NO_STAMP_LIKE_REGION_DETECTED'}
    assert result['status']!='REVIEW_REQUIRED'
    assert 'not' in result['limitation'].lower()


def test_stamp_and_generic_tamper_share_forensic_risk_family():
    fields={'name':'DEMO PERSON','document_number':'VISA123','dob':'2000-01-01','nationality':'IND','issuer_country':'IND'}
    findings=[{'code':'AI_TAMPER_ANOMALY'},{'code':'STAMP_SEAL_TAMPER_REVIEW'}]
    score=risk_policy.assess({'status':'MATCH','fields':[]},{},findings,fields,{'status':'USABLE'},95,'NOT_SUPPORTED')
    assert score['score']==30
    assert [f for f in score['factors'] if f['group']=='forensic_integrity'][0]['points']==30


def test_system_status_advertises_visa_step(client):
    status=client.get('/api/system/status').json()
    assert status['visa_intelligence']=='LOCAL_LABEL_EXTRACTION_AND_RULES_V1'
    assert status['stamp_seal']=='LOCAL_CV_FORENSIC_ASSIST_V1'
    assert status['engine'].startswith('7.1.0')

def test_full_visa_screening_records_visa_and_stamp_evidence(client):
    import json
    from pathlib import Path
    data=(Path(__file__).resolve().parents[2]/'demo_samples/visa_intelligence/03_visa_stamp_suspicious.png').read_bytes()
    meta={'type':'Visa','name':'RIYA DEMO','dob':'12/04/1998','nationality':'IND','document_number':'VISA26001','passport_reference':'PDEMO2601','expiry':'31/03/2027','issuer_country':'IND','issue_date':'20/09/2026','issuing_authority':'DEMO VISA AUTHORITY','visa_type':'TOURIST','number_of_entries':'MULTIPLE','valid_from':'01/10/2026','duration_of_stay':'30 DAYS','ocr_text':'Visa Type: TOURIST\nNumber of Entries: MULTIPLE\nValid From: 01/10/2026\nDuration of Stay: 30 DAYS','ocr_confidence':95}
    r=client.post('/api/screening/batch',headers={'X-Local-Request':'1'},data={'documents_json':json.dumps([meta])},files=[('files',('visa.png',data,'image/png'))])
    assert r.status_code==200,r.text
    a=r.json()['screenings'][0]['result']['ai_analysis']
    assert a['visa_intelligence']['fields']['visa_type']=='TOURIST'
    assert a['forensic_assist']['stamp_seal']['status']=='REVIEW_REQUIRED'
    assert any(f['code']=='STAMP_SEAL_TAMPER_REVIEW' for f in r.json()['screenings'][0]['result']['findings'])
