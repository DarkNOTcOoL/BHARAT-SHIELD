"""Smoke test for demo_passport_mode -- run directly: python backend/run_demo_test.py"""
import sys
sys.path.insert(0, '.')

import app.demo_passport_mode as m

# Speed up the test
m._DEMO_DELAY_SECONDS = 0.0

from app.demo_passport_mode import is_demo_passport, build_demo_analysis, _DEMO_FIELDS

# --- Trigger logic ---
assert is_demo_passport('passport_test_01.png')
assert is_demo_passport('PASSPORT_TEST_01.PNG')
assert is_demo_passport('Untitled design (2).png')
assert is_demo_passport('UNTITLED DESIGN (2).PNG')
assert is_demo_passport('/some/path/passport_test_01.png')
assert not is_demo_passport('passport.png')
assert not is_demo_passport('')
assert not is_demo_passport(None)
assert not is_demo_passport('test.jpg')
print('[TRIGGER] OK -- 9/9 checks passed')

# --- Payload shape ---
result = build_demo_analysis('passport_test_01.png')

assert result['risk'] == 'LOW'
assert result['recommendation'] == 'REVIEW_COMPLETE_CHECKS'
assert result['ocr'] == 96.0
assert result['mrz'] == 100.0
assert result['confidence'] > 90
assert result['ai_status'] == 'DEMO_PRESENTATION_MODE_COMPLETE'
print('[PAYLOAD] Top-level shape OK')

cc = result['ai_analysis']['checkpoint_decision_center']
assert cc['checkpoint_recommendation'] == 'REVIEW_COMPLETE_CHECKS'
assert cc['rule_risk']['score'] == 5
assert cc['decision_readiness'] == 'READY_FOR_OFFICER_DECISION'
assert cc['screening_status'] == 'VERIFIED_AUTOMATIC'
clear_lanes = [l for l in cc['lanes'] if l['status'] == 'CLEAR']
assert len(clear_lanes) >= 4
assert cc['top_reasons'] == []
print('[CHECKPOINT] Decision center lanes OK --', len(clear_lanes), 'CLEAR lanes')

findings = result['findings']
high = [f for f in findings if f.get('severity') == 'HIGH']
assert high == []
mrz_valid = [f for f in findings if f['code'] == 'MRZ_VALID']
assert mrz_valid
print('[FINDINGS] OK -- 0 HIGH severity, MRZ_VALID present')

df = result['_demo_fields']
assert df['name'] == 'SRIKRISHNAN NADAR SIVA SELVA KUMAR'
assert df['document_number'] == 'H1591116'
assert df['nationality'] == 'IND'
assert df['gender'] == 'M'
assert 'NAGERCOIL' in result['_demo_ocr_text']
assert 'MADURAI' in result['_demo_ocr_text']
assert 'H1591116' in result['_demo_ocr_text']
print('[FIELDS] All demo identity fields present')

print()
print('ALL TESTS PASSED')
print('  Coverage:', result['confidence'], '%')
print('  Risk:', result['risk'])
print('  Recommendation:', result['recommendation'])
