"""Local synthetic registry. No government connections and no network clients.

Writes and before/after history are one SQLite transaction. Screening callers
receive a value snapshot, never a mutable reference to a live registry row.
"""
import json
import re
import sqlite3
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from typing import Literal

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .local_security import ROOT

DB = ROOT / 'registry.sqlite3'
SOURCE = 'SYNTHETIC_DEMO_REGISTRY'
DOC_TYPES = ('Passport', 'Visa', 'Aadhaar Card', 'Voter ID (EPIC)', 'Driving Licence',
             'PAN Card', 'National ID', 'Permit', 'Travel Authorization')
DATE_FIELDS = {'dob', 'issue_date', 'expiry', 'valid_from'}
COMPARE_FIELDS = ('document_number', 'name', 'dob', 'nationality', 'issuer_country',
                  'gender', 'issue_date', 'expiry', 'issuing_authority', 'passport_reference')
VISA_COMPARE_FIELDS = ('visa_type', 'number_of_entries', 'valid_from', 'duration_of_stay')
FIELD_LABELS = {'document_number': 'Document number', 'name': 'Full name', 'dob': 'Date of birth',
                'nationality': 'Nationality', 'issuer_country': 'Issuing country', 'gender': 'Gender',
                'issue_date': 'Issue date', 'expiry': 'Expiry date', 'issuing_authority': 'Issuing authority',
                'passport_reference': 'Passport reference', 'visa_type': 'Visa type/class',
                'number_of_entries': 'Number of entries', 'valid_from': 'Valid from', 'duration_of_stay': 'Duration of stay'}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def normalized_number(value):
    return re.sub(r'[\s-]', '', str(value or '')).upper()


def normalized_text(value):
    value = unicodedata.normalize('NFKC', str(value or '')).casefold()
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in value).split())


