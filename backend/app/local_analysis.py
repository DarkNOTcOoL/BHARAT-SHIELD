"""Offline image measurements and optional local face inference.
Quality thresholds are prototype heuristics, not fraud probabilities.
No model downloading, telemetry, web clients, or external inference.
"""
import hashlib
import io
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException

MODEL_DIR = Path(__file__).resolve().parents[1] / 'models'
Image.MAX_IMAGE_PIXELS = 20_000_000

def decode(data):
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in {'JPEG','PNG','WEBP'}: raise ValueError('Unsupported image format')
            if source.width * source.height > 20_000_000: raise ValueError('Image exceeds 20 megapixels')
            source.load()
            return ImageOps.exif_transpose(source).convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(400,'Invalid image. Use a JPG, PNG or WEBP up to 20 megapixels.') from exc

def quality(data):
    image = decode(data)
    small = image.copy(); small.thumbnail((1400,1400))
    rgb = np.asarray(small)
    gray = cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    blur = float(cv2.Laplacian(gray,cv2.CV_64F).var())
    contrast = float(np.std(gray))
    brightness = float(gray.mean())
    issues=[]
    if min(image.size)<400: issues.append('LOW_RESOLUTION')
    if blur<35: issues.append('BLUR_OR_LOW_DETAIL')
    if contrast<15: issues.append('LOW_CONTRAST')
    if brightness<35: issues.append('UNDEREXPOSED')
    if brightness>245: issues.append('OVEREXPOSED')
    return {'status':'RECAPTURE' if issues else 'USABLE','width':image.width,'height':image.height,
            'laplacian_variance':round(blur,2),'contrast':round(contrast,2),'brightness':round(brightness,2),
            'issues':issues,'method':'Local OpenCV quality heuristics v1',
            'limitation':'These thresholds require calibration for the capture device. Quality is not authenticity.'}

def residual_image(data):
    """JPEG recompression residual for manual inspection only; not tamper localization."""
    image=decode(data); image.thumbnail((1400,1400))
    buf=io.BytesIO(); image.save(buf,format='JPEG',quality=90)
    rec=np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert('RGB')).astype(np.float32)
    residual=np.abs(np.asarray(image).astype(np.float32)-rec).max(axis=2)
    scale=max(float(np.percentile(residual,99)),1.0)
    mapped=np.uint8(np.clip(residual/scale*255,0,255))
    heat=cv2.applyColorMap(mapped,cv2.COLORMAP_INFERNO)
    out=io.BytesIO(); Image.fromarray(cv2.cvtColor(heat,cv2.COLOR_BGR2RGB)).save(out,format='PNG')
    return out.getvalue()

def model_status():
    files={'detector':'face_detection_yunet_2023mar.onnx','recognizer':'face_recognition_sface_2021dec.onnx'}
    return {'status':'AVAILABLE' if all((MODEL_DIR/f).is_file() for f in files.values()) else 'MODEL_FILES_REQUIRED',
            'files':{k:{'filename':f,'present':(MODEL_DIR/f).is_file()} for k,f in files.items()},
            'liveness':'ACTIVE_CHALLENGE_AVAILABLE','thresholds':'UNVALIDATED_DEMO'}

