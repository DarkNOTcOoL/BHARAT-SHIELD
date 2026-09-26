"""Authenticated local administration; password changes invalidate sessions."""
import hashlib,hmac,secrets,time
from typing import Literal
from fastapi import Request,HTTPException
from pydantic import BaseModel,Field
from . import local_security as security,local_registry,audit_chain
from . import checkpoints

class PasswordBody(BaseModel):
    current_password:str=Field(max_length=1024)
    new_password:str=Field(min_length=12,max_length=1024)
class AccountBody(BaseModel):
    action:Literal['disable','enable','reset_password','revoke_sessions']
    password:str=Field(default='',max_length=1024)

def install(app,engine):
    @app.post('/api/auth/password')
    def password(body:PasswordBody,request:Request):
        username=request.state.user['username']
        with security.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            user=db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
            if not hmac.compare_digest(security.password_hash(body.current_password,user['salt']),user['password_hash']):raise HTTPException(400,'Current password incorrect.')
            salt=secrets.token_hex(16)
            db.execute('UPDATE users SET salt=?,password_hash=? WHERE username=?',(salt,security.password_hash(body.new_password,salt),username))
            db.execute('DELETE FROM sessions WHERE username=?',(username,))
            security.security_event(db,username,'PASSWORD_CHANGED',username)
        return {'message':'Password changed. All your sessions ended; sign in again.'}

    @app.get('/api/admin/accounts')
    def accounts(request:Request):
        local_registry.require_supervisor(request)
        with security.connect() as db:
            return {'users':[dict(r) for r in db.execute('SELECT username,name,role,enabled FROM users ORDER BY username')],
                    'sessions':[dict(r) for r in db.execute('SELECT digest AS id,username,expires,last_seen FROM sessions WHERE expires>? AND last_seen>?',(time.time(),time.time()-900))],
                    'events':[dict(r) for r in db.execute('SELECT actor,action,subject,timestamp FROM security_events ORDER BY id DESC LIMIT 100')],
                    'session_policy':'15 minutes without authenticated API requests; absolute expiry 8 hours.'}

    @app.post('/api/admin/accounts/{username}')
    def change(username:str,body:AccountBody,request:Request):
        actor=local_registry.require_supervisor(request)
        with security.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            user=db.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
            if not user:raise HTTPException(404,'Account not found.')
            if body.action=='disable':
                if actor==username:raise HTTPException(400,'You cannot disable your own account.')
                if user['role']=='supervisor' and user['enabled'] and db.execute("SELECT count(*) FROM users WHERE role='supervisor' AND enabled=1").fetchone()[0]<=1:raise HTTPException(400,'Keep at least one enabled supervisor.')
                db.execute('UPDATE users SET enabled=0 WHERE username=?',(username,))
            elif body.action=='enable':db.execute('UPDATE users SET enabled=1 WHERE username=?',(username,))
            elif body.action=='reset_password':
                if len(body.password)<12:raise HTTPException(400,'Use at least 12 characters.')
                salt=secrets.token_hex(16)
                db.execute('UPDATE users SET salt=?,password_hash=? WHERE username=?',(salt,security.password_hash(body.password,salt),username))
            if body.action!='enable':db.execute('DELETE FROM sessions WHERE username=?',(username,))
            security.security_event(db,actor,body.action.upper(),username)
        return {'message':'Account updated. History preserved.'}

    @app.delete('/api/admin/sessions/{ident}')
    def revoke(ident:str,request:Request):
        actor=local_registry.require_supervisor(request)
        with security.connect() as db:
            row=db.execute('SELECT username FROM sessions WHERE digest=?',(ident,)).fetchone()
            if not row:raise HTTPException(404,'Session not found.')
            db.execute('DELETE FROM sessions WHERE digest=?',(ident,))
            security.security_event(db,actor,'REVOKE_SESSION',row['username'])
        return {'message':'Session revoked.'}

    @app.get('/api/admin/integrity')
    def integrity(request:Request):
        local_registry.require_supervisor(request)
        with engine.connect() as connection:
            main=audit_chain.verify(connection.connection.driver_connection)
        with local_registry.connection() as db:registry=audit_chain.verify(db)
        with security.connect() as db:accounts=audit_chain.verify(db)
        return {'screening':main,'registry':registry,'accounts':accounts,
                'scope':'Audit events only, not a signature over every document or database field. Save this checkpoint separately to detect later history truncation.'}

    @app.get('/api/admin/audit-checkpoint')
    def checkpoint(request:Request):
        result=integrity(request)
        result['exported_at_unix']=time.time()
        return checkpoints.sign(result)
