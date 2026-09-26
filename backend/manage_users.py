"""Run on the checkpoint computer by its administrator."""
import argparse
import getpass
from app.local_security import create_user
p=argparse.ArgumentParser(description='Create a local BHARATSHIELD account')
p.add_argument('--username',required=True)
p.add_argument('--name',required=True)
p.add_argument('--role',choices=['officer','supervisor'],default='officer')
a=p.parse_args()
pw=getpass.getpass('New password (at least 12 characters): ')
if pw != getpass.getpass('Confirm password: '): raise SystemExit('Passwords do not match.')
try: create_user(a.username,a.name,pw,a.role)
except Exception as exc: raise SystemExit(str(exc))
print('Account created. Sign in with your chosen credentials.')
