# Offline encrypted recovery — v5.2

Stop the server first with Ctrl+C. This utility is NOT a hot-backup system; it cannot prove
you stopped all processes. Never copy or back up private data while an installation is writing.
Use a separate backup destination with sufficient free space. Input is limited to 200 MiB;
larger deployments need a separately engineered backup process.

From the backend folder, create a NEW password-encrypted bundle:

```powershell
.\.venv\Scripts\python.exe recovery.py backup --file "C:\path\bharatshield-backup.bsbackup" --confirm-server-stopped
```

The password is entered privately, not in the command. Use at least 12 characters and keep
it separately. The utility backs up the complete private directory and public trust directory.
It checks SQLite integrity, document decryptability and saved original-file hashes first.
The ZIP manifest is encrypted/authenticated with AES-GCM; its key is derived using scrypt.
Do not lose the password: there is no password recovery. It does not back up the application,
virtual environment or separate issuer private keys. Back those up using their own policy.

Validate and restore to a folder which DOES NOT EXIST:

```powershell
.\.venv\Scripts\python.exe recovery.py restore --file "C:\path\bharatshield-backup.bsbackup" --out "C:\path\BHARATSHIELD_RECOVERED" --confirm-server-stopped
```

Wrong passwords or modified bundles fail authentication. Every archived path and manifest
hash is checked. Databases and encrypted evidence are validated before the restored folder
is published. Restored login sessions are cleared; original accounts/evidence are retained.
The original installation is not modified. Existing output folders/files are refused.

The recovered folder contains `private` and `trust`. To use it:

1. Extract a NEW copy of the same v5.2 application into another new folder.
2. With every backend stopped, copy recovered `private` into its backend directory.
3. Preserve the newly extracted public trust folder separately, then use recovered `trust`
   as that installation's backend/trust. Do not merge private databases.
4. Create its virtual environment/install requirements and start it using UPGRADE_V52.md.
5. Sign in and check history, original evidence, registry and audit integrity before adopting
   the recovery copy. Retain the old installation until validation is complete.

Recovery validation proves internal consistency, not authenticity, legal validity, or that
an administrator did not modify the source before backup. Compare independently retained
audit checkpoints where available. Restrict access to the restored folders immediately:
the metadata databases and local keys require OS permissions and disk encryption.
