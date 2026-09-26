import base64,hashlib,io,json
from pathlib import Path
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from app import main,intake,signed_qr
from test_local import upload,image_bytes
HEAD={'X-Local-Request':'1'}
SAMPLE=Path(__file__).resolve().parents[2]/'demo_samples'/'signed_qr'/'01_signed_match.png'

def test_prepare_authentication_and_invalid_upload(client):
    with TestClient(main.app) as anon:assert anon.post('/api/intake/prepare',headers=HEAD,files={'file':('x.png',b'x','image/png')}).status_code==401
    assert client.post('/api/intake/prepare',headers=HEAD,files={'file':('x.png',b'x','image/png')}).status_code==400
    assert client.post('/api/intake/prepare',headers=HEAD,files={'file':('x.png',b'x'*(10*1024*1024+1),'image/png')}).status_code==400

def test_preparation_masks_qr_without_altering_original(client):
    data=SAMPLE.read_bytes();digest=hashlib.sha256(data).hexdigest()
    r=client.post('/api/intake/prepare',headers=HEAD,files={'file':('signed.png',data,'image/png')})
    assert r.status_code==200,r.text
    prepared=r.json();assert prepared['metadata']['qr_regions'] and prepared['metadata']['original_sha256']==digest
    working=base64.b64decode(prepared['image'].split(',',1)[1])
    assert signed_qr.scan_image(working)['signature_status']=='NO_SIGNED_QR'
    assert signed_qr.scan_image(data)['signature_status']=='SIGNATURE_VALID'
    assert hashlib.sha256(data).hexdigest()==digest

def test_quality_guidance_no_false_authenticity_claim():
    result=intake.prepare(image_bytes(blank=True))
    assert result['metadata']['guidance'] and 'authenticity' not in result
    assert result['metadata']['quality']['status']=='RECAPTURE'

def test_forensic_outputs_are_bounded_inspection_aids():
    data=image_bytes();result=intake.forensic(data)
    assert result['authenticity']=='NOT_DETERMINED' and len(result['copy_move_candidates'])<=20
    assert 'probability' not in result and result['limitations']
    for view in ['texture','repeats']:
        image=Image.open(io.BytesIO(intake.forensic(data,view)));assert max(image.size)<=1200

def test_copy_move_synthetic_texture_pair_and_blank():
    rng=np.random.default_rng(53);patch=rng.integers(0,256,(220,220),dtype=np.uint8)
    array=np.full((700,1000),230,dtype=np.uint8);array[100:320,100:320]=patch;array[380:600,650:870]=patch
    out=io.BytesIO();Image.fromarray(array).save(out,format='PNG')
    result=intake.forensic(out.getvalue());assert result['copy_move_candidates']
    out=io.BytesIO();Image.new('RGB',(900,600),'white').save(out,format='PNG')
    assert intake.forensic(out.getvalue())['status']=='NO_STRONG_INDICATOR'

def test_intake_notes_and_forensic_evidence_survive_report(client):
    notes=json.dumps({'method':'LOCAL_LAYOUT_LABELS_V53','source_values':{'documentNumber':'ABCDE1234F NOISE'}})
    r=upload(client,ocr_notes=notes);assert r.status_code==200
    s=r.json()['screenings'][0];analysis=s['result']['ai_analysis']
    assert analysis['extraction']['intake_notes_browser_supplied']==notes
    assert analysis['forensic_assist']['authenticity']=='NOT_DETERMINED'
    for view in ['texture','repeats']:
        response=client.get('/api/screening/'+s['id']+'/image?view='+view)
        assert response.status_code==200 and response.headers['content-type']=='image/png'
    report=client.get('/api/screening/'+s['id']+'/report').text
    assert 'NOT_DETERMINED' in report and 'LOCAL_LAYOUT_LABELS_V53' in report
