import copy,hashlib,json,sqlite3,time,uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import main,signed_qr,signed_demo,local_registry,local_security,audit_chain,duplicate_checks,checkpoints
from test_registry import supervisor,HEAD

SAMPLES=Path(__file__).resolve().parents[2]/'demo_samples'/'signed_qr'
@pytest.mark.parametrize('filename,status',[
 ('01_signed_match.png','SIGNATURE_VALID'),('02_printed_dob_changed.png','SIGNATURE_VALID'),
 ('03_payload_tampered.png','SIGNATURE_INVALID'),('04_unknown_issuer.png','UNKNOWN_DEMO_ISSUER'),
 ('05_unsigned_required.png','NO_SIGNED_QR'),('06_substituted_valid_qr.png','SIGNATURE_VALID'),('07_reused_credential.png','SIGNATURE_VALID')])
def test_actual_png_decode(filename,status):
    result=signed_qr.scan_image((SAMPLES/filename).read_bytes())
    assert result['signature_status']==status
    if status!='SIGNATURE_VALID':assert result['claims'] is None

def seed(supervisor):
    response=supervisor.post('/api/signed-demo/seed',headers=HEAD)
    assert response.status_code==200,response.text
    return response.json()

@pytest.mark.parametrize('filename,signature,comparison,review',[
 ('01_signed_match.png','SIGNATURE_VALID','CONSISTENT',False),
 ('02_printed_dob_changed.png','SIGNATURE_VALID','SIGNED_DATA_CONFLICT',True),
 ('03_payload_tampered.png','SIGNATURE_INVALID','UNVERIFIED',True),
 ('04_unknown_issuer.png','UNKNOWN_DEMO_ISSUER','UNVERIFIED',True),
 ('05_unsigned_required.png','NO_SIGNED_QR','UNVERIFIED',True),
 ('06_substituted_valid_qr.png','SIGNATURE_VALID','SIGNED_DATA_CONFLICT',True)])
def test_three_source_screening(client,supervisor,filename,signature,comparison,review):
    seed(supervisor)
    metadata=signed_demo.records()[0].copy();metadata['type']=metadata.pop('document_type')
    for k in ['id','version','requires_signed_qr']:metadata.pop(k)
    if filename.startswith('02'):metadata['dob']='2002-03-14'
    metadata.update(ocr_confidence=95,ocr_text='SYNTHETIC DEMO AARAV DEMO DEMO5201')
    r=client.post('/api/screening/batch',headers=HEAD,data={'documents_json':json.dumps([metadata])},files=[('files',(filename,(SAMPLES/filename).read_bytes(),'image/png'))])
    assert r.status_code==200,r.text
    result=r.json()['screenings'][0];e=result['result']['ai_analysis'];qr=e['signed_qr']
    assert qr['signature_status']==signature and qr['comparison_status']==comparison
    assert qr['requires_review']==review and qr['required_by_registry']
    if review:assert result['recommendation'] in ['MANUAL_REVIEW','RECAPTURE','ESCALATE']
    assert e['timing']['local_document_processing_ms']>=0
    assert signature in client.get('/api/screening/'+result['id']+'/report').text

def test_seed_no_overwrite_and_officer_denied(client,supervisor):
    assert client.post('/api/signed-demo/seed',headers=HEAD).status_code==403
    seed(supervisor);assert len(seed(supervisor)['skipped'])==2

def test_signed_reference_version_change():
    qr=signed_qr.scan_image((SAMPLES/'01_signed_match.png').read_bytes())
    record=signed_demo.records()[0]|qr['claims']['fields']
    r=signed_qr.compare(qr,'Permit',record,{'record':record|{'version':2}})
    assert r['signature_status']=='SIGNATURE_VALID' and r['reference_status']=='REFERENCE_VERSION_CHANGED' and r['requires_review']

@pytest.mark.parametrize('text',['BS52.not-valid.abc','BS52.a.b.c','https://example.com/issuer','BS52.'+'a'*6100])
def test_malformed_untrusted_payload(text):
    assert signed_qr.verify_text(text)['claims'] is None

def test_duplicate_signals_not_identity_verdicts():
    f={'name':'AARAV DEMO','dob':'2001-03-14','issuer_country':'IND','document_number':'A123'}
    history=[{'screening_id':'SCR-OLD','fields':f,'document_type':'Permit','document_hash':'hash','claims':None}]
    repeat=duplicate_checks.compare(f,'Permit','hash',None,history)
    assert repeat['candidates'][0]['reasons']==['EXACT_IMAGE_RESCAN'] and not repeat['requires_review']
    conflict=duplicate_checks.compare(f|{'name':'OTHER PERSON'},'Permit','other',None,history)
    assert conflict['requires_review']
    other=duplicate_checks.compare(f|{'document_number':'B456'},'Permit','other',None,history)
    assert 'SAME_NAME_DOB_OTHER_NUMBER' in other['candidates'][0]['reasons'] and not other['requires_review']

def chain_db():
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE security_events(id INTEGER PRIMARY KEY,actor TEXT,action TEXT,subject TEXT,timestamp REAL)')
    audit_chain.initialize(db)
    for i in range(2):db.execute('INSERT INTO security_events VALUES(?,?,?,?,?)',(i+1,'test','ACTION','subject',1.0))
    return db
