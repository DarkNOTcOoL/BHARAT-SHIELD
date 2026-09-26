import io, json
import numpy as np
from PIL import Image, ImageDraw
from app import template_layout
from tests.test_local import image_bytes


def notes(boxes):
    return json.dumps({'field_boxes':boxes,'geometry_frame':'NORMALIZED_EXIF_ORIENTED_ORIGINAL'})


def canvas():
    return np.asarray(Image.new('RGB',(1000,650),'white'))


def test_layout_needs_real_ocr_geometry():
    result,_=template_layout.analyze(canvas(),'PAN Card',notes([{'field':'name','box':[.3,.25,.2,.05]}]),{},'')
    assert result['status']=='INCONCLUSIVE'
    assert result['layout_anomaly_index'] is None


def test_clean_broad_pan_layout_not_flagged():
    boxes=[
        {'field':'name','box':[.34,.28,.30,.06],'confidence':92},
        {'field':'dob','box':[.35,.46,.18,.05],'confidence':91},
        {'field':'documentNumber','box':[.34,.60,.24,.06],'confidence':94},
    ]
    result,_=template_layout.analyze(canvas(),'PAN Card',notes(boxes),{},'')
    assert result['status'] in {'NO_STRONG_LAYOUT_ANOMALY','OBSERVATIONS'}
    assert not any(s['code']=='FIELD_ZONE_DISPLACEMENT' for s in result['signals'])


def test_multiple_displaced_fields_require_review():
    boxes=[
        {'field':'name','box':[.20,.91,.25,.04]},
        {'field':'documentNumber','box':[.55,.92,.24,.04]},
        {'field':'dob','box':[.34,.48,.18,.05]},
    ]
    result,_=template_layout.analyze(canvas(),'PAN Card',notes(boxes),{},'')
    assert result['status']=='REVIEW_REQUIRED'
    assert result['layout_anomaly_index']>0
    assert sum(s['code']=='FIELD_ZONE_DISPLACEMENT' for s in result['signals'])>=2


def test_field_overlapping_photo_is_high_risk_zone_signal():
    boxes=[
        {'field':'name','box':[.13,.24,.24,.06]},
        {'field':'dob','box':[.42,.48,.18,.05]},
    ]
    photo={'photo_region':[.08,.12,.34,.48]}
    result,_=template_layout.analyze(canvas(),'PAN Card',notes(boxes),photo,'')
    assert result['status']=='REVIEW_REQUIRED'
    assert any(s['code']=='FIELD_PHOTO_OVERLAP' for s in result['signals'])


def test_system_status_advertises_v64_layout(client):
    status=client.get('/api/system/status').json()
    assert status['template_layout']=='LOCAL_EXPLAINABLE_LAYOUT_SECURITY_ZONE_V1'
    assert status['engine'].startswith('7.1.0')


def test_screening_routes_layout_review_to_manual_review(client):
    ocr_notes=notes([
        {'field':'name','box':[.18,.91,.24,.04],'confidence':94},
        {'field':'documentNumber','box':[.56,.92,.25,.04],'confidence':95},
        {'field':'dob','box':[.34,.48,.18,.05],'confidence':92},
    ])
    meta={'type':'PAN Card','name':'SAMPLE PERSON','dob':'01/01/1990','document_number':'ABCDE1234F','nationality':'IND','issuer_country':'IND',
          'ocr_text':'INCOME TAX DEPARTMENT SAMPLE PERSON 01/01/1990 ABCDE1234F','ocr_confidence':95,'ocr_notes':ocr_notes}
    r=client.post('/api/screening/batch',headers={'X-Local-Request':'1'},data={'documents_json':json.dumps([meta])},files=[('files',('layout.png',image_bytes(),'image/png'))])
    assert r.status_code==200,r.text
    item=r.json()['screenings'][0]
    layout=item['result']['ai_analysis']['forensic_assist']['template_layout']
    assert layout['status']=='REVIEW_REQUIRED'
    assert item['recommendation']=='MANUAL_REVIEW'
    assert any(f['code']=='LAYOUT_SECURITY_ZONE_REVIEW' for f in item['result']['findings'])
    assert client.get('/api/screening/'+item['id']+'/image?view=layout').headers['content-type']=='image/png'
