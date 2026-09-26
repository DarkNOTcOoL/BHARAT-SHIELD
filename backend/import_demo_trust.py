"""Local administrator imports only public keys, with an independently checked fingerprint."""
import argparse,json,hashlib,re
from pathlib import Path
from app.signed_qr import TRUST,unb64
p=argparse.ArgumentParser();p.add_argument('--file',required=True);p.add_argument('--sha256',required=True);a=p.parse_args()
entries=json.loads(Path(a.file).read_text())
if not isinstance(entries,dict) or len(entries)!=1:raise SystemExit('Import exactly one demo public key.')
ident,entry=next(iter(entries.items()))
if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',ident) or not isinstance(entry,dict) or set(entry)!={'issuer','enabled','public_key','sha256'} or type(entry['enabled']) is not bool or not isinstance(entry['issuer'],str) or not 1<=len(entry['issuer'])<=80:raise SystemExit('Invalid public trust entry.')
raw=unb64(entry['public_key']);fingerprint=hashlib.sha256(raw).hexdigest()
if len(raw)!=32 or fingerprint!=a.sha256.lower() or entry['sha256']!=fingerprint:raise SystemExit('Fingerprint mismatch.')
current=json.loads(TRUST.read_text()) if TRUST.exists() else {}
if ident in current and current[ident]!=entry:raise SystemExit('Key ID already exists. Use a new key ID; do not silently replace trusted keys.')
current[ident]=entry;TRUST.parent.mkdir(exist_ok=True)
temporary=TRUST.with_suffix('.tmp')
with temporary.open('x') as f:json.dump(current,f,indent=2)
temporary.replace(TRUST);print('Demo public key installed. Restart the local server; retain the fingerprint separately.')
