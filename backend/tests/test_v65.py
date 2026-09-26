from app import local_registry, registry_v2, risk_policy, audit_chain
from test_registry import HEAD, REASON, supervisor


def _seed(supervisor):
    r=supervisor.post('/api/registry2/demo-seed',headers=HEAD)
    assert r.status_code==200,r.text
    return r.json()


def test_registry2_summary_and_permissions(client,supervisor):
    assert client.get('/api/registry2/summary').status_code==200
    assert client.post('/api/registry2/demo-seed',headers=HEAD).status_code==403
    result=_seed(supervisor)
    assert str(result['schema_version']).startswith('2.')
    summary=supervisor.get('/api/registry2/summary').json()
    assert summary['source']==registry_v2.SOURCE and summary['external_connections'] is False
    assert summary['counts']['identities']>=2
    assert summary['counts']['document_links']>=3
    assert summary['counts']['travel_events']>=3
    assert summary['counts']['open_alerts']>=1
    assert summary['counts']['issuer_templates']>=3


def test_registry2_demo_is_idempotent_and_graph_has_linked_documents(supervisor):
    first=_seed(supervisor);second=_seed(supervisor)
    assert second['created']=={'identities':0,'documents':0,'travel_events':0,'alerts':0,'issuer_templates':0}
    detail=supervisor.get('/api/registry2/identities/IDN-DEMO65-CLEAN').json()
    assert detail['identity']['canonical_name']=='MAYA REGISTRY DEMO'
    types={d['document_type'] for d in detail['documents']}
    assert {'Passport','Visa'}<=types
    assert any(r['relation_type']=='VISA_REFERENCES_PASSPORT' for r in detail['document_relations'])
    assert {e['event_type'] for e in detail['travel_events']} >= {'VISA_ISSUED','ENTRY','EXIT'}


def test_registry2_clean_reference_enrichment(supervisor):
    _seed(supervisor)
    fields={'document_number':'DEMOUS26001','name':'MAYA REGISTRY DEMO','dob':'1996-06-18','nationality':'USA','issuer_country':'USA','gender':'F','issue_date':'2024-06-18','expiry':'2034-06-17','issuing_authority':'DEMO PASSPORT AUTHORITY','passport_reference':''}
    result=registry_v2.enrich_reference(local_registry.compare('Passport',fields))
    assert result['status']=='MATCH'
    assert result['registry2']['status']=='LINKED'
    assert result['registry2']['identity']['id']=='IDN-DEMO65-CLEAN'
    assert len(result['registry2']['linked_documents'])>=2
    assert not result['registry2']['requires_review']
    assert result['registry2']['issuer_templates']


def test_registry2_lost_stolen_alert_requires_escalation_and_risk(supervisor):
    _seed(supervisor)
    fields={'document_number':'DEMOIND26002','name':'ARJUN REGISTRY DEMO','dob':'1995-02-11','nationality':'IND','issuer_country':'IND','gender':'M','issue_date':'2025-02-11','expiry':'2035-02-10','issuing_authority':'DEMO PASSPORT AUTHORITY','passport_reference':''}
    result=registry_v2.enrich_reference(local_registry.compare('Passport',fields))
    assert result['status']=='MATCH'
    assert result['registry2']['requires_review']
    assert result['registry2']['escalation_required']
    assert any(f['code']=='REGISTRY2_ALERT_LOST_STOLEN_DOCUMENT' for f in result['findings'])
    score=risk_policy.assess(result,{},result['findings'],fields,{'status':'USABLE'},95,'VALID')
    factor={f['group']:f for f in score['factors']}['registry2_alert']
    assert factor['points']==90 and score['band']=='CRITICAL'


def test_registry2_supervisor_can_add_event_and_resolve_alert(supervisor):
    _seed(supervisor)
    clean=supervisor.get('/api/registry2/identities/IDN-DEMO65-CLEAN').json()
    passport=next(d for d in clean['documents'] if d['document_type']=='Passport')
    travel=supervisor.post('/api/registry2/identities/IDN-DEMO65-CLEAN/travel-events',headers=HEAD,json={
        'event_type':'STAMP_OBSERVED','country_code':'IND','port':'DEMO TEST PORT','event_date':'2026-09-10','authority':'DEMO IMMIGRATION',
        'document_record_id':passport['id'],'stamp_reference':'TEST-STAMP-65','notes':'Test only.','source':'SYNTHETIC_TEST','reason':REASON})
    assert travel.status_code==201,travel.text
    alert=supervisor.post('/api/registry2/identities/IDN-DEMO65-CLEAN/alerts',headers=HEAD,json={
        'alert_type':'IDENTITY_REVIEW','severity':'REVIEW','reason':'Synthetic identity requires secondary review for regression testing.',
        'document_record_id':'','source':'SYNTHETIC_TEST'})
    assert alert.status_code==201,alert.text
    resolved=supervisor.post('/api/registry2/alerts/'+alert.json()['id']+'/resolve',headers=HEAD,json={'reason':REASON})
    assert resolved.status_code==200 and resolved.json()['status']=='CLEARED'


def test_registry2_events_are_in_registry_audit_chain(supervisor):
    _seed(supervisor)
    with local_registry.connection() as db:
        check=audit_chain.verify(db)
        assert check['status']=='CHAIN_CONSISTENT',check
        assert db.execute("SELECT count(*) FROM registry2_events").fetchone()[0]>0
        assert db.execute("SELECT count(*) FROM bs_audit_chain WHERE source='registry2_events'").fetchone()[0]>0

def test_registry2_alert_changes_screening_recommendation(supervisor,client):
    from test_local import upload
    _seed(supervisor)
    s=upload(client,type='Passport',document_number='DEMOIND26002',name='ARJUN REGISTRY DEMO',dob='1995-02-11',nationality='IND',issuer_country='IND',gender='M',issue_date='2025-02-11',expiry='2035-02-10',issuing_authority='DEMO PASSPORT AUTHORITY',ocr_text='PASSPORT ARJUN REGISTRY DEMO DEMOIND26002',ocr_confidence=95).json()['screenings'][0]
    assert s['recommendation']=='ESCALATE'
    r2=s['result']['ai_analysis']['registry']['registry2']
    assert r2['escalation_required'] and any(a['alert_type']=='LOST_STOLEN_DOCUMENT' for a in r2['alerts'])

def test_new_legacy_document_is_immediately_linked_to_registry2(supervisor):
    record={'document_type':'Permit','document_number':'REG2AUTO6501','name':'AUTO LINK PERSON','dob':'2001-05-06','nationality':'IND','issuer_country':'IND','expiry':'2035-12-31'}
    created=supervisor.post('/api/registry',headers=HEAD,json={'record':record,'reason':REASON})
    assert created.status_code==201,created.text
    rid=created.json()['id']
    with local_registry.connection() as db:
        row=db.execute('SELECT identity_id FROM registry2_document_links WHERE record_id=?',(rid,)).fetchone()
        assert row is not None
        detail=registry_v2.identity_detail(db,row['identity_id'])
        assert any(d['id']==rid for d in detail['documents'])
