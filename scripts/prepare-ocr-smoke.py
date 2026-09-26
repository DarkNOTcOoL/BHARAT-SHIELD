"""Prepare synthetic fixtures for a real local Tesseract smoke test."""
import argparse,base64,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.intake import prepare
parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
source=root/'demo_samples'/'signed_qr'/'01_signed_match.png'
result=prepare(source.read_bytes());(out/'prepared_signed.png').write_bytes(base64.b64decode(result['image'].split(',',1)[1]))
image=Image.new('RGB',(1500,950),'white');draw=ImageDraw.Draw(image)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',40)
for i,line in enumerate(['FICTIONAL OCR TEST CARD','Name: CASEY TEST','Document number: AX729381','DOB: 1996-07-21','Nationality: IND','Issuing country: IND','Issue date: 2023-01-08','Expiry: 2033-01-08']):draw.text((60,50+i*100),line,font=font,fill='black')
image.save(out/'unseen_layout.png')
print('Prepared synthetic OCR fixtures only; no real personal data.')
