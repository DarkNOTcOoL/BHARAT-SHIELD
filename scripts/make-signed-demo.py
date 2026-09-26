"""Build public demo assets. Ephemeral private keys are never written or shipped."""
import sys,json,base64
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'DEMO_ISSUER'))
from issuer import credential,draw_document,public_entry,canonical,b64
key=Ed25519PrivateKey.generate();issuer='BHARATSHIELD SYNTHETIC DEMO ISSUER';keyid='bs-demo-52'
trust=root/'backend/trust';trust.mkdir(exist_ok=True)
if (trust/'demo_issuers.json').exists():raise SystemExit('Demo trust file exists; refusing to replace existing keys.')
with (trust/'demo_issuers.json').open('x') as f:json.dump({keyid:public_entry(key,issuer)},f,indent=2)
base={'id':'REG-DEMO52-001','version':1,'document_type':'Permit','document_number':'DEMO5201','name':'AARAV DEMO','dob':'2001-03-14','issue_date':'2024-01-01','expiry':'2035-12-31','nationality':'IND','issuer_country':'IND'}
other=base|{'id':'REG-DEMO52-002','document_number':'DEMO5202','name':'MEERA SAMPLE'}
value=credential(base,key,keyid,issuer,'DEMO-CREDENTIAL-5201')
parts=value.split('.');obj=json.loads(base64.urlsafe_b64decode(parts[1]+'='*((-len(parts[1]))%4)));obj['fields']['dob']='2002-03-14';tampered='BS52.'+b64(canonical(obj))+'.'+parts[2]
samples=[('01_signed_match',base,value),('02_printed_dob_changed',base|{'dob':'2002-03-14'},value),('03_payload_tampered',base,tampered),('04_unknown_issuer',base,credential(base,Ed25519PrivateKey.generate(),'unknown-demo-key','UNKNOWN DEMO ISSUER')),('05_unsigned_required',base,''),('06_substituted_valid_qr',base,credential(other,key,keyid,issuer)),('07_reused_credential',base,value)]
out=root/'demo_samples/signed_qr';out.mkdir(parents=True,exist_ok=True)
for name,record,qr in samples:draw_document(record,qr,out/(name+'.png'),note='Fictional sample: '+name)
with (out/'sample_record.json').open('w') as f:json.dump(base,f,indent=2)
print('Built seven signed/altered/unsigned samples and public trust key. No private key persisted.')
