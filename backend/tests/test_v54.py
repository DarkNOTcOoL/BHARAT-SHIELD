import io,json,base64,hashlib
import cv2
import numpy as np
from PIL import Image
from app import intake,main
from test_local import upload,image_bytes

def test_alignment_preview_maps_corners_and_retains_original():
    image=Image.new('RGB',(1000,700),'white');before=hashlib.sha256(intake.png(image)).hexdigest()
    result=intake.alignment_preview(image,[[100,70],[900,100],[850,650],[80,600]])
    assert result['used_for_ocr'] is False and result['status']=='CANDIDATE_PREVIEW_ONLY'
    matrix=np.array(result['source_to_preview']);inverse=np.array(result['preview_to_source'])
    assert np.allclose(matrix@inverse,np.eye(3),atol=1e-6)
    mapped=cv2.perspectiveTransform(np.float32([result['source_corners']]),matrix)[0]
    w,h=result['preview_dimensions'];assert np.allclose(mapped,[[0,0],[w-1,0],[w-1,h-1],[0,h-1]],atol=.01)
    preview=Image.open(io.BytesIO(base64.b64decode(result['image'].split(',')[1])))
    assert list(preview.size)==result['preview_dimensions']
    assert hashlib.sha256(intake.png(image)).hexdigest()==before

def test_alignment_rejects_missing_degenerate_and_out_of_bounds():
    image=Image.new('RGB',(1000,700),'white')
    for corners in [None,[[0,0]]*4,[[-1,0],[900,0],[900,600],[0,600]],[[10,10],[20,10],[20,20],[10,20]]]:
        assert intake.alignment_preview(image,corners) is None

def test_repeat_region_boxes_are_normalized_and_not_a_verdict():
    rng=np.random.default_rng(54);patch=rng.integers(0,256,(220,220),dtype=np.uint8)
    pixels=np.full((700,1000),230,dtype=np.uint8);pixels[100:320,100:320]=patch;pixels[380:600,650:870]=patch
    result=intake.forensic(intake.png(Image.fromarray(pixels)))
    repeats=[r for r in result['inspection_regions'] if r.get('source')=='ORB_REPEATED_FEATURE_CLUSTER']
    assert len(repeats)==2
    for r in repeats:
        x,y,w,h=r['box'];assert 0<=x<x+w<=1.00001 and 0<=y<y+h<=1.00001
        assert r['status']=='MANUAL_INSPECTION_ONLY'
    assert result['tamper_ai']['method']=='LOCAL_UNSUPERVISED_PATCH_ANOMALY_V57'
    assert result['authenticity']=='NOT_DETERMINED'
    assert intake.forensic(image_bytes(blank=True))['inspection_regions']==[]

def test_saved_geometry_survives_without_changing_tamper_coverage(client):
    notes=json.dumps({'field_boxes':[{'field':'documentNumber','text':'ABCDE1234F','box':[.1,.2,.3,.1],'confidence':90}],'geometry_frame':'NORMALIZED_EXIF_ORIENTED_ORIGINAL'})
    response=upload(client,ocr_notes=notes);assert response.status_code==200
    a=response.json()['screenings'][0]['result']['ai_analysis']
    assert json.loads(a['extraction']['intake_notes_browser_supplied'])['field_boxes'][0]['box']==[.1,.2,.3,.1]
    assert a['checks']['tampering'] in {'COMPLETE','INCONCLUSIVE'}
    assert a['engine_version']==main.ENGINE_VERSION
