"""Loopback-only authentication. No outbound clients or default credentials."""
import hashlib
import hmac
import secrets
import sqlite3
import time
import os
from pathlib import Path
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(os.getenv('BHARATSHIELD_DATA_DIR',str(Path(__file__).resolve().parents[1] / 'private'))).resolve()
ROOT.mkdir(exist_ok=True, parents=True)
DB = ROOT / 'accounts.sqlite3'

def connect():
    db = sqlite3.connect(DB, timeout=15)
    db.row_factory = sqlite3.Row
    db.executescript('''CREATE TABLE IF NOT EXISTS users
        (username TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, username TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts (client TEXT PRIMARY KEY, count INTEGER, started REAL);''')
    if 'enabled' not in {r[1] for r in db.execute('PRAGMA table_info(users)')}:
        db.execute('ALTER TABLE users ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1')
    if 'last_seen' not in {r[1] for r in db.execute('PRAGMA table_info(sessions)')}:
        db.execute('ALTER TABLE sessions ADD COLUMN last_seen REAL NOT NULL DEFAULT 0')
        db.execute('DELETE FROM sessions')
    db.execute('CREATE TABLE IF NOT EXISTS security_events(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,subject TEXT NOT NULL,timestamp REAL NOT NULL)')
    from . import audit_chain
    audit_chain.initialize(db)
    db.commit()
    return db

def security_event(db,actor,action,subject):
    db.execute('INSERT INTO security_events(actor,action,subject,timestamp) VALUES(?,?,?,?)',(actor,action,subject,int(time.time()*1000)))

def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

def create_user(username, name, password, role='officer'):
    if not username.strip() or len(username) > 64 or len(password) < 12:
        raise ValueError('Officer ID is required; password must have at least 12 characters.')
    if role not in {'officer', 'supervisor'}: raise ValueError('Invalid role')
    salt = secrets.token_hex(16)
    with connect() as db:
        db.execute('INSERT INTO users(username,name,role,salt,password_hash) VALUES (?,?,?,?,?)', (username.strip(), name[:120], role, salt, password_hash(password, salt)))
        security_event(db,'LOCAL_ADMIN','CREATE_ACCOUNT',username.strip())

def session_user(token):
    if not token: return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    with connect() as db:
        row = db.execute('SELECT u.username,u.name,u.role FROM sessions s JOIN users u ON s.username=u.username WHERE s.digest=? AND s.expires>? AND s.last_seen>? AND u.enabled=1', (digest, time.time(),time.time()-15*60)).fetchone()
        if row:db.execute('UPDATE sessions SET last_seen=? WHERE digest=?',(time.time(),digest))
    return dict(row) if row else None

class LoginBody(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=1024)

def install(app):
    @app.middleware('http')
    async def guard(request: Request, call_next):
        # This build intentionally accepts loopback hostnames only. LAN deployment needs TLS and a separate policy.
        if request.url.hostname not in {'localhost', '127.0.0.1', 'testserver'}:
            return JSONResponse({'detail':'This build only serves loopback hosts.'}, status_code=403)
        if request.method not in {'GET','HEAD','OPTIONS'}:
            if request.headers.get('x-local-request') != '1':
                return JSONResponse({'detail':'Missing local request header.'}, status_code=403)
            origin = request.headers.get('origin')
            if origin and origin not in {'http://127.0.0.1:8000','http://localhost:8000','http://127.0.0.1:5173','http://localhost:5173'}:
                return JSONResponse({'detail':'Origin not allowed.'}, status_code=403)
        if request.url.path.startswith('/api/') and request.url.path not in {'/api/auth/login','/api/auth/status','/api/health'}:
            user = session_user(request.cookies.get('bs_session'))
            if not user: return JSONResponse({'detail':'Sign in required.'}, status_code=401)
            request.state.user = user
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Cache-Control'] = 'no-store'
        # Production is a single loopback origin. Worker assets and fonts are all local.
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; worker-src 'self' blob:; media-src 'self' blob:; frame-ancestors 'none'; object-src 'none'"
        return response

    @app.get('/api/auth/status')
    def status():
        with connect() as db: exists = db.execute('SELECT 1 FROM users LIMIT 1').fetchone() is not None
        return {'account_exists':exists}

    @app.post('/api/auth/login')
    def login(body: LoginBody, request: Request):
        client = request.client.host if request.client else 'local'
        now = time.time()
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM attempts WHERE client=?',(client,)).fetchone()
            if row and now-row['started'] < 60 and row['count'] >= 5:
                raise HTTPException(429,'Too many attempts. Wait one minute.')
            count = row['count']+1 if row and now-row['started'] < 60 else 1
            started = row['started'] if count > 1 else now
            db.execute('INSERT OR REPLACE INTO attempts VALUES (?,?,?)',(client,count,started))
            user = db.execute('SELECT * FROM users WHERE username=?',(body.username.strip(),)).fetchone()
        # Perform a password derivation even for unknown usernames.
        candidate = password_hash(body.password, user['salt'] if user else '00'*16)
        if not user or not user['enabled'] or not hmac.compare_digest(candidate,user['password_hash']):
            with connect() as db:security_event(db,body.username.strip(),'LOGIN_FAILED','local sign-in')
            raise HTTPException(401,'Invalid officer ID or password.')
        token = secrets.token_urlsafe(32)
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM attempts WHERE client=?',(client,))
            db.execute('DELETE FROM sessions WHERE expires<?',(now,))
            current=db.execute('SELECT enabled,password_hash FROM users WHERE username=?',(user['username'],)).fetchone()
            if not current or not current['enabled'] or current['password_hash']!=user['password_hash']:raise HTTPException(401,'Account changed; sign in again.')
            db.execute('INSERT INTO sessions(digest,username,expires,last_seen) VALUES (?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['username'],now+8*3600,now))
            security_event(db,user['username'],'LOGIN_SUCCESS','local sign-in')
        response = JSONResponse({'username':user['username'],'name':user['name'],'role':user['role']})
        response.set_cookie('bs_session',token,httponly=True,samesite='strict',max_age=8*3600,path='/')
        return response

    @app.get('/api/auth/me')
    def me(request: Request): return request.state.user

    @app.post('/api/auth/logout')
    def logout(request: Request):
        digest = hashlib.sha256(request.cookies.get('bs_session','').encode()).hexdigest()
        with connect() as db: db.execute('DELETE FROM sessions WHERE digest=?',(digest,))
        response = JSONResponse({'status':'signed_out'})
        response.delete_cookie('bs_session',path='/')
        return response
