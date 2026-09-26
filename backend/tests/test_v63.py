import base64, io, json
from PIL import Image, ImageDraw
import numpy as np

from app import capture_intelligence, intake
from tests.test_local import image_bytes


def decode_data_uri(uri):
    raw=base64.b64decode(uri.split(',',1)[1]);return Image.open(io.BytesIO(raw)).convert('L')


def test_prepare_returns_same_geometry_ocr_variants():
    result=intake.prepare(image_bytes())
    assert result['metadata']['method']=='ADVANCED_SAME_GEOMETRY_OCR_PREP_V63'
    assert result['metadata']['capture_intelligence']['method']=='LOCAL_CAPTURE_INTELLIGENCE_V1'
    variants=result['ocr_variants']
    assert len(variants)==3
    assert {v['id'] for v in variants}=={'clahe_sharpen','illumination_normalized','adaptive_binary'}
    dims=tuple(result['metadata']['working_dimensions'])
    for variant in variants:
        assert variant['geometry_preserved'] is True
        assert decode_data_uri(variant['image']).size==dims


def test_glare_localization_is_capture_quality_not_authenticity():
    arr=np.full((700,1000,3),150,np.uint8)
    # Strong low-texture saturated patch, surrounded by mid-tone background.
    arr[180:420,300:700]=255
    result=capture_intelligence.glare_analysis(arr)
    assert result['status'] in {'REVIEW','RECAPTURE_RECOMMENDED'}
    assert result['coverage']>0
    assert result['regions']
    assert 'authenticity' in result['limitation'].lower()


def test_capture_analysis_keeps_geometry_policy_explicit():
    img=Image.new('RGB',(1000,700),'white');d=ImageDraw.Draw(img)
    d.rectangle((70,80,930,620),outline='black',width=8)
    for y in range(150,560,50):d.line((140,y,850,y+5),fill='black',width=4)
    result=capture_intelligence.analyze(np.asarray(img))
    assert result['boundary']['status'] in {'DETECTED','UNCERTAIN'}
    assert 'preserve' in result['geometry_policy'].lower()
    assert result['skew']['limitation']


def test_system_status_advertises_v63_capture_and_ocr(client):
    status=client.get('/api/system/status').json()
    assert status['capture_intelligence']=='LOCAL_CAPTURE_INTELLIGENCE_V1'
    assert status['ocr_preprocessing']=='MULTI_PREPROCESSING_TESSERACT_FALLBACK_V1'
    assert status['engine'].startswith('7.1.0') and status['capture_intelligence']=='LOCAL_CAPTURE_INTELLIGENCE_V1'


def test_screening_saves_capture_and_multi_ocr_evidence(client):
    prep={'capture_intelligence':{'method':'LOCAL_CAPTURE_INTELLIGENCE_V1','glare':{'status':'NO_STRONG_GLARE','coverage':0,'regions':[]},'skew':{'deskew_recommended':False},'illumination':{'status':'EVEN_ENOUGH'}},
          'ocr_preprocessing':{'method':'MULTI_PREPROCESSING_TESSERACT_FALLBACK_V1','primary':'clahe_sharpen','variant_ids':['clahe_sharpen','illumination_normalized','adaptive_binary'],'geometry_preserved':True}}
    notes={'preparation':prep,'multi_ocr':{'performed':True,'selected':'illumination_normalized','read_count':3},'ocr_ms':123}
    meta={'type':'PAN Card','name':'SAMPLE PERSON','dob':'01/01/1990','document_number':'ABCDE1234F','nationality':'IND','issuer_country':'IND','ocr_text':'SAMPLE PERSON ABCDE1234F','ocr_confidence':95,'ocr_notes':json.dumps(notes)}
    r=client.post('/api/screening/batch',headers={'X-Local-Request':'1'},data={'documents_json':json.dumps([meta])},files=[('files',('sample.png',image_bytes(),'image/png'))])
    assert r.status_code==200,r.text
    saved=client.get('/api/screening/'+r.json()['screenings'][0]['id']).json()
    analysis=saved['result']['ai_analysis']
    assert analysis['capture_intelligence']['method']=='LOCAL_CAPTURE_INTELLIGENCE_V1'
    assert analysis['ocr_strategy']['multi_ocr']['selected']=='illumination_normalized'
    assert saved['result']['ocr_method'].startswith('Local Tesseract.js + v7.1') and 'Multi-Preprocessing' in saved['result']['ocr_method']


def test_server_recomputed_strong_glare_routes_recapture(client):
    image=Image.new('RGB',(1000,700),(150,150,150));draw=ImageDraw.Draw(image)
    draw.text((40,40),'SAMPLE PERSON ABCDE1234F',fill='black')
    draw.rectangle((300,180,700,420),fill='white')
    buf=io.BytesIO();image.save(buf,format='PNG')
    notes={'preparation':{'capture_intelligence':{'method':'BROWSER_REPORT_SHOULD_NOT_BE_AUTHORITATIVE','glare':{'status':'NO_STRONG_GLARE'}},'ocr_preprocessing':{'method':'MULTI_PREPROCESSING_TESSERACT_FALLBACK_V1'}}}
    meta={'type':'PAN Card','name':'SAMPLE PERSON','dob':'01/01/1990','document_number':'ABCDE1234F','nationality':'IND','issuer_country':'IND','ocr_text':'SAMPLE PERSON ABCDE1234F','ocr_confidence':95,'ocr_notes':json.dumps(notes)}
    r=client.post('/api/screening/batch',headers={'X-Local-Request':'1'},data={'documents_json':json.dumps([meta])},files=[('files',('glare.png',buf.getvalue(),'image/png'))])
    assert r.status_code==200,r.text
    item=r.json()['screenings'][0]
    assert item['result']['ai_analysis']['capture_intelligence']['server_recomputed'] is True
    assert item['recommendation']=='RECAPTURE'
    assert any(f['code']=='CAPTURE_GLARE' for f in item['result']['findings'])
