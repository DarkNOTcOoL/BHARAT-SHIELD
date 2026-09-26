"""Generate fictional permit images for the local registry demonstration."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root=Path(__file__).resolve().parents[1]/'demo_samples'/'registry'
root.mkdir(parents=True,exist_ok=True)
font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font=ImageFont.truetype(font_path,32)
title=ImageFont.truetype(font_path,44)
samples=[('01_match','AARAV DEMO','DEMO1001','14/03/2001','31/12/2035'),
 ('02_dob_conflict','AARAV DEMO','DEMO1001','14/08/2001','31/12/2035'),
 ('03_not_found','UNKNOWN SAMPLE','DEMO9999','14/03/2001','31/12/2035'),
 ('04_revoked','MEERA SAMPLE','DEMO1002','14/03/2001','31/12/2035'),
 ('05_expired','KABIR SAMPLE','DEMO1003','14/03/2001','01/01/2005'),
 ('06_blocked','TARA DEMO','DEMO1004','14/03/2001','31/12/2035'),
 ('07_similar_name','AARAV DEM0','DEMO1001','14/03/2001','31/12/2035'),
 ('08_name_transposition','AARAV DEOM','DEMO1001','14/03/2001','31/12/2035')]
for filename,name,number,dob,expiry in samples:
    im=Image.new('RGB',(1400,900),'white');draw=ImageDraw.Draw(im)
    draw.rectangle((20,20,1380,880),outline='#193555',width=4)
    draw.text((65,55),'SYNTHETIC TEST ONLY - DEMO PERMIT',font=title,fill='#193555')
    lines=[f'Name: {name}',f'Document number: {number}',f'DOB: {dob}',
           'Nationality: IND','Issuing country: IND',f'Expiry: {expiry}']
    for i,line in enumerate(lines):draw.text((75,175+i*80),line,font=font,fill='black')
    draw.text((75,760),'Fictional presentation sample. Not issued by any government.',font=font,fill='#193555')
    im.save(root/(filename+'.png'))
