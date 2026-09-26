import hashlib,sqlite3
from pathlib import Path
import pytest
from cryptography.fernet import Fernet
from cryptography.exceptions import InvalidTag
from recovery import backup,restore

def fixture(root):
    private=root/'private';private.mkdir();trust=root/'trust';trust.mkdir()
    (trust/'demo_issuers.json').write_text('{}')
    secret=Fernet.generate_key();(private/'document.key').write_bytes(secret)
    (private/'documents').mkdir();data=b'synthetic evidence'
    (private/'documents'/'test.enc').write_bytes(Fernet(secret).encrypt(data))
    for filename in ['accounts.sqlite3','registry.sqlite3','bharatshield.db']:
        with sqlite3.connect(private/filename) as db:
            db.execute('CREATE TABLE sessions(digest TEXT)');db.execute("INSERT INTO sessions VALUES('old-session')")
            if filename=='bharatshield.db':
                db.execute('CREATE TABLE screenings(stored_path TEXT,document_hash TEXT)')
                db.execute('INSERT INTO screenings VALUES(?,?)',('C:\\previous\\documents\\test.enc','sha256:'+hashlib.sha256(data).hexdigest()))
    return private,trust

def test_encrypted_restore_validates_evidence_and_clears_sessions(tmp_path):
    private,trust=fixture(tmp_path);path=tmp_path/'backup.bsbackup'
    backup(private,trust,'backup-password-12345',path)
    assert b'synthetic evidence' not in path.read_bytes()
    destination=tmp_path/'restored';restore(path,'backup-password-12345',destination)
    assert (destination/'private'/'document.key').read_bytes()==(private/'document.key').read_bytes()
    with sqlite3.connect(destination/'private'/'accounts.sqlite3') as db:assert db.execute('SELECT count(*) FROM sessions').fetchone()[0]==0
    with sqlite3.connect(private/'accounts.sqlite3') as db:assert db.execute('SELECT count(*) FROM sessions').fetchone()[0]==1
    with pytest.raises(ValueError):restore(path,'backup-password-12345',destination)

def test_wrong_password_or_tampered_bundle_never_restores(tmp_path):
    private,trust=fixture(tmp_path);path=tmp_path/'backup.bsbackup';backup(private,trust,'backup-password-12345',path)
    with pytest.raises(InvalidTag):restore(path,'incorrect-password-12345',tmp_path/'bad')
    raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
    with pytest.raises(InvalidTag):restore(path,'backup-password-12345',tmp_path/'bad')
    assert not (tmp_path/'bad').exists()

def test_backup_refuses_bad_evidence_and_existing_output(tmp_path):
    private,trust=fixture(tmp_path);path=tmp_path/'backup.bsbackup';path.write_bytes(b'keep')
    with pytest.raises(ValueError):backup(private,trust,'backup-password-12345',path)
    assert path.read_bytes()==b'keep'
    (private/'documents'/'test.enc').write_bytes(Fernet((private/'document.key').read_bytes()).encrypt(b'altered'))
    with pytest.raises(ValueError):backup(private,trust,'backup-password-12345',tmp_path/'new.bsbackup')
