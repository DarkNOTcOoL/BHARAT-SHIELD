"""Visa-specific extraction validation and local stamp/seal inspection.

This module deliberately does not authenticate an issuer stamp. It extracts common
visa fields and uses local computer-vision/forensic cues to identify stamp-like
regions that deserve officer review. Results are evidence, not a forgery verdict.
"""
from __future__ import annotations
import re
from datetime import datetime
import cv2
import numpy as np

METHOD='VISA_INTELLIGENCE_V1'
STAMP_METHOD='LOCAL_STAMP_SEAL_FORENSIC_V1'

VISA_FIELDS=('visa_type','number_of_entries','valid_from','duration_of_stay')

_DATE_PATTERNS=(
    '%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y','%Y/%m/%d','%d %b %Y','%d %B %Y'
)

def _date(value):
    value=str(value or '').strip()
    for fmt in _DATE_PATTERNS:
        try:return datetime.strptime(value,fmt).date().isoformat()
        except ValueError:pass
    return None

def normalize_entries(value):
    t=re.sub(r'[^A-Z0-9]','',str(value or '').upper())
    aliases={'SINGLE':'1','ONE':'1','01':'1','DOUBLE':'2','TWO':'2','02':'2','MULTIPLE':'MULTIPLE','MULT':'MULTIPLE','M':'MULTIPLE','UNLIMITED':'MULTIPLE'}
    return aliases.get(t,t)

def extract(text):
    """Server-side supplemental visa parsing used as evidence cross-check only."""
    raw=str(text or '')[:20000]
    def grab(pattern,max_len=80):
        m=re.search(pattern,raw,re.I|re.M)
        return re.sub(r'\s+',' ',m.group(1)).strip(' .,:;#-')[:max_len] if m else ''
    visa_type=grab(r'(?:visa\s*(?:type|class|category)|type\s+of\s+visa)\s*[:#-]?\s*([^\n|]{1,60})')
    entries=grab(r'(?:number\s+of\s+entries|no\.?\s+of\s+entries|entries)\s*[:#-]?\s*([^\n|]{1,30})',30)
    valid_from=grab(r'(?:valid\s+from|validity\s+from|from)\s*[:#-]?\s*([0-9A-Za-z ./-]{6,30})',30)
    duration=grab(r'(?:duration\s+of\s+stay|duration\s+of\s+each\s+stay|max(?:imum)?\s+stay)\s*[:#-]?\s*([^\n|]{1,40})',40)
    return {'visa_type':visa_type,'number_of_entries':entries,'valid_from':valid_from,'duration_of_stay':duration}

def assess_fields(fields,ocr_text=''):
    supplied={k:str(fields.get(k,'') or '').strip() for k in VISA_FIELDS}
    parsed=extract(ocr_text)
    observed={k:(supplied[k] or parsed[k]) for k in VISA_FIELDS}
    findings=[];gaps=[]
    entries=normalize_entries(observed['number_of_entries'])
    if observed['number_of_entries'] and entries not in {'1','2','MULTIPLE'}:
        findings.append({'code':'VISA_ENTRIES_UNRECOGNIZED','severity':'MEDIUM','status':'REVIEW_REQUIRED','message':'Visa number-of-entries value is not one of SINGLE/1, DOUBLE/2 or MULTIPLE. Inspect the original.'})
    vf=_date(observed['valid_from']);ex=_date(fields.get('expiry',''));issued=_date(fields.get('issue_date',''))
    if observed['valid_from'] and not vf:
        findings.append({'code':'VISA_VALID_FROM_UNREADABLE','severity':'INFO','status':'MISSING','message':'Visa valid-from date could not be parsed.'})
    if vf and ex and vf>ex:
        findings.append({'code':'VISA_VALIDITY_ORDER_CONFLICT','severity':'HIGH','status':'CONFLICT','message':'Visa valid-from date follows the extracted expiry/valid-until date.'})
    if issued and vf and issued>vf:
        findings.append({'code':'VISA_ISSUE_AFTER_VALID_FROM','severity':'MEDIUM','status':'REVIEW_REQUIRED','message':'Visa issue date follows the extracted valid-from date. Verify the dates on the original.'})
    if not observed['visa_type']:gaps.append('Visa type/class not extracted.')
    if not observed['number_of_entries']:gaps.append('Number of entries not extracted.')
    if not observed['valid_from']:gaps.append('Valid-from date not extracted.')
    # Compare browser parser and server parser only when both saw a value. This never auto-corrects OCR.
    parser_disagreements=[]
    for key in VISA_FIELDS:
        a=re.sub(r'\s+',' ',supplied[key]).strip().casefold();b=re.sub(r'\s+',' ',parsed[key]).strip().casefold()
        if a and b and a!=b:parser_disagreements.append(key)
    if parser_disagreements:
        findings.append({'code':'VISA_PARSER_DISAGREEMENT','severity':'INFO','status':'REVIEW_REQUIRED','message':'Browser/server visa parsers disagree for: '+', '.join(parser_disagreements)+'. Inspect the original; no value was silently replaced.'})
    return {'method':METHOD,'fields':supplied,'server_parsed':parsed,'observed_fields':observed,'field_source':{k:('OFFICER_REVIEWED_BROWSER_OCR' if supplied[k] else 'SERVER_SUPPLEMENTAL_OCR_PARSE' if parsed[k] else 'MISSING') for k in VISA_FIELDS},'normalized_entries':entries or None,
            'findings':findings,'gaps':gaps,'status':'REVIEW_REQUIRED' if any(f.get('status') in {'CONFLICT','REVIEW_REQUIRED'} for f in findings) else 'COMPLETE' if not gaps else 'PARTIAL',
            'limitation':'Common printed visa labels are supported. Layouts vary by country and visa class; missing extraction is not evidence of fraud.'}

