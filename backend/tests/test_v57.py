import io, json
import numpy as np
from PIL import Image, ImageDraw
from app import intake, risk_policy


def fixture_bytes(tampered=False):
    image=Image.new('RGB',(1000,650),'white');draw=ImageDraw.Draw(image)
    for y in range(80,580,60):
        draw.text((100,y),f'FIELD {y} VALUE 123456789',fill='black')
    if tampered:
        arr=np.asarray(image).copy();rng=np.random.default_rng(7)
        arr[280:380,600:780]=rng.integers(0,256,(100,180,3),dtype=np.uint8)
        image=Image.fromarray(arr)
    out=io.BytesIO();image.save(out,format='JPEG',quality=95);return out.getvalue()


def test_local_unsupervised_tamper_anomaly_is_conservative_and_localizes():
    clean=intake.forensic(fixture_bytes(False))['tamper_ai']
    assert clean['status']=='NO_STRONG_ANOMALY'
    notes=json.dumps({'field_boxes':[{'field':'expiry','box':[.58,.40,.24,.22]}]})
    suspicious=intake.forensic(fixture_bytes(True),ocr_notes=notes)['tamper_ai']
    assert suspicious['status']=='REVIEW_REQUIRED'
    assert suspicious['strong_region_count']>=1
    assert suspicious['max_anomaly_score']>=82
    assert 'expiry' in suspicious['affected_fields']
    assert 'NOT a probability' in suspicious['score_meaning']


def test_tamper_anomaly_is_explainable_review_points_not_probability():
    fields={'name':'DEMO PERSON','document_number':'DEMO1','dob':'2000-01-01','nationality':'IND','issuer_country':'IND'}
    score=risk_policy.assess({'status':'MATCH','fields':[]},{},[{'code':'AI_TAMPER_ANOMALY'}],fields,{'status':'USABLE'},95,'NOT_APPLICABLE')
    assert score['score']==20
    assert score['band']=='REVIEW'
    assert score['factors'][0]['group']=='forensic_integrity'
    assert 'not a calibrated probability' in score['limitation']
