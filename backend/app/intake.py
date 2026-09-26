"""Local image preparation and experimental forensic inspection, never an authenticity verdict."""
import base64,io,hashlib,time
import cv2
import numpy as np
from PIL import Image,ImageOps,ImageDraw
from . import local_analysis, tamper_ai, photo_substitution, visa_intelligence, capture_intelligence, template_layout, visual_security

def png(image):
    out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()

def alignment_preview(image, boundary):
    """Candidate perspective view only; never replaces OCR input or evidence bytes."""
    if boundary is None:return None
    points=np.asarray(boundary,dtype=np.float32)
    if points.shape!=(4,2) or not np.isfinite(points).all():return None
    if (points<0).any() or (points[:,0]>=image.width).any() or (points[:,1]>=image.height).any():return None
    # Order around centroid, then choose the top-left starting point.
    center=points.mean(axis=0);angles=np.arctan2(points[:,1]-center[1],points[:,0]-center[0])
    points=points[np.argsort(angles)];points=np.roll(points,-int(np.argmin(points.sum(axis=1))),axis=0)
    if not cv2.isContourConvex(points.reshape(-1,1,2)) or cv2.contourArea(points)<.1*image.width*image.height:return None
    tl,tr,br,bl=points
    width=int(round(max(np.linalg.norm(tr-tl),np.linalg.norm(br-bl))))
    height=int(round(max(np.linalg.norm(bl-tl),np.linalg.norm(br-tr))))
    if min(width,height)<80 or max(width,height)>4000:return None
    destination=np.float32([[0,0],[width-1,0],[width-1,height-1],[0,height-1]])
    matrix=cv2.getPerspectiveTransform(points,destination)
    if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix))<1e-9:return None
    result=cv2.warpPerspective(np.asarray(image),matrix,(width,height))
    return {'status':'CANDIDATE_PREVIEW_ONLY','image':'data:image/png;base64,'+base64.b64encode(png(Image.fromarray(result))).decode(),
            'source_dimensions':list(image.size),'preview_dimensions':[width,height],
            'source_corners':points.tolist(),'source_to_preview':matrix.tolist(),
            'preview_to_source':np.linalg.inv(matrix).tolist(), 'used_for_ocr':False}

def prepare(data):
    """Create same-geometry OCR variants plus capture-quality guidance.

    Perspective/orientation transforms stay preview-only in v6.3 so browser OCR boxes remain
    mapped to the EXIF-normalized original evidence frame.
    """
    started=time.perf_counter();image=local_analysis.decode(data);original_size=image.size
    image.thumbnail((2600,2600))
    if max(image.size)<1200:
        scale=min(2,1600/max(image.size));image=image.resize((round(image.width*scale),round(image.height*scale)),Image.Resampling.LANCZOS)
    array=np.asarray(image);regions=[];messages=[]
    try:
        import zxingcpp
        for code in zxingcpp.read_barcodes(array,formats=zxingcpp.BarcodeFormat.QRCode):
            pos=code.position;points=[pos.top_left,pos.top_right,pos.bottom_right,pos.bottom_left]
            regions.append([(int(p.x),int(p.y)) for p in points])
    except ImportError:messages.append('QR exclusion unavailable: install zxing-cpp. Original pixels retained.')
    except Exception:messages.append('QR localization failed; original pixels retained for OCR.')
    if not regions:
        try:
            found,points=cv2.QRCodeDetector().detectMulti(array)
            if found:regions=[[(int(x),int(y)) for x,y in quad] for quad in points]
        except cv2.error:pass

    capture=capture_intelligence.analyze(array)
    variants=capture_intelligence.ocr_variants(array,regions)
    q=local_analysis.quality(data)
    advice={'LOW_RESOLUTION':'Move closer; keep the entire document in frame.','BLUR_OR_LOW_DETAIL':'Hold the camera steady, focus on small text and recapture.','LOW_CONTRAST':'Use even lighting and avoid shadows.','UNDEREXPOSED':'Increase lighting without shining directly on the document.','OVEREXPOSED':'Reduce exposure; avoid reflections. White paper can also trigger this heuristic.'}
    messages.extend(advice[x] for x in q['issues'])
    messages.extend(capture.get('guidance') or [])
    boundary=(capture.get('boundary') or {}).get('corners')
    if boundary is None:messages.append('Document boundary uncertain. Automatic geometric crop is not applied to OCR evidence.')
    else:messages.append('Four-corner document candidate found. Perspective correction is preview-only so OCR field geometry remains tied to the original.')
    messages.append('v6.3 OCR uses same-geometry enhancement variants. If the primary read is weak, the browser can retry local Tesseract on illumination-normalized/adaptive variants.')
    primary=variants['primary']['image']
    metadata={'method':'ADVANCED_SAME_GEOMETRY_OCR_PREP_V63','original_sha256':hashlib.sha256(data).hexdigest(),
              'original_dimensions':list(original_size),'working_dimensions':list(image.size),'qr_regions':regions,
              'boundary_candidate':boundary,'boundary_confidence':(capture.get('boundary') or {}).get('confidence',0),
              'quality':q,'capture_intelligence':capture,'ocr_preprocessing':{'method':variants['method'],'primary':variants['primary']['id'],'variant_ids':[v['id'] for v in variants['variants']],'geometry_preserved':True},
              'guidance':messages,'elapsed_ms':round((time.perf_counter()-started)*1000,1),
              'limitation':'OCR working copies preserve geometry but alter contrast/tonality. Perspective/orientation correction remains preview-only. Compare all extracted fields with the original; capture signals are not authenticity evidence.'}
    return {'image':primary,
            'ocr_variants':variants['variants'],
            'alignment_preview':alignment_preview(image,boundary),
            'glare_preview':capture_intelligence.glare_overlay(array,capture.get('glare') or {}),
            'original_working_image':('data:image/png;base64,'+base64.b64encode(png(image)).decode()) if regions else None,
            'metadata':metadata}

