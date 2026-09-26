"""Read-only release integrity check. No extraction or private data access."""
import argparse,hashlib,json,zipfile
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('zip');args=parser.parse_args()
path=Path(args.zip)
with zipfile.ZipFile(path) as archive:
    names=archive.namelist();assert len(names)==len(set(names)),'Duplicate members'
    assert archive.testzip() is None,'CRC failure'
    assert all(n.startswith('BHARATSHIELD/') and '..' not in Path(n).parts for n in names)
    prohibited={'private','node_modules','.venv','venv','__pycache__','.git'}
    assert not any(prohibited.intersection(Path(n).parts) for n in names),'Private/development directory'
    assert not any(Path(n).suffix in {'.key','.pem','.db','.sqlite','.sqlite3','.bsbackup'} for n in names),'Sensitive file'
    prefix='BHARATSHIELD/';manifest=json.loads(archive.read(prefix+'RELEASE_SHA256.json'))
    assert set(names)=={prefix+n for n in manifest}|{prefix+'RELEASE_SHA256.json'},'Manifest/member mismatch'
    for name,digest in manifest.items():assert hashlib.sha256(archive.read(prefix+name)).hexdigest()==digest,name
    for required in ['UPGRADE_V71.md','RELEASE_NOTES_V71.md','UPGRADE_V70.md','RELEASE_NOTES_V70.md','FRONTEND_FEATURE_MAP_V70.md','src/console/DecisionBoundary.jsx','src/console/DemoReadiness.jsx','src/console/EvidencePanels.jsx','src/console/RegistryGraph.jsx','UPGRADE_V69.md','RELEASE_NOTES_V69.md','SIH26188_DEMO_RUNBOOK_V69.md','START_SIH_DEMO.bat','backend/demo_preflight.py','backend/app/demo_hardening.py','backend/tests/test_v69.py','UPGRADE_V68.md','RELEASE_NOTES_V68.md','backend/app/checkpoint_center.py','backend/tests/test_v68.py','UPGRADE_V67.md','RELEASE_NOTES_V67.md','backend/app/travel_intelligence.py','backend/tests/test_v67.py','demo_samples/travel_intelligence/01_clean_multiple_entry_visa.png','demo_samples/travel_intelligence/02_single_entry_overused_visa.png','demo_samples/travel_intelligence/03_duration_exceeded_visa.png','UPGRADE_V66.md','RELEASE_NOTES_V66.md','backend/app/visual_security.py','backend/tests/test_v66.py','demo_samples/visual_security/01_template_features_present.png','backend/reference_templates/v66/manifest.json','backend/reference_templates/v66/ind_passport_emblem.png','backend/reference_templates/v66/ind_passport_header.png','backend/reference_templates/v66/ind_passport_rosette.png','demo_samples/visual_security/02_template_features_missing.png','demo_samples/visual_security/03_emblem_moved.png','UPGRADE_V65.md','RELEASE_NOTES_V65.md','backend/app/registry_v2.py','backend/tests/test_v65.py','demo_samples/registry2/01_clean_travel_authorization.png','UPGRADE_V64.md','RELEASE_NOTES_V64.md','backend/app/template_layout.py','backend/tests/test_v64.py','demo_samples/layout_security/01_layout_consistent.png','UPGRADE_V63.md','RELEASE_NOTES_V63.md','backend/app/capture_intelligence.py','backend/tests/test_v63.py','demo_samples/ocr_capture/01_shadow_low_contrast.png','UPGRADE_V62.md','RELEASE_NOTES_V62.md','backend/app/document_type.py','backend/tests/test_v62.py','src/documentTypeDetector.js','UPGRADE_V61.md','RELEASE_NOTES_V61.md','backend/app/biometric_history.py','backend/tests/test_v61.py','UPGRADE_V60.md','RELEASE_NOTES_V60.md','backend/app/visa_intelligence.py','demo_samples/visa_intelligence/01_visa_clean.png','UPGRADE_V59.md','RELEASE_NOTES_V59.md','backend/app/active_liveness.py','src/LivenessCameraCapture.jsx','UPGRADE_V58.md','RELEASE_NOTES_V58.md','backend/app/photo_substitution.py','UPGRADE_V57.md','RELEASE_NOTES_V57.md','DEMO_VIDEO_GUIDE_V56.md','backend/app/risk_policy.py','demo_samples/video_demo/01_active_match.png','OCR_BENCHMARK_V56.json','src/OptionalPersonCheck.jsx','src/LiveCameraCapture.jsx','src/SupervisorAcceptance.jsx','src/DocumentInspector.jsx','src/fieldGeometry.js','dist/index.html','dist/ocr/worker.min.js','dist/ocr/tessdata/eng.traineddata.gz','backend/trust/demo_issuers.json']:
        assert required in manifest,required
    assert any(n.startswith('dist/ocr/core/') and n.endswith('.wasm.js') for n in manifest)
    assert len([n for n in manifest if n.endswith('.onnx')])>=2
    import re
    html=archive.read(prefix+'dist/index.html').decode()
    entries=re.findall(r'<script[^>]+src="([^"]+)"',html)
    assert len(entries)==1 and entries[0].startswith('/assets/'),'Expected one compiled entry'
    assert 'dist'+entries[0] in manifest,'Missing compiled entry'
    assert not any(re.match(r'dist/v[56]\d-.*\.js$',n) for n in manifest),'Retired enhancement present'
    assert not any('MutationObserver' in archive.read(prefix+n).decode() for n in manifest if n.startswith('src/') and n.endswith(('.js','.jsx'))),'DOM observer enhancement present' 
    assert json.loads(archive.read(prefix+'package.json'))['version']=='7.1.0'
print(json.dumps({'verified':True,'files':len(names),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
