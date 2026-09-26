"""Local capture/OCR preparation intelligence for BHARATSHIELD v6.3.

All outputs are capture/readability aids. They are not authenticity or fraud verdicts.
Geometric transforms are preview-only so OCR field boxes keep the same coordinate frame.
"""
from __future__ import annotations
import base64, io, math
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

METHOD='LOCAL_CAPTURE_INTELLIGENCE_V1'
OCR_METHOD='MULTI_PREPROCESSING_TESSERACT_FALLBACK_V1'


def _png_data(gray_or_rgb: np.ndarray) -> str:
    arr=np.asarray(gray_or_rgb)
    if arr.ndim==2:
        image=Image.fromarray(arr.astype(np.uint8),'L')
    else:
        image=Image.fromarray(arr.astype(np.uint8),'RGB')
    out=io.BytesIO(); image.save(out,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()


def _norm_box(x:int,y:int,w:int,h:int,width:int,height:int)->list[float]:
    return [round(max(0,x)/max(width,1),6),round(max(0,y)/max(height,1),6),
            round(max(0,w)/max(width,1),6),round(max(0,h)/max(height,1),6)]


def detect_boundary(rgb:np.ndarray)->dict:
    h,w=rgb.shape[:2]
    scale=min(1.0,1600/max(h,w))
    work=cv2.resize(rgb,(max(1,round(w*scale)),max(1,round(h*scale)))) if scale<1 else rgb.copy()
    gray=cv2.cvtColor(work,cv2.COLOR_RGB2GRAY)
    gray=cv2.GaussianBlur(gray,(5,5),0)
    edges=cv2.Canny(gray,45,150)
    edges=cv2.morphologyEx(edges,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8),iterations=2)
    contours,_=cv2.findContours(edges,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    best=None
    area_total=work.shape[0]*work.shape[1]
    for contour in sorted(contours,key=cv2.contourArea,reverse=True)[:20]:
        area=float(cv2.contourArea(contour));
        if area<.18*area_total: continue
        peri=cv2.arcLength(contour,True)
        poly=cv2.approxPolyDP(contour,.018*peri,True)
        if len(poly)!=4 or not cv2.isContourConvex(poly): continue
        rect=cv2.minAreaRect(contour); rw,rh=rect[1]
        rectangle_area=max(float(rw*rh),1.0)
        rectangularity=min(1.0,area/rectangle_area)
        area_ratio=area/area_total
        confidence=max(0.0,min(1.0,.58*min(area_ratio/.65,1)+.42*rectangularity))
        points=(poly.reshape(-1,2)/scale).astype(float)
        best=(confidence,area_ratio,rectangularity,points)
        break
    if not best:
        return {'status':'UNCERTAIN','confidence':0,'corners':None,'area_ratio':0,'rectangularity':0}
    confidence,area_ratio,rectangularity,points=best
    # clockwise, start top-left
    center=points.mean(axis=0); angles=np.arctan2(points[:,1]-center[1],points[:,0]-center[0])
    points=points[np.argsort(angles)]; points=np.roll(points,-int(np.argmin(points.sum(axis=1))),axis=0)
    touches=any(x<.015*w or y<.015*h or x>.985*w or y>.985*h for x,y in points)
    return {'status':'DETECTED' if confidence>=.55 else 'UNCERTAIN','confidence':round(confidence*100,1),
            'corners':[[round(float(x),1),round(float(y),1)] for x,y in points],
            'area_ratio':round(area_ratio,4),'rectangularity':round(rectangularity,4),'touches_frame':bool(touches)}


def estimate_skew(rgb:np.ndarray)->dict:
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    # text-like edge map; calculate only near-horizontal line segments.
    edges=cv2.Canny(gray,60,170)
    min_len=max(35,int(min(gray.shape[:2])*.08))
    lines=cv2.HoughLinesP(edges,1,np.pi/180,threshold=45,minLineLength=min_len,maxLineGap=10)
    angles=[]; weights=[]
    horizontal_weight=0.0; vertical_weight=0.0
    if lines is not None:
        for line in lines[:600]:
            x1,y1,x2,y2=map(float,line[0]); dx=x2-x1;dy=y2-y1
            length=math.hypot(dx,dy)
            if length<min_len:continue
            angle=math.degrees(math.atan2(dy,dx))
            while angle<=-90:angle+=180
            while angle>90:angle-=180
            if abs(angle)<=25:
                angles.append(angle);weights.append(length);horizontal_weight+=length
            elif abs(abs(angle)-90)<=25:
                vertical_weight+=length
    skew=0.0
    if angles:
        order=np.argsort(angles); a=np.asarray(angles)[order]; wt=np.asarray(weights)[order]; cs=np.cumsum(wt)
        skew=float(a[np.searchsorted(cs,cs[-1]/2)])
    text_axis='HORIZONTAL_LIKELY' if horizontal_weight>=vertical_weight*.8 else 'ROTATED_90_POSSIBLE'
    confidence=0 if horizontal_weight+vertical_weight==0 else round(100*abs(horizontal_weight-vertical_weight)/(horizontal_weight+vertical_weight),1)
    return {'skew_angle_degrees':round(skew,2),'deskew_recommended':bool(1.5<=abs(skew)<=12),
            'text_axis':text_axis,'axis_confidence':confidence,
            'limitation':'Line orientation is advisory. Document design can contain vertical graphics/text; no automatic rotation is applied.'}


def glare_analysis(rgb:np.ndarray)->dict:
    h,w=rgb.shape[:2]
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    sat=hsv[:,:,1]; val=hsv[:,:,2]
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    texture=cv2.GaussianBlur(np.abs(gray.astype(np.float32)-cv2.GaussianBlur(gray,(0,0),2).astype(np.float32)),(9,9),0)
    # low-saturation saturated pixels with little local texture are more glare-like than ordinary white text/background.
    mask=((val>=248)&(sat<=40)&(texture<7)).astype(np.uint8)*255
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8))
    count,labels,stats,_=cv2.connectedComponentsWithStats(mask,8)
    boxes=[]; area=0
    for i in range(1,count):
        x,y,bw,bh,a=stats[i]
        frac=a/max(h*w,1)
        if frac<.0015 or frac>.20: continue
        boxes.append({'box':_norm_box(x,y,bw,bh,w,h),'area_fraction':round(float(frac),4)})
        area+=int(a)
    coverage=float(area/max(h*w,1))
    status='RECAPTURE_RECOMMENDED' if coverage>=.035 else 'REVIEW' if coverage>=.012 else 'NO_STRONG_GLARE'
    return {'status':status,'coverage':round(coverage,4),'regions':boxes[:12],
            'limitation':'Bright paper/security elements can resemble glare. This is a capture-quality signal, not document authenticity.'}