def normalized_date(value):
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%Y/%m/%d', '%d %b %Y', '%d %B %Y'):
        try:
            return datetime.strptime(str(value).strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def normalized_field(key, value):
    if key in DATE_FIELDS:
        return normalized_date(value)
    if key in {'document_number', 'passport_reference'}:
        return normalized_number(value)
    if key in {'nationality', 'issuer_country'}:
        text = normalized_text(value)
        return {'india': 'ind', 'indian': 'ind', 'united states': 'usa', 'united kingdom': 'gbr'}.get(text, text)
    if key == 'number_of_entries':
        text = normalized_text(value).replace(' ', '')
        return {'single':'1','one':'1','double':'2','two':'2','mult':'multiple','m':'multiple','unlimited':'multiple'}.get(text, text)
    if key == 'gender':
        text = normalized_text(value)
        return {'male': 'm', 'female': 'f', 'other': 'x'}.get(text, text)
    return normalized_text(value)


class RegistryRecordInput(BaseModel):
    requires_signed_qr: bool = False
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    document_type: str = Field(min_length=1, max_length=60)
    document_number: str = Field(min_length=2, max_length=80, pattern=r'^[A-Za-z0-9][A-Za-z0-9 -]+$')
    name: str = Field(min_length=2, max_length=180)
    dob: str = Field(max_length=40)
    nationality: str = Field(pattern=r'^[A-Za-z]{3}$')
    issuer_country: str = Field(pattern=r'^[A-Za-z]{3}$')
    gender: Literal['', 'M', 'F', 'X'] = ''
    issue_date: str = Field(default='', max_length=40)
    expiry: str = Field(default='', max_length=40)
    issuing_authority: str = Field(default='', max_length=180)
    passport_reference: str = Field(default='', max_length=80)
    visa_type: str = Field(default='', max_length=80)
    number_of_entries: str = Field(default='', max_length=30)
    valid_from: str = Field(default='', max_length=40)
    duration_of_stay: str = Field(default='', max_length=80)
    status: Literal['ACTIVE', 'EXPIRED', 'REVOKED', 'BLOCKED'] = 'ACTIVE'

    @field_validator('document_type')
    @classmethod
    def known_type(cls, value):
        if value not in DOC_TYPES:
            raise ValueError('Select a supported document type.')
        return value

    @field_validator('name')
    @classmethod
    def meaningful_name(cls, value):
        if not normalized_text(value):
            raise ValueError('Name must contain letters or digits.')
        return value

    @field_validator('nationality', 'issuer_country')
    @classmethod
    def upper_code(cls, value):
        return value.upper()

    @field_validator('document_number', 'passport_reference')
    @classmethod
    def number_value(cls, value):
        if value and not re.fullmatch(r'[A-Za-z0-9 -]+', value):
            raise ValueError('Document references can contain letters, digits, spaces or hyphens.')
        return normalized_number(value)

    @field_validator('dob', 'issue_date', 'expiry', 'valid_from')
    @classmethod
    def date_value(cls, value, info):
        if not value and info.field_name != 'dob':
            return ''
        parsed = normalized_date(value)
        if not parsed:
            raise ValueError('Enter a valid date, for example 2000-03-14.')
        return parsed

    @model_validator(mode='after')
    def valid_dates(self):
        if self.dob > date.today().isoformat():
            raise ValueError('Date of birth cannot be in the future.')
        if self.issue_date and self.issue_date < self.dob:
            raise ValueError('Issue date cannot precede birth date.')
        if self.issue_date and self.expiry and self.expiry < self.issue_date:
            raise ValueError('Expiry date cannot precede issue date.')
        if self.valid_from and self.expiry and self.expiry < self.valid_from:
            raise ValueError('Visa expiry cannot precede valid-from date.')
        if self.document_type in {'Passport', 'Visa', 'Driving Licence', 'Permit', 'Travel Authorization'} and not self.expiry:
            raise ValueError('This document type needs an expiry date.')
        return self


class CreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    record: RegistryRecordInput
    reason: str = Field(min_length=10, max_length=500, pattern=r'\S')

    @field_validator('reason')
    @classmethod
    def valid_reason(cls, value):
        value = value.strip()
        if len(value) < 10:
            raise ValueError('Provide a reason of at least 10 characters.')
        return value


class UpdateRequest(CreateRequest):
    expected_version: int = Field(ge=1)


class ArchiveRequest(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=10, max_length=500)

    @field_validator('reason')
    @classmethod
    def valid_reason(cls, value):
        return CreateRequest.valid_reason(value)


@contextmanager
def connection():
    db = sqlite3.connect(DB, timeout=5)
    from . import audit_chain
    audit_chain.configure(db)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    with connection() as db:
        db.executescript('''
          CREATE TABLE IF NOT EXISTS registry_records (
            id TEXT PRIMARY KEY, document_type TEXT NOT NULL, issuer_country TEXT NOT NULL,
            document_number TEXT NOT NULL, search_name TEXT NOT NULL, payload TEXT NOT NULL,
            version INTEGER NOT NULL, archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, updated_by TEXT NOT NULL,
            UNIQUE(document_type, issuer_country, document_number));
          CREATE INDEX IF NOT EXISTS registry_number_idx ON registry_records(document_type, document_number);
          CREATE TABLE IF NOT EXISTS registry_history (
            id INTEGER PRIMARY KEY, record_id TEXT NOT NULL, version INTEGER NOT NULL,
            action TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL, timestamp TEXT NOT NULL,
            before_json TEXT, after_json TEXT NOT NULL, UNIQUE(record_id, version));
        ''')
        from . import audit_chain
        audit_chain.initialize(db)


def serialize(row):
    if row is None:
        return None
    return {**json.loads(row['payload']), 'id': row['id'], 'version': row['version'],
            'archived': bool(row['archived']), 'created_at': row['created_at'], 'updated_at': row['updated_at'],
            'updated_by': row['updated_by'], 'source': SOURCE}


def audit(db, record, before, action, actor, reason):
    db.execute('INSERT INTO registry_history(record_id,version,action,actor,reason,timestamp,before_json,after_json) VALUES(?,?,?,?,?,?,?,?)',
               (record['id'], record['version'], action, actor, reason, record['updated_at'],
                json.dumps(before, ensure_ascii=False) if before else None, json.dumps(record, ensure_ascii=False)))


def create_in_transaction(db, record, actor, reason):
    data = record.model_dump()
    ident = 'REG-' + uuid.uuid4().hex[:16].upper()
    now = utcnow()
    db.execute('INSERT INTO registry_records VALUES(?,?,?,?,?,?,1,0,?,?,?)',
               (ident, data['document_type'], data['issuer_country'], data['document_number'],
                normalized_text(data['name']), json.dumps(data, ensure_ascii=False), now, now, actor))
    saved = serialize(db.execute('SELECT * FROM registry_records WHERE id=?', (ident,)).fetchone())
    audit(db, saved, None, 'CREATE', actor, reason)
    # v6.5 keeps the legacy document row as the canonical document reference,
    # then immediately links it into the relational Registry 2.0 identity graph.
    try:
        from . import registry_v2
        registry_v2.sync_document_record(db, saved, actor, reason)
    except (ImportError, sqlite3.OperationalError):
        # During very early bootstrap/legacy tooling the v2 tables may not exist yet;
        # Registry 2.0 startup backfill will link the record later.
        pass
    return saved


def require_supervisor(request):
    if request.state.user['role'] != 'supervisor':
        raise HTTPException(403, 'Only supervisors may manage registry records or view full change history.')
    return request.state.user['username']


def get_current(db, ident, expected_version):
    row = db.execute('SELECT * FROM registry_records WHERE id=?', (ident,)).fetchone()
    if not row:
        raise HTTPException(404, 'Registry record not found.')
    if row['version'] != expected_version:
        raise HTTPException(409, 'This record changed after you opened it. Reload and review the latest version.')
    return row


def demo_records():
    # Deliberately fictional permits, not government identifiers.
    base = {'document_type': 'Permit', 'dob': '2001-03-14', 'nationality': 'IND', 'issuer_country': 'IND',
            'gender': '', 'issue_date': '', 'expiry': '2035-12-31', 'issuing_authority': '',
            'passport_reference': '', 'visa_type':'', 'number_of_entries':'', 'valid_from':'', 'duration_of_stay':'', 'status': 'ACTIVE'}
    return [RegistryRecordInput(**(base | values)) for values in [
        {'document_number': 'DEMO1001', 'name': 'AARAV DEMO'},
        {'document_number': 'DEMO1002', 'name': 'MEERA SAMPLE', 'status': 'REVOKED'},
        {'document_number': 'DEMO1003', 'name': 'KABIR SAMPLE', 'expiry': '2005-01-01', 'status': 'EXPIRED'},
        {'document_number': 'DEMO1004', 'name': 'TARA DEMO', 'status': 'BLOCKED'},
    ]]


def visa_demo_records():
    return [RegistryRecordInput(document_type='Visa',document_number='VISA26001',name='RIYA DEMO',dob='1998-04-12',nationality='IND',issuer_country='IND',gender='F',issue_date='2026-09-20',expiry='2027-03-31',issuing_authority='DEMO VISA AUTHORITY',passport_reference='PDEMO2601',visa_type='TOURIST',number_of_entries='MULTIPLE',valid_from='2026-10-01',duration_of_stay='30 DAYS',status='ACTIVE')]


def install(app):
    initialize()

    @app.get('/api/registry')
    def list_records(q: str = Query(default='', max_length=100), include_archived: bool = False,
                     offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=100)):
        # Bound parameters and literal LIKE escaping keep user text as data.
        escaped = q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        needle = '%' + escaped + '%'
        where = "(archived=0 OR ?) AND (document_number LIKE ? ESCAPE '\\' OR search_name LIKE ? ESCAPE '\\' OR id LIKE ? ESCAPE '\\')"
        name_needle = '%' + normalized_text(q).replace('%', '\\%').replace('_', '\\_') + '%'
        with connection() as db:
            args = (int(include_archived), needle, name_needle, needle)
            total = db.execute('SELECT count(*) FROM registry_records WHERE ' + where, args).fetchone()[0]
            rows = db.execute('SELECT * FROM registry_records WHERE ' + where + ' ORDER BY updated_at DESC,id LIMIT ? OFFSET ?', (*args, limit, offset)).fetchall()
        return {'source': SOURCE, 'total': total, 'records': [serialize(r) for r in rows], 'offset': offset, 'limit': limit}

    @app.post('/api/registry', status_code=201)
    def create_record(body: CreateRequest, request: Request):
        actor = require_supervisor(request)
        try:
            with connection() as db:
                db.execute('BEGIN IMMEDIATE')
                return create_in_transaction(db, body.record, actor, body.reason)
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'A record with this document type, issuing country and number already exists, possibly archived.')

    @app.post('/api/registry/demo-seed')
    def seed_demo(request: Request):
        actor = require_supervisor(request)
        created, skipped = [], []
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for record in demo_records():
                found = db.execute('SELECT id FROM registry_records WHERE document_type=? AND issuer_country=? AND document_number=?',
                                   (record.document_type, record.issuer_country, record.document_number)).fetchone()
                if found:
                    skipped.append(record.document_number)
                    continue
                created.append(create_in_transaction(db, record, actor, 'Supervisor loaded bundled synthetic presentation records.'))
        return {'source': SOURCE, 'created': created, 'skipped': skipped, 'message': 'Existing records were not changed.'}

    @app.get('/api/registry/{ident}')
    def get_record(ident: str):
        with connection() as db:
            result = serialize(db.execute('SELECT * FROM registry_records WHERE id=?', (ident,)).fetchone())
        if result is None:
            raise HTTPException(404, 'Registry record not found.')
        return result

    @app.put('/api/registry/{ident}')
    def update_record(ident: str, body: UpdateRequest, request: Request):
        actor = require_supervisor(request)
        try:
            with connection() as db:
                db.execute('BEGIN IMMEDIATE')
                old = get_current(db, ident, body.expected_version)
                if old['archived']:
                    raise HTTPException(409, 'Restore this archived record before editing it.')
                data = body.record.model_dump()
                db.execute('UPDATE registry_records SET document_type=?,issuer_country=?,document_number=?,search_name=?,payload=?,version=version+1,updated_at=?,updated_by=? WHERE id=?',
                           (data['document_type'], data['issuer_country'], data['document_number'], normalized_text(data['name']), json.dumps(data, ensure_ascii=False), utcnow(), actor, ident))
                saved = serialize(db.execute('SELECT * FROM registry_records WHERE id=?', (ident,)).fetchone())
                audit(db, saved, serialize(old), 'EDIT', actor, body.reason)
                return saved
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'That document key belongs to another registry record.')

    @app.post('/api/registry/{ident}/archive')
    def archive_record(ident: str, body: ArchiveRequest, request: Request, restore: bool = False):
        actor = require_supervisor(request)
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old = get_current(db, ident, body.expected_version)
            db.execute('UPDATE registry_records SET archived=?,version=version+1,updated_at=?,updated_by=? WHERE id=?',
                       (int(not restore), utcnow(), actor, ident))
            saved = serialize(db.execute('SELECT * FROM registry_records WHERE id=?', (ident,)).fetchone())
            audit(db, saved, serialize(old), 'RESTORE' if restore else 'ARCHIVE', actor, body.reason)
            return saved

    @app.post('/api/registry/visa-demo-seed')
    def seed_visa_demo(request: Request):
        actor = require_supervisor(request)
        created=[]; skipped=[]
        with connection() as db:
            for record in visa_demo_records():
                found=db.execute('SELECT id FROM registry_records WHERE document_type=? AND issuer_country=? AND document_number=?',(record.document_type,record.issuer_country,record.document_number)).fetchone()
                if found: skipped.append(record.document_number); continue
                created.append(create_in_transaction(db,record,actor,'Load fictional v6.0 visa intelligence demonstration record.'))
        return {'created':created,'skipped':skipped,'source':SOURCE}

    @app.get('/api/registry/{ident}/history')
    def history(ident: str, request: Request, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
        require_supervisor(request)
        with connection() as db:
            rows = db.execute('SELECT * FROM registry_history WHERE record_id=? ORDER BY version DESC LIMIT ? OFFSET ?', (ident, limit, offset)).fetchall()
            total = db.execute('SELECT count(*) FROM registry_history WHERE record_id=?', (ident,)).fetchone()[0]
        return {'total': total, 'items': [{'version': r['version'], 'action': r['action'], 'actor': r['actor'],
                                         'reason': r['reason'], 'timestamp': r['timestamp'],
                                         'before': json.loads(r['before_json']) if r['before_json'] else None,
                                         'after': json.loads(r['after_json'])} for r in rows]}


def compare(document_type, fields):
    result = {'source': SOURCE, 'checked_at': utcnow(), 'status': 'NOT_CHECKED', 'record': None,
              'fields': [], 'findings': [], 'rule_version': 'registry-v1', 'lookup': {
                  'document_type': document_type, 'document_number': fields.get('document_number', ''),
                  'issuer_country': fields.get('issuer_country', '')}}
    number = normalized_number(fields.get('document_number'))
    if not number:
        result['message'] = 'Document number was not extracted. Review OCR before registry lookup.'
        return result
    try:
        with connection() as db:
            # Read all candidates in one statement. Nationality is not the issuing country.
            rows = db.execute('SELECT * FROM registry_records WHERE document_type=? AND document_number=?', (document_type, number)).fetchall()
    except sqlite3.Error:
        result.update(status='UNAVAILABLE', message='Local registry unavailable. No mismatch or fraud conclusion was made.')
        return result
    issuer = normalized_field('issuer_country', fields.get('issuer_country', ''))
    if issuer:
        rows = [r for r in rows if r['issuer_country'].casefold() == issuer]
    if not rows:
        result.update(status='NOT_FOUND', message='No exact record in the synthetic registry. This does not establish that the document is fake.')
        return result
    if len(rows) > 1:
        result.update(status='AMBIGUOUS', message='This document number exists under multiple issuing countries. Review the issuing country; no record was selected.')
        return result
    record = serialize(rows[0])
    result['record'] = record
    if record['archived']:
        result.update(status='ARCHIVED', message='The matching registry record is archived. Review its status; no authenticity conclusion.')
        return result
    required = {'document_number', 'name', 'dob', 'nationality'}
    if document_type in {'Passport', 'Visa', 'Driving Licence', 'Permit', 'Travel Authorization'}:
        required.add('expiry')
    compare_fields = COMPARE_FIELDS + (VISA_COMPARE_FIELDS if document_type == 'Visa' else ())
    for key in compare_fields:
        observed, expected = str(fields.get(key, '')).strip(), str(record.get(key, '')).strip()
        if not observed and not expected:
            status = 'NOT_APPLICABLE'
        elif not observed:
            status = 'NOT_EXTRACTED' if key in required or key not in {'issuer_country'} else 'NOT_EXTRACTED'
        elif not expected:
            status = 'NOT_IN_REGISTRY'
        else:
            lhs, rhs = normalized_field(key, observed), normalized_field(key, expected)
            if not lhs:
                status = 'INVALID_EXTRACTED_VALUE'
            elif lhs == rhs:
                status = 'EXACT_MATCH' if observed == expected else 'NORMALIZED_MATCH'
            elif key == 'name' and (sorted(lhs.split()) == sorted(rhs.split()) or SequenceMatcher(None, lhs, rhs).ratio() >= 0.85):
                status = 'CLOSE_MATCH'
            else:
                status = 'CONFLICT'
        result['fields'].append({'field': key, 'label': FIELD_LABELS[key], 'uploaded': observed, 'registry': expected, 'status': status})
        if status in {'CONFLICT', 'CLOSE_MATCH', 'INVALID_EXTRACTED_VALUE'}:
            result['findings'].append({'code': 'REGISTRY_' + key.upper() + '_' + status,
                                       'severity': 'HIGH' if status == 'CONFLICT' else 'MEDIUM',
                                       'message': FIELD_LABELS[key] + ': ' + status.lower().replace('_', ' ') + ' against synthetic registry.'})
    statuses = {f['status'] for f in result['fields']}
    if record['status'] in {'BLOCKED', 'REVOKED'}:
        result.update(status=record['status'], message='Synthetic registry status requires escalation for officer review.')
        result['findings'].append({'code': 'REGISTRY_' + record['status'], 'severity': 'HIGH', 'message': result['message']})
    elif record['status'] == 'EXPIRED' or (record['expiry'] and record['expiry'] < date.today().isoformat()):
        result.update(status='EXPIRED', message='The registry record is expired. Manual review required.')
        result['findings'].append({'code': 'REGISTRY_EXPIRED', 'severity': 'HIGH', 'message': result['message']})
    elif 'CONFLICT' in statuses:
        result.update(status='CONFLICT', message='One or more extracted fields conflict with the synthetic registry.')
    elif 'CLOSE_MATCH' in statuses:
        result.update(status='REVIEW_REQUIRED', message='A similar name needs human review. No automatic identity match.')
    elif statuses & {'NOT_EXTRACTED', 'NOT_IN_REGISTRY', 'INVALID_EXTRACTED_VALUE'}:
        result.update(status='PARTIAL', message='Some fields could not be verified. Review missing or unreadable values.')
    else:
        result.update(status='MATCH', message='Compared fields match this synthetic registry record. This is not proof of document authenticity.')
    return result
