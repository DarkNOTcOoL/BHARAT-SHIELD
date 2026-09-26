"""Generate fictional demo cards; no private state is read or written."""
import sys,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.video_demo import scenarios
out=root/'demo_samples'/'video_demo';out.mkdir(parents=True,exist_ok=True)
fontpath='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font=ImageFont.truetype(fontpath,40);title=ImageFont.truetype(fontpath,48);small=ImageFont.truetype(fontpath,26)
fields=[('name','Name'),('document_number','Document number'),('dob','DOB'),('nationality','Nationality'),('issuer_country','Issuing country'),('issue_date','Issue date'),('expiry','Expiry')]
for case in scenarios():
    image=Image.new('RGB',(1800,1100),'#edf2f6');draw=ImageDraw.Draw(image)
    draw.rectangle((30,30,1770,1070),outline='#244562',width=4)
    draw.text((80,75),'SYNTHETIC DEMO PERMIT',font=title,fill='#183a57')
    draw.text((80,150),'FICTIONAL DATA - NOT A GOVERNMENT DOCUMENT',font=small,fill='#34465b')
    for i,(key,label) in enumerate(fields):draw.text((80,245+i*95),label+': '+case['printed'][key],font=font,fill='#111b24')
    draw.text((80,990),'Presentation sample only. No real identity or issuer is represented.',font=small,fill='#34465b')
    if case['degraded']:image=image.resize((270,165)).filter(ImageFilter.GaussianBlur(1.0))
    image.save(out/case['file'])
(out/'expected_scenarios.json').write_text(json.dumps(scenarios(),indent=2)+'\n')
print('Generated 9 fictional permits and expected scenario manifest.')
