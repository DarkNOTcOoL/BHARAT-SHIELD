import json
from app import active_liveness, main
from tests.test_local import image_bytes, upload


def test_active_liveness_motion_requires_opposite_turns():
    good={
        'FRONT':{'ok':True,'yaw_proxy':0.02},
        'TURN_LEFT':{'ok':True,'yaw_proxy':-0.43},
        'TURN_RIGHT':{'ok':True,'yaw_proxy':0.49},
    }
    passed=active_liveness.evaluate_motion(good)
    assert passed['status']=='PASSED_ACTIVE_CHALLENGE'
    assert passed['motion_checks']['opposite_turns'] is True
    bad={**good,'TURN_RIGHT':{'ok':True,'yaw_proxy':-0.28}}
    retry=active_liveness.evaluate_motion(bad)
    assert retry['status']=='RETRY_REQUIRED'
    assert retry['motion_checks']['opposite_turns'] is False


def test_active_liveness_rejects_bad_quality_frame():
    samples={
        'FRONT':{'ok':False,'yaw_proxy':0.0},
        'TURN_LEFT':{'ok':True,'yaw_proxy':-0.4},
        'TURN_RIGHT':{'ok':True,'yaw_proxy':0.4},
    }
    result=active_liveness.evaluate_motion(samples)
    assert result['status']=='RETRY_REQUIRED'


def test_server_issued_challenge_is_one_time():
    c=active_liveness.create_challenge('SCR-X','tester')
    assert c['steps'][0]=='FRONT' and set(c['steps'])=={'FRONT','TURN_LEFT','TURN_RIGHT'}
    assert active_liveness.consume_challenge(c['challenge_id'],'SCR-X','tester') is not None
    assert active_liveness.consume_challenge(c['challenge_id'],'SCR-X','tester') is None


def test_liveness_endpoint_saves_evidence(client,monkeypatch):
    s=upload(client).json()['screenings'][0]
    monkeypatch.setattr(main.local_analysis,'compare_faces',lambda a,b:{'status':'REVIEW_REQUIRED','cosine_similarity':0.7,'liveness':'NOT_RUN'})
    face=client.post('/api/screening/'+s['id']+'/face',headers={'X-Local-Request':'1'},data={'capture_source':'LIVE_CAMERA'},files={'photo':('person.png',image_bytes(),'image/png')})
    assert face.status_code==200
    c=client.post('/api/screening/'+s['id']+'/face/liveness/challenge',headers={'X-Local-Request':'1'})
    assert c.status_code==200,c.text
    challenge=c.json()
    monkeypatch.setattr(active_liveness,'analyze_sequence',lambda frames:{
        'status':'PASSED_ACTIVE_CHALLENGE','reason':'test pass','method':'RANDOMIZED_ACTIVE_HEAD_TURN_V1',
        'motion_checks':{'opposite_turns':True,'yaw_separation':0.9},'image_retention':'NOT_STORED'
    })
    img=image_bytes()
    r=client.post('/api/screening/'+s['id']+'/face/liveness',headers={'X-Local-Request':'1'},data={'challenge_id':challenge['challenge_id']},files={
        'front':('front.png',img,'image/png'),'turn_left':('left.png',img,'image/png'),'turn_right':('right.png',img,'image/png')
    })
    assert r.status_code==200,r.text
    assert r.json()['status']=='PASSED_ACTIVE_CHALLENGE'
    saved=client.get('/api/screening/'+s['id']).json()['result']['ai_analysis']
    assert saved['liveness']['status']=='PASSED_ACTIVE_CHALLENGE'
    assert saved['checks']['liveness']=='COMPLETE'
    assert saved['liveness_attempt_count']==1


def test_system_status_advertises_active_liveness(client):
    status=client.get('/api/system/status').json()
    assert status['liveness']=='RANDOMIZED_ACTIVE_HEAD_TURN_V1'
    assert status['face']['liveness']=='ACTIVE_CHALLENGE_AVAILABLE'
