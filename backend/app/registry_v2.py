"""BHARATSHIELD Synthetic Government Registry 2.0.

Relational companion layer over the legacy document-centric registry.  It stays
strictly local/demo-only and never implies a government or external connection.
Existing registry_records remain the canonical per-document reference rows so
older screenings and signed-demo workflows keep working.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
import hashlib
from pathlib import Path
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import audit_chain, local_registry

VERSION = 'SYNTHETIC_REGISTRY_2_2_TRAVEL_INTELLIGENCE'
SOURCE = 'SYNTHETIC_GOVERNMENT_REGISTRY_2_0_DEMO_ONLY'


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return prefix + '-' + uuid.uuid4().hex[:16].upper()


def _json(value, default):
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError):
        return default


def _event(db, entity_type: str, entity_id: str, action: str, actor: str, reason: str, payload: dict):
    db.execute(
        'INSERT INTO registry2_events(entity_type,entity_id,action,actor,reason,timestamp,payload_json) VALUES(?,?,?,?,?,?,?)',
        (entity_type, entity_id, action, actor, reason, utcnow(), json.dumps(payload, ensure_ascii=False, separators=(',', ':'))),
    )


def initialize():
    with local_registry.connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS registry2_meta(
          key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS registry2_identities(
          id TEXT PRIMARY KEY, canonical_name TEXT NOT NULL, search_name TEXT NOT NULL,
          dob TEXT NOT NULL, nationality TEXT NOT NULL, gender TEXT NOT NULL DEFAULT '',
          place_of_birth TEXT NOT NULL DEFAULT '', aliases_json TEXT NOT NULL DEFAULT '[]',
          identity_status TEXT NOT NULL DEFAULT 'ACTIVE', notes TEXT NOT NULL DEFAULT '',
          version INTEGER NOT NULL DEFAULT 1, archived INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, updated_by TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS registry2_identity_search_idx ON registry2_identities(search_name,dob,nationality);
        CREATE TABLE IF NOT EXISTS registry2_document_links(
          record_id TEXT PRIMARY KEY, identity_id TEXT NOT NULL, relationship TEXT NOT NULL DEFAULT 'PRIMARY',
          linked_at TEXT NOT NULL, linked_by TEXT NOT NULL, reason TEXT NOT NULL,
          FOREIGN KEY(record_id) REFERENCES registry_records(id),
          FOREIGN KEY(identity_id) REFERENCES registry2_identities(id));
        CREATE INDEX IF NOT EXISTS registry2_doc_identity_idx ON registry2_document_links(identity_id);
        CREATE TABLE IF NOT EXISTS registry2_document_relations(
          id TEXT PRIMARY KEY, from_record_id TEXT NOT NULL, to_record_id TEXT NOT NULL,
          relation_type TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
          created_by TEXT NOT NULL, UNIQUE(from_record_id,to_record_id,relation_type));
        CREATE TABLE IF NOT EXISTS registry2_travel_events(
          id TEXT PRIMARY KEY, identity_id TEXT NOT NULL, document_record_id TEXT NOT NULL DEFAULT '',
          event_type TEXT NOT NULL, country_code TEXT NOT NULL DEFAULT '', port TEXT NOT NULL DEFAULT '',
          event_date TEXT NOT NULL, authority TEXT NOT NULL DEFAULT '', stamp_reference TEXT NOT NULL DEFAULT '',
          notes TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'SYNTHETIC_DEMO',
          created_at TEXT NOT NULL, created_by TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS registry2_travel_identity_idx ON registry2_travel_events(identity_id,event_date);
        CREATE TABLE IF NOT EXISTS registry2_alerts(
          id TEXT PRIMARY KEY, identity_id TEXT NOT NULL, document_record_id TEXT NOT NULL DEFAULT '',
          alert_type TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN',
          reason TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'SYNTHETIC_DEMO',
          created_at TEXT NOT NULL, created_by TEXT NOT NULL, resolved_at TEXT NOT NULL DEFAULT '',
          resolved_by TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS registry2_alert_identity_idx ON registry2_alerts(identity_id,status);
        CREATE TABLE IF NOT EXISTS registry2_issuer_templates(
          id TEXT PRIMARY KEY, document_type TEXT NOT NULL, issuer_country TEXT NOT NULL,
          issuer_name TEXT NOT NULL, template_version TEXT NOT NULL, valid_from TEXT NOT NULL DEFAULT '',
          valid_to TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
          expected_zones_json TEXT NOT NULL DEFAULT '[]', notes TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL, created_by TEXT NOT NULL,
          UNIQUE(document_type,issuer_country,template_version));
        CREATE TABLE IF NOT EXISTS registry2_template_features(
          id TEXT PRIMARY KEY, template_id TEXT NOT NULL, feature_code TEXT NOT NULL,
          feature_label TEXT NOT NULL, expected_box_json TEXT NOT NULL, reference_asset TEXT NOT NULL,
          reference_sha256 TEXT NOT NULL, required INTEGER NOT NULL DEFAULT 1, critical INTEGER NOT NULL DEFAULT 0,
          min_score REAL NOT NULL DEFAULT 0.48, match_method TEXT NOT NULL DEFAULT 'ORB_EDGE_ZONE_V1',
          notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, created_by TEXT NOT NULL,
          UNIQUE(template_id,feature_code), FOREIGN KEY(template_id) REFERENCES registry2_issuer_templates(id));
        CREATE INDEX IF NOT EXISTS registry2_template_feature_idx ON registry2_template_features(template_id,feature_code);
        CREATE TABLE IF NOT EXISTS registry2_biometric_refs(
          id TEXT PRIMARY KEY, identity_id TEXT NOT NULL, screening_id TEXT NOT NULL,
          template_sha256 TEXT NOT NULL, model_ref TEXT NOT NULL DEFAULT 'SFace',
          liveness_status TEXT NOT NULL DEFAULT 'PASSED_ACTIVE_CHALLENGE',
          created_at TEXT NOT NULL, created_by TEXT NOT NULL,
          UNIQUE(identity_id,screening_id));
        CREATE TABLE IF NOT EXISTS registry2_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
          action TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, timestamp TEXT NOT NULL,
          payload_json TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS registry2_event_entity_idx ON registry2_events(entity_type,entity_id,id);
        ''')
        db.execute("INSERT OR REPLACE INTO registry2_meta(key,value) VALUES('schema_version','2.2')")
        db.execute("INSERT OR REPLACE INTO registry2_meta(key,value) VALUES('travel_intelligence','REGISTRY2_VISA_ENTRY_SEQUENCE_V1')")
        db.execute("INSERT OR REPLACE INTO registry2_meta(key,value) VALUES('visual_template_features','SYNTHETIC_REFERENCE_FEATURES_V1')")
        db.execute("INSERT OR REPLACE INTO registry2_meta(key,value) VALUES('source',?)", (SOURCE,))
        # audit_chain knows about registry2_events in v6.5 and creates its trigger here.
        audit_chain.initialize(db)
        _backfill_existing(db)


def _identity_row(db, ident: str):
    return db.execute('SELECT * FROM registry2_identities WHERE id=?', (ident,)).fetchone()


def _serialize_identity(row):
    if not row:
        return None
    return {
        'id': row['id'], 'canonical_name': row['canonical_name'], 'dob': row['dob'],
        'nationality': row['nationality'], 'gender': row['gender'], 'place_of_birth': row['place_of_birth'],
        'aliases': _json(row['aliases_json'], []), 'identity_status': row['identity_status'],
        'notes': row['notes'], 'version': row['version'], 'archived': bool(row['archived']),
        'created_at': row['created_at'], 'updated_at': row['updated_at'], 'updated_by': row['updated_by'],
        'source': SOURCE,
    }


def _create_identity(db, *, name: str, dob: str, nationality: str, gender: str = '', place_of_birth: str = '', aliases=None,
                     identity_status: str = 'ACTIVE', notes: str = '', actor: str, reason: str, explicit_id: str | None = None):
    ident = explicit_id or _id('IDN')
    now = utcnow()
    aliases = aliases or []
    db.execute('''INSERT INTO registry2_identities
      (id,canonical_name,search_name,dob,nationality,gender,place_of_birth,aliases_json,identity_status,notes,version,archived,created_at,updated_at,updated_by)
      VALUES(?,?,?,?,?,?,?,?,?,?,1,0,?,?,?)''',
      (ident, name, local_registry.normalized_text(name), dob, nationality.upper(), gender, place_of_birth,
       json.dumps(aliases, ensure_ascii=False), identity_status, notes, now, now, actor))
    saved = _serialize_identity(_identity_row(db, ident))
    _event(db, 'IDENTITY', ident, 'CREATE', actor, reason, saved)
    return saved


def _link_document(db, identity_id: str, record_id: str, actor: str, reason: str, relationship: str = 'PRIMARY'):
    if not _identity_row(db, identity_id):
        raise HTTPException(404, 'Registry 2.0 identity not found.')
    if not db.execute('SELECT id FROM registry_records WHERE id=?', (record_id,)).fetchone():
        raise HTTPException(404, 'Legacy registry document record not found.')
    current = db.execute('SELECT identity_id FROM registry2_document_links WHERE record_id=?', (record_id,)).fetchone()
    if current:
        if current['identity_id'] == identity_id:
            return False
        raise HTTPException(409, 'This document is already linked to another Registry 2.0 identity.')
    db.execute('INSERT INTO registry2_document_links VALUES(?,?,?,?,?,?)', (record_id, identity_id, relationship, utcnow(), actor, reason))
    _event(db, 'DOCUMENT_LINK', record_id, 'LINK', actor, reason, {'record_id': record_id, 'identity_id': identity_id, 'relationship': relationship})
    return True


def _backfill_existing(db):
    rows = db.execute('SELECT * FROM registry_records ORDER BY created_at,id').fetchall()
    for row in rows:
        if db.execute('SELECT 1 FROM registry2_document_links WHERE record_id=?', (row['id'],)).fetchone():
            continue
        record = local_registry.serialize(row)
        key = (local_registry.normalized_text(record.get('name')), record.get('dob', ''), record.get('nationality', ''))
        match = db.execute('SELECT * FROM registry2_identities WHERE search_name=? AND dob=? AND nationality=? AND archived=0 ORDER BY created_at LIMIT 1', key).fetchone()
        if match:
            ident = match['id']
        else:
            ident = _create_identity(
                db, name=record.get('name') or 'UNKNOWN SYNTHETIC IDENTITY', dob=record.get('dob') or '1900-01-01',
                nationality=(record.get('nationality') or 'UNK')[:3], gender=record.get('gender') or '',
                actor='SYSTEM_MIGRATION', reason='Automatic Registry 2.0 linkage of an existing synthetic document record.'
            )['id']
        _link_document(db, ident, row['id'], 'SYSTEM_MIGRATION', 'Automatic Registry 2.0 linkage of an existing synthetic document record.')


def sync_document_record(db, record: dict, actor: str, reason: str) -> str | None:
    """Immediately attach a newly-created legacy document record to Registry 2.0.

    Called from local_registry after its document/history write.  If the relational
    tables are not initialized yet, it is a no-op; normal v6.5 startup initializes
    them before user writes are possible.
    """
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if 'registry2_identities' not in tables or 'registry2_document_links' not in tables:
        return None
    existing=db.execute('SELECT identity_id FROM registry2_document_links WHERE record_id=?',(record.get('id'),)).fetchone()
    if existing:return existing['identity_id']
    key=(local_registry.normalized_text(record.get('name')),record.get('dob',''),record.get('nationality',''))
    match=db.execute('SELECT * FROM registry2_identities WHERE search_name=? AND dob=? AND nationality=? AND archived=0 ORDER BY created_at LIMIT 1',key).fetchone()
    ident=match['id'] if match else _create_identity(db,name=record.get('name') or 'UNKNOWN SYNTHETIC IDENTITY',dob=record.get('dob') or '1900-01-01',nationality=(record.get('nationality') or 'UNK')[:3],gender=record.get('gender') or '',actor=actor,reason='Registry 2.0 identity profile created with a new synthetic document record.')['id']
    _link_document(db,ident,record['id'],actor,reason,'PRIMARY')
    return ident


def ensure_link_for_record(record_id: str) -> str | None:
    with local_registry.connection() as db:
        row = db.execute('SELECT identity_id FROM registry2_document_links WHERE record_id=?', (record_id,)).fetchone()
        if row:
            return row['identity_id']
        record_row = db.execute('SELECT * FROM registry_records WHERE id=?', (record_id,)).fetchone()
        if not record_row:
            return None
        record = local_registry.serialize(record_row)
        key = (local_registry.normalized_text(record.get('name')), record.get('dob', ''), record.get('nationality', ''))
        match = db.execute('SELECT * FROM registry2_identities WHERE search_name=? AND dob=? AND nationality=? AND archived=0 ORDER BY created_at LIMIT 1', key).fetchone()
        ident = match['id'] if match else _create_identity(
            db, name=record.get('name') or 'UNKNOWN SYNTHETIC IDENTITY', dob=record.get('dob') or '1900-01-01',
            nationality=(record.get('nationality') or 'UNK')[:3], gender=record.get('gender') or '', actor='SYSTEM_AUTO_LINK',
            reason='Registry 2.0 created a local identity link for a matched synthetic document.'
        )['id']
        _link_document(db, ident, record_id, 'SYSTEM_AUTO_LINK', 'Registry 2.0 linked a matched synthetic document to its identity graph.')
        return ident


def identity_detail(db, identity_id: str) -> dict | None:
    row = _identity_row(db, identity_id)
    if not row:
        return None
    identity = _serialize_identity(row)
    docs = []
    for link in db.execute('SELECT * FROM registry2_document_links WHERE identity_id=? ORDER BY linked_at', (identity_id,)).fetchall():
        rec = db.execute('SELECT * FROM registry_records WHERE id=?', (link['record_id'],)).fetchone()
        if rec:
            d = local_registry.serialize(rec)
            docs.append({**d, 'relationship': link['relationship'], 'linked_at': link['linked_at']})
    alerts = [dict(r) for r in db.execute('SELECT * FROM registry2_alerts WHERE identity_id=? ORDER BY created_at DESC', (identity_id,)).fetchall()]
    travel = [dict(r) for r in db.execute('SELECT * FROM registry2_travel_events WHERE identity_id=? ORDER BY event_date DESC,created_at DESC', (identity_id,)).fetchall()]
    relations = [dict(r) for r in db.execute('''SELECT * FROM registry2_document_relations
       WHERE from_record_id IN (SELECT record_id FROM registry2_document_links WHERE identity_id=?)
          OR to_record_id IN (SELECT record_id FROM registry2_document_links WHERE identity_id=?) ORDER BY created_at DESC''', (identity_id, identity_id)).fetchall()]
    biometrics = [dict(r) for r in db.execute('SELECT * FROM registry2_biometric_refs WHERE identity_id=? ORDER BY created_at DESC', (identity_id,)).fetchall()]
    return {'schema_version': '2.2', 'source': SOURCE, 'identity': identity, 'documents': docs, 'travel_events': travel,
            'alerts': alerts, 'document_relations': relations, 'biometric_references': biometrics}


def enrich_reference(result: dict) -> dict:
    """Attach a saved Registry 2.0 graph snapshot to a normal document comparison."""
    result = dict(result)
    result.setdefault('findings', [])
    record = result.get('record') or {}
    record_id = record.get('id')
    if not record_id:
        result['registry2'] = {'schema_version': '2.2', 'source': SOURCE, 'status': 'NOT_LINKED', 'requires_review': False,
                               'escalation_required': False, 'message': 'No exact document reference was selected, so no Registry 2.0 identity graph was attached.'}
        return result
    try:
        identity_id = ensure_link_for_record(record_id)
        with local_registry.connection() as db:
            detail = identity_detail(db, identity_id) if identity_id else None
            templates = []
            if detail:
                templates = [dict(r) for r in db.execute('''SELECT * FROM registry2_issuer_templates
                    WHERE document_type=? AND issuer_country=? AND active=1 ORDER BY valid_from DESC,template_version DESC LIMIT 5''',
                    (record.get('document_type',''), record.get('issuer_country',''))).fetchall()]
    except sqlite3.Error:
        result['registry2'] = {'schema_version': '2.2', 'source': SOURCE, 'status': 'UNAVAILABLE', 'requires_review': False,
                               'escalation_required': False, 'message': 'Registry 2.0 relational evidence is unavailable.'}
        return result
    if not detail:
        result['registry2'] = {'schema_version': '2.2', 'source': SOURCE, 'status': 'NOT_LINKED', 'requires_review': False,
                               'escalation_required': False, 'message': 'Document matched the legacy reference but has no Registry 2.0 identity link.'}
        return result
    open_alerts = [a for a in detail['alerts'] if a['status'] == 'OPEN']
    relevant_alerts = [a for a in open_alerts if not a.get('document_record_id') or a.get('document_record_id') == record_id]
    requires_review = any(a['severity'] in {'REVIEW','HIGH','CRITICAL'} for a in relevant_alerts)
    escalation = any(a['severity'] == 'CRITICAL' or a['alert_type'] in {'DOCUMENT_BLOCKED','DOCUMENT_REVOKED','LOST_STOLEN_DOCUMENT'} for a in relevant_alerts)
    for a in relevant_alerts:
        if a['severity'] == 'INFO':
            sev = 'INFO'
        elif a['severity'] == 'REVIEW':
            sev = 'MEDIUM'
        else:
            sev = 'HIGH'
        result['findings'].append({'code': 'REGISTRY2_ALERT_' + a['alert_type'], 'severity': sev,
                                   'status': 'REVIEW_REQUIRED' if a['severity'] != 'INFO' else 'OBSERVATION',
                                   'message': 'Synthetic Registry 2.0 alert: ' + a['reason'] + ' Source: ' + a['source'] + '.'})
    result['registry2'] = {
        'schema_version': '2.2', 'source': SOURCE, 'status': 'REVIEW_REQUIRED' if requires_review else 'LINKED',
        'requires_review': requires_review, 'escalation_required': escalation,
        'identity': detail['identity'],
        'linked_documents': [{k: d.get(k) for k in ('id','document_type','document_number','issuer_country','status','issue_date','valid_from','expiry','visa_type','number_of_entries','duration_of_stay','passport_reference','issuing_authority','relationship','version')} for d in detail['documents']],
        'travel_events': [{k: e.get(k) for k in ('id','event_type','country_code','port','event_date','authority','stamp_reference','source')} for e in detail['travel_events'][:20]],
        'alerts': [{k: a.get(k) for k in ('id','alert_type','severity','status','reason','source','document_record_id','created_at')} for a in open_alerts[:20]],
        'document_relations': detail['document_relations'][:20],
        'biometric_references': detail['biometric_references'][:10],
        'issuer_templates': templates,
        'message': f"Linked to synthetic identity {detail['identity']['id']} with {len(detail['documents'])} document(s), {len(detail['travel_events'])} travel/stamp event(s) and {len(open_alerts)} open alert(s).",
        'limitation': 'Synthetic local relational data only. No government, immigration, issuer or watchlist system is connected.'
    }
    return result


class IdentityInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    canonical_name: str = Field(min_length=2, max_length=180)
    dob: str = Field(min_length=8, max_length=40)
    nationality: str = Field(min_length=3, max_length=3)
    gender: Literal['','M','F','X'] = ''
    place_of_birth: str = Field(default='', max_length=180)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    identity_status: Literal['ACTIVE','RESTRICTED','ARCHIVED'] = 'ACTIVE'
    notes: str = Field(default='', max_length=1000)

    @field_validator('dob')
    @classmethod
    def valid_dob(cls, value):
        parsed = local_registry.normalized_date(value)
        if not parsed or parsed > date.today().isoformat():
            raise ValueError('Enter a valid non-future date of birth.')
        return parsed

    @field_validator('nationality')
    @classmethod
    def code(cls, value):
        return value.upper()


class IdentityCreate(BaseModel):
    identity: IdentityInput
    reason: str = Field(min_length=10, max_length=500)


class IdentityUpdate(IdentityCreate):
    expected_version: int = Field(ge=1)


class LinkDocumentInput(BaseModel):
    record_id: str = Field(min_length=5, max_length=80)
    relationship: Literal['PRIMARY','LINKED','PREVIOUS','REPLACEMENT'] = 'LINKED'
    reason: str = Field(min_length=10, max_length=500)


class RelationInput(BaseModel):
    from_record_id: str = Field(min_length=5, max_length=80)
    to_record_id: str = Field(min_length=5, max_length=80)
    relation_type: Literal['VISA_REFERENCES_PASSPORT','REISSUES','REPLACES','RELATED_DOCUMENT']
    notes: str = Field(default='', max_length=500)
    reason: str = Field(min_length=10, max_length=500)


class TravelEventInput(BaseModel):
    event_type: Literal['ENTRY','EXIT','VISA_ISSUED','STAMP_OBSERVED']
    country_code: str = Field(default='', max_length=3)
    port: str = Field(default='', max_length=180)
    event_date: str = Field(min_length=8, max_length=40)
    authority: str = Field(default='', max_length=180)
    document_record_id: str = Field(default='', max_length=80)
    stamp_reference: str = Field(default='', max_length=180)
    notes: str = Field(default='', max_length=1000)
    source: str = Field(default='SYNTHETIC_DEMO', max_length=120)
    reason: str = Field(min_length=10, max_length=500)

    @field_validator('event_date')
    @classmethod
    def event_date_valid(cls, value):
        parsed = local_registry.normalized_date(value)
        if not parsed:
            raise ValueError('Enter a valid event date.')
        return parsed


class AlertInput(BaseModel):
    alert_type: Literal['INFORMATION','WATCHLIST_REVIEW','LOST_STOLEN_DOCUMENT','DUPLICATE_IDENTITY','IDENTITY_REVIEW','DOCUMENT_REVOKED','DOCUMENT_BLOCKED']
    severity: Literal['INFO','REVIEW','HIGH','CRITICAL'] = 'REVIEW'
    reason: str = Field(min_length=10, max_length=1000)
    document_record_id: str = Field(default='', max_length=80)
    source: str = Field(default='SYNTHETIC_DEMO', max_length=120)


class ResolveAlertInput(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


class IssuerTemplateInput(BaseModel):
    document_type: str = Field(min_length=1, max_length=60)
    issuer_country: str = Field(min_length=3, max_length=3)
    issuer_name: str = Field(min_length=2, max_length=180)
    template_version: str = Field(min_length=1, max_length=80)
    valid_from: str = Field(default='', max_length=40)
    valid_to: str = Field(default='', max_length=40)
    active: bool = True
    expected_zones: list[str] = Field(default_factory=list, max_length=40)
    notes: str = Field(default='', max_length=1000)
    reason: str = Field(min_length=10, max_length=500)


class BiometricRefInput(BaseModel):
    screening_id: str = Field(min_length=4, max_length=80)
    template_sha256: str = Field(min_length=64, max_length=64)
    model_ref: str = Field(default='SFace', max_length=180)
    liveness_status: str = Field(default='PASSED_ACTIVE_CHALLENGE', max_length=80)
    reason: str = Field(min_length=10, max_length=500)


def _create_demo_document(db, payload: dict, actor: str):
    model = local_registry.RegistryRecordInput(**payload)
    found = db.execute('SELECT * FROM registry_records WHERE document_type=? AND issuer_country=? AND document_number=?',
                       (model.document_type, model.issuer_country, model.document_number)).fetchone()
    if found:
        return local_registry.serialize(found), False
    return local_registry.create_in_transaction(db, model, actor, 'Registry 2.0 loaded a bundled fictional linked-document demonstration record.'), True


def issuer_template_profile(document_type: str, issuer_country: str, issuer_name: str = '', issue_date: str = ''):
    """Return one active local synthetic template plus versioned visual features.

    This never queries an external issuer. The profile is only a bundled demo reference.
    """
    country=(issuer_country or '').strip().upper()
    if not document_type or len(country)!=3:
        return None
    with local_registry.connection() as db:
        rows=db.execute("""SELECT * FROM registry2_issuer_templates
            WHERE document_type=? AND issuer_country=? AND active=1
            ORDER BY valid_from DESC, template_version DESC""",(document_type,country)).fetchall()
        if not rows:
            return None
        normalized_issuer=local_registry.normalized_text(issuer_name)
        candidates=[]
        for row in rows:
            if issue_date:
                start=row['valid_from'] or '' ; end=row['valid_to'] or ''
                if start and issue_date < start: continue
                if end and issue_date > end: continue
            exact = bool(normalized_issuer and local_registry.normalized_text(row['issuer_name'])==normalized_issuer)
            candidates.append((1 if exact else 0,row))
        if not candidates:
            return None
        candidates.sort(key=lambda x:(x[0],x[1]['valid_from'] or '',x[1]['template_version']),reverse=True)
        row=candidates[0][1]
        features=db.execute('SELECT * FROM registry2_template_features WHERE template_id=? ORDER BY feature_code',(row['id'],)).fetchall()
        serialized=[]
        for f in features:
            item=dict(f);item['expected_box']=_json(item.pop('expected_box_json'),[]);item['required']=bool(item['required']);item['critical']=bool(item['critical'])
            serialized.append(item)
        return {'reference_class':'SYNTHETIC_DEMO_TEMPLATE','source':SOURCE,'template':{**dict(row),'active':bool(row['active']),'expected_zones':_json(row['expected_zones_json'],[])},'visual_features':serialized,
                'external_connections':False,'limitation':'Bundled synthetic issuer/template reference only; not an official government or issuer template database.'}


def seed_visual_demo(db, actor: str):
    """Load one fictional passport plus hash-bound visual reference features for v6.6."""
    seed_demo(db,actor)  # ensures IND-P-DEMO-2026 exists; idempotent.
    created={'identities':0,'documents':0,'template_features':0}
    identity_id='IDN-DEMO66-TEMPLATE'
    if not _identity_row(db,identity_id):
        _create_identity(db,explicit_id=identity_id,name='ANAYA TEMPLATE DEMO',dob='1998-04-14',nationality='IND',gender='F',
                         actor=actor,reason='Load bundled v6.6 visual-template demonstration identity.',notes='Fictional SIH visual-security template demonstration.')
        created['identities']+=1
    payload={'document_type':'Passport','document_number':'DEMOIND66001','name':'ANAYA TEMPLATE DEMO','dob':'1998-04-14','nationality':'IND','issuer_country':'IND','gender':'F','issue_date':'2026-08-01','expiry':'2036-07-31','issuing_authority':'DEMO PASSPORT AUTHORITY','passport_reference':'','visa_type':'','number_of_entries':'','valid_from':'','duration_of_stay':'','status':'ACTIVE'}
    rec,made=_create_demo_document(db,payload,actor);created['documents']+=int(made)
    if not db.execute('SELECT 1 FROM registry2_document_links WHERE record_id=?',(rec['id'],)).fetchone():
        _link_document(db,identity_id,rec['id'],actor,'v6.6 visual-template demo linked this fictional passport to its identity.','PRIMARY')
    template=db.execute("SELECT * FROM registry2_issuer_templates WHERE document_type='Passport' AND issuer_country='IND' AND template_version='IND-P-DEMO-2026'").fetchone()
    if not template:
        raise RuntimeError('Synthetic IND passport template missing after demo seed.')
    refroot=Path(__file__).resolve().parents[1]/'reference_templates'
    features=[
      ('EMBLEM','Synthetic issuer emblem',[0.04,0.0605,0.15,0.2368],'v66/ind_passport_emblem.png',1,1,0.46),
      ('HEADER_BAND','Synthetic passport header',[0.31,0.05,0.35,0.1263],'v66/ind_passport_header.png',1,0,0.44),
      ('SECURITY_ROSETTE','Synthetic security rosette',[0.795,0.0632,0.1417,0.1711],'v66/ind_passport_rosette.png',1,0,0.43),
    ]
    for code,label,box,asset,required,critical,min_score in features:
        path=refroot/asset
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        existing=db.execute('SELECT id FROM registry2_template_features WHERE template_id=? AND feature_code=?',(template['id'],code)).fetchone()
        if existing: continue
        fid=_id('FTF')
        db.execute('INSERT INTO registry2_template_features VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (fid,template['id'],code,label,json.dumps(box),asset,digest,required,critical,min_score,'ORB_EDGE_ZONE_V1','Bundled fictional visual reference feature for v6.6 demonstration.',utcnow(),actor))
        created['template_features']+=1
        _event(db,'TEMPLATE_FEATURE',fid,'CREATE',actor,'Load bundled v6.6 synthetic visual-template feature.',{'template_id':template['id'],'feature_code':code,'expected_box':box,'reference_sha256':digest,'reference_asset':asset})
    return {'created':created,'identity_id':identity_id,'document_record_id':rec['id'],'template_id':template['id'],'source':SOURCE,'reference_class':'SYNTHETIC_DEMO_TEMPLATE'}

def seed_travel_demo_v67(db, actor: str):
    """Load fictional travel/visa histories for SIH26188 consistency demonstrations."""
    created = {'identities': 0, 'documents': 0, 'travel_events': 0, 'document_relations': 0}
    cases = [
        {
            'identity_id': 'IDN-DEMO67-ENTRYLIMIT', 'name': 'KAVYA TRAVEL DEMO', 'dob': '1997-03-12', 'nationality': 'GBR', 'gender': 'F',
            'passport': {'document_type':'Passport','document_number':'DEMOGB67001','name':'KAVYA TRAVEL DEMO','dob':'1997-03-12','nationality':'GBR','issuer_country':'GBR','gender':'F','issue_date':'2024-03-12','expiry':'2034-03-11','issuing_authority':'DEMO PASSPORT AUTHORITY','passport_reference':'','visa_type':'','number_of_entries':'','valid_from':'','duration_of_stay':'','status':'ACTIVE'},
            'visa': {'document_type':'Visa','document_number':'DEMOVISA6701','name':'KAVYA TRAVEL DEMO','dob':'1997-03-12','nationality':'GBR','issuer_country':'IND','gender':'F','issue_date':'2026-05-01','expiry':'2026-12-31','issuing_authority':'DEMO VISA AUTHORITY','passport_reference':'DEMOGB67001','visa_type':'TOURIST','number_of_entries':'SINGLE','valid_from':'2026-05-10','duration_of_stay':'30 DAYS','status':'ACTIVE'},
            'events': [
                ('VISA_ISSUED','IND','DEMO VISA CENTRE','2026-05-01','DEMO VISA AUTHORITY','V67-VISA-ISSUE-1'),
                ('ENTRY','IND','DEMO DEL PORT','2026-06-01','DEMO IMMIGRATION','V67-ENTRY-1'),
                ('EXIT','IND','DEMO DEL PORT','2026-06-10','DEMO IMMIGRATION','V67-EXIT-1'),
                ('ENTRY','IND','DEMO BOM PORT','2026-08-01','DEMO IMMIGRATION','V67-ENTRY-2'),
                ('EXIT','IND','DEMO BOM PORT','2026-08-08','DEMO IMMIGRATION','V67-EXIT-2'),
            ],
        },
        {
            'identity_id': 'IDN-DEMO67-DURATION', 'name': 'OMAR STAY DEMO', 'dob': '1994-11-08', 'nationality': 'USA', 'gender': 'M',
            'passport': {'document_type':'Passport','document_number':'DEMOUS67002','name':'OMAR STAY DEMO','dob':'1994-11-08','nationality':'USA','issuer_country':'USA','gender':'M','issue_date':'2023-11-08','expiry':'2033-11-07','issuing_authority':'DEMO PASSPORT AUTHORITY','passport_reference':'','visa_type':'','number_of_entries':'','valid_from':'','duration_of_stay':'','status':'ACTIVE'},
            'visa': {'document_type':'Visa','document_number':'DEMOVISA6702','name':'OMAR STAY DEMO','dob':'1994-11-08','nationality':'USA','issuer_country':'IND','gender':'M','issue_date':'2026-06-01','expiry':'2026-11-30','issuing_authority':'DEMO VISA AUTHORITY','passport_reference':'DEMOUS67002','visa_type':'BUSINESS','number_of_entries':'MULTIPLE','valid_from':'2026-06-10','duration_of_stay':'7 DAYS','status':'ACTIVE'},
            'events': [
                ('VISA_ISSUED','IND','DEMO VISA CENTRE','2026-06-01','DEMO VISA AUTHORITY','V67-VISA-ISSUE-2'),
                ('ENTRY','IND','DEMO DEL PORT','2026-07-01','DEMO IMMIGRATION','V67-STAY-ENTRY'),
                ('EXIT','IND','DEMO DEL PORT','2026-07-20','DEMO IMMIGRATION','V67-STAY-EXIT'),
            ],
        },
    ]
    for case in cases:
        identity_id = case['identity_id']
        if not _identity_row(db, identity_id):
            _create_identity(db, explicit_id=identity_id, name=case['name'], dob=case['dob'], nationality=case['nationality'], gender=case['gender'],
                             actor=actor, reason='Load bundled v6.7 synthetic travel-intelligence identity.', notes='Fictional SIH26188 travel/visa consistency demonstration identity.')
            created['identities'] += 1
        saved_docs = {}
        for relationship, payload in [('PRIMARY',case['passport']),('LINKED',case['visa'])]:
            rec, made = _create_demo_document(db, payload, actor); created['documents'] += int(made); saved_docs[payload['document_type']] = rec
            if not db.execute('SELECT 1 FROM registry2_document_links WHERE record_id=?',(rec['id'],)).fetchone():
                _link_document(db, identity_id, rec['id'], actor, 'v6.7 synthetic travel-intelligence demo linked document.', relationship)
        visa=saved_docs['Visa'];passport=saved_docs['Passport']
        if not db.execute('SELECT 1 FROM registry2_document_relations WHERE from_record_id=? AND to_record_id=? AND relation_type=?',(visa['id'],passport['id'],'VISA_REFERENCES_PASSPORT')).fetchone():
            rid=_id('REL');db.execute('INSERT INTO registry2_document_relations VALUES(?,?,?,?,?,?,?)',(rid,visa['id'],passport['id'],'VISA_REFERENCES_PASSPORT','v6.7 synthetic visa-passport relationship.',utcnow(),actor));created['document_relations']+=1
            _event(db,'DOCUMENT_RELATION',rid,'CREATE',actor,'Load bundled v6.7 synthetic visa-passport linkage.',{'from_record_id':visa['id'],'to_record_id':passport['id'],'relation_type':'VISA_REFERENCES_PASSPORT'})
        for event_type,country,port,event_date,authority,stamp in case['events']:
            document_record_id = visa['id'] if event_type=='VISA_ISSUED' else passport['id']
            if db.execute('SELECT 1 FROM registry2_travel_events WHERE identity_id=? AND event_type=? AND event_date=? AND stamp_reference=?',(identity_id,event_type,event_date,stamp)).fetchone():
                continue
            eid=_id('TRV');db.execute('INSERT INTO registry2_travel_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(eid,identity_id,document_record_id,event_type,country,port,event_date,authority,stamp,'Bundled v6.7 fictional travel event.','SYNTHETIC_DEMO',utcnow(),actor));created['travel_events']+=1
            _event(db,'TRAVEL_EVENT',eid,'CREATE',actor,'Load bundled v6.7 synthetic travel/immigration history.',{'identity_id':identity_id,'event_type':event_type,'event_date':event_date,'document_record_id':document_record_id,'stamp_reference':stamp})
    return {'created': created, 'identity_ids': [x['identity_id'] for x in cases], 'source': SOURCE, 'reference_class': 'SYNTHETIC_TRAVEL_HISTORY'}


def seed_demo(db, actor: str):
    created = {'identities': 0, 'documents': 0, 'travel_events': 0, 'alerts': 0, 'issuer_templates': 0}
    clean_id = 'IDN-DEMO65-CLEAN'
    review_id = 'IDN-DEMO65-REVIEW'
    if not _identity_row(db, clean_id):
        _create_identity(db, explicit_id=clean_id, name='MAYA REGISTRY DEMO', dob='1996-06-18', nationality='USA', gender='F',
                         place_of_birth='DEMO CITY', aliases=['MAYA DEMO'], actor=actor,
                         reason='Load bundled Registry 2.0 clean linked-identity demonstration.', notes='Fictional SIH demonstration identity.')
        created['identities'] += 1
    if not _identity_row(db, review_id):
        _create_identity(db, explicit_id=review_id, name='ARJUN REGISTRY DEMO', dob='1995-02-11', nationality='IND', gender='M',
                         actor=actor, reason='Load bundled Registry 2.0 alert demonstration.', notes='Fictional SIH review-path identity.')
        created['identities'] += 1
    docs = [
      (clean_id, {'document_type':'Passport','document_number':'DEMOUS26001','name':'MAYA REGISTRY DEMO','dob':'1996-06-18','nationality':'USA','issuer_country':'USA','gender':'F','issue_date':'2024-06-18','expiry':'2034-06-17','issuing_authority':'DEMO PASSPORT AUTHORITY','passport_reference':'','visa_type':'','number_of_entries':'','valid_from':'','duration_of_stay':'','status':'ACTIVE'}),
      (clean_id, {'document_type':'Visa','document_number':'DEMOVISA2601','name':'MAYA REGISTRY DEMO','dob':'1996-06-18','nationality':'USA','issuer_country':'IND','gender':'F','issue_date':'2026-07-20','expiry':'2027-03-31','issuing_authority':'DEMO VISA AUTHORITY','passport_reference':'DEMOUS26001','visa_type':'TOURIST','number_of_entries':'MULTIPLE','valid_from':'2026-08-01','duration_of_stay':'30 DAYS','status':'ACTIVE'}),
      (clean_id, {'document_type':'Travel Authorization','document_number':'DEMOAUTH2601','name':'MAYA REGISTRY DEMO','dob':'1996-06-18','nationality':'USA','issuer_country':'IND','gender':'F','issue_date':'2026-07-25','expiry':'2027-03-31','issuing_authority':'DEMO TRAVEL AUTHORITY','passport_reference':'DEMOUS26001','visa_type':'','number_of_entries':'','valid_from':'','duration_of_stay':'','status':'ACTIVE'}),
      (review_id, {'document_type':'Passport','document_number':'DEMOIND26002','name':'ARJUN REGISTRY DEMO','dob':'1995-02-11','nationality':'IND','issuer_country':'IND','gender':'M','issue_date':'2025-02-11','expiry':'2035-02-10','issuing_authority':'DEMO PASSPORT AUTHORITY','passport_reference':'','visa_type':'','number_of_entries':'','valid_from':'','duration_of_stay':'','status':'ACTIVE'}),
    ]
    doc_by_number = {}
    for identity_id, payload in docs:
        rec, made = _create_demo_document(db, payload, actor); created['documents'] += int(made); doc_by_number[rec['document_number']] = rec
        if not db.execute('SELECT 1 FROM registry2_document_links WHERE record_id=?', (rec['id'],)).fetchone():
            _link_document(db, identity_id, rec['id'], actor, 'Registry 2.0 demo linked this fictional document to its identity graph.','PRIMARY' if payload['document_type']=='Passport' else 'LINKED')
    # Explicit visa -> passport relation.
    visa = doc_by_number['DEMOVISA2601']; passport = doc_by_number['DEMOUS26001']
    if not db.execute('SELECT 1 FROM registry2_document_relations WHERE from_record_id=? AND to_record_id=? AND relation_type=?', (visa['id'],passport['id'],'VISA_REFERENCES_PASSPORT')).fetchone():
        rid = _id('REL'); db.execute('INSERT INTO registry2_document_relations VALUES(?,?,?,?,?,?,?)', (rid,visa['id'],passport['id'],'VISA_REFERENCES_PASSPORT','Visa passport-reference relationship.',utcnow(),actor))
        _event(db,'DOCUMENT_RELATION',rid,'CREATE',actor,'Registry 2.0 demo created visa-to-passport linkage.',{'from_record_id':visa['id'],'to_record_id':passport['id'],'relation_type':'VISA_REFERENCES_PASSPORT'})
    demo_events = [
      (clean_id,visa['id'],'VISA_ISSUED','IND','DEMO VISA CENTRE','2026-07-20','DEMO VISA AUTHORITY','VISA-STAMP-2601'),
      (clean_id,passport['id'],'ENTRY','IND','DEMO DEL PORT','2026-08-15','DEMO IMMIGRATION','ENTRY-260815'),
      (clean_id,passport['id'],'EXIT','IND','DEMO DEL PORT','2026-09-01','DEMO IMMIGRATION','EXIT-260901'),
    ]
    for ident,record_id,event_type,country,port,event_date,authority,stamp in demo_events:
        if not db.execute('SELECT 1 FROM registry2_travel_events WHERE identity_id=? AND event_type=? AND event_date=? AND stamp_reference=?',(ident,event_type,event_date,stamp)).fetchone():
            eid=_id('TRV');db.execute('INSERT INTO registry2_travel_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(eid,ident,record_id,event_type,country,port,event_date,authority,stamp,'Bundled fictional travel/stamp event.','SYNTHETIC_DEMO',utcnow(),actor));created['travel_events']+=1
            _event(db,'TRAVEL_EVENT',eid,'CREATE',actor,'Registry 2.0 demo loaded fictional travel/stamp history.',{'identity_id':ident,'event_type':event_type,'event_date':event_date,'document_record_id':record_id})
    review_doc=doc_by_number['DEMOIND26002']
    if not db.execute("SELECT 1 FROM registry2_alerts WHERE identity_id=? AND document_record_id=? AND alert_type='LOST_STOLEN_DOCUMENT' AND status='OPEN'",(review_id,review_doc['id'])).fetchone():
        aid=_id('ALT');db.execute('INSERT INTO registry2_alerts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(aid,review_id,review_doc['id'],'LOST_STOLEN_DOCUMENT','CRITICAL','OPEN','Fictional document reported lost/stolen for SIH demonstration.','SYNTHETIC_DEMO',utcnow(),actor,'',''));created['alerts']+=1
        _event(db,'ALERT',aid,'CREATE',actor,'Registry 2.0 demo loaded a fictional lost/stolen-document alert.',{'identity_id':review_id,'document_record_id':review_doc['id'],'alert_type':'LOST_STOLEN_DOCUMENT','severity':'CRITICAL'})
    templates=[
      ('Passport','IND','DEMO PASSPORT AUTHORITY','IND-P-DEMO-2026',['PORTRAIT_ZONE','MRZ_ZONE','NAME_ZONE','DOCUMENT_NUMBER_ZONE']),
      ('Visa','IND','DEMO VISA AUTHORITY','IND-V-DEMO-2026',['VISA_NUMBER_ZONE','PHOTO_ZONE','VALIDITY_ZONE','STAMP_ZONE']),
      ('Passport','USA','DEMO PASSPORT AUTHORITY','USA-P-DEMO-2026',['PORTRAIT_ZONE','MRZ_ZONE','NAME_ZONE','DOCUMENT_NUMBER_ZONE']),
    ]
    for doc_type,country,issuer,version,zones in templates:
        if not db.execute('SELECT 1 FROM registry2_issuer_templates WHERE document_type=? AND issuer_country=? AND template_version=?',(doc_type,country,version)).fetchone():
            tid=_id('TPL');db.execute('INSERT INTO registry2_issuer_templates VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(tid,doc_type,country,issuer,version,'2026-01-01','',1,json.dumps(zones), 'Synthetic versioned template metadata for future visual checks.',utcnow(),actor));created['issuer_templates']+=1
            _event(db,'ISSUER_TEMPLATE',tid,'CREATE',actor,'Registry 2.0 demo loaded synthetic issuer/template metadata.',{'document_type':doc_type,'issuer_country':country,'template_version':version,'expected_zones':zones})
    return created


def install(app):
    initialize()

    @app.get('/api/registry2/summary')
    def summary():
        with local_registry.connection() as db:
            counts = {name: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for name, table in {
                'identities':'registry2_identities','document_links':'registry2_document_links','travel_events':'registry2_travel_events',
                'open_alerts':'registry2_alerts','issuer_templates':'registry2_issuer_templates','template_features':'registry2_template_features','biometric_references':'registry2_biometric_refs'}.items()}
            counts['open_alerts'] = db.execute("SELECT count(*) FROM registry2_alerts WHERE status='OPEN'").fetchone()[0]
        return {'schema_version':'2.2','source':SOURCE,'counts':counts,'external_connections':False,
                'message':'Synthetic relational registry only; no government/immigration/watchlist system is connected.'}

    @app.get('/api/registry2/identities')
    def identities(q: str = Query(default='', max_length=100), offset: int = Query(default=0,ge=0), limit: int = Query(default=25,ge=1,le=100)):
        escaped=q.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_');needle='%'+local_registry.normalized_text(q).replace('%','\\%').replace('_','\\_')+'%'
        with local_registry.connection() as db:
            total=db.execute("SELECT count(*) FROM registry2_identities WHERE archived=0 AND (search_name LIKE ? ESCAPE '\\' OR id LIKE ?)",(needle,'%'+escaped+'%')).fetchone()[0]
            rows=db.execute("SELECT * FROM registry2_identities WHERE archived=0 AND (search_name LIKE ? ESCAPE '\\' OR id LIKE ?) ORDER BY updated_at DESC LIMIT ? OFFSET ?",(needle,'%'+escaped+'%',limit,offset)).fetchall()
        return {'source':SOURCE,'total':total,'offset':offset,'limit':limit,'identities':[_serialize_identity(r) for r in rows]}

    @app.get('/api/registry2/identities/{identity_id}')
    def get_identity(identity_id: str):
        with local_registry.connection() as db: result=identity_detail(db,identity_id)
        if not result: raise HTTPException(404,'Registry 2.0 identity not found.')
        return result

    @app.post('/api/registry2/identities', status_code=201)
    def create_identity(body: IdentityCreate, request: Request):
        actor=local_registry.require_supervisor(request);d=body.identity
        with local_registry.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            return _create_identity(db,name=d.canonical_name,dob=d.dob,nationality=d.nationality,gender=d.gender,place_of_birth=d.place_of_birth,aliases=d.aliases,identity_status=d.identity_status,notes=d.notes,actor=actor,reason=body.reason)

    @app.put('/api/registry2/identities/{identity_id}')
    def update_identity(identity_id: str, body: IdentityUpdate, request: Request):
        actor=local_registry.require_supervisor(request);d=body.identity
        with local_registry.connection() as db:
            db.execute('BEGIN IMMEDIATE');row=_identity_row(db,identity_id)
            if not row: raise HTTPException(404,'Registry 2.0 identity not found.')
            if row['version']!=body.expected_version: raise HTTPException(409,'Identity changed after you opened it. Reload the latest version.')
            db.execute('''UPDATE registry2_identities SET canonical_name=?,search_name=?,dob=?,nationality=?,gender=?,place_of_birth=?,aliases_json=?,identity_status=?,notes=?,version=version+1,updated_at=?,updated_by=? WHERE id=?''',
              (d.canonical_name,local_registry.normalized_text(d.canonical_name),d.dob,d.nationality,d.gender,d.place_of_birth,json.dumps(d.aliases,ensure_ascii=False),d.identity_status,d.notes,utcnow(),actor,identity_id))
            saved=_serialize_identity(_identity_row(db,identity_id));_event(db,'IDENTITY',identity_id,'EDIT',actor,body.reason,saved);return saved

    @app.post('/api/registry2/identities/{identity_id}/link-document')
    def link_document(identity_id: str, body: LinkDocumentInput, request: Request):
        actor=local_registry.require_supervisor(request)
        with local_registry.connection() as db:
            db.execute('BEGIN IMMEDIATE');created=_link_document(db,identity_id,body.record_id,actor,body.reason,body.relationship)
        return {'created':created,'identity_id':identity_id,'record_id':body.record_id}

    @app.post('/api/registry2/identities/{identity_id}/document-relations')
    def add_relation(identity_id: str, body: RelationInput, request: Request):
        actor=local_registry.require_supervisor(request)
        with local_registry.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            linked={r[0] for r in db.execute('SELECT record_id FROM registry2_document_links WHERE identity_id=?',(identity_id,)).fetchall()}
            if body.from_record_id not in linked or body.to_record_id not in linked: raise HTTPException(409,'Both document records must be linked to this identity first.')
            ident=_id('REL')
            try: db.execute('INSERT INTO registry2_document_relations VALUES(?,?,?,?,?,?,?)',(ident,body.from_record_id,body.to_record_id,body.relation_type,body.notes,utcnow(),actor))
            except sqlite3.IntegrityError: raise HTTPException(409,'That document relationship already exists.')
            payload={'id':ident,**body.model_dump(exclude={'reason'})};_event(db,'DOCUMENT_RELATION',ident,'CREATE',actor,body.reason,payload);return payload

    @app.post('/api/registry2/identities/{identity_id}/travel-events', status_code=201)
    def add_travel(identity_id: str, body: TravelEventInput, request: Request):
        actor=local_registry.require_supervisor(request)
        with local_registry.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if not _identity_row(db,identity_id): raise HTTPException(404,'Registry 2.0 identity not found.')
            if body.document_record_id and not db.execute('SELECT 1 FROM registry2_document_links WHERE identity_id=? AND record_id=?',(identity_id,body.document_record_id)).fetchone(): raise HTTPException(409,'Travel event document must be linked to this identity.')
            ident=_id('TRV');payload=body.model_dump(exclude={'reason'});db.execute('INSERT INTO registry2_travel_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(ident,identity_id,payload['document_record_id'],payload['event_type'],payload['country_code'].upper(),payload['port'],payload['event_date'],payload['authority'],payload['stamp_reference'],payload['notes'],payload['source'],utcnow(),actor));payload={'id':ident,'identity_id':identity_id,**payload};_event(db,'TRAVEL_EVENT',ident,'CREATE',actor,body.reason,payload);return payload

    @app.post('/api/registry2/identities/{identity_id}/alerts', status_code=201)
    def add_alert(identity_id: str, body: AlertInput, request: Request):
        actor=local_registry.require_supervisor(request)
        with local_registry.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if not _identity_row(db,identity_id): raise HTTPException(404,'Registry 2.0 identity not found.')
            if body.document_record_id and not db.execute('SELECT 1 FROM registry2_document_links WHERE identity_id=? AND record_id=?',(identity_id,body.document_record_id)).fetchone(): raise HTTPException(409,'Alert document must be linked to this identity.')
            ident=_id('ALT');db.execute('INSERT INTO registry2_alerts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(ident,identity_id,body.document_record_id,body.alert_type,body.severity,'OPEN',body.reason,body.source,utcnow(),actor,'',''));payload={'id':ident,'identity_id':identity_id,'status':'OPEN',**body.model_dump()};_event(db,'ALERT',ident,'CREATE',actor,body.reason,payload);return payload

    @app.post('/api/registry2/alerts/{alert_id}/resolve')
    def resolve_alert(alert_id: str, body: ResolveAlertInput, request: Request):
        actor=local_registry.require_supervisor(request)
        with local_registry.connection() as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT * FROM registry2_alerts WHERE id=?',(alert_id,)).fetchone()
            if not row: raise HTTPException(404,'Registry 2.0 alert not found.')
            if row['status']=='CLEARED': return dict(row)
            now=utcnow();db.execute("UPDATE registry2_alerts SET status='CLEARED',resolved_at=?,resolved_by=? WHERE id=?",(now,actor,alert_id));saved=dict(db.execute('SELECT * FROM registry2_alerts WHERE id=?',(alert_id,)).fetchone());_event(db,'ALERT',alert_id,'RESOLVE',actor,body.reason,saved);return saved

    @app.get('/api/registry2/issuer-templates')
    def issuer_templates(document_type: str = '', issuer_country: str = ''):
        where=[];args=[]
        if document_type: where.append('document_type=?');args.append(document_type)
        if issuer_country: where.append('issuer_country=?');args.append(issuer_country.upper())
        sql='SELECT * FROM registry2_issuer_templates'+((' WHERE '+' AND '.join(where)) if where else '')+' ORDER BY document_type,issuer_country,template_version'
        with local_registry.connection() as db: rows=db.execute(sql,args).fetchall()
        return {'source':SOURCE,'templates':[{**dict(r),'active':bool(r['active']),'expected_zones':_json(r['expected_zones_json'],[])} for r in rows]}

    @app.get('/api/registry2/issuer-templates/{template_id}/features')
    def issuer_template_features(template_id: str):
        with local_registry.connection() as db:
            template=db.execute('SELECT * FROM registry2_issuer_templates WHERE id=?',(template_id,)).fetchone()
            if not template: raise HTTPException(404,'Issuer template not found.')
            rows=db.execute('SELECT * FROM registry2_template_features WHERE template_id=? ORDER BY feature_code',(template_id,)).fetchall()
        features=[]
        for r in rows:
            item=dict(r);item['expected_box']=_json(item.pop('expected_box_json'),[]);item['required']=bool(item['required']);item['critical']=bool(item['critical']);features.append(item)
        return {'source':SOURCE,'reference_class':'SYNTHETIC_DEMO_TEMPLATE','template':{**dict(template),'active':bool(template['active']),'expected_zones':_json(template['expected_zones_json'],[])},'features':features,'external_connections':False}

    @app.post('/api/registry2/issuer-templates', status_code=201)
    def add_template(body: IssuerTemplateInput, request: Request):
        actor=local_registry.require_supervisor(request);ident=_id('TPL')
        with local_registry.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try: db.execute('INSERT INTO registry2_issuer_templates VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(ident,body.document_type,body.issuer_country.upper(),body.issuer_name,body.template_version,body.valid_from,body.valid_to,int(body.active),json.dumps(body.expected_zones),body.notes,utcnow(),actor))
            except sqlite3.IntegrityError: raise HTTPException(409,'This document/issuer/template version already exists.')
            payload={'id':ident,**body.model_dump(exclude={'reason'})};_event(db,'ISSUER_TEMPLATE',ident,'CREATE',actor,body.reason,payload);return payload

    @app.post('/api/registry2/identities/{identity_id}/biometric-references', status_code=201)
    def add_biometric_ref(identity_id: str, body: BiometricRefInput, request: Request):
        actor=local_registry.require_supervisor(request);ident=_id('BIO')
        with local_registry.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if not _identity_row(db,identity_id): raise HTTPException(404,'Registry 2.0 identity not found.')
            try: db.execute('INSERT INTO registry2_biometric_refs VALUES(?,?,?,?,?,?,?,?)',(ident,identity_id,body.screening_id,body.template_sha256,body.model_ref,body.liveness_status,utcnow(),actor))
            except sqlite3.IntegrityError: raise HTTPException(409,'This screening is already linked as a biometric reference for the identity.')
            payload={'id':ident,'identity_id':identity_id,**body.model_dump(exclude={'reason'})};_event(db,'BIOMETRIC_REFERENCE',ident,'CREATE',actor,body.reason,payload);return payload

    @app.get('/api/registry2/events')
    def events(request: Request, identity_id: str = '', limit: int = Query(default=100,ge=1,le=500)):
        local_registry.require_supervisor(request)
        with local_registry.connection() as db:
            if identity_id:
                related=[identity_id]+[r[0] for r in db.execute('SELECT record_id FROM registry2_document_links WHERE identity_id=?',(identity_id,)).fetchall()]
                placeholders=','.join('?' for _ in related);rows=db.execute(f'SELECT * FROM registry2_events WHERE entity_id IN ({placeholders}) ORDER BY id DESC LIMIT ?',(*related,limit)).fetchall()
            else: rows=db.execute('SELECT * FROM registry2_events ORDER BY id DESC LIMIT ?',(limit,)).fetchall()
        return {'source':SOURCE,'events':[{**dict(r),'payload':_json(r['payload_json'],{})} for r in rows]}

    @app.post('/api/registry2/demo-seed-travel-v67')
    def demo_seed_travel_v67(request: Request):
        actor=local_registry.require_supervisor(request)
        with local_registry.connection() as db:
            db.execute('BEGIN IMMEDIATE');result=seed_travel_demo_v67(db,actor)
        return {'schema_version':'2.2',**result,'message':'Bundled fictional v6.7 travel/immigration consistency demos loaded. Existing records preserved.'}

    @app.post('/api/registry2/demo-seed-visual-v66')
    def demo_seed_visual_v66(request: Request):
        actor=local_registry.require_supervisor(request)
        with local_registry.connection() as db:
            db.execute('BEGIN IMMEDIATE');result=seed_visual_demo(db,actor)
        return {'schema_version':'2.2',**result,'message':'Bundled fictional v6.6 visual template/reference features loaded. Existing records preserved.'}

    @app.post('/api/registry2/demo-seed')
    def demo_seed(request: Request):
        actor=local_registry.require_supervisor(request)
        with local_registry.connection() as db:
            db.execute('BEGIN IMMEDIATE');created=seed_demo(db,actor)
        return {'source':SOURCE,'schema_version':'2.2','created':created,'message':'Existing synthetic Registry 2.x records were preserved.'}
