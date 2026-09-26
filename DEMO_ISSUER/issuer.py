"""Separate synthetic issuer. Private keys must be outside the application tree."""
import argparse,base64,hashlib,json,uuid,getpass,re
from pathlib import Path
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
FIELDS=('document_number','name','dob','nationality','issuer_country','gender','issue_date','expiry','issuing_authority','passport_reference')
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def b64(value):return base64.urlsafe_b64encode(value).decode().rstrip('=')
def public_entry(key,issuer):
    public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    return {'issuer':issuer,'enabled':True,'public_key':b64(public),'sha256':hashlib.sha256(public).hexdigest()}
def credential(record,key,key_id,issuer,credential_id=None):
    if record.get('document_type')!='Permit':raise ValueError('This demo layout supports Permit only.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',key_id) or not 1<=len(issuer)<=80:raise ValueError('Invalid demo issuer metadata.')
    if type(record.get('version')) is not int or record['version']<1 or not isinstance(record.get('id'),str) or not 1<=len(record['id'])<=80:raise ValueError('Download a versioned registry record first.')
    fields={k:str(record.get(k,'')) for k in FIELDS}
    if any(len(value)>180 for value in fields.values()):raise ValueError('Field too long.')
    if any(fields[k] for k in ['gender','issuing_authority','passport_reference']):raise ValueError('The demo Permit layout requires gender, issuing authority and passport reference to be blank.')
    if len(fields['name'])>30 or len(fields['document_number'])>24:raise ValueError('The printed demo layout supports names up to 30 and numbers up to 24 characters.')
    for k in ['dob','issue_date','expiry']:
        if datetime.strptime(fields[k],'%Y-%m-%d').strftime('%Y-%m-%d')!=fields[k]:raise ValueError('Dates must use YYYY-MM-DD.')
    if not fields['dob']<=fields['issue_date']<=fields['expiry']:raise ValueError('Invalid date order.')
    obj={'schema':'BS52-DEMO-1','issuer':issuer,'key_id':key_id,'credential_id':credential_id or 'DEMO-'+uuid.uuid4().hex,
         'registry_id':record['id'],'registry_version':record['version'],'document_type':record['document_type'],'fields':fields}
    raw=canonical(obj)
    return 'BS52.'+b64(raw)+'.'+b64(key.sign(raw))
def draw_document(record,qr_value,destination,note='Fictional credential. No government authority.'):
    import qrcode
    from PIL import Image,ImageDraw,ImageFont
    font_candidates=['C:/Windows/Fonts/arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    font_path=next((x for x in font_candidates if Path(x).is_file()),None)
    def font(size):return ImageFont.truetype(font_path,size) if font_path else ImageFont.load_default(size=size)
    image=Image.new('RGB',(2400,1400),'white');d=ImageDraw.Draw(image)
    d.rectangle((20,20,2380,1380),outline='#173957',width=5)
    d.text((75,65),'SYNTHETIC DEMO PERMIT — TEST ONLY',font=font(60),fill='#173957')
    labels=[('name','Name'),('document_number','Document number'),('dob','DOB'),('nationality','Nationality'),('issuer_country','Issuing country'),('issue_date','Issue date'),('expiry','Expiry')]
    for i,(key,label) in enumerate(labels):d.text((80,220+i*115),label+': '+str(record.get(key,'')),font=font(44),fill='black')
    if qr_value:
        qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=9,border=4);qr.add_data(qr_value);qr.make(fit=True)
        tile=qr.make_image(fill_color='black',back_color='white').convert('RGB');tile.thumbnail((1050,1050),Image.Resampling.NEAREST)
        image.paste(tile,(1290,190));d.text((1450,1250),'BS52 DEMO SIGNATURE',font=font(32),fill='#173957')
    d.text((80,1160),note,font=font(32),fill='#173957')
    image.save(destination)
def main():
    p=argparse.ArgumentParser(description='Synthetic issuer: generate keys outside the screening application')
    p.add_argument('action',choices=['init','issue']);p.add_argument('--key-dir',required=True);p.add_argument('--key-id',default='my-demo-issuer');p.add_argument('--issuer',default='Local Synthetic Issuer');p.add_argument('--record');p.add_argument('--out')
    args=p.parse_args();directory=Path(args.key_dir).resolve();app_root=Path(__file__).resolve().parents[1]
    if directory==app_root or app_root in directory.parents:raise SystemExit('Signing keys must be outside the BHARATSHIELD folder.')
    keypath=directory/'issuer-private.pem'
    if args.action=='init':
        directory.mkdir(parents=True,exist_ok=True)
        if keypath.exists():raise SystemExit('Key already exists. It will not be overwritten.')
        password=getpass.getpass('Private key password (12+ characters): ')
        if len(password)<12 or password!=getpass.getpass('Confirm password: '):raise SystemExit('Password too short or confirmation differs.')
        key=Ed25519PrivateKey.generate()
        with keypath.open('xb') as f:f.write(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.BestAvailableEncryption(password.encode())))
        keypath.chmod(0o600);entry=public_entry(key,args.issuer)
        with (directory/'trust-public.json').open('x') as f:json.dump({args.key_id:entry},f,indent=2)
        print('Public key SHA-256:',entry['sha256']);print('Keep the private key here. Transfer only trust-public.json to the verifier.')
    else:
        if not args.record or not args.out:raise SystemExit('issue needs --record and --out')
        out=Path(args.out)
        if out.exists():raise SystemExit('Output exists; choose a new filename.')
        key=serialization.load_pem_private_key(keypath.read_bytes(),password=getpass.getpass('Private key password: ').encode())
        record=json.loads(Path(args.record).read_text());value=credential(record,key,args.key_id,args.issuer)
        draw_document(record,value,out);print('Synthetic document created:',out)
if __name__=='__main__':main()
