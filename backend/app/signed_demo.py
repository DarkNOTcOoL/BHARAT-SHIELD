"""Fixed fictional record IDs allow packaged QR signatures to reference a demo record."""
import json
from . import local_registry as registry
def records():
    base={'document_type':'Permit','dob':'2001-03-14','nationality':'IND','issuer_country':'IND','issue_date':'2024-01-01','expiry':'2035-12-31','requires_signed_qr':True}
    return [base|{'id':'REG-DEMO52-001','version':1,'name':'AARAV DEMO','document_number':'DEMO5201'},base|{'id':'REG-DEMO52-002','version':1,'name':'MEERA SAMPLE','document_number':'DEMO5202'}]
def install(app):
    from fastapi import Request
    @app.post('/api/signed-demo/seed')
    def seed(request:Request):
        actor=registry.require_supervisor(request);created=[];skipped=[]
        with registry.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for values in records():
                ident=values['id'];data={k:v for k,v in values.items() if k not in {'id','version'}}
                if db.execute('SELECT 1 FROM registry_records WHERE id=? OR (document_type=? AND issuer_country=? AND document_number=?)',(ident,data['document_type'],data['issuer_country'],data['document_number'])).fetchone():skipped.append(ident);continue
                record=registry.RegistryRecordInput.model_validate(data).model_dump();now=registry.utcnow()
                db.execute('INSERT INTO registry_records VALUES(?,?,?,?,?,?,1,0,?,?,?)',(ident,record['document_type'],record['issuer_country'],record['document_number'],registry.normalized_text(record['name']),json.dumps(record),now,now,actor))
                saved=registry.serialize(db.execute('SELECT * FROM registry_records WHERE id=?',(ident,)).fetchone());registry.audit(db,saved,None,'CREATE',actor,'Loaded synthetic signed QR demonstration reference.');created.append(ident)
        return {'created':created,'skipped':skipped,'message':'Existing records are never overwritten. Packaged signatures reference version 1.'}
