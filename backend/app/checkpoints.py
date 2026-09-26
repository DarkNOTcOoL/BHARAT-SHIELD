"""Signed local audit checkpoints. Pin the public-key fingerprint separately."""
import base64,hashlib,json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from .local_security import ROOT

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sign(payload):
    path=ROOT/'audit-checkpoint.key'
    if not path.exists():
        key=Ed25519PrivateKey.generate()
        try:
            with path.open('xb') as f:f.write(key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()))
            path.chmod(0o600)
        except FileExistsError:pass
    key=Ed25519PrivateKey.from_private_bytes(path.read_bytes())
    public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    return {'format':'BS52-AUDIT-CHECKPOINT-1','payload':payload,'public_key':base64.b64encode(public).decode(),
            'public_key_sha256':hashlib.sha256(public).hexdigest(),'signature':base64.b64encode(key.sign(canonical(payload))).decode()}
def verify(value,pinned_fingerprint):
    if value['format']!='BS52-AUDIT-CHECKPOINT-1':raise ValueError('Unsupported checkpoint')
    key=base64.b64decode(value['public_key'],validate=True)
    fingerprint=hashlib.sha256(key).hexdigest()
    if fingerprint!=pinned_fingerprint.lower() or fingerprint!=value['public_key_sha256']:raise ValueError('Checkpoint public key fingerprint mismatch')
    Ed25519PublicKey.from_public_bytes(key).verify(base64.b64decode(value['signature'],validate=True),canonical(value['payload']))
    return value['payload']
