import json
from fastapi import FastAPI
from test_local import upload
from test_registry import supervisor, HEAD, REASON
from app import main,local_registry,review_workflow

def get_review(c,id):
    return next(x for x in c.get('/api/reviews?state=ALL&limit=100').json()['items'] if x['screening_id']==id)

def test_corrections_are_attributed_by_server(client):
    s=upload(client,name='REVIEWED PERSON',ocr_fields={'name':'RAW PERSON','documentNumber':'ABCDE1234F'},reviewed_by='forged-user').json()['screenings'][0]
    x=s['result']['ai_analysis']['extraction']
    assert x['reviewed_by']=='tester' and x['reviewed_at']
    assert x['parsed_fields']['name']=='RAW PERSON' and x['parsed_fields']['document_number']=='ABCDE1234F'
    assert {'field':'name','before':'RAW PERSON','after':'REVIEWED PERSON'} in x['corrections']
    assert x['raw_text']=='SAMPLE PERSON ABCDE1234F'

def test_review_permissions_version_resolution(client,supervisor):
    s=upload(client,document_number='QQQQQ1234Z').json()['screenings'][0];id=s['id'];r=get_review(client,id)
    assert r['state']=='PENDING' and r['reason']
    path='/api/reviews/'+id
    claim={'action':'CLAIM','expected_version':r['version'],'reason':REASON}
    saved=client.post(path,headers=HEAD,json=claim).json()
    assert saved['state']=='UNDER_REVIEW' and saved['assigned_to']=='tester'
    assert client.post(path,headers=HEAD,json=claim).status_code==409
    resolve={'action':'RESOLVE','expected_version':saved['version'],'reason':REASON,'outcome':'FLAG'}
    assert client.post(path,headers=HEAD,json=resolve).status_code==403
    done=supervisor.post(path,headers=HEAD,json=resolve)
    assert done.status_code==200 and done.json()['state']=='RESOLVED'
    evidence=client.get('/api/screening/'+id+'/evidence').json()
    assert evidence['review']['resolved_by']=='supervisor' and evidence['recommendation']==s['recommendation']
    assert any('Review RESOLVE' in e['action'] for e in evidence['audit'])
    assert supervisor.post(path,headers=HEAD,json={'action':'REOPEN','expected_version':done.json()['version'],'reason':REASON}).json()['state']=='PENDING'

def test_assignment_validation(client,supervisor):
    s=upload(client,ocr_confidence=0).json()['screenings'][0];r=get_review(client,s['id']);path='/api/reviews/'+s['id']
    body={'action':'ASSIGN','expected_version':r['version'],'reason':REASON,'assignee':'nonexistent'}
    assert supervisor.post(path,headers=HEAD,json=body).status_code==400
    body['assignee']='supervisor'
    assigned=supervisor.post(path,headers=HEAD,json=body).json()
    assert client.post(path,headers=HEAD,json={'action':'CLAIM','expected_version':assigned['version'],'reason':REASON}).status_code==409

def test_queued_blocked_cannot_be_cleared(client,supervisor):
    supervisor.post('/api/registry/demo-seed',headers=HEAD)
    d=local_registry.demo_records()[3].model_dump();d['type']=d.pop('document_type')
    s=upload(client,**d).json()['screenings'][0];r=get_review(client,s['id']);path='/api/reviews/'+s['id']
    r=supervisor.post(path,headers=HEAD,json={'action':'CLAIM','expected_version':r['version'],'reason':REASON}).json()
    for outcome in ['ACCEPT','FLAG','RECAPTURE']:
        assert supervisor.post(path,headers=HEAD,json={'action':'RESOLVE','expected_version':r['version'],'reason':REASON,'outcome':outcome}).status_code==409
    assert supervisor.post(path,headers=HEAD,json={'action':'RESOLVE','expected_version':r['version'],'reason':REASON,'outcome':'ESCALATE'}).status_code==200

