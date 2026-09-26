"""Fictional fixtures; never imported by OCR or decision rules."""
from . import local_registry as registry

def scenarios():
    base={'document_type':'Permit','name':'KAVYA SAMPLE','dob':'1998-07-21','nationality':'IND','issuer_country':'IND','issue_date':'2022-01-15','expiry':'2035-12-31'}
    specs=[('01_active_match','REF7611',{}, {},'MATCH',0,'LOW'),
           ('02_second_match','REF7622',{'name':'ARUN EXAMPLE'},{},'MATCH',0,'LOW'),
           ('03_dob_conflict','REF7633',{}, {'dob':'1999-07-21'},'CONFLICT',40,'HIGH'),
           ('04_expired','REF7644',{'issue_date':'2015-01-15','expiry':'2020-12-31','status':'EXPIRED'}, {},'EXPIRED',40,'HIGH'),
           ('05_revoked','REF7655',{'status':'REVOKED'}, {},'REVOKED',90,'CRITICAL'),
           ('06_blocked','REF7666',{'status':'BLOCKED'}, {},'BLOCKED',100,'CRITICAL'),
           ('07_unknown_record','REF7677',{}, {},'NOT_FOUND',None,'UNASSESSED'),
           ('08_similar_name','REF7688',{}, {'name':'KAVYA SAMPEL'},'REVIEW_REQUIRED',10,'REVIEW'),
           ('09_poor_capture','REF7699',{}, {},'MATCH',None,'UNASSESSED')]
    out=[]
    for filename,number,changes,printed_changes,status,score,band in specs:
        ref=base|{'document_number':number,'status':'ACTIVE'}|changes
        out.append({'file':filename+'.png','reference':None if status=='NOT_FOUND' else ref,
                    'printed':{k:v for k,v in ref.items() if k!='status'}|printed_changes,
                    'expected_registry':status,'expected_score_after_correct_review':score,'expected_band':band,'degraded':filename=='09_poor_capture'})
    return out

def install(app):
    from fastapi import Request
    @app.post('/api/video-demo/seed')
    def seed(request:Request):
        actor=registry.require_supervisor(request);created=[];skipped=[]
        with registry.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for case in scenarios():
                if case['reference'] is None:continue
                record=registry.RegistryRecordInput.model_validate(case['reference'])
                if db.execute('SELECT id FROM registry_records WHERE document_type=? AND issuer_country=? AND document_number=?',(record.document_type,record.issuer_country,record.document_number)).fetchone():skipped.append(record.document_number);continue
                created.append(registry.create_in_transaction(db,record,actor,'Loaded v5.6 fictional video demonstration reference.'))
        return {'created':created,'skipped':skipped,'source':'SYNTHETIC_VIDEO_DEMO','message':'Existing references preserved. Expected scenarios never override verification.'}
