from pathlib import Path
from app import demo_hardening, main


def supervisor_login(client):
    r=client.post('/api/auth/login',headers={'X-Local-Request':'1'},json={'username':'supervisor','password':'test-password-12345'})
    assert r.status_code==200,r.text


def test_v69_readiness_api_reports_local_dependencies(client):
    d=client.get('/api/demo/readiness').json()
    assert d['version']=='SIH26188_DEMO_HARDENING_V1'
    assert d['overall'] in {'READY','READY_WITH_WARNINGS'}
    assert d['blocking_count']==0
    names={x['name'] for x in d['checks']}
    assert {'Python runtime','Offline OCR assets','Local face models','Screening database','Synthetic registry database','Curated SIH demo samples'} <= names


def test_v69_scenario_manifest_is_sih_specific_and_synthetic(client):
    d=client.get('/api/demo/scenarios').json()
    assert len(d['scenarios'])>=8
    keys={x['key'] for x in d['scenarios']}
    assert {'clean_active','dob_tamper','blocked_document','visa_stamp_review','entry_limit','lost_stolen'} <= keys
    assert 'synthetic' in d['limitation'].lower()


def test_v69_sample_endpoint_only_serves_whitelisted_fixture(client):
    r=client.get('/api/demo/sample/clean_active')
    assert r.status_code==200
    assert r.headers['content-type'].startswith('image/png')
    assert len(r.content)>1000
    assert client.get('/api/demo/sample/not-a-real-demo').status_code==404


def test_v69_seed_all_requires_supervisor(client):
    r=client.post('/api/demo/seed-all',headers={'X-Local-Request':'1'})
    assert r.status_code==403


def test_v69_seed_all_is_idempotent(client):
    supervisor_login(client)
    first=client.post('/api/demo/seed-all',headers={'X-Local-Request':'1'})
    assert first.status_code==200,first.text
    d=first.json();assert d['version']=='SIH26188_DEMO_HARDENING_V1'
    second=client.post('/api/demo/seed-all',headers={'X-Local-Request':'1'})
    assert second.status_code==200,second.text
    assert len(second.json()['legacy']['created'])==0
    # Registry 2.x seed functions are also idempotent; the call itself must remain safe.
    assert 'Existing records were preserved' in second.json()['message']


def test_v69_system_status_exposes_demo_hardening(client):
    d=client.get('/api/system/status').json()
    assert d['demo_hardening']=='SIH26188_DEMO_HARDENING_V1'
    assert d['engine'].startswith('7.1.0')


def test_v70_integrated_runtime_assets_are_packaged():
    import re
    root=Path(main.BACKEND_ROOT).parent
    html=(root/'dist'/'index.html').read_text()
    scripts=re.findall(r'<script[^>]+src="([^"]+)"',html)
    assert len(scripts)==1
    assert scripts[0].startswith('/assets/')
    js=(root/'dist'/scripts[0].lstrip('/')).read_text()
    assert 'SIH26188 Demo Readiness' in js
    assert 'Prepare all synthetic demo data' in js
    assert 'Synthetic Registry 2.2: linked identities' in js
    assert 'CHECKPOINT DECISION CENTER' in js
    assert not list((root/'dist').glob('v6*-*.js'))
    assert (root/'SIH26188_DEMO_RUNBOOK_V69.md').exists()
