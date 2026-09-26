import json
from app import document_type, main
from tests.test_local import upload, image_bytes


def test_document_type_router_detects_strong_types():
    assert document_type.assess('REPUBLIC OF INDIA\nPASSPORT\nP<INDDOE<<JANE<<<<<<<<<<<<<<<<<<<<<<<<')['detected_type']=='Passport'
    assert document_type.assess('INDIA E-VISA\nENTRIES: MULTIPLE\nVALID FROM: 01/01/2026\nDURATION OF STAY: 90 DAYS')['detected_type']=='Visa'
    assert document_type.assess('INCOME TAX DEPARTMENT\nPERMANENT ACCOUNT NUMBER\nABCDE1234F')['detected_type']=='PAN Card'
    assert document_type.assess('UNIQUE IDENTIFICATION AUTHORITY OF INDIA\nAADHAAR\n1234 5678 9012')['detected_type']=='Aadhaar Card'


def test_document_type_conflict_is_review_evidence():
    result=document_type.compare('Passport','INCOME TAX DEPARTMENT\nPERMANENT ACCOUNT NUMBER\nABCDE1234F','OFFICER_SELECTED')
    assert result['review_required'] is True
    assert result['finding']['code']=='DOCUMENT_TYPE_CONFLICT'


def test_screening_saves_type_routing_evidence(client):
    item=upload(client,document_type='PAN Card',document_number='ABCDE1234F',ocr_text='INCOME TAX DEPARTMENT\nPERMANENT ACCOUNT NUMBER\nABCDE1234F').json()['screenings'][0]
    saved=client.get('/api/screening/'+item['id']).json()
    routed=saved['result']['ai_analysis']['document_type_detection']
    assert routed['detected_type']=='PAN Card'
    assert any(f['code']=='DOCUMENT_TYPE_DETECTED' for f in saved['result']['findings'])


def test_system_status_advertises_auto_document_routing(client):
    status=client.get('/api/system/status').json()
    assert status['document_type_routing']=='LOCAL_EXPLAINABLE_DOCUMENT_TYPE_ROUTER_V1'
    assert status['ocr_routing']=='AUTO_DOCUMENT_FIELD_REPARSE_V1'
    assert status['engine'].startswith('7.1.0')


def test_auto_reroute_changes_default_passport_to_pan_without_registry_help():
    meta={'type':'Passport','document_type_source':'AUTO_DETECTED','ocr_text':'INCOME TAX DEPARTMENT\nPERMANENT ACCOUNT NUMBER\nABCDE1234F\nName: DEMO USER\nDOB: 01/01/2000','ocr_fields':{},'document_number':'','name':'','dob':''}
    routed=document_type.reroute_metadata(meta)
    assert routed['type']=='PAN Card'
    assert routed['document_number']=='ABCDE1234F'
    assert routed['name']=='DEMO USER'


def test_auto_reroute_preserves_officer_corrected_value():
    meta={'type':'Passport','document_type_source':'AUTO_DETECTED','ocr_text':'INCOME TAX DEPARTMENT\nPERMANENT ACCOUNT NUMBER\nABCDE1234F\nName: OCR USER','ocr_fields':{'name':'OCR USER'},'name':'OFFICER CORRECTED','document_number':''}
    routed=document_type.reroute_metadata(meta)
    assert routed['type']=='PAN Card'
    assert routed['name']=='OFFICER CORRECTED'


def test_batch_auto_routing_changes_effective_document_type(client):
    meta={'type':'Passport','document_type_source':'AUTO_DETECTED','ocr_text':'INCOME TAX DEPARTMENT\nPERMANENT ACCOUNT NUMBER\nABCDE1234F\nName: AUTO ROUTED USER\nDOB: 01/01/2000','ocr_confidence':90,'name':'AUTO ROUTED USER','dob':'01/01/2000','document_number':'','ocr_fields':{}}
    response=client.post('/api/screening/batch',headers={'X-Local-Request':'1'},data={'documents_json':json.dumps([meta])},files=[('files',('auto-pan.png',image_bytes(),'image/png'))])
    assert response.status_code==200,response.text
    item=response.json()['screenings'][0]
    assert item['type']=='PAN Card'
    assert item['number']=='ABCDE1234F'
    assert item['result']['ai_analysis']['document_type_detection']['matches_submitted'] is True