def test_report_self_contained_escaped_and_authenticated(client):
    s=upload(client,name='<script>alert(1)</script>',ocr_fields={'name':'<script>'}).json()['screenings'][0]
    r=client.get('/api/screening/'+s['id']+'/report')
    assert r.status_code==200 and 'text/html' in r.headers['content-type']
    assert '<script>' not in r.text and '&lt;script&gt;' in r.text
    assert 'SYNTHETIC DEMONSTRATION' in r.text and 'NOT_RUN' in r.text
    assert s['document_hash'] in r.text and 'tester' in r.text and 'href="http' not in r.text

def test_cross_passport_visa_missing_close_conflict_dates():
    p={'type':'Passport','name':'AARAV DEMO','dob':'2001-03-14','nationality':'IND','document_number':'P1234567','issue_date':'2020-01-01','expiry':'2030-01-01'}
    v=p|{'type':'Visa','document_number':'V7654321','passport_reference':'P1234567','issue_date':'2025-01-01','expiry':'2029-01-01'}
    assert main.cross_verify([p,v])[1]=='CONSISTENT'
    assert main.cross_verify([p,v|{'passport_reference':''}])[1]=='PARTIAL'
    assert main.cross_verify([p,v|{'name':'AARAV DEOM'}])[1]=='REVIEW_REQUIRED'
    assert main.cross_verify([p,v|{'passport_reference':'P0000000'}])[1]=='CONFLICT'
    assert main.cross_verify([p,v|{'issue_date':'2031-01-01','expiry':'2032-01-01'}])[1]=='CONFLICT'
    assert main.cross_verify([p,v|{'dob':'31/02/2001'}])[1]=='PARTIAL'
    assert not any(f['code']=='CROSS_PASSPORT_LINK' and f['severity']=='HIGH' for f in main.cross_verify([p,v])[2])

def test_legacy_queue_backfill_idempotent(client):
    s=upload(client,ocr_confidence=0).json()['screenings'][0]
    with main.SessionLocal() as db:
        db.delete(db.get(main.ReviewCase,s['id']));db.commit()
    for _ in range(2):review_workflow.install(FastAPI(),main.SessionLocal,main.Screening,main.AuditLog,main.ReviewCase)
    assert get_review(client,s['id'])['state']=='PENDING'

def test_direct_accept_cannot_bypass_queue_version(client,supervisor):
    s=upload(client,ocr_confidence=0).json()['screenings'][0]
    r=supervisor.post('/api/screening/'+s['id']+'/decision?action=ACCEPT',headers=HEAD,data={'reason':REASON})
    assert r.status_code==409
    assert get_review(client,s['id'])['state']=='PENDING'
    assert client.get('/api/screening/'+s['id']).json()['recommendation']==s['recommendation']

def test_supervisor_direct_accepts_noncritical_evidence_gap_without_claim(client,supervisor):
    # Unknown but structurally valid PAN creates an evidence-gap MANUAL_REVIEW, not an explicit conflict.
    s=upload(client,document_number='QQQQQ1234Z').json()['screenings'][0]
    assert s['recommendation']=='MANUAL_REVIEW'
    assert s['decision_policy']['supervisor_direct_accept_allowed'] is True
    before=get_review(client,s['id'])
    assert before['state']=='PENDING'
    r=supervisor.post('/api/screening/'+s['id']+'/decision?action=ACCEPT',headers=HEAD,data={'reason':'Original document inspected; evidence gap accepted by supervisor.'})
    assert r.status_code==200,r.text
    assert r.json()['direct_supervisor_override'] is True
    after=get_review(client,s['id'])
    assert after['state']=='RESOLVED' and after['resolution']=='ACCEPT' and after['resolved_by']=='supervisor'
    saved=supervisor.get('/api/screening/'+s['id']).json()
    assert saved['status']=='Verified'


def test_supervisor_direct_accept_still_blocked_for_explicit_review_signal(client,supervisor):
    # Expired Visa produces a HIGH finding and remains on the protected review path.
    s=upload(client,type='Visa',expiry='01/01/2000').json()['screenings'][0]
    assert s['recommendation']=='MANUAL_REVIEW'
    assert s['decision_policy']['supervisor_direct_accept_allowed'] is False
    r=supervisor.post('/api/screening/'+s['id']+'/decision?action=ACCEPT',headers=HEAD,data={'reason':'Attempted direct acceptance despite explicit review signal.'})
    assert r.status_code==409
