"""Read-only verification against a separately saved, fingerprint-pinned checkpoint."""
import argparse,json,sqlite3
from app import checkpoints,audit_chain,local_security,local_registry
p=argparse.ArgumentParser();p.add_argument('--file',required=True);p.add_argument('--sha256',required=True)
def main():
    from pathlib import Path
    args=p.parse_args()
    payload=checkpoints.verify(json.loads(Path(args.file).read_text()),args.sha256)
    results={}
    for name,path in [('screening',local_security.ROOT/'bharatshield.db'),('registry',local_registry.DB),('accounts',local_security.DB)]:
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            results[name]=audit_chain.verify(db,payload[name])
    print(json.dumps(results,indent=2))
    if any(v['status']!='CHAIN_CONSISTENT' for v in results.values()):raise SystemExit(1)
if __name__=='__main__':main()
