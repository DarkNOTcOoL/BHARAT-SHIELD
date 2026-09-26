import json
from app import checkpoint_center, main
from test_local import upload


def base_evidence():
    return {
        'checks':{'mrz':'NOT_APPLICABLE','fields':'COMPLETE'},
        'quality':{'status':'USABLE'},
        'capture_intelligence':{'glare':{'status':'CLEAR'}},
        'document_type_detection':{'status':'DETECTED','review_required':False},
        'registry':{'status':'MATCH','registry2':{'status':'LINKED','requires_review':False,'escalation_required':False,'alerts':[]}},
        'signed_qr':{'signature_status':'SIGNATURE_VALID','comparison_status':'MATCH','requires_review':False},
        'forensic_assist':{
            'tamper_ai':{'status':'NO_STRONG_ANOMALY'},
            'photo_substitution':{'status':'NO_PORTRAIT_DETECTED'},
            'stamp_seal':{'status':'NO_STAMP_LIKE_REGION_DETECTED'},
            'template_layout':{'status':'NO_STRONG_LAYOUT_ANOMALY'},
            'issuer_visual_security':{'status':'REFERENCE_FEATURES_CONSISTENT'},
        },
        'visa_intelligence':{'status':'NOT_APPLICABLE'},
        'travel_intelligence':{'status':'INCONCLUSIVE_NO_HISTORY','requires_review':False},
        'duplicates':{'status':'CLEAR','requires_review':False},
        'face':{'status':'NOT_RUN'},'liveness':{'status':'NOT_RUN'},'identity_history':{'status':'NOT_RUN','requires_review':False},
        'risk_score':{'score':0,'band':'LOW'}
    }


def test_v68_clean_summary_is_not_authenticity_verdict():
    c=checkpoint_center.build(recommendation='REVIEW_COMPLETE_CHECKS',risk='LOW',screening_status='COMPLETED',document_type='PAN Card',findings=[],evidence=base_evidence(),ocr_confidence=95)
    assert c['version']=='SIH26188_CHECKPOINT_DECISION_CENTER_V1'
    assert c['decision_readiness']=='READY_FOR_OFFICER_DECISION'
    assert c['checkpoint_recommendation']=='REVIEW_COMPLETE_CHECKS'
    assert 'does not create a new fraud' in c['meaning']
    assert any(x['key']=='person_assurance' and x['optional'] for x in c['lanes'])


def test_v68_registry_critical_alert_is_escalate_lane():
    e=base_evidence();e['registry']={'status':'BLOCKED','registry2':{'status':'REVIEW_REQUIRED','requires_review':True,'escalation_required':True,'alerts':[{'status':'OPEN','alert_type':'LOST_STOLEN_DOCUMENT','reason':'Fictional lost/stolen demo alert'}]}}
    c=checkpoint_center.build(recommendation='ESCALATE',risk='CRITICAL',screening_status='COMPLETED',document_type='Passport',findings=[{'code':'REGISTRY2_ALERT_LOST_STOLEN_DOCUMENT','severity':'HIGH','status':'REVIEW_REQUIRED','message':'demo'}],evidence=e,ocr_confidence=95)
    lane=next(x for x in c['lanes'] if x['key']=='registry')
    assert lane['status']=='ESCALATE'
    assert c['decision_readiness']=='HOLD_FOR_ESCALATION'
    assert c['sih26188_scenario_coverage']['expired_revoked_blocked_or_lost_stolen']=='ESCALATION_SIGNAL'


def test_v68_photo_and_tamper_scenarios_are_review_signals_not_verdicts():
    e=base_evidence();e['forensic_assist']['tamper_ai']={'status':'REVIEW_REQUIRED','max_anomaly_score':88};e['forensic_assist']['photo_substitution']={'status':'REVIEW_REQUIRED','photo_integrity_index':82,'cues':['BOUNDARY_SEAM','NOISE_MISMATCH']}
    findings=[{'code':'AI_TAMPER_ANOMALY','severity':'MEDIUM','status':'REVIEW_REQUIRED','message':'tamper review'}, {'code':'PHOTO_SUBSTITUTION_REVIEW','severity':'MEDIUM','status':'REVIEW_REQUIRED','message':'photo review'}]
    c=checkpoint_center.build(recommendation='MANUAL_REVIEW',risk='HIGH',screening_status='COMPLETED',document_type='Passport',findings=findings,evidence=e,ocr_confidence=92)
    assert next(x for x in c['lanes'] if x['key']=='document_integrity')['status']=='REVIEW'
    assert next(x for x in c['lanes'] if x['key']=='photo_integrity')['status']=='REVIEW'
    assert c['sih26188_scenario_coverage']['altered_or_replaced_photo']=='REVIEW_SIGNAL'


def test_v68_identity_history_and_liveness_are_separate_supporting_evidence():
    e=base_evidence();e['face']={'status':'REVIEW_REQUIRED','cosine_similarity':0.71};e['liveness']={'status':'PASSED_ACTIVE_CHALLENGE'};e['identity_history']={'status':'REVIEW_REQUIRED','requires_review':True,'review_candidate_count':1}
    c=checkpoint_center.build(recommendation='MANUAL_REVIEW',risk='LOW',screening_status='COMPLETED',document_type='Passport',findings=[{'code':'BIOMETRIC_IDENTITY_HISTORY_CANDIDATE','severity':'HIGH','status':'REVIEW_REQUIRED','message':'candidate'}],evidence=e,ocr_confidence=94)
    assert next(x for x in c['lanes'] if x['key']=='identity_history')['status']=='REVIEW'
    assert next(x for x in c['lanes'] if x['key']=='person_assurance')['status']=='OPTIONAL_REVIEW_ONLY'
    assert c['sih26188_scenario_coverage']['multiple_identity_candidate']=='REVIEW_SIGNAL'


def test_v68_screening_api_contains_dynamic_decision_center(client):
    r=upload(client)
    assert r.status_code==200,r.text
    sid=r.json()['screenings'][0]['id']
    d=client.get('/api/screening/'+sid).json()
    center=d['result']['ai_analysis']['checkpoint_decision_center']
    assert center['version']=='SIH26188_CHECKPOINT_DECISION_CENTER_V1'
    assert len(center['lanes'])>=9
    exported=client.get('/api/screening/'+sid+'/evidence').json()
    assert exported['result']['ai_analysis']['checkpoint_decision_center']['version']==center['version']


def test_v68_system_status_exposes_center(client):
    d=client.get('/api/system/status').json()
    assert d['checkpoint_decision_center']=='SIH26188_UNIFIED_OFFICER_SUMMARY_V1'
    assert d['engine'].startswith('7.1.0')
