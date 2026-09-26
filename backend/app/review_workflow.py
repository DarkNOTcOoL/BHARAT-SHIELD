from datetime import datetime, timezone
from typing import Literal
from fastapi import HTTPException, Request, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, text, func
from . import local_security

class ReviewChange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['CLAIM','ASSIGN','RESOLVE','REOPEN']
    expected_version:int=Field(ge=1)
    reason:str=Field(min_length=10,max_length=500)
    assignee:str=Field(default='',max_length=64)
    outcome:Literal['','ACCEPT','FLAG','ESCALATE','RECAPTURE']=''

def serialize(row):
    if not row:return None
    return {k:getattr(row,k) for k in ['screening_id','state','assigned_to','reason','version','resolution','resolution_reason','resolved_by','updated_at']}

def install(app,Session,Screening,AuditLog,Review):
    # Add unresolved v5 cases to the new queue without changing old evidence/decisions.
    with Session() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        existing=set(db.scalars(select(Review.screening_id)).all())
        rows=db.scalars(select(Screening).where(Screening.recommendation.in_(['RECAPTURE','MANUAL_REVIEW','ESCALATE']),~Screening.status.in_(['Verified']))).all()
        for s in rows:
            if s.screening_id not in existing:
                db.add(Review(screening_id=s.screening_id,reason='Imported unresolved v5 case: '+s.recommendation))
        db.commit()

    @app.get('/api/reviews')
    def queue(state:Literal['ALL','PENDING','UNDER_REVIEW','RESOLVED']='PENDING',offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=100)):
        with Session() as db:
            query=select(Review)
            if state!='ALL':query=query.where(Review.state==state)
            total=db.scalar(select(func.count()).select_from(query.subquery()))
            rows=db.scalars(query.order_by(Review.updated_at.desc(),Review.screening_id).offset(offset).limit(limit)).all()
            items=[]
            for row in rows:
                s=db.scalar(select(Screening).where(Screening.screening_id==row.screening_id))
                items.append(serialize(row)|{'person':s.person_name,'recommendation':s.recommendation,'document_type':s.document_type})
            return {'total':total,'items':items}

    @app.get('/api/reviews/officers')
    def officers():
        with local_security.connect() as db:
            return [dict(r) for r in db.execute('SELECT username,name,role FROM users WHERE enabled=1 ORDER BY username')]

    @app.post('/api/reviews/{screening_id}')
    def change(screening_id:str,body:ReviewChange,request:Request):
        actor=request.state.user['username'];supervisor=request.state.user['role']=='supervisor'
        reason=body.reason.strip()
        if len(reason)<10:raise HTTPException(400,'Provide a reason of at least 10 characters.')
        with Session() as db:
            db.execute(text('BEGIN IMMEDIATE'))
            row=db.scalar(select(Review).where(Review.screening_id==screening_id))
            if not row:raise HTTPException(404,'Review case not found.')
            if row.version!=body.expected_version:raise HTTPException(409,'Review changed. Reload before submitting.')
            s=db.scalar(select(Screening).where(Screening.screening_id==screening_id))
            if body.action=='CLAIM':
                if row.state=='RESOLVED' or (row.assigned_to and row.assigned_to!=actor):raise HTTPException(409,'Case is resolved or assigned to another officer.')
                row.assigned_to=actor;row.state='UNDER_REVIEW'
            elif not supervisor:raise HTTPException(403,'Supervisor permission required for assignment, resolution or reopening.')
            elif body.action=='ASSIGN':
                if row.state=='RESOLVED':raise HTTPException(409,'Reopen the case before assignment.')
                with local_security.connect() as users:
                    if not users.execute('SELECT 1 FROM users WHERE username=? AND enabled=1',(body.assignee,)).fetchone():raise HTTPException(400,'Choose an enabled officer.')
                row.assigned_to=body.assignee;row.state='UNDER_REVIEW'
            elif body.action=='REOPEN':
                if row.state!='RESOLVED':raise HTTPException(409,'Only resolved cases can be reopened.')
                row.state='PENDING';row.assigned_to='';row.resolution='';row.resolution_reason='';row.resolved_by='';s.status='Under review'
            elif body.action=='RESOLVE':
                if row.state!='UNDER_REVIEW' or not body.outcome:raise HTTPException(409,'Assign or claim the case, then choose a resolution.')
                import json
                evidence=json.loads(s.result.ai_analysis_json or '{}')
                if evidence.get('registry',{}).get('status') in {'BLOCKED','REVOKED'} and body.outcome!='ESCALATE':raise HTTPException(409,'Blocked/revoked synthetic records require escalation. Corrections need a new screening.')
                row.state='RESOLVED';row.resolution=body.outcome;row.resolution_reason=reason;row.resolved_by=actor
                s.status={'ACCEPT':'Verified','FLAG':'Flagged','ESCALATE':'Escalated','RECAPTURE':'Recapture requested'}[body.outcome]
            row.version+=1;row.updated_at=datetime.now(timezone.utc).isoformat()
            db.add(AuditLog(reference=screening_id,action=f'Review {body.action}; assignee={row.assigned_to}; outcome={row.resolution}; reason={reason}',result=row.state,officer=actor))
            db.commit();return serialize(row)

    @app.get('/api/reviews/{screening_id}')
    def review_detail(screening_id:str):
        with Session() as db:
            if not db.scalar(select(Screening).where(Screening.screening_id==screening_id)):
                raise HTTPException(404,'Screening not found.')
            return {'review':serialize(db.get(Review,screening_id))}
