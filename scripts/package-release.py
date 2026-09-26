"""Create a distributable with no private state, credentials or virtual environments."""
import argparse,hashlib,json,os,zipfile
from pathlib import Path
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];out=Path(args.out).resolve()
    if root in out.parents or out.exists():raise SystemExit('Choose a NEW output ZIP outside the project.')
    excluded={'private','node_modules','.venv','venv','__pycache__','.pytest_cache','.git','.vite','.env','RELEASE_SHA256.json'}
    sensitive={'.key','.pem','.db','.sqlite','.sqlite3','.bsbackup','.pyc'}
    files=[]
    for directory,dirs,names in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if d not in excluded and not (Path(directory)/d).is_symlink()]
        # Runtime assets are already included under dist/ocr; npm postinstall recreates
        # public/ocr for developers. Avoid distributing a second identical copy.
        if Path(directory)==root/'public':dirs[:]=[d for d in dirs if d!='ocr']
        for name in names:
            path=Path(directory)/name
            if name in excluded or path.is_symlink() or path.suffix in sensitive or name.endswith(('-wal','-shm','-journal')):continue
            files.append(path)
    manifest={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    required=['dist/index.html','UPGRADE_V71.md','RELEASE_NOTES_V71.md','UPGRADE_V70.md','RELEASE_NOTES_V70.md','FRONTEND_FEATURE_MAP_V70.md','src/console/DecisionBoundary.jsx','src/console/DemoReadiness.jsx','src/console/EvidencePanels.jsx','src/console/RegistryGraph.jsx','UPGRADE_V69.md','RELEASE_NOTES_V69.md','SIH26188_DEMO_RUNBOOK_V69.md','START_SIH_DEMO.bat','backend/demo_preflight.py','backend/app/demo_hardening.py','backend/tests/test_v69.py','UPGRADE_V68.md','RELEASE_NOTES_V68.md','backend/app/checkpoint_center.py','backend/tests/test_v68.py','UPGRADE_V67.md','RELEASE_NOTES_V67.md','backend/app/travel_intelligence.py','backend/tests/test_v67.py','demo_samples/travel_intelligence/01_clean_multiple_entry_visa.png','demo_samples/travel_intelligence/02_single_entry_overused_visa.png','demo_samples/travel_intelligence/03_duration_exceeded_visa.png','UPGRADE_V66.md','RELEASE_NOTES_V66.md','backend/app/visual_security.py','backend/tests/test_v66.py','demo_samples/visual_security/01_template_features_present.png','backend/reference_templates/v66/manifest.json','backend/reference_templates/v66/ind_passport_emblem.png','backend/reference_templates/v66/ind_passport_header.png','backend/reference_templates/v66/ind_passport_rosette.png','demo_samples/visual_security/02_template_features_missing.png','demo_samples/visual_security/03_emblem_moved.png','UPGRADE_V65.md','RELEASE_NOTES_V65.md','backend/app/registry_v2.py','backend/tests/test_v65.py','demo_samples/registry2/01_clean_travel_authorization.png','UPGRADE_V64.md','RELEASE_NOTES_V64.md','backend/app/template_layout.py','backend/tests/test_v64.py','demo_samples/layout_security/01_layout_consistent.png','UPGRADE_V63.md','RELEASE_NOTES_V63.md','backend/app/capture_intelligence.py','backend/tests/test_v63.py','demo_samples/ocr_capture/01_shadow_low_contrast.png','UPGRADE_V62.md','RELEASE_NOTES_V62.md','backend/app/document_type.py','backend/tests/test_v62.py','src/documentTypeDetector.js','UPGRADE_V61.md','RELEASE_NOTES_V61.md','backend/app/biometric_history.py','backend/tests/test_v61.py','UPGRADE_V60.md','RELEASE_NOTES_V60.md','backend/app/visa_intelligence.py','demo_samples/visa_intelligence/01_visa_clean.png','backend/trust/demo_issuers.json','UPGRADE_V59.md','RELEASE_NOTES_V59.md','backend/app/active_liveness.py','src/LivenessCameraCapture.jsx','backend/requirements.txt','demo_samples/signed_qr/01_signed_match.png']
    if any(name not in manifest for name in required):raise SystemExit('Missing required release assets.')
    if not any(k.startswith('dist/ocr/') and k.endswith(('.wasm','.wasm.js')) for k in manifest):raise SystemExit('Missing offline OCR WASM.')
    if 'dist/ocr/tessdata/eng.traineddata.gz' not in manifest or 'dist/ocr/worker.min.js' not in manifest:raise SystemExit('Missing offline English OCR assets.')
    if not any(k.endswith('.onnx') for k in manifest):raise SystemExit('Missing local face models.')
    with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in sorted(files):archive.write(path,'BHARATSHIELD/'+path.relative_to(root).as_posix())
        archive.writestr('BHARATSHIELD/RELEASE_SHA256.json',json.dumps(manifest,indent=2,sort_keys=True))
    with zipfile.ZipFile(out) as archive:
        if archive.testzip():raise SystemExit('ZIP CRC check failed.')
        assert not any('/private/' in p or '/node_modules/' in p for p in archive.namelist())
    print(json.dumps({'file':str(out),'bytes':out.stat().st_size,'files':len(files)+1,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
if __name__=='__main__':main()
