import json
import sqlite3
import pytest
from fastapi.testclient import TestClient
from test_local import upload, image_bytes
from app import main, local_registry as registry

HEAD={'X-Local-Request':'1'}
REASON='Synthetic registry regression test.'

@pytest.fixture
def supervisor(client):
    with TestClient(main.app) as c:
        assert c.post('/api/auth/login',headers=HEAD,json={'username':'supervisor','password':'test-password-12345'}).status_code==200
        yield c

def base(number='REGTEST01'):
    return dict(document_type='Permit',name='TEST PERSON',document_number=number,dob='2001-03-14',nationality='IND',issuer_country='IND',expiry='2035-12-31')

def create(c,number):
    r=c.post('/api/registry',headers=HEAD,json={'record':base(number),'reason':REASON})
    assert r.status_code==201,r.text
    return r.json()

def payload(record):
    return {k:record[k] for k in registry.RegistryRecordInput.model_fields}

def test_registry_permissions(client,supervisor):
    with TestClient(main.app) as anon: assert anon.get('/api/registry').status_code==401
    r=create(supervisor,'PERMISSION01')
    assert client.get('/api/registry').status_code==200
    for path,method,body in [('', 'post',{'record':base(),'reason':REASON}),('/demo-seed','post',None),('/'+r['id'],'put',{'record':base(),'reason':REASON,'expected_version':1}),('/'+r['id']+'/archive','post',{'reason':REASON,'expected_version':1})]:
        assert getattr(client,method)('/api/registry'+path,headers=HEAD,json=body).status_code==403
    assert client.get('/api/registry/'+r['id']+'/history').status_code==403

def test_version_history_duplicate_archive(supervisor):
    r=create(supervisor,'VERSION01');path='/api/registry/'+r['id']
    body={'record':payload(r)|{'name':'UPDATED PERSON'},'reason':REASON,'expected_version':1}
    changed=supervisor.put(path,headers=HEAD,json=body)
    assert changed.status_code==200 and changed.json()['version']==2
    assert supervisor.put(path,headers=HEAD,json=body).status_code==409
    assert supervisor.post('/api/registry',headers=HEAD,json={'record':base('VERSION01'),'reason':REASON}).status_code==409
    history=supervisor.get(path+'/history').json()['items']
    assert len(history)==2 and history[0]['before']['name']=='TEST PERSON' and history[0]['after']['name']=='UPDATED PERSON'
    assert supervisor.post(path+'/archive',headers=HEAD,json={'reason':REASON,'expected_version':2}).json()['archived']
    assert registry.compare('Permit',base('VERSION01'))['status']=='ARCHIVED'
    assert not supervisor.post(path+'/archive?restore=true',headers=HEAD,json={'reason':REASON,'expected_version':3}).json()['archived']

@pytest.mark.parametrize('changes,status',[
    ({},'MATCH'),({'dob':'14/03/2001','name':'test person','nationality':'India'},'MATCH'),
    ({'dob':'2002-03-14'},'CONFLICT'),({'name':'TEST PERSOM'},'REVIEW_REQUIRED'),
    ({'name':'PERSON TEST'},'REVIEW_REQUIRED'),({'dob':'31/02/2001'},'PARTIAL'),
    ({'dob':''},'PARTIAL'),({'name':'!!!'},'PARTIAL'),({'document_number':'NOTPRESENT'},'NOT_FOUND'),
    ({'document_number':''},'NOT_CHECKED'),({'issuer_country':'USA'},'NOT_FOUND')])
def test_comparison(supervisor,changes,status):
    # Unique lookup for each parameter; seeded idempotently by direct lookup.
    if not supervisor.get('/api/registry?q=COMPARE01').json()['total']: create(supervisor,'COMPARE01')
    value=registry.compare('Permit',base('COMPARE01')|changes)
    assert value['status']==status,value

def test_ambiguous_different_issuers(supervisor):
    r=create(supervisor,'AMBIGUOUS01')
    assert supervisor.post('/api/registry',headers=HEAD,json={'record':base('AMBIGUOUS01')|{'issuer_country':'USA'},'reason':REASON}).status_code==201
    assert registry.compare('Permit',base('AMBIGUOUS01')|{'issuer_country':''})['status']=='AMBIGUOUS'
    assert registry.compare('Permit',base('AMBIGUOUS01'))['status']=='MATCH'

def test_seed_does_not_overwrite(supervisor):
    result=supervisor.post('/api/registry/demo-seed',headers=HEAD).json()
    assert len(result['created'])==4
    again=supervisor.post('/api/registry/demo-seed',headers=HEAD).json()
    assert not again['created'] and len(again['skipped'])==4
    for record in registry.demo_records():
        assert registry.compare('Permit',record.model_dump())['status']==('MATCH' if record.status=='ACTIVE' else record.status)

def test_snapshot_and_escalation(supervisor,client):
    r=create(supervisor,'SNAPSHOT01');path='/api/registry/'+r['id']
    s=upload(client,**(base('SNAPSHOT01')|{'type':'Permit'})).json()['screenings'][0]
    assert s['result']['ai_analysis']['registry']['record']['version']==1
    changed=supervisor.put(path,headers=HEAD,json={'record':payload(r)|{'status':'BLOCKED'},'expected_version':1,'reason':REASON})
    assert changed.status_code==200
    old=client.get('/api/screening/'+s['id']).json()
    assert old['result']['ai_analysis']['registry']['record']['version']==1
    blocked=upload(client,**(base('SNAPSHOT01')|{'type':'Permit'})).json()['screenings'][0]
    assert blocked['recommendation']=='ESCALATE'
    decision='/api/screening/'+blocked['id']+'/decision?action='
    assert supervisor.post(decision+'ACCEPT',headers=HEAD,data={'reason':REASON}).status_code==409
    assert client.post(decision+'ESCALATE',headers=HEAD,data={'reason':REASON}).status_code==200

def test_missing_and_unavailable_not_fake(client,monkeypatch):
    s=upload(client,document_number='ZZZZZ9999Z').json()['screenings'][0]
    assert s['risk']=='UNASSESSED' and s['result']['ai_analysis']['registry']['status']=='NOT_FOUND'
    def unavailable(): raise sqlite3.OperationalError('test failure')
    monkeypatch.setattr(registry,'connection',unavailable)
    assert registry.compare('Permit',base())['status']=='UNAVAILABLE'

def test_legacy_windows_path(client):
    s=upload(client).json()['screenings'][0]
    with main.SessionLocal() as db:
        row=db.scalar(main.select(main.Screening).where(main.Screening.screening_id==s['id']))
        name=row.stored_path.replace('\\','/').rsplit('/',1)[-1]
        row.stored_path='C:\\old-v4\\backend\\private\\documents\\'+name
        db.commit()
    assert client.get('/api/screening/'+s['id']+'/image').status_code==200
    assert client.get('/api/screening/'+s['id']+'/evidence').json()['hash_integrity_ok']

def test_input_validation(supervisor):
    for change in [{'name':'!!!'},{'dob':'2039-01-01'},{'expiry':''},{'issuer_country':'INDIA'},{'status':'GENUINE'}]:
        r=supervisor.post('/api/registry',headers=HEAD,json={'record':base()|change,'reason':REASON})
        assert r.status_code==422,r.text
