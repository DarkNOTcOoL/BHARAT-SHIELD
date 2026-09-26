import json
from pathlib import Path
from app import video_demo,risk_policy,local_registry
from test_registry import supervisor,HEAD

def test_demo_reference_checks(client,supervisor):
    assert client.post('/api/video-demo/seed',headers=HEAD).status_code==403
    assert len(supervisor.post('/api/video-demo/seed',headers=HEAD).json()['created'])==8
    assert len(supervisor.post('/api/video-demo/seed',headers=HEAD).json()['skipped'])==8
    root=Path(__file__).resolve().parents[2]/'demo_samples/video_demo'
    for case in video_demo.scenarios():
        meta=case['printed']|{'type':'Permit','ocr_text':'\n'.join(case['printed'].values()),'ocr_confidence':95}
        r=client.post('/api/screening/batch',headers=HEAD,data={'documents_json':json.dumps([meta])},files=[('files',(case['file'],(root/case['file']).read_bytes(),'image/png'))]);assert r.status_code==200,r.text
        s=r.json()['screenings'][0];a=s['result']['ai_analysis'];score=a['risk_score']
        assert a['registry']['status']==case['expected_registry']
        assert score['score']==case['expected_score_after_correct_review'],(case['file'],score)
        assert score['band']==case['expected_band']
        if score['band']=='LOW':assert s['recommendation']=='REVIEW_COMPLETE_CHECKS'
        if score['band']=='CRITICAL':assert s['recommendation']=='ESCALATE'
        assert score==client.get('/api/screening/'+s['id']+'/evidence').json()['result']['ai_analysis']['risk_score']

def test_expiry_deduplication_and_missing_evidence():
    f={'name':'ANY PERSON','document_number':'OTHER123','dob':'1990-01-01','nationality':'IND','issuer_country':'IND'}
    score=risk_policy.assess({'status':'EXPIRED','fields':[]},{},[{'code':'DOCUMENT_EXPIRED'},{'code':'REGISTRY_EXPIRED'}],f,{'status':'USABLE'},95,'NOT_APPLICABLE')
    assert score['score']==40 and len(score['factors'])==1
    for status,quality in [('NOT_FOUND','USABLE'),('MATCH','RECAPTURE')]:
        result=risk_policy.assess({'status':status,'fields':[]},{},[],f,{'status':quality},95,'NOT_APPLICABLE');assert result['score'] is None

def test_reference_changes_not_filename_control_score(client,supervisor):
    case=video_demo.scenarios()[0];record=supervisor.get('/api/registry?q=REF7611').json()['records'][0];path='/api/registry/'+record['id']
    changed=supervisor.put(path,headers=HEAD,json={'record':case['reference']|{'status':'REVOKED'},'reason':'Testing real reference evaluation.','expected_version':record['version']});assert changed.status_code==200
    r=local_registry.compare('Permit',case['printed']);assert risk_policy.assess(r,{},r['findings'],case['printed'],{'status':'USABLE'},95,'NOT_APPLICABLE')['score']==90
    assert supervisor.put(path,headers=HEAD,json={'record':case['reference'],'reason':'Restore the fictional fixture.','expected_version':changed.json()['version']}).status_code==200

def test_actual_engine_reads_through_screening(client,supervisor):
    root=Path(__file__).resolve().parents[2];results=json.loads((root/'OCR_BENCHMARK_V56.json').read_text())['cases'];expected={x['file']:x for x in video_demo.scenarios()}
    supervisor.post('/api/video-demo/seed',headers=HEAD)
    aliases={'documentNumber':'document_number','issuerCountry':'issuer_country','issueDate':'issue_date','issuingAuthority':'issuing_authority','passportReference':'passport_reference'}
    for read in results:
        meta={aliases.get(k,k):v for k,v in read['fields'].items()}|{'type':'Permit','ocr_text':read['raw_text'],'ocr_confidence':read['confidence'],'ocr_fields':read['fields']}
        r=client.post('/api/screening/batch',headers=HEAD,data={'documents_json':json.dumps([meta])},files=[('files',(read['file'],(root/'demo_samples/video_demo'/read['file']).read_bytes(),'image/png'))]);assert r.status_code==200,r.text
        s=r.json()['screenings'][0];score=s['result']['ai_analysis']['risk_score'];assert score['band']==expected[read['file']]['expected_band'];assert score['score']==expected[read['file']]['expected_score_after_correct_review']
        if read['degraded']:assert s['recommendation']=='RECAPTURE'