def illumination_analysis(rgb:np.ndarray)->dict:
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY).astype(np.float32)
    k=max(31,int(min(gray.shape[:2])*.06)//2*2+1)
    k=min(k,151)
    field=cv2.GaussianBlur(gray,(k,k),0)
    p10,p90=np.percentile(field,[10,90]); uneven=float(p90-p10)
    status='UNEVEN_LIGHTING' if uneven>=75 else 'MODERATE_VARIATION' if uneven>=48 else 'EVEN_ENOUGH'
    return {'status':status,'illumination_range':round(uneven,2),'p10':round(float(p10),1),'p90':round(float(p90),1)}


def analyze(rgb:np.ndarray)->dict:
    boundary=detect_boundary(rgb); skew=estimate_skew(rgb); glare=glare_analysis(rgb); illumination=illumination_analysis(rgb)
    guidance=[]
    if boundary['status']!='DETECTED':guidance.append('Keep all four document corners visible against a contrasting background.')
    elif boundary.get('touches_frame'):guidance.append('Document edge is very close to the frame. Move slightly back to avoid clipping.')
    if glare['status']=='RECAPTURE_RECOMMENDED':guidance.append('Strong saturated glare may cover text. Tilt the document or light source and recapture.')
    elif glare['status']=='REVIEW':guidance.append('Possible glare detected. Inspect affected regions before trusting OCR.')
    if illumination['status']=='UNEVEN_LIGHTING':guidance.append('Uneven lighting/shadow detected. Use diffuse lighting if possible.')
    if skew['deskew_recommended']:guidance.append(f"Document text appears skewed by about {skew['skew_angle_degrees']}°. Straighten the camera/document for best OCR.")
    if skew['text_axis']=='ROTATED_90_POSSIBLE':guidance.append('Text-line orientation may be rotated 90°. Keep text upright before capture.')
    return {'method':METHOD,'boundary':boundary,'skew':skew,'glare':glare,'illumination':illumination,'guidance':guidance,
            'geometry_policy':'OCR preprocessing variants preserve pixel geometry. Perspective/rotation correction remains preview/advisory so field evidence maps to the original.'}


def analyze_bytes(data:bytes)->dict:
    """Server-side capture analysis from original uploaded bytes."""
    with Image.open(io.BytesIO(data)) as source:
        image=ImageOps.exif_transpose(source).convert('RGB')
        image.thumbnail((2600,2600))
        return analyze(np.asarray(image))

def _mask_qr(gray:np.ndarray, regions:Iterable)->np.ndarray:
    out=gray.copy()
    for points in regions or []:
        pts=np.asarray(points,dtype=np.int32)
        if pts.shape==(4,2): cv2.fillPoly(out,[pts],255)
    return out


def ocr_variants(rgb:np.ndarray, qr_regions=None)->dict:
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    gray=_mask_qr(gray,qr_regions)
    # 1. CLAHE + conservative unsharp: good default for printed IDs.
    clahe=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(gray)
    blur=cv2.GaussianBlur(clahe,(0,0),1.0)
    sharpen=cv2.addWeighted(clahe,1.45,blur,-.45,0)
    # 2. Illumination normalization: useful for phone shadows and uneven lighting.
    k=max(31,int(min(gray.shape[:2])*.07)//2*2+1); k=min(k,151)
    background=cv2.GaussianBlur(gray,(k,k),0)
    normalized=cv2.divide(gray,np.maximum(background,1),scale=205)
    normalized=cv2.createCLAHE(clipLimit=1.8,tileGridSize=(8,8)).apply(normalized)
    # 3. Adaptive binary: fallback for faint labels/low contrast. Same dimensions/geometry.
    denoise=cv2.GaussianBlur(gray,(3,3),0)
    binary=cv2.adaptiveThreshold(denoise,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,35,13)
    # Avoid an accidentally inverted-looking page.
    if float(binary.mean())<110: binary=255-binary
    variants=[
        {'id':'clahe_sharpen','label':'CLAHE + sharpen','image':_png_data(sharpen),'geometry_preserved':True},
        {'id':'illumination_normalized','label':'Illumination normalized','image':_png_data(normalized),'geometry_preserved':True},
        {'id':'adaptive_binary','label':'Adaptive binary','image':_png_data(binary),'geometry_preserved':True},
    ]
    return {'primary':variants[0],'variants':variants,
            'method':OCR_METHOD,'limitation':'Preprocessing can help readability but can also suppress security printing. Officer review must use the original image.'}


def glare_overlay(rgb:np.ndarray, glare:dict)->str:
    image=Image.fromarray(rgb.copy());draw=ImageDraw.Draw(image);w,h=image.size
    for item in glare.get('regions',[]):
        x,y,bw,bh=item['box'];box=(int(x*w),int(y*h),int((x+bw)*w),int((y+bh)*h))
        draw.rectangle(box,outline='#ff7a00',width=max(2,round(min(w,h)/300)))
    out=io.BytesIO();image.save(out,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()