def compare_faces(document,live):
    if model_status()['status']!='AVAILABLE':
        return {'status':'NOT_RUN','reason':'Local YuNet and SFace ONNX files are required. No download was attempted.','liveness':'NOT_RUN'}
    try:
        detector=cv2.FaceDetectorYN.create(str(MODEL_DIR/'face_detection_yunet_2023mar.onnx'),'',(320,320),0.9)
        recognizer=cv2.FaceRecognizerSF.create(str(MODEL_DIR/'face_recognition_sface_2021dec.onnx'),'')
        features=[]; boxes=[];regions={};counts={};quality_checks={}
        for label,data in [('document',document),('person',live)]:
            image=decode(data); image.thumbnail((1600,1600))
            bgr=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR)
            detector.setInputSize((bgr.shape[1],bgr.shape[0]))
            _,faces=detector.detect(bgr)
            counts[label]=0 if faces is None else len(faces)
            if faces is None or len(faces)!=1:
                return {'status':'INCONCLUSIVE','reason':f'{label.title()} image contains {counts[label]} detected faces. Exactly one is required. Use a clear document portrait or recapture the person alone.','face_counts':counts,'liveness':'NOT_RUN'}
            face=faces[0]
            if min(face[2],face[3])<60:
                return {'status':'INCONCLUSIVE','reason':f'{label.title()} face crop is too small. Recapture closer.','face_counts':counts,'liveness':'NOT_RUN'}
            aligned=recognizer.alignCrop(bgr,face)
            gray_face=cv2.cvtColor(aligned,cv2.COLOR_BGR2GRAY)
            blur=float(cv2.Laplacian(gray_face,cv2.CV_64F).var())
            brightness=float(gray_face.mean())
            face_fraction=float((face[2]*face[3])/max(bgr.shape[0]*bgr.shape[1],1))
            qissues=[]
            if blur<28:qissues.append('BLUR_OR_LOW_DETAIL')
            if brightness<35:qissues.append('UNDEREXPOSED')
            if brightness>235:qissues.append('OVEREXPOSED')
            if face_fraction<0.012:qissues.append('FACE_TOO_SMALL_IN_FRAME')
            quality_checks[label]={'status':'USABLE' if not qissues else 'RECAPTURE','blur':round(blur,2),'brightness':round(brightness,2),'face_fraction':round(face_fraction,4),'issues':qissues}
            if label=='person' and qissues:
                return {'status':'INCONCLUSIVE','reason':'Person capture quality requires recapture: '+', '.join(qissues)+'.','face_counts':counts,'face_quality':quality_checks,'liveness':'NOT_RUN'}
            features.append(recognizer.feature(aligned).copy())
            boxes.append([float(v) for v in face[:4]])
            x,y,w,h=[float(v) for v in face[:4]]
            left=max(0,min(x,image.width));top=max(0,min(y,image.height));right=max(left,min(x+w,image.width));bottom=max(top,min(y+h,image.height))
            regions[label]={'box':[left/image.width,top/image.height,(right-left)/image.width,(bottom-top)/image.height],
                            'frame':'NORMALIZED_EXIF_ORIENTED_ORIGINAL','working_dimensions':list(image.size)}
        score=float(recognizer.match(features[0],features[1],cv2.FaceRecognizerSF_FR_COSINE))
        if not np.isfinite(score):return {'status':'MODEL_ERROR','reason':'Model returned an invalid similarity value.','liveness':'NOT_RUN'}
        # Deliberately no match/mismatch identity decision until site-specific calibration exists.
        return {'status':'REVIEW_REQUIRED','cosine_similarity':round(score,4),'boxes':boxes,
                'face_regions':regions,'face_counts':counts,'face_quality':quality_checks,
                'reason':'Quality-gated SFace similarity measurement. Officer review required; no identity conclusion. Run the separate active liveness challenge for replay resistance.',
                'liveness':'NOT_RUN','liveness_available':True,'similarity_interpretation':'REVIEW_ONLY_UNCALIBRATED','model':'YuNet + SFace',
                'model_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [MODEL_DIR/'face_detection_yunet_2023mar.onnx',MODEL_DIR/'face_recognition_sface_2021dec.onnx']}}
    except cv2.error:
        return {'status':'MODEL_ERROR','reason':'Local models could not run. Check ONNX files and OpenCV compatibility.','liveness':'NOT_RUN'}

def extract_face_embedding(data, *, require_quality=True):
    """Extract one normalized local SFace template from an image.

    The caller decides whether/how to persist it. Raw image bytes are not returned.
    This is a biometric template, not an identity verdict.
    """
    if model_status()['status']!='AVAILABLE':
        return {'status':'MODEL_UNAVAILABLE','reason':'Local YuNet and SFace ONNX files are required. No download was attempted.'}
    try:
        detector=cv2.FaceDetectorYN.create(str(MODEL_DIR/'face_detection_yunet_2023mar.onnx'),'',(320,320),0.9)
        recognizer=cv2.FaceRecognizerSF.create(str(MODEL_DIR/'face_recognition_sface_2021dec.onnx'),'')
        image=decode(data); image.thumbnail((1600,1600))
        bgr=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR)
        detector.setInputSize((bgr.shape[1],bgr.shape[0]))
        _,faces=detector.detect(bgr)
        count=0 if faces is None else len(faces)
        if faces is None or len(faces)!=1:
            return {'status':'INCONCLUSIVE','reason':f'Image contains {count} detected faces. Exactly one is required.','face_count':count}
        face=faces[0]
        if min(face[2],face[3])<60:
            return {'status':'INCONCLUSIVE','reason':'Face crop is too small. Recapture closer.','face_count':count}
        aligned=recognizer.alignCrop(bgr,face)
        gray=cv2.cvtColor(aligned,cv2.COLOR_BGR2GRAY)
        blur=float(cv2.Laplacian(gray,cv2.CV_64F).var());brightness=float(gray.mean())
        face_fraction=float((face[2]*face[3])/max(bgr.shape[0]*bgr.shape[1],1))
        issues=[]
        if blur<28:issues.append('BLUR_OR_LOW_DETAIL')
        if brightness<35:issues.append('UNDEREXPOSED')
        if brightness>235:issues.append('OVEREXPOSED')
        if face_fraction<0.012:issues.append('FACE_TOO_SMALL_IN_FRAME')
        if require_quality and issues:
            return {'status':'INCONCLUSIVE','reason':'Face quality requires recapture: '+', '.join(issues)+'.','face_count':count,
                    'face_quality':{'status':'RECAPTURE','blur':round(blur,2),'brightness':round(brightness,2),'face_fraction':round(face_fraction,4),'issues':issues}}
        feature=np.asarray(recognizer.feature(aligned),dtype=np.float32).reshape(-1)
        norm=float(np.linalg.norm(feature))
        if not np.isfinite(norm) or norm<=1e-12:
            return {'status':'MODEL_ERROR','reason':'SFace returned an invalid face template.'}
        feature=feature/norm
        x,y,w,h=[float(v) for v in face[:4]]
        left=max(0,min(x,image.width));top=max(0,min(y,image.height));right=max(left,min(x+w,image.width));bottom=max(top,min(y+h,image.height))
        return {
            'status':'TEMPLATE_READY','embedding':feature,
            'face_count':count,
            'face_quality':{'status':'USABLE' if not issues else 'REVIEW','blur':round(blur,2),'brightness':round(brightness,2),'face_fraction':round(face_fraction,4),'issues':issues},
            'face_region':{'box':[left/image.width,top/image.height,(right-left)/image.width,(bottom-top)/image.height],'frame':'NORMALIZED_EXIF_ORIENTED_ORIGINAL'},
            'model':'YuNet + SFace','model_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [MODEL_DIR/'face_detection_yunet_2023mar.onnx',MODEL_DIR/'face_recognition_sface_2021dec.onnx']},
            'meaning':'Normalized SFace biometric template for local similarity retrieval only.'
        }
    except cv2.error:
        return {'status':'MODEL_ERROR','reason':'Local models could not run. Check ONNX files and OpenCV compatibility.'}
