import numpy as np
import cv2
from app import photo_substitution, risk_policy


def _portrait_fixture(altered=False):
    h,w=700,1100
    rng=np.random.default_rng(7)
    base=np.full((h,w,3),228,np.uint8)
    base=np.clip(base.astype(np.int16)+rng.normal(0,2,base.shape).astype(np.int16),0,255).astype(np.uint8)
    for y in range(70,630,55):
        cv2.line(base,(430,y),(980,y),(45,45,45),2)
    box=(80,130,260,360)
    patch=np.full((360,260,3),190,np.uint8)
    patch=np.clip(patch.astype(np.int16)+rng.normal(0,4,patch.shape).astype(np.int16),0,255).astype(np.uint8)
    yy,xx=np.ogrid[:360,:260]
    mask=((xx-130)**2/70**2+(yy-150)**2/100**2)<1
    patch[mask]=np.clip(patch[mask].astype(np.int16)-45,0,255)
    if altered:
        patch=np.full_like(patch,150)
        patch=np.clip(patch.astype(np.int16)+rng.normal(0,30,patch.shape).astype(np.int16),0,255).astype(np.uint8)
    base[130:490,80:340]=patch
    return base,box,(135,190,110,145)


def test_photo_substitution_region_is_multi_cue_and_conservative():
    clean,box,face=_portrait_fixture(False)
    normal,_=photo_substitution.analyze_region(clean,box,face_box=face,tamper_regions=[])
    assert normal['status']=='NO_STRONG_PHOTO_SUBSTITUTION_SIGNAL'
    assert normal['photo_integrity_index']<55

    altered,box,face=_portrait_fixture(True)
    h,w=altered.shape[:2]
    tamper=[{'box':[box[0]/w,box[1]/h,box[2]/w,box[3]/h],'anomaly_score':96}]
    suspicious,_=photo_substitution.analyze_region(altered,box,face_box=face,tamper_regions=tamper)
    assert suspicious['status']=='REVIEW_REQUIRED'
    assert 'HARD_RECTANGULAR_BOUNDARY' in suspicious['cues']
    assert 'OVERLAPPING_TAMPER_ANOMALY' in suspicious['cues']
    assert 'NOT a probability' in suspicious['score_meaning']


def test_photo_and_generic_tamper_do_not_double_count_forensic_family():
    fields={'name':'DEMO PERSON','document_number':'DEMO1','dob':'2000-01-01','nationality':'IND','issuer_country':'IND'}
    findings=[{'code':'AI_TAMPER_ANOMALY'},{'code':'PHOTO_SUBSTITUTION_REVIEW'}]
    score=risk_policy.assess({'status':'MATCH','fields':[]},{},findings,fields,{'status':'USABLE'},95,'NOT_APPLICABLE')
    assert score['score']==30
    assert score['factors'][0]['group']=='forensic_integrity'
    assert 'avoid double counting' in score['method']
