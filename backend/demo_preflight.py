"""Command-line SIH26188 demo preflight. Run from backend: python demo_preflight.py"""
from pathlib import Path
from app import demo_hardening, local_security

BACKEND=Path(__file__).resolve().parent
PRIVATE=local_security.ROOT
result=demo_hardening.readiness(BACKEND,PRIVATE,PRIVATE/'bharatshield.db')
print('\nBHARATSHIELD SIH26188 DEMO PREFLIGHT')
print('='*42)
for item in result['checks']:
    print(f"[{item['status']:<5}] {item['name']}: {item['detail']}")
print('-'*42)
print('OVERALL:',result['overall'])
raise SystemExit(1 if result['overall']=='NOT_READY' else 0)
