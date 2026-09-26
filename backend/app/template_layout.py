"""Explainable document layout/security-zone anomaly assistance for BHARATSHIELD v6.4.

This module is intentionally conservative. It does not authenticate an issuer template and
must not be described as proof that a document is genuine/fake. It evaluates broad
family-level zones and relational geometry using OCR field boxes already tied to the
original EXIF-normalized image frame.
"""
from __future__ import annotations
import json, math
from typing import Any
import cv2
import numpy as np

METHOD='LOCAL_EXPLAINABLE_LAYOUT_SECURITY_ZONE_V1'

# Broad family zones, not exact government templates. Each box is x,y,w,h normalized.
# These are deliberately generous so ordinary issuer/layout variants do not trigger on
# small shifts. Exact-generation templates would require an authorized reference library.
PROFILES={
    'Passport':{
        'fields':{
            'name':[.20,.08,.78,.52], 'dob':[.20,.18,.78,.55], 'nationality':[.20,.12,.78,.58],
            'documentNumber':[.34,.04,.64,.48], 'expiry':[.20,.30,.78,.48], 'issueDate':[.20,.20,.78,.52],
            'gender':[.20,.18,.78,.52], 'issuerCountry':[.20,.04,.78,.55],
        },
        'photo_zone':[.01,.06,.58,.82], 'min_fields':3,
    },
    'Visa':{
        'fields':{
            'name':[.12,.05,.86,.72], 'dob':[.12,.10,.86,.70], 'documentNumber':[.20,.03,.78,.62],
            'expiry':[.12,.15,.86,.72], 'passportReference':[.12,.12,.86,.74], 'visaType':[.10,.05,.88,.72],
            'numberOfEntries':[.10,.05,.88,.72], 'validFrom':[.10,.10,.88,.72], 'durationOfStay':[.10,.12,.88,.72],
        },
        'photo_zone':[.01,.04,.62,.88], 'min_fields':3,
    },
    'Aadhaar Card':{
        'fields':{'name':[.08,.08,.86,.72],'dob':[.08,.16,.86,.68],'documentNumber':[.08,.34,.86,.58]},
        'photo_zone':[.01,.08,.55,.78], 'min_fields':2,
    },
    'PAN Card':{
        'fields':{'name':[.08,.08,.88,.72],'dob':[.08,.18,.88,.66],'documentNumber':[.08,.24,.88,.62]},
        'photo_zone':[.01,.08,.58,.80], 'min_fields':2,
    },
    'Voter ID (EPIC)':{
        'fields':{'name':[.08,.08,.88,.74],'dob':[.08,.12,.88,.72],'documentNumber':[.08,.08,.88,.78]},
        'photo_zone':[.01,.06,.60,.86], 'min_fields':2,
    },
    'Driving Licence':{
        'fields':{'name':[.08,.06,.90,.76],'dob':[.08,.10,.90,.74],'documentNumber':[.08,.04,.90,.78],'expiry':[.08,.12,.90,.76]},
        'photo_zone':[.01,.05,.62,.88], 'min_fields':2,
    },
    'National ID':{'fields':{},'photo_zone':[.01,.04,.65,.90],'min_fields':2},
    'Permit':{'fields':{},'photo_zone':None,'min_fields':2},
    'Travel Authorization':{'fields':{},'photo_zone':None,'min_fields':2},
}

ALIASES={
    'document_number':'documentNumber','passport_reference':'passportReference','issuer_country':'issuerCountry',
    'issue_date':'issueDate','issuing_authority':'issuingAuthority','visa_type':'visaType',
    'number_of_entries':'numberOfEntries','valid_from':'validFrom','duration_of_stay':'durationOfStay',
}

def _parse_notes(notes: str|dict|None)->dict:
    if isinstance(notes,dict): return notes
    if not notes:return {}
    try:
        value=json.loads(notes)
        return value if isinstance(value,dict) else {}
    except Exception:return {}

def _safe_boxes(notes)->list[dict]:
    out=[]
    for item in (_parse_notes(notes).get('field_boxes') or [])[:40]:
        if not isinstance(item,dict) or not isinstance(item.get('box'),list) or len(item['box'])!=4:continue
        try:b=[float(v) for v in item['box']]
        except Exception:continue
        if not all(math.isfinite(v) for v in b):continue
        if any(v<0 or v>1.0001 for v in b) or b[2]<=0 or b[3]<=0 or b[0]+b[2]>1.0001 or b[1]+b[3]>1.0001:continue
        field=ALIASES.get(str(item.get('field','')),str(item.get('field','')))
        out.append({'field':field[:80],'box':b,'confidence':item.get('confidence')})
    return out