def _norm_box(box,w,h):
    x,y,bw,bh=box;return [round(float(x)/float(w),6),round(float(y)/float(h),6),round(float(bw)/float(w),6),round(float(bh)/float(h),6)]

def _iou(a,b):
    ax,ay,aw,ah=a;bx,by,bw,bh=b
    x1=max(ax,bx);y1=max(ay,by);x2=min(ax+aw,bx+bw);y2=min(ay+ah,by+bh)
    inter=max(0,x2-x1)*max(0,y2-y1)
    return inter/max(aw*ah+bw*bh-inter,1e-9)

def analyze_stamp_seal(rgb,tamper_regions=None,enabled=True):
    """Find stamp/seal-like regions and fuse them with local forensic anomalies.

    Detection is intentionally conservative. A stamp-like contour alone never raises
    a tamper alert; review requires overlap with an independent tamper anomaly and/or
    a strong local recompression/noise mismatch.
    """
    if not enabled:
        return ({'method':STAMP_METHOD,'status':'NOT_APPLICABLE','candidate_count':0,'inspection_regions':[],
                 'reason':'Stamp/seal analysis is enabled for Visa documents in this release.',
                 'limitation':'No issuer stamp authentication was performed.'},rgb.copy())
    h,w=rgb.shape[:2];overlay=rgb.copy()
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV);gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    sat=hsv[:,:,1]
    # Combine colored ink with dark high-edge components. This catches common blue/red stamps
    # and some monochrome immigration stamps without assuming a country-specific template.
    color_mask=((sat>70)&(hsv[:,:,2]<245)).astype(np.uint8)*255
    edges=cv2.Canny(gray,70,170)
    mask=cv2.morphologyEx(cv2.bitwise_or(color_mask,edges),cv2.MORPH_CLOSE,np.ones((5,5),np.uint8),iterations=2)
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    candidates=[]
    for c in contours:
        x,y,bw,bh=cv2.boundingRect(c);area=bw*bh;frac=area/max(w*h,1)
        if frac<0.002 or frac>0.16 or min(bw,bh)<24:continue
        contour_area=cv2.contourArea(c);per=cv2.arcLength(c,True);circ=(4*np.pi*contour_area/(per*per)) if per else 0
        aspect=bw/max(bh,1)
        if not (0.3<=aspect<=3.3):continue
        color_ratio=float((color_mask[y:y+bh,x:x+bw]>0).mean())
        edge_ratio=float((edges[y:y+bh,x:x+bw]>0).mean())
        if color_ratio<0.025 and edge_ratio<0.08:continue
        score=min(1.0,0.45*min(color_ratio/0.22,1)+0.35*min(edge_ratio/0.22,1)+0.2*min(circ/0.6,1))
        if score<0.28:continue
        candidates.append({'box':_norm_box((x,y,bw,bh),w,h),'shape_score':round(score,3),'color_ink_ratio':round(color_ratio,3),'edge_ratio':round(edge_ratio,3)})
    # Circular immigration/seal marks are common; add Hough circle proposals that may
    # not survive contour merging with nearby printed text.
    blur=cv2.medianBlur(gray,5)
    circles=cv2.HoughCircles(blur,cv2.HOUGH_GRADIENT,dp=1.2,minDist=max(40,min(w,h)//8),param1=120,param2=42,minRadius=max(16,min(w,h)//35),maxRadius=max(30,min(w,h)//4))
    if circles is not None:
        for cx,cy,r in np.round(circles[0]).astype(int)[:10]:
            x=max(0,cx-r-8);y=max(0,cy-r-8);x2=min(w,cx+r+8);y2=min(h,cy+r+8);bw=x2-x;bh=y2-y
            if bw<=0 or bh<=0:continue
            box=_norm_box((x,y,bw,bh),w,h)
            if any(_iou(box,c['box'])>.55 for c in candidates):continue
            color_ratio=float((color_mask[y:y2,x:x2]>0).mean());edge_ratio=float((edges[y:y2,x:x2]>0).mean())
            score=min(1.0,0.45+0.3*min(color_ratio/0.18,1)+0.25*min(edge_ratio/0.18,1))
            candidates.append({'box':box,'shape_score':round(score,3),'color_ink_ratio':round(color_ratio,3),'edge_ratio':round(edge_ratio,3),'proposal':'HOUGH_CIRCLE'})
    candidates=sorted(candidates,key=lambda r:r['shape_score'],reverse=True)[:8]
    tamper=[r.get('box') for r in (tamper_regions or []) if r.get('box') and r.get('source')=='ROBUST_PCA_PATCH_ANOMALY']
    strong=[]
    residual=np.abs(gray.astype(np.float32)-cv2.GaussianBlur(gray,(5,5),0).astype(np.float32))
    global_res=float(np.mean(residual))+1e-6
    for c in candidates:
        bx=c['box'];x=int(bx[0]*w);y=int(bx[1]*h);bw=max(1,int(bx[2]*w));bh=max(1,int(bx[3]*h))
        local=float(np.mean(residual[y:y+bh,x:x+bw])) if bw and bh else 0
        ratio=local/global_res
        overlap=max((_iou(bx,t) for t in tamper),default=0)
        c['tamper_overlap']=round(float(overlap),3);c['residual_ratio']=round(float(ratio),3)
        cues=[]
        if overlap>=0.12:cues.append('OVERLAPS_TAMPER_ANOMALY')
        if ratio>=2.2:cues.append('LOCAL_RECOMPRESSION_OR_EDGE_MISMATCH')
        c['cues']=cues
        if len(cues)>=2 or overlap>=0.3:strong.append(c)
    regions=[]
    for c in candidates:
        regions.append({'field':'visa_stamp_or_seal','box':c['box'],'source':'STAMP_SEAL_CANDIDATE','status':'REVIEW_REQUIRED' if c in strong else 'MANUAL_INSPECTION_ONLY','score':c['shape_score']})
        x=int(c['box'][0]*w);y=int(c['box'][1]*h);bw=int(c['box'][2]*w);bh=int(c['box'][3]*h)
        cv2.rectangle(overlay,(x,y),(x+bw,y+bh),(255,191,0) if c not in strong else (255,70,70),2)
    status='REVIEW_REQUIRED' if strong else 'CANDIDATES_FOUND' if candidates else 'NO_STAMP_LIKE_REGION_DETECTED'
    reason=(f'{len(strong)} stamp/seal-like region(s) overlap independent forensic anomaly cues.' if strong else
            f'{len(candidates)} stamp/seal-like candidate region(s) found for manual inspection; no multi-cue tamper alert.' if candidates else
            'No stamp/seal-like region was confidently localized. Absence does not establish that a required stamp is missing.')
    return ({'method':STAMP_METHOD,'status':status,'candidate_count':len(candidates),'strong_region_count':len(strong),
             'candidates':candidates,'inspection_regions':regions,'reason':reason,
             'limitation':'This is country-agnostic local CV/forensic assistance, not a trained issuer-stamp classifier and not stamp authenticity verification. Printed logos, seals, signatures and background art can look stamp-like.'},overlay)