def test_audit_tamper_and_external_tail_checkpoint():
    with chain_db() as db:
        saved=audit_chain.verify(db);assert saved['status']=='CHAIN_CONSISTENT'
        db.execute('UPDATE security_events SET actor=? WHERE id=1',('altered',))
        assert audit_chain.verify(db)['status']=='INTEGRITY_ERROR'
    with chain_db() as db:
        saved=audit_chain.verify(db)
        db.execute('DELETE FROM security_events WHERE id=2');db.execute('DELETE FROM bs_audit_chain WHERE seq=2')
        assert audit_chain.verify(db)['status']=='CHAIN_CONSISTENT'
        assert audit_chain.verify(db,saved)['status']=='INTEGRITY_ERROR'

def test_integrity_permissions_and_signed_export(client,supervisor):
    assert client.get('/api/admin/integrity').status_code==403
    response=supervisor.get('/api/admin/integrity');assert response.status_code==200,response.text
    for name in ['screening','registry','accounts']:assert response.json()[name]['status']=='CHAIN_CONSISTENT',response.json()[name]
    value=supervisor.get('/api/admin/audit-checkpoint').json()
    assert checkpoints.verify(value,value['public_key_sha256'])['screening']['status']=='CHAIN_CONSISTENT'
    with pytest.raises(ValueError):checkpoints.verify(value,'00'*32)
    altered=copy.deepcopy(value);altered['payload']['screening']['count']+=1
    from cryptography.exceptions import InvalidSignature
    with pytest.raises(InvalidSignature):checkpoints.verify(altered,value['public_key_sha256'])

def test_account_disable_reset_session_revocation(client,supervisor):
    name='account-'+uuid.uuid4().hex[:8];password='original-password-12345'
    local_security.create_user(name,'Account Test',password)
    assert client.get('/api/admin/accounts').status_code==403
    assert supervisor.post('/api/admin/accounts/supervisor',headers=HEAD,json={'action':'disable'}).status_code==400
    with TestClient(main.app) as officer:
        assert officer.post('/api/auth/login',headers=HEAD,json={'username':name,'password':password}).status_code==200
        assert supervisor.post('/api/admin/accounts/'+name,headers=HEAD,json={'action':'disable'}).status_code==200
        assert officer.get('/api/auth/me').status_code==401
        assert officer.post('/api/auth/login',headers=HEAD,json={'username':name,'password':password}).status_code==401
        supervisor.post('/api/admin/accounts/'+name,headers=HEAD,json={'action':'enable'})
        supervisor.post('/api/admin/accounts/'+name,headers=HEAD,json={'action':'reset_password','password':'new-password-123456'})
        assert officer.post('/api/auth/login',headers=HEAD,json={'username':name,'password':'new-password-123456'}).status_code==200
        assert officer.post('/api/auth/password',headers=HEAD,json={'current_password':'wrong','new_password':'another-password-12345'}).status_code==400
        assert officer.post('/api/auth/password',headers=HEAD,json={'current_password':'new-password-123456','new_password':'another-password-12345'}).status_code==200
        assert officer.get('/api/auth/me').status_code==401
        assert officer.post('/api/auth/login',headers=HEAD,json={'username':name,'password':'another-password-12345'}).status_code==200
        session=next(s for s in supervisor.get('/api/admin/accounts').json()['sessions'] if s['username']==name)
        assert supervisor.delete('/api/admin/sessions/'+session['id'],headers=HEAD).status_code==200
        assert officer.get('/api/auth/me').status_code==401

def test_idle_expiry():
    name='idle-'+uuid.uuid4().hex[:8];local_security.create_user(name,'Idle Test','password-for-idle-1234')
    token='unique-test-token-'+name;digest=hashlib.sha256(token.encode()).hexdigest()
    with local_security.connect() as db:
        db.execute('INSERT INTO sessions(digest,username,expires,last_seen) VALUES(?,?,?,?)',(digest,name,time.time()+3600,time.time()-901))
    assert local_security.session_user(token) is None

def test_legacy_accounts_migration_preserves_users_invalidates_sessions(tmp_path,monkeypatch):
    path=tmp_path/'legacy.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE users(username TEXT PRIMARY KEY,name TEXT NOT NULL,role TEXT NOT NULL,salt TEXT NOT NULL,password_hash TEXT NOT NULL)')
        db.execute("INSERT INTO users VALUES('legacy','Existing Supervisor','supervisor','salt','hash')")
        db.execute('CREATE TABLE sessions(digest TEXT PRIMARY KEY,username TEXT NOT NULL,expires REAL NOT NULL)')
        db.execute("INSERT INTO sessions VALUES('old','legacy',9999999999)")
    monkeypatch.setattr(local_security,'DB',path)
    for _ in range(2):
        with local_security.connect() as db:
            row=db.execute('SELECT * FROM users').fetchone();assert row['username']=='legacy' and row['password_hash']=='hash' and row['enabled']==1
            assert db.execute('SELECT count(*) FROM sessions').fetchone()[0]==0

def test_audit_legacy_baseline_is_explicit_and_idempotent():
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE security_events(id INTEGER PRIMARY KEY,actor TEXT,action TEXT,subject TEXT,timestamp REAL)')
        db.execute("INSERT INTO security_events VALUES(1,'legacy','ACTION','subject',1.0)")
        audit_chain.initialize(db);audit_chain.initialize(db)
        result=audit_chain.verify(db);assert result['status']=='CHAIN_CONSISTENT' and result['legacy_baseline_count']==1
        db.execute("INSERT INTO security_events VALUES(2,'new','ACTION','subject',2.0)")
        assert audit_chain.verify(db)['count']==2
