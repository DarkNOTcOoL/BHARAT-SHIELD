import json
from pathlib import Path

import numpy as np
from PIL import Image

from app import registry_v2, visual_security, risk_policy
from test_registry import HEAD, supervisor

ROOT=Path(__file__).resolve().parents[2]
DEMO=ROOT/'demo_samples'/'visual_security'


def _seed(supervisor):
    r=supervisor.post('/api/registry2/demo-seed-visual-v66',headers=HEAD)
    assert r.status_code==200,r.text
    return r.json()


def test_v66_registry_visual_feature_schema_and_profile(supervisor):
    seeded=_seed(supervisor)
    assert seeded['reference_class']=='SYNTHETIC_DEMO_TEMPLATE'
    summary=supervisor.get('/api/registry2/summary').json()
    assert str(summary['schema_version']).startswith('2.')
    assert summary['counts']['template_features']>=3
    profile=registry_v2.issuer_template_profile('Passport','IND','DEMO PASSPORT AUTHORITY','2026-08-01')
    assert profile and profile['template']['template_version']=='IND-P-DEMO-2026'
    assert len(profile['visual_features'])>=3
    assert all(len(x['reference_sha256'])==64 for x in profile['visual_features'])
    detail=supervisor.get('/api/registry2/issuer-templates/'+profile['template']['id']+'/features').json()
    assert len(detail['features'])>=3 and detail['external_connections'] is False


def test_v66_clean_and_missing_reference_features(supervisor):
    _seed(supervisor)
    profile=registry_v2.issuer_template_profile('Passport','IND','DEMO PASSPORT AUTHORITY','2026-08-01')
    clean=np.asarray(Image.open(DEMO/'01_template_features_present.png').convert('RGB'))
    missing=np.asarray(Image.open(DEMO/'02_template_features_missing.png').convert('RGB'))
    moved=np.asarray(Image.open(DEMO/'03_emblem_moved.png').convert('RGB'))
    good,_=visual_security.analyze(clean,profile)
    bad,_=visual_security.analyze(missing,profile)
    moved_result,_=visual_security.analyze(moved,profile)
    assert good['status']=='REFERENCE_FEATURES_CONSISTENT',good
    assert bad['status']=='REVIEW_REQUIRED',bad
    assert moved_result['status']=='REVIEW_REQUIRED',moved_result
    assert any(x['feature_code']=='EMBLEM' and x['status']=='REVIEW_MISSING_OR_INCONSISTENT' for x in bad['feature_results'])


def test_v66_no_profile_is_not_false_alert():
    rgb=np.zeros((500,800,3),dtype=np.uint8)
    result,_=visual_security.analyze(rgb,None)
    assert result['status']=='NOT_ASSESSED_NO_REFERENCE'
    assert result['visual_anomaly_index'] is None


def test_v66_visual_review_shares_forensic_risk_family():
    findings=[
        {'code':'AI_TAMPER_ANOMALY','status':'REVIEW_REQUIRED'},
        {'code':'ISSUER_VISUAL_FEATURE_REVIEW','status':'REVIEW_REQUIRED'},
    ]
    score=risk_policy.assess({'status':'MATCH','fields':[]},{},findings,{'name':'A','document_number':'X','dob':'2000-01-01','nationality':'IND','issuer_country':'IND'},{'status':'USABLE'},95,'VALID')
    forensic=[x for x in score['factors'] if x['group']=='forensic_integrity']
    assert len(forensic)==1 and forensic[0]['points']==30


def test_v66_screening_saves_visual_reference_evidence(supervisor):
    _seed(supervisor)
    meta={
        'type':'Passport','name':'ANAYA TEMPLATE DEMO','dob':'1998-04-14','document_number':'DEMOIND66001',
        'nationality':'IND','issuer_country':'IND','gender':'F','issue_date':'2026-08-01','expiry':'2036-07-31',
        'issuing_authority':'DEMO PASSPORT AUTHORITY','ocr_text':'PASSPORT ANAYA TEMPLATE DEMO DEMOIND66001 NATIONALITY IND',
        'ocr_confidence':95,
    }
    data=(DEMO/'01_template_features_present.png').read_bytes()
    r=supervisor.post('/api/screening/batch',headers=HEAD,data={'documents_json':json.dumps([meta])},files=[('files',('visual-demo.png',data,'image/png'))])
    assert r.status_code==200,r.text
    screening=r.json()['screenings'][0]
    visual=screening['result']['ai_analysis']['forensic_assist']['issuer_visual_security']
    assert visual['status']=='REFERENCE_FEATURES_CONSISTENT',visual
    assert visual['template_reference']['template_version']=='IND-P-DEMO-2026'
    overlay=supervisor.get('/api/screening/'+screening['id']+'/image?view=visual-security')
    assert overlay.status_code==200 and overlay.headers['content-type']=='image/png'


def test_v66_missing_critical_feature_routes_review(supervisor):
    _seed(supervisor)
    meta={
        'type':'Passport','name':'ANAYA TEMPLATE DEMO','dob':'1998-04-14','document_number':'DEMOIND66001',
        'nationality':'IND','issuer_country':'IND','gender':'F','issue_date':'2026-08-01','expiry':'2036-07-31',
        'issuing_authority':'DEMO PASSPORT AUTHORITY','ocr_text':'PASSPORT ANAYA TEMPLATE DEMO DEMOIND66001 NATIONALITY IND',
        'ocr_confidence':95,
    }
    data=(DEMO/'02_template_features_missing.png').read_bytes()
    r=supervisor.post('/api/screening/batch',headers=HEAD,data={'documents_json':json.dumps([meta])},files=[('files',('visual-missing.png',data,'image/png'))])
    assert r.status_code==200,r.text
    screening=r.json()['screenings'][0]
    codes={x['code'] for x in screening['result']['findings']}
    assert 'ISSUER_VISUAL_FEATURE_REVIEW' in codes
    assert screening['recommendation']=='MANUAL_REVIEW'
