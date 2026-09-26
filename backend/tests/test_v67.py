import json
from pathlib import Path

from app import local_registry, registry_v2, travel_intelligence, risk_policy
from test_registry import HEAD, supervisor
from test_local import upload

ROOT=Path(__file__).resolve().parents[2]
DEMO=ROOT/'demo_samples'/'travel_intelligence'


def _seed_base(supervisor):
    r=supervisor.post('/api/registry2/demo-seed',headers=HEAD)
    assert r.status_code==200,r.text
    return r.json()


def _seed_travel(supervisor):
    r=supervisor.post('/api/registry2/demo-seed-travel-v67',headers=HEAD)
    assert r.status_code==200,r.text
    return r.json()


def _reference(doc_type, fields):
    return registry_v2.enrich_reference(local_registry.compare(doc_type, fields))


def test_v67_registry22_and_richer_linked_visa_fields(supervisor):
    _seed_base(supervisor)
    summary=supervisor.get('/api/registry2/summary').json()
    assert summary['schema_version']=='2.2'
    fields={'document_number':'DEMOUS26001','name':'MAYA REGISTRY DEMO','dob':'1996-06-18','nationality':'USA','issuer_country':'USA','gender':'F','issue_date':'2024-06-18','expiry':'2034-06-17','issuing_authority':'DEMO PASSPORT AUTHORITY'}
    ref=_reference('Passport',fields)
    visa=next(x for x in ref['registry2']['linked_documents'] if x['document_type']=='Visa')
    assert visa['number_of_entries']=='MULTIPLE'
    assert visa['valid_from']=='2026-08-01'
    assert visa['duration_of_stay']=='30 DAYS'


def test_v67_clean_multiple_entry_history_is_consistent(supervisor):
    _seed_base(supervisor)
    fields={'document_number':'DEMOVISA2601','name':'MAYA REGISTRY DEMO','dob':'1996-06-18','nationality':'USA','issuer_country':'IND','gender':'F','issue_date':'2026-07-20','expiry':'2027-03-31','issuing_authority':'DEMO VISA AUTHORITY','passport_reference':'DEMOUS26001','visa_type':'TOURIST','number_of_entries':'MULTIPLE','valid_from':'2026-08-01','duration_of_stay':'30 DAYS'}
    ref=_reference('Visa',fields)
    result=travel_intelligence.assess(ref,'Visa',fields,'ENTRY IND 15/08/2026\nEXIT IND 01/09/2026')
    assert result['status']=='CONSISTENT_WITH_SYNTHETIC_HISTORY',result
    assert not result['requires_review']
    assert result['entry_count']==1 and result['exit_count']==1
    assert result['ocr_stamp_mentions'] and all(x['status']=='MATCHED_SYNTHETIC_EVENT' for x in result['stamp_comparisons'])


def test_v67_single_entry_used_twice_routes_review(supervisor):
    seeded=_seed_travel(supervisor)
    assert seeded['reference_class']=='SYNTHETIC_TRAVEL_HISTORY'
    fields={'document_number':'DEMOVISA6701','name':'KAVYA TRAVEL DEMO','dob':'1997-03-12','nationality':'GBR','issuer_country':'IND','gender':'F','issue_date':'2026-05-01','expiry':'2026-12-31','issuing_authority':'DEMO VISA AUTHORITY','passport_reference':'DEMOGB67001','visa_type':'TOURIST','number_of_entries':'SINGLE','valid_from':'2026-05-10','duration_of_stay':'30 DAYS'}
    ref=_reference('Visa',fields)
    result=travel_intelligence.assess(ref,'Visa',fields,'ENTRY IND 01/06/2026\nEXIT IND 10/06/2026\nENTRY IND 01/08/2026')
    assert result['status']=='REVIEW_REQUIRED'
    assert any(f['code']=='TRAVEL_VISA_ENTRY_LIMIT_CONFLICT' for f in result['findings'])
    visa=result['visa_assessments'][0]
    assert visa['allowed_entries']==1 and visa['entries_observed_in_registry']==2


