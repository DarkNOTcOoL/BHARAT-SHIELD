"""Independent SQLite audit chains. Exported checkpoints detect later tail deletion.

A local administrator can rewrite the chain and local keys; not immutable storage.
"""
import hashlib,json
SOURCES={'audit_logs':['id','reference','action','result','officer','created_at'],
         'registry_history':['id','record_id','version','action','actor','reason','timestamp','before_json','after_json'],
         'security_events':['id','actor','action','subject','timestamp'],
         'registry2_events':['id','entity_type','entity_id','action','actor','reason','timestamp','payload_json']}
ZERO='0'*64
def digest(previous,source,ident,payload):return hashlib.sha256(json.dumps([previous,source,ident,payload],separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def configure(db):db.create_function('bs_audit_hash',4,digest)
def initialize(db):
    configure(db)
    db.execute('CREATE TABLE IF NOT EXISTS bs_audit_chain(seq INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, row_id INTEGER NOT NULL, payload TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL, UNIQUE(source,row_id))')
    db.execute('CREATE TABLE IF NOT EXISTS bs_audit_meta(id INTEGER PRIMARY KEY CHECK(id=1), legacy_count INTEGER NOT NULL)')
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    legacy=db.execute('SELECT 1 FROM bs_audit_meta WHERE id=1').fetchone()
    if not legacy:
        count=0
        for source,cols in SOURCES.items():
            if source not in tables:continue
            for row in db.execute('SELECT '+','.join(cols)+' FROM '+source+' ORDER BY id').fetchall():
                previous=db.execute('SELECT hash FROM bs_audit_chain ORDER BY seq DESC LIMIT 1').fetchone()
                previous=previous[0] if previous else ZERO;payload=json.dumps(list(row),separators=(',',':'),ensure_ascii=False)
                db.execute('INSERT INTO bs_audit_chain(source,row_id,payload,previous,hash) VALUES(?,?,?,?,?)',(source,row[0],payload,previous,digest(previous,source,row[0],payload)));count+=1
        db.execute('INSERT INTO bs_audit_meta VALUES(1,?)',(count,))
    for source,cols in SOURCES.items():
        if source not in tables:continue
        payload='json_array('+','.join('NEW.'+c for c in cols)+')'
        previous="COALESCE((SELECT hash FROM bs_audit_chain ORDER BY seq DESC LIMIT 1),'"+ZERO+"')"
        db.execute(f'''CREATE TRIGGER IF NOT EXISTS bs_append_{source} AFTER INSERT ON {source}
          BEGIN INSERT INTO bs_audit_chain(source,row_id,payload,previous,hash)
          VALUES('{source}',NEW.id,{payload},{previous},bs_audit_hash({previous},'{source}',NEW.id,{payload})); END''')

def verify(db,checkpoint=None):
    rows=db.execute('SELECT seq,source,row_id,payload,previous,hash FROM bs_audit_chain ORDER BY seq').fetchall()
    previous=ZERO;issues=[];counts={}
    for expected,row in enumerate(rows,1):
        seq,source,ident,payload,prev,hashed=row
        if seq!=expected or prev!=previous or digest(prev,source,ident,payload)!=hashed:issues.append(f'Chain mismatch at event {seq}')
        cols=SOURCES.get(source)
        if not cols:issues.append('Unknown audit source');continue
        current=db.execute('SELECT '+','.join(cols)+' FROM '+source+' WHERE id=?',(ident,)).fetchone()
        try:stored=json.loads(payload)
        except (ValueError,TypeError):stored=None
        if current is None or list(current)!=stored:issues.append(f'Source mismatch at event {seq}')
        previous=hashed;counts[source]=counts.get(source,0)+1
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for source in SOURCES:
        if source in tables and db.execute('SELECT count(*) FROM '+source).fetchone()[0]!=counts.get(source,0):issues.append('Source count mismatch: '+source)
    if checkpoint:
        seq=checkpoint['count'];known=rows[seq-1][5] if 0<seq<=len(rows) else ZERO if seq==0 else None
        if known!=checkpoint['head']:issues.append('External checkpoint mismatch or history truncated')
    legacy=db.execute('SELECT legacy_count FROM bs_audit_meta WHERE id=1').fetchone()
    return {'status':'INTEGRITY_ERROR' if issues else 'CHAIN_CONSISTENT','count':len(rows),'head':previous,'legacy_baseline_count':legacy[0] if legacy else None,'issues':issues[:50],
            'limitation':'Legacy entries were baselined at upgrade. Tail deletion requires a previously exported checkpoint. Local administrator rewrites are not prevented.'}
