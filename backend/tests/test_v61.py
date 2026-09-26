import json
import numpy as np

from app import biometric_history, main, active_liveness
from tests.test_local import image_bytes, upload


def test_biometric_history_only_reviews_identity_differences():
    current=np.array([1.0,0.0,0.0],dtype=np.float32)
    rows=[{
        'screening_id':'SCR-OLD','embedding':np.array([0.99,0.05,0.0],dtype=np.float32),
        'person_name':'OTHER NAME','date_of_birth':'1991-02-03','document_number':'OTHER123','document_type':'Passport','liveness_status':'PASSED_ACTIVE_CHALLENGE'
    }]
    result=biometric_history.search(current,{'name':'CURRENT NAME','dob':'1990-01-01','document_number':'CUR123'},rows)
    assert result['status']=='REVIEW_REQUIRED'
    assert result['requires_review'] is True
    assert result['candidates'][0]['screening_id']=='SCR-OLD'
    assert 'DIFFERENT_NAME' in result['candidates'][0]['identity_differences']


def test_same_identity_high_similarity_is_not_multiple_identity_alert():
    current=np.array([1.0,0.0,0.0],dtype=np.float32)
    rows=[{'screening_id':'SCR-OLD','embedding':np.array([1.0,0.0,0.0],dtype=np.float32),'person_name':'SAME PERSON','date_of_birth':'1990-01-01','document_number':'ABC123','document_type':'Passport','liveness_status':'PASSED_ACTIVE_CHALLENGE'}]
    result=biometric_history.search(current,{'name':'SAME PERSON','dob':'1990-01-01','document_number':'ABC123'},rows)
    assert result['requires_review'] is False
    assert result['status']=='CANDIDATES_FOUND'


def test_embedding_is_encrypted_at_rest():
    values=np.array([0.2,0.3,0.4,0.5],dtype=np.float32)
    token,digest,dimension=biometric_history.seal_embedding(values,main.BIOMETRIC_CIPHER)
    assert dimension==4 and digest and '0.2' not in token
    restored=biometric_history.open_embedding(token,main.BIOMETRIC_CIPHER)
    assert np.isclose(np.linalg.norm(restored),1.0)


def test_liveness_pass_searches_history_and_saves_template(client,monkeypatch):
    previous=upload(client,name='OLD ALIAS',document_number='OLD12345',dob='01/01/1990').json()['screenings'][0]
    vector=np.zeros(128,dtype=np.float32);vector[0]=1.0
    token,digest,dimension=biometric_history.seal_embedding(vector,main.BIOMETRIC_CIPHER)
    with main.SessionLocal() as db:
        db.add(main.BiometricTemplate(screening_id=previous['id'],template_ciphertext=token,template_sha256=digest,dimension=dimension,
            model_sha256='{}',person_name='OLD ALIAS',date_of_birth='01/01/1990',document_number='OLD12345',document_type='PAN Card',liveness_status='PASSED_ACTIVE_CHALLENGE'))
        db.commit()

    current=upload(client,name='NEW IDENTITY',document_number='NEW98765',dob='01/01/1990').json()['screenings'][0]
    monkeypatch.setattr(main.local_analysis,'compare_faces',lambda a,b:{'status':'REVIEW_REQUIRED','cosine_similarity':0.8,'liveness':'NOT_RUN'})
    monkeypatch.setattr(main.local_analysis,'extract_face_embedding',lambda data,require_quality=True:{'status':'TEMPLATE_READY','embedding':vector,'model_sha256':{'recognizer':'demo'},'model':'YuNet + SFace'})
    monkeypatch.setattr(active_liveness,'analyze_sequence',lambda frames:{'status':'PASSED_ACTIVE_CHALLENGE','reason':'test pass','method':'RANDOMIZED_ACTIVE_HEAD_TURN_V1','motion_checks':{'opposite_turns':True},'image_retention':'NOT_STORED'})
    face=client.post('/api/screening/'+current['id']+'/face',headers={'X-Local-Request':'1'},data={'capture_source':'LIVE_CAMERA'},files={'photo':('person.png',image_bytes(),'image/png')})
    assert face.status_code==200,face.text
    challenge=client.post('/api/screening/'+current['id']+'/face/liveness/challenge',headers={'X-Local-Request':'1'}).json()
    img=image_bytes()
    live=client.post('/api/screening/'+current['id']+'/face/liveness',headers={'X-Local-Request':'1'},data={'challenge_id':challenge['challenge_id']},files={
        'front':('front.png',img,'image/png'),'turn_left':('left.png',img,'image/png'),'turn_right':('right.png',img,'image/png')})
    assert live.status_code==200,live.text
    history=live.json()['identity_history']
    assert history['status']=='REVIEW_REQUIRED'
    assert history['candidates'][0]['screening_id']==previous['id']
    saved=client.get('/api/screening/'+current['id']).json()
    assert saved['result']['ai_analysis']['identity_history']['requires_review'] is True
    assert saved['recommendation']=='MANUAL_REVIEW'
    assert any(f['code']=='BIOMETRIC_IDENTITY_HISTORY_CANDIDATE' for f in saved['result']['findings'])
    with main.SessionLocal() as db:
        stored=db.scalar(main.select(main.BiometricTemplate).where(main.BiometricTemplate.screening_id==current['id']))
        assert stored is not None and stored.template_ciphertext and stored.template_sha256


def test_system_status_advertises_identity_history(client):
    status=client.get('/api/system/status').json()
    assert status['identity_history']=='LOCAL_ENCRYPTED_SFACE_HISTORY_V1'
    assert status['biometric_templates']=='FERNET_ENCRYPTED_AFTER_PASSED_LIVENESS'
    assert status['engine'].startswith('7.1.0')
