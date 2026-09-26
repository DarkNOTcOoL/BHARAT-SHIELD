import hashlib,json
from pathlib import Path
import numpy as np
from fastapi.testclient import TestClient
from app import main,local_analysis
from test_local import upload,image_bytes
from test_registry import supervisor,HEAD,REASON

def post_photo(c,s,source='LIVE_CAMERA'):
    return c.post('/api/screening/'+s['id']+'/face',headers=HEAD,data={'capture_source':source},files={'photo':('person.png',image_bytes(True),'image/png')})

def test_skip_is_optional_audited_idempotent_and_not_a_decision(client):
    s=upload(client).json()['screenings'][0];path='/api/screening/'+s['id']
    with TestClient(main.app) as anonymous:assert anonymous.post(path+'/face/skip',headers=HEAD).status_code==401
    r=client.post(path+'/face/skip',headers=HEAD);assert r.status_code==200
    assert r.json()['status']=='SKIPPED' and r.json()['performed_by']=='tester'
    client.post(path+'/face/skip',headers=HEAD)
    after=client.get(path).json();assert (after['confidence'],after['status'],after['recommendation'])==(s['confidence'],s['status'],s['recommendation'])
    a=after['result']['ai_analysis'];assert a['checks']['liveness']=='OPTIONAL_NOT_RUN'
    assert len(a['person_comparison_history'])==1
    report=client.get(path+'/report').text;assert 'SKIPPED' in report and 'person comparison history' in report

def test_face_source_history_hash_and_no_photo_or_embedding_storage(client,monkeypatch):
    s=upload(client,ocr_confidence=40).json()['screenings'][0];path='/api/screening/'+s['id']
    monkeypatch.setattr(local_analysis,'compare_faces',lambda a,b:{'status':'REVIEW_REQUIRED','cosine_similarity':.72,'liveness':'NOT_RUN'})
    before={str(p) for p in Path(main.PRIVATE_ROOT).rglob('*') if p.is_file()}
    for source in ['LIVE_CAMERA','UPLOADED_PHOTO']:
        r=post_photo(client,s,source);assert r.status_code==200,r.text
        d=r.json();assert d['capture_source']==source and d['capture_source_attestation']=='NOT_ATTESTED'
        assert d['performed_by']=='tester' and d['performed_at'] and d['photo_retention']=='NOT_STORED'
        assert d['submitted_photo_sha256']==hashlib.sha256(image_bytes(True)).hexdigest()
    after=client.get(path).json();a=after['result']['ai_analysis']
    assert len(a['person_comparison_history'])==2 and a['person_comparison_attempt_count']==2
    assert (after['status'],after['recommendation'],after['confidence'])==(s['status'],s['recommendation'],s['confidence'])
    assert {str(p) for p in Path(main.PRIVATE_ROOT).rglob('*') if p.is_file()}==before
    assert client.post(path+'/face/skip',headers=HEAD).status_code==409
    assert post_photo(client,s,'TRUSTED_LIVENESS').status_code==400
    exported=client.get(path+'/evidence').json();assert any('source=LIVE_CAMERA' in x['action'] for x in exported['audit'])

def test_supervisor_accept_flow_still_checks_role_reason_version_and_final_evidence(client,supervisor):
    s=upload(client,ocr_confidence=0).json()['screenings'][0];id=s['id'];path='/api/reviews/'+id
    r=supervisor.get(path).json()['review'];assert r['state']=='PENDING'
    assert supervisor.post(path,headers=HEAD,json={'action':'RESOLVE','expected_version':r['version'],'reason':REASON,'outcome':'ACCEPT'}).status_code==409
    claimed=supervisor.post(path,headers=HEAD,json={'action':'CLAIM','expected_version':r['version'],'reason':REASON}).json()
    body={'action':'RESOLVE','expected_version':claimed['version'],'reason':REASON,'outcome':'ACCEPT'}
    assert client.post(path,headers=HEAD,json=body).status_code==403
    assert supervisor.post(path,headers=HEAD,json=body|{'reason':'short'}).status_code==422
    assert supervisor.post(path,headers=HEAD,json=body|{'expected_version':r['version']}).status_code==409
    done=supervisor.post(path,headers=HEAD,json=body);assert done.status_code==200
    assert client.get('/api/screening/'+id).json()['status']=='Verified'
    assert post_photo(client,s).status_code==409
    assert client.post('/api/screening/'+id+'/face/skip',headers=HEAD).status_code==409
    assert client.get('/api/screening/'+id).json()['recommendation']==s['recommendation']

def test_optional_skip_does_not_block_ordinary_accept(client,supervisor):
    record={'document_type':'PAN Card','document_number':'VUVUV5533V','name':'OPTIONAL TEST PERSON','dob':'1990-01-01','nationality':'IND','issuer_country':'IND'}
    created=supervisor.post('/api/registry',headers=HEAD,json={'record':record,'reason':REASON})
    assert created.status_code==201
    s=upload(client,document_number=record['document_number'],name=record['name']).json()['screenings'][0]
    assert s['recommendation']=='REVIEW_COMPLETE_CHECKS'
    assert client.post('/api/screening/'+s['id']+'/face/skip',headers=HEAD).status_code==200
    assert client.post('/api/screening/'+s['id']+'/decision?action=ACCEPT',headers=HEAD,data={'reason':REASON}).status_code==200

def test_face_detector_reports_which_image_is_ambiguous_and_normalized_geometry(monkeypatch):
    face=np.array([[100.,100.,100.,100.,110,110,170,110,150,150,120,170,170,170,.99]],np.float32)
    class Detector:
        def setInputSize(self,s):pass
        def detect(self,bgr):return None,face
    class Recognizer:
        def alignCrop(self,bgr,f):return bgr[:100,:100]
        def feature(self,img):return np.array([1.,0.])
        def match(self,a,b,kind):return .71
    monkeypatch.setattr(local_analysis.cv2.FaceDetectorYN,'create',lambda *a:Detector())
    monkeypatch.setattr(local_analysis.cv2.FaceRecognizerSF,'create',lambda *a:Recognizer())
    result=local_analysis.compare_faces(image_bytes(),image_bytes())
    assert result['status']=='REVIEW_REQUIRED' and result['face_counts']=={'document':1,'person':1}
    for region in result['face_regions'].values():assert all(0<=v<=1 for v in region['box'])
    monkeypatch.setattr(Detector,'detect',lambda self,bgr:(None,np.concatenate([face,face])))
    result=local_analysis.compare_faces(image_bytes(),image_bytes())
    assert result['status']=='INCONCLUSIVE' and result['face_counts']['document']==2
    assert 'Document image contains 2' in result['reason']