def forensic(data,view=None,ocr_notes=None,document_type=None,ocr_text=None,issuer_profile=None):
    started=time.perf_counter();image=local_analysis.decode(data);image.thumbnail((1200,1200))
    rgb=np.asarray(image);gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    tamper_result,tamper_overlay=tamper_ai.analyze(rgb,ocr_notes)
    photo_result,photo_overlay=photo_substitution.analyze(rgb,tamper_result.get('inspection_regions') or [])
    stamp_result,stamp_overlay=visa_intelligence.analyze_stamp_seal(rgb,tamper_result.get('inspection_regions') or [],enabled=document_type=='Visa')
    layout_result,layout_overlay=template_layout.analyze(rgb,document_type or 'National ID',ocr_notes,photo_result,ocr_text or '')
    visual_result,visual_overlay=visual_security.analyze(rgb,issuer_profile)
    if view in {'anomaly','tamper-ai'}:
        return png(Image.fromarray(tamper_overlay))
    if view in {'photo','photo-integrity','photo-substitution'}:
        return png(Image.fromarray(photo_overlay))
    if view in {'stamp','stamp-integrity','visa-stamp'}:
        return png(Image.fromarray(stamp_overlay))
    if view in {'layout','template-layout','security-zones'}:
        return png(Image.fromarray(layout_overlay))
    if view in {'visual-security','issuer-template','issuer-features'}:
        return png(Image.fromarray(visual_overlay))
    high=np.abs(gray.astype(np.float32)-cv2.GaussianBlur(gray,(5,5),0).astype(np.float32))
    texture=cv2.GaussianBlur(high,(31,31),0)
    if view=='texture':
        scale=max(float(np.percentile(texture,99)),1)
        heat=cv2.applyColorMap(np.uint8(np.clip(texture/scale*255,0,255)),cv2.COLORMAP_INFERNO)
        overlay=cv2.addWeighted(rgb,.6,cv2.cvtColor(heat,cv2.COLOR_BGR2RGB),.4,0)
    # Repeated local-feature candidates; ordinary security patterns/text also repeat.
    pairs=[];detector=cv2.ORB_create(nfeatures=700);keypoints,descriptors=detector.detectAndCompute(gray,None)
    if descriptors is not None and len(descriptors)>8:
        groups={}
        for matches in cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(descriptors,descriptors,k=5):
            for m in matches:
                if m.queryIdx>=m.trainIdx or m.distance>24:continue
                a=np.array(keypoints[m.queryIdx].pt);b=np.array(keypoints[m.trainIdx].pt);delta=b-a
                if np.linalg.norm(delta)<80:continue
                if delta[0]<0:a,b=b,a;delta=-delta
                group=tuple(np.round(delta/24).astype(int));groups.setdefault(group,[]).append((a,b));break
        if groups:
            best=max(groups.values(),key=len)
            if len(best)>=6:pairs=[{'a':[round(float(v),1) for v in a],'b':[round(float(v),1) for v in b]} for a,b in best[:20]]
    regions=[]
    if pairs:
        for side in ['a','b']:
            points=np.array([p[side] for p in pairs]);lo=np.maximum(points.min(axis=0)-14,0);hi=np.minimum(points.max(axis=0)+14,[image.width,image.height])
            regions.append({'field':'repeat_'+side,'box':[round(float(lo[0]/image.width),6),round(float(lo[1]/image.height),6),round(float((hi[0]-lo[0])/image.width),6),round(float((hi[1]-lo[1])/image.height),6)],
                            'source':'ORB_REPEATED_FEATURE_CLUSTER','status':'MANUAL_INSPECTION_ONLY'})
    photo_regions=(photo_result.get('inspection_regions') or []) if photo_result.get('status')=='REVIEW_REQUIRED' else []
    stamp_regions=(stamp_result.get('inspection_regions') or [])
    layout_regions=(layout_result.get('inspection_regions') or [])
    visual_regions=(visual_result.get('inspection_regions') or [])
    all_regions=(tamper_result.get('inspection_regions') or []) + photo_regions + stamp_regions + layout_regions + visual_regions + regions
    ai_review=tamper_result.get('status')=='REVIEW_REQUIRED' or photo_result.get('status')=='REVIEW_REQUIRED' or stamp_result.get('status')=='REVIEW_REQUIRED' or layout_result.get('status')=='REVIEW_REQUIRED' or visual_result.get('status')=='REVIEW_REQUIRED'
    result={'method':'LOCAL_FORENSIC_FUSION_V66','status':'AI_REVIEW_REQUIRED' if ai_review else ('MANUAL_INSPECTION_REQUIRED' if pairs else 'NO_STRONG_INDICATOR'),
            'inspection_regions':all_regions,'geometry_frame':'NORMALIZED_EXIF_ORIENTED_ORIGINAL',
            'authenticity':'NOT_DETERMINED','copy_move_candidates':pairs,'working_dimensions':list(image.size),
            'tamper_ai':tamper_result,'photo_substitution':photo_result,'stamp_seal':stamp_result,'template_layout':layout_result,'issuer_visual_security':visual_result,
            'texture_residual_mean':round(float(texture.mean()),2),'processing_ms':round((time.perf_counter()-started)*1000,1),
            'limitations':['The AI-assisted anomaly score is a within-document statistical outlier index, not a fraud probability or authenticity verdict.',
                          'Layout/security-zone analysis uses broad family rules and OCR geometry; it is not issuer-template authentication.',
                          'Issuer visual-feature matching is only against bundled synthetic demo references; it is not official issuer authentication or hologram/UV/IR verification.',
                          'Repeated features can be legitimate print, QR patterns or security backgrounds. Candidates are not proof of copy-move editing.',
                          'Texture heatmap shows local high-frequency energy, including ordinary text and edges; it remains an inspection aid.',
                          'JPEG residual is a recompression visualization, not an authenticity test. Scans and screenshots can conceal editing traces.',
                          'Stamp/seal analysis is country-agnostic CV/forensic assistance and does not authenticate issuer stamps.',
                          'Photo-substitution analysis uses YuNet localization plus uncalibrated local forensic cues; it is not a universal replacement-photo classifier.',
                          'No calibrated universal forgery classifier or issuer-authenticating stamp classifier. Active head-turn liveness is prototype replay resistance, not certified PAD. Absence of indicators does not establish genuineness.']}
    if view=='texture':return png(Image.fromarray(overlay))
    if view=='repeats':
        canvas=image.copy();draw=ImageDraw.Draw(canvas)
        for pair in pairs:
            a,b=tuple(pair['a']),tuple(pair['b']);draw.line([a,b],fill='#e02020',width=3)
            for x,y in [a,b]:draw.ellipse((x-9,y-9,x+9,y+9),outline='#e02020',width=3)
        return png(canvas)
    return result

def install(app):
    from fastapi import UploadFile,File,HTTPException
    @app.post('/api/intake/prepare')
    async def prepare_upload(file:UploadFile=File(...)):
        data=await file.read(10*1024*1024+1)
        if len(data)>10*1024*1024:raise HTTPException(400,'Image must be at most 10 MiB.')
        return prepare(data)
