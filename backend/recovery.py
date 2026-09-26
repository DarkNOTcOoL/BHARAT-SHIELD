"""Offline encrypted recovery bundles. Stop the server before backup or restore.

Restores only to a NEW directory. Never overwrites a running installation.
This memory-based demo utility limits uncompressed input to 200 MiB.
"""
import argparse,getpass,hashlib,io,json,os,secrets,sqlite3,tempfile,zipfile
from pathlib import Path,PurePosixPath
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.fernet import Fernet
MAGIC=b'BS52BACKUP1';LIMIT=200*1024*1024
def key(password,salt):
    if len(password)<12:raise ValueError('Backup password must have at least 12 characters.')
    return Scrypt(salt=salt,length=32,n=2**15,r=8,p=1).derive(password.encode())
def validate_private(root):
    required=['accounts.sqlite3','registry.sqlite3','bharatshield.db','document.key']
    for name in required:
        if not (root/name).is_file():raise ValueError('Missing required file: '+name)
    cipher=Fernet((root/'document.key').read_bytes())
    for name in required[:3]:
        with sqlite3.connect((root/name).as_uri()+'?mode=ro',uri=True) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failure: '+name)
            if name=='bharatshield.db':
                for stored,digest in db.execute('SELECT stored_path,document_hash FROM screenings'):
                    filename=str(stored).replace('\\','/').rsplit('/',1)[-1]
                    data=cipher.decrypt((root/'documents'/filename).read_bytes())
                    if hashlib.sha256(data).hexdigest()!=digest.removeprefix('sha256:'):raise ValueError('Evidence hash mismatch: '+filename)
    for document in (root/'documents').glob('*'):
        if document.is_file():cipher.decrypt(document.read_bytes())
def backup(private,trust,password,destination):
    if Path(private).is_symlink() or Path(trust).is_symlink():raise ValueError('Symlink source not allowed.')
    private=Path(private).resolve();trust=Path(trust).resolve();destination=Path(destination).resolve()
    if not trust.is_dir():raise ValueError('Public trust directory missing.')
    if destination==private or private in destination.parents or destination==trust or trust in destination.parents:raise ValueError('Save backups outside the source directories.')
    if destination.exists():raise ValueError('Output already exists.')
    validate_private(private)
    files={};size=0
    for prefix,root in [('private',private),('trust',trust)]:
        if root.is_symlink():raise ValueError('Symlink source not allowed.')
        for path in root.rglob('*'):
            if path.is_symlink():raise ValueError('Symlinks are not allowed in recovery bundles.')
            if not path.is_file():continue
            size+=path.stat().st_size
            if size>LIMIT:raise ValueError('Backup exceeds demo utility 200 MiB limit.')
            files[prefix+'/'+path.relative_to(root).as_posix()]=path.read_bytes()
    manifest={name:hashlib.sha256(value).hexdigest() for name,value in files.items()}
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,value in files.items():archive.writestr(name,value)
        archive.writestr('manifest.json',json.dumps(manifest,sort_keys=True))
    salt=secrets.token_bytes(16);nonce=secrets.token_bytes(12)
    encrypted=AESGCM(key(password,salt)).encrypt(nonce,buffer.getvalue(),MAGIC)
    with destination.open('xb') as out:out.write(MAGIC+salt+nonce+encrypted)
    destination.chmod(0o600)
def restore(source,password,destination):
    source=Path(source);destination=Path(destination).resolve()
    if destination.exists():raise ValueError('Restore destination must not exist. Choose a NEW folder.')
    if source.stat().st_size>LIMIT+1024*1024:raise ValueError('Bundle exceeds demo size limit.')
    raw=source.read_bytes();offset=len(MAGIC)
    if not raw.startswith(MAGIC):raise ValueError('Unsupported backup format.')
    plaintext=AESGCM(key(password,raw[offset:offset+16])).decrypt(raw[offset+16:offset+28],raw[offset+28:],MAGIC)
    with zipfile.ZipFile(io.BytesIO(plaintext)) as archive:
        infos=archive.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(names)) or sum(i.file_size for i in infos)>LIMIT+1024*1024:raise ValueError('Invalid or oversized archive.')
        for name in names:
            path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name or not(name=='manifest.json' or path.parts[0] in {'private','trust'}):raise ValueError('Unsafe archive path.')
        manifest=json.loads(archive.read('manifest.json'))
        if set(manifest)!=set(names)-{'manifest.json'}:raise ValueError('Manifest does not cover every file.')
        files={name:archive.read(name) for name in manifest}
        for name,data in files.items():
            if hashlib.sha256(data).hexdigest()!=manifest[name]:raise ValueError('Manifest hash mismatch.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bs-restore-',dir=destination.parent) as stage:
        staging=Path(stage)/'recovered';staging.mkdir()
        for name,data in files.items():
            path=staging/name;path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as out:out.write(data)
        validate_private(staging/'private')
        with sqlite3.connect(staging/'private'/'accounts.sqlite3') as db:db.execute('DELETE FROM sessions')
        if destination.exists():raise ValueError('Destination appeared during restore; no files overwritten.')
        staging.rename(destination)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['backup','restore'])
    p.add_argument('--private',default='private');p.add_argument('--trust',default='trust');p.add_argument('--file',required=True);p.add_argument('--out');p.add_argument('--confirm-server-stopped',action='store_true')
    a=p.parse_args()
    if not a.confirm_server_stopped:raise SystemExit('Stop the server first; then pass --confirm-server-stopped. This is not a hot-backup utility.')
    password=getpass.getpass('Backup password (12+ characters): ')
    if a.action=='backup':
        if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords differ.')
        backup(a.private,a.trust,password,a.file);print('Encrypted backup created. Keep the password separately.')
    else:
        if not a.out:raise SystemExit('Restore requires --out NEW_FOLDER')
        restore(a.file,password,a.out);print('Validated recovery folder created. Sessions cleared. Original installation unchanged.')
if __name__=='__main__':main()