def test_v67_duration_of_stay_exceeded(supervisor):
    _seed_travel(supervisor)
    fields={'document_number':'DEMOVISA6702','name':'OMAR STAY DEMO','dob':'1994-11-08','nationality':'USA','issuer_country':'IND','gender':'M','issue_date':'2026-06-01','expiry':'2026-11-30','issuing_authority':'DEMO VISA AUTHORITY','passport_reference':'DEMOUS67002','visa_type':'BUSINESS','number_of_entries':'MULTIPLE','valid_from':'2026-06-10','duration_of_stay':'7 DAYS'}
    ref=_reference('Visa',fields)
    result=travel_intelligence.assess(ref,'Visa',fields,'ENTRY IND 01/07/2026\nEXIT IND 20/07/2026')
    assert result['requires_review']
    assert any(f['code']=='TRAVEL_STAY_DURATION_EXCEEDED' for f in result['findings'])
    assert result['visa_assessments'][0]['stays'][0]['days']==19


def test_v67_unmatched_ocr_stamp_is_gap_not_fraud(supervisor):
    _seed_base(supervisor)
    fields={'document_number':'DEMOUS26001','name':'MAYA REGISTRY DEMO','dob':'1996-06-18','nationality':'USA','issuer_country':'USA','gender':'F','issue_date':'2024-06-18','expiry':'2034-06-17','issuing_authority':'DEMO PASSPORT AUTHORITY'}
    ref=_reference('Passport',fields)
    result=travel_intelligence.assess(ref,'Passport',fields,'ENTRY IND 24/09/2026')
    assert not result['requires_review'],result
    assert result['stamp_comparisons'][0]['status']=='NOT_FOUND_IN_SYNTHETIC_HISTORY'
    assert result['gaps']


def test_v67_travel_risk_is_explainable_family():
    findings=[{'code':'TRAVEL_VISA_ENTRY_LIMIT_CONFLICT','status':'REVIEW_REQUIRED'},{'code':'TRAVEL_STAY_DURATION_EXCEEDED','status':'REVIEW_REQUIRED'}]
    score=risk_policy.assess({'status':'MATCH','fields':[]},{},findings,{'name':'A','document_number':'X','dob':'2000-01-01','nationality':'USA','issuer_country':'IND'},{'status':'USABLE'},95,'NOT_SUPPORTED')
    factors=[x for x in score['factors'] if x['group']=='travel_consistency']
    assert len(factors)==1 and factors[0]['points']==35


def test_v67_screening_saves_travel_evidence_and_manual_review(supervisor):
    _seed_travel(supervisor)
    meta={
        'type':'Visa','name':'KAVYA TRAVEL DEMO','dob':'1997-03-12','document_number':'DEMOVISA6701','nationality':'GBR','issuer_country':'IND','gender':'F',
        'issue_date':'2026-05-01','expiry':'2026-12-31','issuing_authority':'DEMO VISA AUTHORITY','passport_reference':'DEMOGB67001','visa_type':'TOURIST','number_of_entries':'SINGLE','valid_from':'2026-05-10','duration_of_stay':'30 DAYS',
        'ocr_text':'VISA KAVYA TRAVEL DEMO DEMOVISA6701 ENTRIES SINGLE VALID FROM 10/05/2026 VALID UNTIL 31/12/2026\nENTRY IND 01/06/2026\nEXIT IND 10/06/2026\nENTRY IND 01/08/2026','ocr_confidence':95,
    }
    data=(DEMO/'02_single_entry_overused_visa.png').read_bytes()
    r=supervisor.post('/api/screening/batch',headers=HEAD,data={'documents_json':json.dumps([meta])},files=[('files',('travel-v67.png',data,'image/png'))])
    assert r.status_code==200,r.text
    screening=r.json()['screenings'][0]
    ti=screening['result']['ai_analysis']['travel_intelligence']
    assert ti['status']=='REVIEW_REQUIRED',ti
    assert screening['recommendation']=='MANUAL_REVIEW'
    assert any(x['code']=='TRAVEL_VISA_ENTRY_LIMIT_CONFLICT' for x in screening['result']['findings'])
    assert screening['result']['ai_analysis']['checks']['travel_immigration_consistency']=='REVIEW_REQUIRED'