def _center(box):return (box[0]+box[2]/2,box[1]+box[3]/2)
def _inside(point,zone):
    x,y=point;zx,zy,zw,zh=zone
    return zx<=x<=zx+zw and zy<=y<=zy+zh

def _overlap(a,b,denominator='a'):
    ax,ay,aw,ah=a;bx,by,bw,bh=b
    x0,y0=max(ax,bx),max(ay,by);x1,y1=min(ax+aw,bx+bw),min(ay+ah,by+bh)
    inter=max(0,x1-x0)*max(0,y1-y0)
    denom=aw*ah if denominator=='a' else min(aw*ah,bw*bh)
    return inter/max(denom,1e-9)

def _normalized_photo(photo_result:dict|None):
    b=(photo_result or {}).get('photo_region')
    if isinstance(b,list) and len(b)==4:
        try:
            b=[float(v) for v in b]
            if all(math.isfinite(v) for v in b) and all(0<=v<=1.0001 for v in b) and b[2]>0 and b[3]>0:return b
        except Exception:pass
    return None

def _passport_mrz_band(rgb:np.ndarray,ocr_text:str)->dict:
    text=(ocr_text or '').upper()
    mrz_text=bool('P<' in text or sum(1 for line in text.splitlines() if '<' in line and len(line.strip())>=30)>=1)
    h,w=rgb.shape[:2];gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    roi=gray[int(h*.58):,:]
    if roi.size==0:return {'text_detected':mrz_text,'bottom_band_score':0,'status':'NOT_ASSESSED'}
    # MRZ tends to create long horizontal groups of dark glyphs in the lower page. This
    # only supports layout review and is never used as MRZ validity.
    bw=cv2.threshold(roi,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(max(12,int(w*.018)),3))
    joined=cv2.morphologyEx(bw,cv2.MORPH_CLOSE,kernel)
    contours,_=cv2.findContours(joined,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    wide=[]
    for c in contours:
        x,y,cw,ch=cv2.boundingRect(c)
        if cw>=w*.30 and 5<=ch<=max(45,h*.09):wide.append([x,y+int(h*.58),cw,ch])
    score=min(100,len(wide)*35)
    status='BAND_FOUND' if wide else 'BAND_NOT_LOCALIZED'
    return {'text_detected':mrz_text,'bottom_band_score':score,'status':status,'candidate_count':len(wide),'candidates':wide[:4],
            'limitation':'Image morphology only; this is not MRZ decoding or authenticity validation.'}

def analyze(rgb:np.ndarray, document_type:str, ocr_notes=None, photo_result:dict|None=None, ocr_text:str='')->tuple[dict,np.ndarray]:
    boxes=_safe_boxes(ocr_notes);profile=PROFILES.get(document_type,PROFILES['National ID'])
    overlay=rgb.copy();h,w=rgb.shape[:2]
    photo=_normalized_photo(photo_result)
    signals=[];regions=[]
    if len(boxes)<profile.get('min_fields',2):
        result={'method':METHOD,'status':'INCONCLUSIVE','document_type':document_type,'field_box_count':len(boxes),
                'layout_anomaly_index':None,'signals':[],'inspection_regions':[],
                'reason':'Too few unambiguous OCR field boxes are available for layout assessment.',
                'limitation':'Layout analysis needs reliable OCR geometry and broad family profiles; absence of a signal does not establish authenticity.'}
        return result,overlay

    # 1) broad field-zone displacement
    for item in boxes:
        field=item['field'];box=item['box'];expected=profile.get('fields',{}).get(field)
        if expected and not _inside(_center(box),expected):
            signals.append({'code':'FIELD_ZONE_DISPLACEMENT','field':field,'severity':2,'message':f'{field} lies outside the broad expected {document_type} field zone.'})
            regions.append({'field':field,'box':box,'source':METHOD,'status':'LAYOUT_REVIEW'})

    # 2) text intruding strongly into AI-localized portrait region
    if photo:
        for item in boxes:
            frac=_overlap(item['box'],photo,'a')
            if frac>=.38:
                signals.append({'code':'FIELD_PHOTO_OVERLAP','field':item['field'],'severity':3,'overlap':round(frac,3),'message':f"{item['field']} overlaps the localized portrait/photo region."})
                regions.append({'field':item['field'],'box':item['box'],'source':METHOD,'status':'SECURITY_ZONE_OVERLAP'})
        pzone=profile.get('photo_zone')
        if pzone and not _inside(_center(photo),pzone):
            signals.append({'code':'PHOTO_ZONE_DISPLACEMENT','field':'document_photo','severity':2,'message':'Localized portrait is outside the broad document-family portrait zone.'})
            regions.append({'field':'document_photo','box':photo,'source':METHOD,'status':'LAYOUT_REVIEW'})

    # 3) OCR fields should not geometrically collide heavily with one another
    for i,a in enumerate(boxes):
        for b in boxes[i+1:]:
            frac=_overlap(a['box'],b['box'],'min')
            if frac>=.58 and a['field']!=b['field']:
                signals.append({'code':'FIELD_BOX_COLLISION','field':a['field']+' / '+b['field'],'severity':2,'overlap':round(frac,3),'message':'Two independently extracted field regions substantially overlap.'})
                regions.extend([{'field':a['field'],'box':a['box'],'source':METHOD,'status':'LAYOUT_REVIEW'},{'field':b['field'],'box':b['box'],'source':METHOD,'status':'LAYOUT_REVIEW'}])

    # 4) extreme isolated field-center outlier relative to other personalized fields
    if len(boxes)>=4:
        centers=np.asarray([_center(x['box']) for x in boxes],dtype=float)
        med=np.median(centers,axis=0);dist=np.linalg.norm(centers-med,axis=1)
        for idx,d in enumerate(dist):
            if d>=.56:
                item=boxes[idx]
                signals.append({'code':'EXTREME_FIELD_OUTLIER','field':item['field'],'severity':2,'distance':round(float(d),3),'message':'Field position is an extreme outlier relative to the other extracted personalized fields.'})
                regions.append({'field':item['field'],'box':item['box'],'source':METHOD,'status':'LAYOUT_REVIEW'})

    mrz=_passport_mrz_band(rgb,ocr_text) if document_type=='Passport' else {'status':'NOT_APPLICABLE'}
    if document_type=='Passport' and mrz.get('text_detected') and mrz.get('status')=='BAND_NOT_LOCALIZED':
        signals.append({'code':'MRZ_SECURITY_ZONE_NOT_LOCALIZED','field':'mrz','severity':2,'message':'MRZ-like OCR text exists, but a broad lower-page MRZ text band was not localized.'})

    # De-duplicate regions/signals and fuse conservatively. One odd field is information;
    # review requires either a high-risk portrait overlap or multiple independent signals.
    uniq=[];seen=set()
    for s in signals:
        key=(s.get('code'),s.get('field'))
        if key not in seen:seen.add(key);uniq.append(s)
    signals=uniq
    severe=sum(1 for s in signals if s.get('severity',0)>=3);moderate=sum(1 for s in signals if s.get('severity',0)>=2)
    raw=sum(s.get('severity',0)*18 for s in signals)
    index=min(100,raw)
    review=bool(severe>=1 or moderate>=2)
    status='REVIEW_REQUIRED' if review else ('OBSERVATIONS' if signals else 'NO_STRONG_LAYOUT_ANOMALY')

    # draw broad inspection evidence only
    color=(255,70,70) if review else (255,190,50)
    for region in regions[:20]:
        x,y,bw,bh=region['box'];x0,y0=int(x*w),int(y*h);x1,y1=int((x+bw)*w),int((y+bh)*h)
        cv2.rectangle(overlay,(x0,y0),(x1,y1),color,2)
    if photo:
        x,y,bw,bh=photo;cv2.rectangle(overlay,(int(x*w),int(y*h)),(int((x+bw)*w),int((y+bh)*h)),(60,210,255),2)
    label='LAYOUT REVIEW' if review else 'LAYOUT CHECK'
    cv2.putText(overlay,label,(12,28),cv2.FONT_HERSHEY_SIMPLEX,.65,color,2,cv2.LINE_AA)

    dedup_regions=[];seenr=set()
    for r in regions:
        key=(r['field'],tuple(round(v,5) for v in r['box']),r['status'])
        if key not in seenr:seenr.add(key);dedup_regions.append(r)
    result={'method':METHOD,'status':status,'document_type':document_type,'field_box_count':len(boxes),
            'layout_anomaly_index':index,'signals':signals,'inspection_regions':dedup_regions[:20],'mrz_zone':mrz,
            'reason':('Multiple independent layout/security-zone inconsistencies require officer inspection.' if review else
                      'No multi-signal layout anomaly crossed the review threshold. A clean result does not authenticate the document.'),
            'score_meaning':'0-100 prototype layout anomaly index based on explainable geometry rules; NOT a forgery probability.',
            'limitation':'Broad document-family zones and OCR geometry cannot authenticate an issuer template. Genuine document generations vary. Exact layout authentication requires an authorized versioned template/security-feature reference library.'}
    return result,overlay
