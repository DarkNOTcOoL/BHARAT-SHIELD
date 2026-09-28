import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import local_analysis, local_security, local_registry, evidence_rules, review_workflow, local_report, registry_v2
from . import signed_qr, signed_demo, audit_chain, duplicate_checks, account_controls
from . import intake
from . import risk_policy,video_demo,active_liveness,visa_intelligence,biometric_history,capture_intelligence,travel_intelligence,checkpoint_center,demo_hardening
from . import demo_passport_mode  # Demo/Presentation Mode interceptor -- does NOT touch face/liveness
from . import document_type as document_type_router
from cryptography.fernet import Fernet
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel, Field, ConfigDict, ValidationError
import math
import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, create_engine, select, text, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = Path(os.getenv('BHARATSHIELD_DATA_DIR', str(BACKEND_ROOT / 'private'))).resolve()
PRIVATE_ROOT.mkdir(exist_ok=True, parents=True)
# Force local SQLite; cloud connection strings from older installs are not used.
DATABASE_URL = 'sqlite:///' + str(PRIVATE_ROOT / 'bharatshield.db')
KEY_PATH = PRIVATE_ROOT / 'document.key'
try:
    with KEY_PATH.open('xb') as key_file: key_file.write(Fernet.generate_key())
    KEY_PATH.chmod(0o600)
except FileExistsError:
    pass
DOCUMENT_CIPHER = Fernet(KEY_PATH.read_bytes())
BIOMETRIC_KEY_PATH = PRIVATE_ROOT / 'biometric.key'
try:
    with BIOMETRIC_KEY_PATH.open('xb') as key_file: key_file.write(Fernet.generate_key())
    BIOMETRIC_KEY_PATH.chmod(0o600)
except FileExistsError:
    pass
BIOMETRIC_CIPHER = Fernet(BIOMETRIC_KEY_PATH.read_bytes())
UPLOAD_DIR = PRIVATE_ROOT / "documents"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
event.listen(engine, 'connect', lambda connection, record: audit_chain.configure(connection))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

class Officer(Base):
    __tablename__ = "officers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    officer_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    checkpoint: Mapped[str] = mapped_column(String(120))

class ReferenceCountry(Base):
    __tablename__ = "reference_countries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(3), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))

class DocumentRule(Base):
    __tablename__ = "document_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_type: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    required_fields: Mapped[str] = mapped_column(Text, default="[]")
    mrz_format: Mapped[str] = mapped_column(String(20), default="NONE")
    notes: Mapped[str] = mapped_column(Text, default="")

class IssuerRecord(Base):
    __tablename__ = "issuer_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country_code: Mapped[str] = mapped_column(String(3), index=True)
    issuer_name: Mapped[str] = mapped_column(String(180))
    document_type: Mapped[str] = mapped_column(String(60))
    active: Mapped[bool] = mapped_column(default=True)

class FraudRule(Base):
    __tablename__ = "fraud_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    severity: Mapped[str] = mapped_column(String(20))
    penalty: Mapped[float] = mapped_column(Float, default=0)
    description: Mapped[str] = mapped_column(Text, default="")

class WatchlistRecord(Base):
    __tablename__ = "watchlist_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifier: Mapped[str] = mapped_column(String(120), index=True)
    person_name: Mapped[str] = mapped_column(String(180), default="")
    category: Mapped[str] = mapped_column(String(80), default="Document watch")
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE")
    source: Mapped[str] = mapped_column(String(120), default="DEMO")

class IdentityRecord(Base):
    __tablename__ = "identity_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_name: Mapped[str] = mapped_column(String(180))
    date_of_birth: Mapped[str] = mapped_column(String(30), default="")
    nationality: Mapped[str] = mapped_column(String(80), default="")
    document_number: Mapped[str] = mapped_column(String(80), index=True)
    document_type: Mapped[str] = mapped_column(String(60), default="Passport")
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE")
    demo_only: Mapped[bool] = mapped_column(default=True)

class Screening(Base):
    __tablename__ = "screenings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    screening_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    case_id: Mapped[str] = mapped_column(String(50), index=True, default="")
    verification_mode: Mapped[str] = mapped_column(String(30), default="SINGLE_DOCUMENT")
    document_index: Mapped[int] = mapped_column(Integer, default=1)
    document_count: Mapped[int] = mapped_column(Integer, default=1)
    document_type: Mapped[str] = mapped_column(String(60))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    document_hash: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default="COMPLETED")
    risk: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    recommendation: Mapped[str] = mapped_column(String(30), default="FLAG")
    person_name: Mapped[str] = mapped_column(String(180), default="")
    date_of_birth: Mapped[str] = mapped_column(String(30), default="")
    nationality: Mapped[str] = mapped_column(String(80), default="")
    document_number: Mapped[str] = mapped_column(String(80), default="")
    expiry_date: Mapped[str] = mapped_column(String(30), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    result: Mapped["VerificationResult"] = relationship(back_populates="screening", uselist=False, cascade="all, delete-orphan")

class VerificationResult(Base):
    __tablename__ = "verification_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id", ondelete="CASCADE"), unique=True)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=0)
    authenticity_score: Mapped[float] = mapped_column(Float, default=0)
    face_match_score: Mapped[float] = mapped_column(Float, default=0)
    database_match_score: Mapped[float] = mapped_column(Float, default=0)
    mrz_score: Mapped[float] = mapped_column(Float, default=0)
    field_consistency_score: Mapped[float] = mapped_column(Float, default=0)
    cross_document_score: Mapped[float] = mapped_column(Float, default=0)
    forensic_score: Mapped[float] = mapped_column(Float, default=0)
    watchlist_status: Mapped[str] = mapped_column(String(60), default="NOT_CHECKED")
    duplicate_status: Mapped[str] = mapped_column(String(60), default="NOT_CHECKED")
    forgery_status: Mapped[str] = mapped_column(String(60), default="PENDING AI")
    details: Mapped[str] = mapped_column(Text, default="")
    findings_json: Mapped[str] = mapped_column(Text, default="[]")
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    ocr_method: Mapped[str] = mapped_column(String(60), default="Tesseract.js")
    ai_status: Mapped[str] = mapped_column(String(80), default="NOT_CONFIGURED")
    ai_analysis_json: Mapped[str] = mapped_column(Text, default="{}")
    screening: Mapped[Screening] = relationship(back_populates="result")

class BiometricTemplate(Base):
    __tablename__ = "biometric_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    screening_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    template_ciphertext: Mapped[str] = mapped_column(Text)
    template_sha256: Mapped[str] = mapped_column(String(64), index=True)
    dimension: Mapped[int] = mapped_column(Integer, default=0)
    model_sha256: Mapped[str] = mapped_column(Text, default="{}")
    person_name: Mapped[str] = mapped_column(String(180), default="")
    date_of_birth: Mapped[str] = mapped_column(String(30), default="")
    document_number: Mapped[str] = mapped_column(String(80), default="")
    document_type: Mapped[str] = mapped_column(String(60), default="")
    liveness_status: Mapped[str] = mapped_column(String(60), default="PASSED_ACTIVE_CHALLENGE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(120))
    result: Mapped[str] = mapped_column(String(40))
    officer: Mapped[str] = mapped_column(String(120), default="Inspector Arjun Singh")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ReviewCase(Base):
    __tablename__='review_cases'
    screening_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    state: Mapped[str] = mapped_column(String(30), default='PENDING',index=True)
    assigned_to: Mapped[str] = mapped_column(String(64),default='')
    reason: Mapped[str] = mapped_column(Text,default='')
    version: Mapped[int] = mapped_column(Integer,default=1)
    resolution: Mapped[str] = mapped_column(String(30),default='')
    resolution_reason: Mapped[str] = mapped_column(Text,default='')
    resolved_by: Mapped[str] = mapped_column(String(64),default='')
    updated_at: Mapped[str] = mapped_column(String(60),default=lambda:datetime.now(timezone.utc).isoformat())

Base.metadata.create_all(engine)
with engine.begin() as connection:
    audit_chain.initialize(connection.connection.driver_connection)

# Lightweight migrations for existing local SQLite databases.
def ensure_sqlite_columns():
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        table_additions = {
            "screenings": {
                "person_name": "VARCHAR(180) DEFAULT ''", "date_of_birth": "VARCHAR(30) DEFAULT ''",
                "nationality": "VARCHAR(80) DEFAULT ''", "document_number": "VARCHAR(80) DEFAULT ''",
                "expiry_date": "VARCHAR(30) DEFAULT ''", "case_id": "VARCHAR(50) DEFAULT ''",
                "verification_mode": "VARCHAR(30) DEFAULT 'SINGLE_DOCUMENT'", "document_index": "INTEGER DEFAULT 1",
                "document_count": "INTEGER DEFAULT 1",
            },
            "verification_results": {
                "ocr_text": "TEXT DEFAULT ''", "ocr_method": "VARCHAR(60) DEFAULT 'Tesseract.js'",
                "mrz_score": "FLOAT DEFAULT 0", "field_consistency_score": "FLOAT DEFAULT 0",
                "cross_document_score": "FLOAT DEFAULT 0", "forensic_score": "FLOAT DEFAULT 0",
                "findings_json": "TEXT DEFAULT '[]'", "ai_status": "VARCHAR(80) DEFAULT 'NOT_CONFIGURED'", "ai_analysis_json": "TEXT DEFAULT '{}'",
            },
        }
        for table, additions in table_additions.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for column, definition in additions.items():
                if column not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
ensure_sqlite_columns()

app = FastAPI(title="BHARATSHIELD Local", version="7.1.0", docs_url=None, redoc_url=None, openapi_url=None)
local_security.install(app)
local_registry.install(app)
registry_v2.install(app)
signed_demo.install(app)
account_controls.install(app,engine)
intake.install(app)

class DocumentInput(BaseModel):
    model_config = ConfigDict(extra='ignore', str_max_length=20000)
    type: str = Field(default='Passport', max_length=60)
    ocr_text: str = ''
    ocr_confidence: float = Field(default=0, ge=0, le=100, allow_inf_nan=False)
    name: str = Field(default='', max_length=180)
    dob: str = Field(default='', max_length=40)
    nationality: str = Field(default='', max_length=80)
    document_number: str = Field(default='', max_length=80)
    passport_reference: str = Field(default='', max_length=80)
    expiry: str = Field(default='', max_length=40)
    issuer_country: str = Field(default='', max_length=80)
    gender: str = Field(default='', max_length=40)
    issue_date: str = Field(default='', max_length=40)
    issuing_authority: str = Field(default='', max_length=180)
    visa_type: str = Field(default='', max_length=80)
    number_of_entries: str = Field(default='', max_length=30)
    valid_from: str = Field(default='', max_length=40)
    duration_of_stay: str = Field(default='', max_length=80)
    ocr_fields: dict[str, str] = Field(default_factory=dict, max_length=15)
    ocr_notes: str = Field(default='',max_length=20000)
    document_type_detection: dict = Field(default_factory=dict)
    document_type_source: str = Field(default='OFFICER_SELECTED', max_length=40)



def norm(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())

def norm_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())

def name_key(value: str) -> str:
    parts = [p for p in re.sub(r"[^A-Z0-9 ]", " ", (value or "").upper()).split() if p]
    return " ".join(sorted(parts))

def parse_date(value: str) -> Optional[tuple[int, int, int]]:
    value=(value or '').strip().upper()
    for pattern in ['%d/%m/%Y','%d-%m-%Y','%d.%m.%Y','%Y-%m-%d','%Y/%m/%d','%d %b %Y','%d %B %Y']:
        try:
            date=datetime.strptime(value,pattern)
            return date.year,date.month,date.day
        except ValueError: pass
    return None


def date_equal(a: str, b: str) -> bool:
    pa, pb = parse_date(a), parse_date(b)
    return bool(pa and pb and pa == pb)

def mrz_char_value(c: str) -> int:
    if c == "<": return 0
    if c.isdigit(): return int(c)
    return ord(c) - ord("A") + 10

def mrz_check_ok(field: str, check: str) -> bool:
    if not check or not check.isdigit() or not field:
        return False
    weights = [7, 3, 1]
    total = sum(mrz_char_value(c) * weights[i % 3] for i, c in enumerate(field))
    return total % 10 == int(check)

def find_td3_mrz(ocr_text: str) -> tuple[str, str]:
    lines = [re.sub(r"[^A-Z0-9<]", "", x.upper()) for x in (ocr_text or "").splitlines()]
    lines = [x for x in lines if len(x) >= 35]
    for i, line in enumerate(lines):
        if line.startswith("P<") and i + 1 < len(lines):
            return line[:60], lines[i + 1][:60]
    # OCR often loses the initial P<; recognize a line beginning with country code + surname.
    for i, line in enumerate(lines):
        if i + 1 < len(lines) and len(line) >= 30 and len(lines[i + 1]) >= 35:
            second = lines[i + 1]
            if re.match(r"^[A-Z0-9<]{9}[0-9][A-Z]{3}\d{7}[0-9][MF<]\d{7}[0-9]", second):
                return line[:60], second[:60]
    return "", ""

def validate_passport_mrz(ocr_text: str, fields: dict) -> dict:
    l1, l2 = find_td3_mrz(ocr_text)
    if not l1 or not l2:
        return {"score": 0, "detected": False, "valid": False, "findings": [{"code":"MRZ_NOT_FOUND","severity":"MEDIUM","message":"TD3 passport MRZ could not be confidently detected from OCR."}]}

    def evaluate(line2: str, repaired: bool = False):
        if len(line2) < 44:
            return None
        checks = [
            ("DOCUMENT_NUMBER", line2[0:9], line2[9]),
            ("DATE_OF_BIRTH", line2[13:19], line2[19]),
            ("DATE_OF_EXPIRY", line2[21:27], line2[27]),
            ("PERSONAL_NUMBER", line2[28:42], line2[42]),
            ("COMPOSITE", line2[0:10] + line2[13:20] + line2[21:28] + line2[28:43], line2[43]),
        ]
        valid_count = sum(int(mrz_check_ok(field, check)) for _, field, check in checks)
        return valid_count, checks, line2[10:13], line2[0:9].replace("<", ""), line2[13:19], line2[21:27]

    candidate = evaluate(l2)
    repaired_candidate = None
    # OCR sometimes inserts a stray numeric character immediately after the document check digit.
    # If the normal country-code slot is invalid but the next 3 characters form a known code,
    # evaluate a one-character-shifted candidate and mark it as an OCR repair rather than silently trusting it.
    normal_country = l2[10:13] if len(l2) >= 13 else ""
    with SessionLocal() as db:
        known_codes = {r.code for r in db.scalars(select(ReferenceCountry)).all()}
    if len(l2) >= 45 and normal_country not in known_codes and l2[11:14] in known_codes:
        repaired_line = l2[:10] + l2[11:]
        repaired_candidate = evaluate(repaired_line, True)

    chosen = candidate
    repaired = False
    if repaired_candidate and (candidate is None or repaired_candidate[0] > candidate[0]):
        chosen = repaired_candidate; repaired = True
    if not chosen:
        return {"score":0,"detected":True,"valid":False,"findings":[{"code":"MRZ_UNREADABLE","severity":"HIGH","message":"MRZ was detected but could not be normalized to a complete TD3 line."}]}

    valid_count, checks, nationality, mrz_number, mrz_dob, mrz_exp = chosen
    findings = []
    for label, field, check in checks:
        ok = mrz_check_ok(field, check)
        findings.append({"code":"MRZ_CHECK_"+label, "severity":"LOW" if ok else "HIGH", "message":f"{label.replace('_',' ').title()} check digit {'valid' if ok else 'failed'}."})
    if repaired:
        findings.append({"code":"MRZ_OCR_REPAIR","severity":"MEDIUM","message":"A one-character OCR shift was required to align the MRZ country-code field; re-capture is recommended for high-assurance use."})
    if fields.get("document_number") and norm(fields["document_number"]) != norm(mrz_number):
        findings.append({"code":"MRZ_VIZ_DOC_CONFLICT","severity":"HIGH","message":"Document number differs between extracted visible data and MRZ."})
    if fields.get("nationality") and norm(fields["nationality"])[0:3] != norm(nationality):
        findings.append({"code":"MRZ_VIZ_NATIONALITY_CONFLICT","severity":"HIGH","message":"Nationality differs between extracted visible data and MRZ."})
    for key, raw in [('dob',mrz_dob),('expiry',mrz_exp)]:
        parsed = parse_date(fields.get(key,''))
        if parsed:
            year, month, day = parsed
            if f'{year % 100:02d}{month:02d}{day:02d}' != raw:
                findings.append({'code':'MRZ_VIZ_'+key.upper()+'_CONFLICT','severity':'HIGH','message':f'{key.title()} differs between visible text and MRZ.'})
    score = round((valid_count / 5) * 100, 1)
    if repaired: score = max(0, score - 10)
    if valid_count == 5 and not repaired:
        findings.append({"code":"MRZ_VALID","severity":"PASS","message":"TD3 MRZ structure and check digits validated."})
    elif valid_count == 5:
        findings.append({"code":"MRZ_REPAIRED","severity":"MEDIUM","message":"MRZ checks pass after OCR alignment repair; use a clearer capture for high-assurance verification."})
    return {"score":score,"detected":True,"valid":valid_count==5 and not repaired,"issuer":l1[2:5],"nationality":nationality,"document_number":mrz_number,"dob_raw":mrz_dob,"expiry_raw":mrz_exp,"findings":findings}

# --- Document-number format checks for India's common ID types -----------------------------
# These are structural checks only (does the number look like a real one of its kind);
# they are one more evidence signal for the Verification Engine, not a genuineness claim.
_VERHOEFF_D = [
    [0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],
    [4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],
    [8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0],
]
_VERHOEFF_P = [
    [0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
    [9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8],
]

def verhoeff_valid(number: str) -> bool:
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(digit)]]
    return c == 0

DOC_NUMBER_PATTERNS = {
    "Aadhaar Card": re.compile(r"^\d{12}$"),
    "Voter ID (EPIC)": re.compile(r"^[A-Z]{3}\d{7}$"),
    "PAN Card": re.compile(r"^[A-Z]{5}\d{4}[A-Z]$"),
    # Indian driving licences vary by state (e.g. MH1220110012345); this is a loose structural
    # check (state code + digits) rather than a strict national format.
    "Driving Licence": re.compile(r"^[A-Z]{2}\d{11,15}$"),
}

def validate_document_number_format(document_type: str, value: str) -> dict:
    value_norm = norm(value)
    if not value_norm:
        return {"checked": False, "valid": None, "findings": []}
    pattern = DOC_NUMBER_PATTERNS.get(document_type)
    if not pattern:
        return {"checked": False, "valid": None, "findings": []}
    if not pattern.match(value_norm):
        return {"checked": True, "valid": False, "findings": [{"code":"DOCUMENT_NUMBER_FORMAT_INVALID","severity":"MEDIUM","message":f"{document_type} number does not match the expected format ({len(value_norm)} characters captured)."}]}
    if document_type == "Aadhaar Card" and not verhoeff_valid(value_norm):
        return {"checked": True, "valid": False, "findings": [{"code":"AADHAAR_CHECKSUM_FAILED","severity":"HIGH","message":"Aadhaar number failed its Verhoeff checksum digit — likely an OCR misread or invalid number."}]}
    return {"checked": True, "valid": True, "findings": [{"code":"DOCUMENT_NUMBER_FORMAT_VALID","severity":"PASS","message":f"{document_type} number matches the expected format."}]}

def field_completeness(fields: dict, required: list[str]) -> float:
    if not required:
        return 0
    present = sum(1 for k in required if str(fields.get(k, "")).strip())
    return round(present / len(required) * 100, 1)

def check_reference(db, fields: dict, document_type: str, ocr_confidence: float = 0, doc_format: Optional[dict] = None) -> dict:
    """Match submitted fields against the trusted identity reference DB.

    When no record exists (the common case for real/non-seeded documents), we compute a
    *structural fallback score* from signals that are available without a trusted record:
      - Document-number format validity for the declared type  (40 pts)
      - Presence of core identity fields (name, dob / expiry, doc number)  (40 pts)
      - OCR confidence (normalised to 0-20 pts)                            (20 pts)

    This replaces the previous hard 0 so the score card conveys real evidence quality
    rather than a meaningless zero for any document that isn't in the demo DB.
    """
    findings = []
    doc_no = norm(fields.get("document_number", ""))
    name = norm_name(fields.get("name", ""))
    dob = fields.get("dob", "")

    # --- try to find a matching record -----------------------------------------------
    record = db.scalar(select(IdentityRecord).where(IdentityRecord.document_number == fields.get("document_number", ""))) if fields.get("document_number") else None
    if not record and doc_no:
        records = db.scalars(select(IdentityRecord)).all()
        record = next((r for r in records if norm(r.document_number) == doc_no), None)

    # --- no record found: structural fallback ----------------------------------------
    if not record:
        # 1. Document-number format score (0 or 40)
        fmt_score = 0.0
        if doc_format and doc_format.get("checked"):
            fmt_score = 40.0 if doc_format.get("valid") else 0.0
        elif not doc_format or not doc_format.get("checked"):
            # Format not applicable for this doc type — award partial credit if a number exists
            fmt_score = 20.0 if doc_no else 0.0

        # 2. Field completeness score (0–40): name + doc_number + at least one of dob/nationality/expiry
        field_hits = [
            bool(name),
            bool(doc_no),
            bool(dob or fields.get("nationality") or fields.get("expiry")),
        ]
        field_score = round(sum(field_hits) / len(field_hits) * 40, 1)

        # 3. OCR confidence contribution (0–20)
        ocr_norm = max(0.0, min(100.0, float(ocr_confidence or 0)))
        ocr_contrib = round(ocr_norm * 0.20, 1)

        fallback_score = round(min(100.0, fmt_score + field_score + ocr_contrib), 1)

        print(
            f"[BHARATSHIELD][REF_MATCH] No identity record found for doc_no='{doc_no}' type='{document_type}'. "
            f"Structural fallback: fmt={fmt_score}, fields={field_score}, ocr_contrib={ocr_contrib} "
            f"=> fallback_score={fallback_score}",
            flush=True,
        )

        findings.append({
            "code": "REFERENCE_NOT_FOUND",
            "severity": "INFO",
            "message": (
                f"No trusted reference record for document number '{doc_no or '(none)'}'. "
                f"Structural quality score: {fallback_score:.0f}% "
                f"(format={'valid' if fmt_score>=40 else 'n/a' if fmt_score==20 else 'invalid'}, "
                f"fields={'complete' if field_score>=40 else 'partial'}, "
                f"ocr={ocr_norm:.0f}%)."
            ),
        })
        return {
            "score": fallback_score,
            "status": "NO REFERENCE RECORD",
            "findings": findings,
            "fallback": True,
        }

    # --- record found: compare identity fields ----------------------------------------
    matches = []
    matches.append(bool(name and name_key(record.person_name) == name_key(fields.get("name", ""))))
    matches.append(bool(dob and date_equal(record.date_of_birth, dob)))
    matches.append(bool(fields.get("nationality") and norm(record.nationality) == norm(fields.get("nationality"))))
    if record.document_type.lower() != document_type.lower():
        findings.append({"code":"REFERENCE_DOC_TYPE_CONFLICT","severity":"HIGH","message":"Reference record uses a different document type."})
    score = round(sum(matches) / len(matches) * 100, 1)

    print(
        f"[BHARATSHIELD][REF_MATCH] Record found for doc_no='{doc_no}'. "
        f"Field matches={matches} => score={score}%",
        flush=True,
    )

    if score == 100:
        status = "VERIFIED"
        findings.append({"code":"REFERENCE_MATCH","severity":"PASS","message":"Synthetic trusted identity record matches the extracted fields."})
    else:
        status = "CONFLICT"
        findings.append({"code":"REFERENCE_CONFLICT","severity":"HIGH","message":"One or more identity fields conflict with the trusted reference record."})
    return {"score": score, "status": status, "findings": findings, "record": record}

def check_watchlist(db, fields: dict) -> tuple[str, list[dict]]:
    doc_no = norm(fields.get("document_number", ""))
    name = norm_name(fields.get("name", ""))
    rows = db.scalars(select(WatchlistRecord)).all()
    for row in rows:
        if (doc_no and norm(row.identifier) == doc_no) or (name and norm_name(row.person_name) == name):
            return "MATCH", [{"code":"WATCHLIST_HIT","severity":"CRITICAL","message":f"Potential watchlist match ({row.category}); source: {row.source}."}]
    return "CLEAR", [{"code":"WATCHLIST_CLEAR","severity":"PASS","message":"No match in the configured prototype watchlist."}]

def cross_verify(documents: list[dict]) -> tuple[float, str, list[dict]]:
    return evidence_rules.cross_checks(documents)

def score_band(value: float) -> dict:
    """Legacy API field retained, but never equates coverage with authenticity."""
    v = max(0.0, min(100.0, float(value)))
    return {'band':'CHECK_COVERAGE','label':f'{v:g}% of checks completed','message':'Coverage is not a probability of authenticity or a risk estimate.'}


ENGINE_VERSION = '7.1.0-integrated-officer-console-ui-polish'

def verify_document(db, fields, document_type, ocr_confidence, ocr_text, data, mode,
                    cross_score=0, cross_findings=None, ai_analysis=None, ai_status='LOCAL'):
    required_by_type = {
        'Passport':['name','dob','nationality','document_number','expiry'],
        'Visa':['name','document_number','expiry'],
        'Driving Licence':['name','dob','document_number','expiry'],
        'Aadhaar Card':['name','dob','document_number'],
        'PAN Card':['name','dob','document_number'],
    }
    required = required_by_type.get(document_type,['name','document_number'])
    missing = [k for k in required if not fields.get(k)]
    fields_score = field_completeness(fields, required)
    observation = ai_analysis or {'quality':local_analysis.quality(data)}
    quality = observation['quality']
    visa_info = visa_intelligence.assess_fields(fields, ocr_text) if document_type=='Visa' else {'status':'NOT_APPLICABLE','fields':{},'findings':[],'gaps':[]}
    observation['visa_intelligence']=visa_info
    fmt = validate_document_number_format(document_type,fields.get('document_number',''))
    mrz = validate_passport_mrz(ocr_text,fields) if document_type=='Passport' else {'score':0,'detected':False,'valid':False,'findings':[]}
    mrz_status = ('VALID' if mrz['valid'] else 'INVALID' if mrz['detected'] else 'NOT_DETECTED') if document_type=='Passport' else 'NOT_SUPPORTED' if document_type=='Visa' else 'NOT_APPLICABLE'
    type_detection=observation.get('document_type_detection') or document_type_router.compare(document_type,ocr_text,'OFFICER_SELECTED')
    observation['document_type_detection']=type_detection
    findings = list(mrz['findings']) + list(fmt.get('findings',[])) + list(cross_findings or []) + list(visa_info.get('findings',[]))
    if type_detection.get('finding'): findings.append(type_detection['finding'])
    findings.append({'code':'EXTRACTION_SOURCE','severity':'INFO','message':'Local browser OCR and officer-reviewed fields; extraction is not independent issuer verification.'})
    for issue in quality['issues']:
        findings.append({'code':issue,'severity':'QUALITY','message':'Capture issue: '+issue.lower().replace('_',' ')+'. Recapture recommended.'})
    capture=observation.get('capture_intelligence') or {}
    glare=(capture.get('glare') or {}) if isinstance(capture,dict) else {}
    skew=(capture.get('skew') or {}) if isinstance(capture,dict) else {}
    illumination=(capture.get('illumination') or {}) if isinstance(capture,dict) else {}
    if glare.get('status')=='RECAPTURE_RECOMMENDED':
        findings.append({'code':'CAPTURE_GLARE','severity':'QUALITY','status':'RECAPTURE_RECOMMENDED','message':f"Strong glare-like saturated regions cover about {round(float(glare.get('coverage',0))*100,1)}% of the working image. Recapture before relying on OCR."})
    elif glare.get('status')=='REVIEW':
        findings.append({'code':'CAPTURE_GLARE_REVIEW','severity':'INFO','message':'Possible localized glare may obscure text. Inspect the original and OCR field confidence.'})
    if skew.get('deskew_recommended'):
        findings.append({'code':'CAPTURE_SKEW','severity':'INFO','message':f"Text-line skew is estimated near {skew.get('skew_angle_degrees')} degrees. Straighten the document for a cleaner recapture; no silent geometric transform was applied."})
    if illumination.get('status')=='UNEVEN_LIGHTING':
        findings.append({'code':'CAPTURE_UNEVEN_LIGHTING','severity':'INFO','message':'Uneven illumination/shadow was detected. v6.3 illumination-normalized OCR fallback may help, but compare fields with the original.'})
    if missing: findings.append({'code':'MISSING_FIELDS','severity':'INFO','message':'Not extracted: '+', '.join(missing)})
    today=datetime.now(timezone.utc).date()
    for key in ['dob','issue_date','expiry']:
        value=fields.get(key,'')
        if not value: continue
        parsed=parse_date(value)
        if parsed is None:
            findings.append({'code':'DATE_UNREADABLE','severity':'INFO','message':f'{key} could not be parsed. Review extraction.'})
        elif key=='expiry' and datetime(*parsed).date()<today:
            findings.append({'code':'DOCUMENT_EXPIRED','severity':'HIGH','message':'Extracted expiry date is in the past. Verify against the document.'})
        elif key=='dob' and datetime(*parsed).date()>today:
            findings.append({'code':'DOB_IN_FUTURE','severity':'HIGH','message':'Extracted date of birth is in the future.'})
        elif key=='issue_date' and datetime(*parsed).date()>today:
            findings.append({'code':'ISSUE_DATE_IN_FUTURE','severity':'HIGH','message':'Extracted issue date is in the future. Inspect the original.'})
    dates={k:local_registry.normalized_date(fields.get(k,'')) for k in ['dob','issue_date','expiry']}
    for first,last in [('dob','issue_date'),('issue_date','expiry')]:
        if dates[first] and dates[last] and dates[first]>dates[last]:
            findings.append({'code':'DATE_ORDER_CONFLICT','severity':'HIGH','message':first+' follows '+last+'. Review against original evidence.'})
    # This entire build is a simulator. Demo registry evidence is labelled at every boundary.
    registry = registry_v2.enrich_reference(local_registry.compare(document_type, fields))
    travel_info = travel_intelligence.assess(registry, document_type, fields, ocr_text)
    observation['travel_intelligence'] = travel_info
    findings.extend(travel_info.get('findings', []))
    qr = signed_qr.compare(observation.get('signed_qr') or signed_qr.scan_image(data),document_type,fields,registry)
    observation['signed_qr'] = qr
    findings.extend(qr['findings'])
    findings.extend(registry['findings'])
    findings.append({'code':'SYNTHETIC_REGISTRY_'+registry['status'], 'severity':'INFO', 'message':registry['message']})
    findings.append({'code':'ISSUER_NOT_CONNECTED','severity':'INFO','message':'No authorized issuer or watchlist database connected.'})
    forensic=observation.get('forensic_assist') or {}
    tamper=forensic.get('tamper_ai') or {}
    photo=forensic.get('photo_substitution') or {}
    if tamper.get('status')=='REVIEW_REQUIRED':
        affected=', '.join(tamper.get('affected_fields') or [])
        suffix=(' Affected OCR field region(s): '+affected+'.') if affected else ''
        findings.append({'code':'AI_TAMPER_ANOMALY','severity':'MEDIUM','status':'REVIEW_REQUIRED','message':f"Local unsupervised tamper-anomaly analysis found {tamper.get('strong_region_count',0)} strong region(s) (max anomaly index {tamper.get('max_anomaly_score')}).{suffix} This is an inspection signal, not proof of editing."})
    elif tamper.get('status')=='INCONCLUSIVE':
        findings.append({'code':'AI_TAMPER_INCONCLUSIVE','severity':'INFO','message':'Local tamper-anomaly analysis was inconclusive; manual forensic inspection remains available.'})
    else:
        findings.append({'code':'AI_TAMPER_NO_STRONG_ANOMALY','severity':'INFO','message':'Local unsupervised tamper-anomaly analysis found no strong within-document outlier. This does not establish authenticity.'})
    if photo.get('status')=='REVIEW_REQUIRED':
        cues=', '.join(photo.get('cues') or []) or 'multiple local forensic cues'
        findings.append({'code':'PHOTO_SUBSTITUTION_REVIEW','severity':'MEDIUM','status':'REVIEW_REQUIRED','message':f"AI-localized portrait region requires substitution review (photo-integrity index {photo.get('photo_integrity_index')}; cues: {cues}). This is not proof that the photograph was replaced."})
    elif photo.get('status') in {'MODEL_ERROR','MODEL_UNAVAILABLE','INCONCLUSIVE','INCONCLUSIVE_MULTIPLE_PORTRAITS'}:
        findings.append({'code':'PHOTO_SUBSTITUTION_INCONCLUSIVE','severity':'INFO','message':'Portrait substitution analysis was inconclusive. Inspect the document photograph manually.'})
    elif photo.get('status')=='NO_PORTRAIT_DETECTED':
        findings.append({'code':'PHOTO_SUBSTITUTION_NOT_ASSESSED','severity':'INFO','message':'No portrait face was detected in this document image; photo substitution was not assessed.'})
    else:
        findings.append({'code':'PHOTO_SUBSTITUTION_NO_STRONG_SIGNAL','severity':'INFO','message':'No multi-cue portrait-substitution signal crossed the local review threshold. This does not establish photo authenticity.'})
    stamp=forensic.get('stamp_seal') or {}
    layout=forensic.get('template_layout') or {}
    visual=forensic.get('issuer_visual_security') or {}
    if layout.get('status')=='REVIEW_REQUIRED':
        affected=', '.join(dict.fromkeys(str(x.get('field','')) for x in layout.get('signals',[]) if x.get('field')))
        suffix=(' Affected zone(s): '+affected+'.') if affected else ''
        findings.append({'code':'LAYOUT_SECURITY_ZONE_REVIEW','severity':'MEDIUM','status':'REVIEW_REQUIRED','message':f"Document layout/security-zone analysis found multiple geometric inconsistencies (layout anomaly index {layout.get('layout_anomaly_index')}).{suffix} This is not issuer-template authentication."})
    elif layout.get('status')=='INCONCLUSIVE':
        findings.append({'code':'LAYOUT_SECURITY_ZONE_INCONCLUSIVE','severity':'INFO','message':'Too little unambiguous OCR geometry was available for document layout/security-zone assessment.'})
    elif layout.get('status')=='OBSERVATIONS':
        findings.append({'code':'LAYOUT_SECURITY_ZONE_OBSERVATIONS','severity':'INFO','message':'Layout analysis recorded isolated geometric observations below the review threshold. Inspect the original if other evidence conflicts.'})
    else:
        findings.append({'code':'LAYOUT_SECURITY_ZONE_NO_STRONG_ANOMALY','severity':'INFO','message':'No multi-signal layout/security-zone anomaly crossed the local review threshold. This does not establish template authenticity.'})
    if visual.get('status')=='REVIEW_REQUIRED':
        missing=[x.get('label') or x.get('feature_code') for x in visual.get('feature_results',[]) if x.get('status')=='REVIEW_MISSING_OR_INCONSISTENT']
        affected=', '.join([x for x in missing if x])
        suffix=(' Affected synthetic reference feature(s): '+affected+'.') if affected else ''
        findings.append({'code':'ISSUER_VISUAL_FEATURE_REVIEW','severity':'MEDIUM','status':'REVIEW_REQUIRED','message':f"Bundled synthetic issuer-template visual reference check found missing/inconsistent required features (visual anomaly index {visual.get('visual_anomaly_index')}).{suffix} This is not official issuer authentication."})
    elif visual.get('status')=='OBSERVATIONS':
        findings.append({'code':'ISSUER_VISUAL_FEATURE_OBSERVATIONS','severity':'INFO','message':'Synthetic issuer-template visual reference matching produced borderline observations below the review threshold. This is not official authentication.'})
    elif visual.get('status')=='REFERENCE_FEATURES_CONSISTENT':
        findings.append({'code':'ISSUER_VISUAL_FEATURES_CONSISTENT','severity':'INFO','message':'Bundled synthetic reference features were visually consistent in their expected zones. This does not authenticate a real issuer document.'})
    else:
        findings.append({'code':'ISSUER_VISUAL_FEATURES_NOT_ASSESSED','severity':'INFO','message':'No matching bundled synthetic visual reference profile was available. No official issuer template database is connected.'})

    if document_type=='Visa':
        if stamp.get('status')=='REVIEW_REQUIRED':
            findings.append({'code':'STAMP_SEAL_TAMPER_REVIEW','severity':'MEDIUM','status':'REVIEW_REQUIRED','message':f"Local stamp/seal inspection found {stamp.get('strong_region_count',0)} candidate region(s) overlapping independent forensic anomaly cues. This is not issuer-stamp authentication or proof of tampering."})
        elif stamp.get('status')=='CANDIDATES_FOUND':
            findings.append({'code':'STAMP_SEAL_CANDIDATES','severity':'INFO','message':f"{stamp.get('candidate_count',0)} stamp/seal-like region(s) localized for manual inspection; no multi-cue tamper alert."})
        elif stamp.get('status')=='NO_STAMP_LIKE_REGION_DETECTED':
            findings.append({'code':'STAMP_SEAL_NOT_LOCALIZED','severity':'INFO','message':'No stamp/seal-like region was confidently localized. Absence does not establish that a required stamp is missing.'})
    strong=[f for f in findings if f.get('severity')=='HIGH']
    registry2=registry.get('registry2',{})
    insufficient = bool(registry['status'] != 'MATCH' or registry2.get('requires_review',False) or missing or ocr_confidence<65 or (document_type=='Passport' and not mrz['detected']) or any(f['code'] in {'DATE_UNREADABLE','CROSS_LINK_UNAVAILABLE'} or f.get('status') in {'MISSING','REVIEW_REQUIRED'} for f in findings))
    duplicates=observation.get('duplicates',{})
    if duplicates.get('requires_review'):
        findings.append({'code':'HISTORY_IDENTITY_CONFLICT','severity':'MEDIUM','message':'Identity fields differ across local history. Investigate candidates; this is not proof of impersonation.'})
    insufficient = insufficient or qr['requires_review'] or duplicates.get('requires_review',False) or type_detection.get('review_required',False) or layout.get('status')=='REVIEW_REQUIRED' or visual.get('status')=='REVIEW_REQUIRED' or travel_info.get('requires_review',False) or (document_type=='Visa' and (visa_info.get('status') in {'REVIEW_REQUIRED','PARTIAL'} or stamp.get('status')=='REVIEW_REQUIRED'))
    if registry2.get('escalation_required') or registry['status'] in {'BLOCKED', 'REVOKED'}:
        risk,recommendation='CRITICAL','ESCALATE'
    elif quality['status']=='RECAPTURE' or glare.get('status')=='RECAPTURE_RECOMMENDED' or ocr_confidence<35:
        risk,recommendation='UNASSESSED','RECAPTURE'
    elif strong:
        risk,recommendation='HIGH','MANUAL_REVIEW'
    elif insufficient:
        risk,recommendation='UNASSESSED','MANUAL_REVIEW'
    else:
        risk,recommendation='LOW','REVIEW_COMPLETE_CHECKS'
    # Coverage counts performed checks, not authenticity or probability.
    tamper_check='INCONCLUSIVE' if tamper.get('status')=='INCONCLUSIVE' else 'COMPLETE' if tamper else 'NOT_RUN'
    photo_check='COMPLETE' if photo.get('status') in {'REVIEW_REQUIRED','NO_STRONG_PHOTO_SUBSTITUTION_SIGNAL'} else ('NOT_APPLICABLE' if photo.get('status')=='NO_PORTRAIT_DETECTED' else 'INCONCLUSIVE' if photo else 'NOT_RUN')
    checks={'quality':'COMPLETE','capture_intelligence':'COMPLETE' if capture else 'NOT_RUN','ocr_preprocessing':'COMPLETE' if observation.get('ocr_strategy') else 'NOT_RUN','ocr':'COMPLETE' if ocr_text.strip() else 'NOT_RUN','document_type':'REVIEW_REQUIRED' if type_detection.get('review_required') else ('COMPLETE' if type_detection.get('status')=='DETECTED' else 'INCONCLUSIVE'),
            'fields':'COMPLETE' if not missing else 'INCOMPLETE','document_number':'COMPLETE' if fmt.get('checked') else 'NOT_VERIFIED',
            'mrz':mrz_status,'tampering':tamper_check,'photo_substitution':photo_check,'layout_security_zones':('INCONCLUSIVE' if layout.get('status')=='INCONCLUSIVE' else 'REVIEW_REQUIRED' if layout.get('status')=='REVIEW_REQUIRED' else 'COMPLETE' if layout else 'NOT_RUN'),'issuer_visual_features':('REVIEW_REQUIRED' if visual.get('status')=='REVIEW_REQUIRED' else 'INCONCLUSIVE' if visual.get('status') in {'OBSERVATIONS'} else 'COMPLETE' if visual.get('status')=='REFERENCE_FEATURES_CONSISTENT' else 'NOT_VERIFIED'),'visa_fields':visa_info.get('status','NOT_APPLICABLE'),'stamp_seal':('COMPLETE' if stamp.get('status') in {'CANDIDATES_FOUND','NO_STAMP_LIKE_REGION_DETECTED'} else 'INCONCLUSIVE' if stamp.get('status')=='REVIEW_REQUIRED' else 'NOT_APPLICABLE'),'issuer':'NO_AUTHORIZED_EXTERNAL_CONNECTION','watchlist':'NOT_CONNECTED',
            'face':'NOT_RUN','liveness':'OPTIONAL_NOT_RUN','forensic_assist':'COMPLETE' if observation.get('forensic_assist') else 'NOT_RUN',
            'synthetic_registry':'NOT_VERIFIED' if registry['status'] in {'NOT_CHECKED','UNAVAILABLE','AMBIGUOUS'} else 'COMPLETE',
            'registry2_identity_graph':'REVIEW_REQUIRED' if registry2.get('requires_review') else ('COMPLETE' if registry2.get('status')=='LINKED' else 'NOT_VERIFIED'),
            'travel_immigration_consistency':'REVIEW_REQUIRED' if travel_info.get('requires_review') else ('COMPLETE' if travel_info.get('status')=='CONSISTENT_WITH_SYNTHETIC_HISTORY' else 'INCONCLUSIVE')}
    applicable=[v for k,v in checks.items() if v!='NOT_APPLICABLE' and k not in {'face','liveness'}]
    completed=sum(v in {'COMPLETE','VALID','INVALID'} for v in applicable)
    coverage=round(completed/len(applicable)*100,1)
    observation.update({'engine_version':ENGINE_VERSION,'checks':checks,'coverage':coverage,
                        'quality':quality,'mrz_status':mrz_status,'extraction_source':'LOCAL_BROWSER_OCR_AND_OFFICER_REVIEW',
                        'face':{'status':'NOT_RUN','optional':True},'liveness':{'status':'NOT_RUN','optional':True,'method':'RANDOMIZED_ACTIVE_HEAD_TURN_V1'},'optional_checks':['face','liveness'],'external_inference':'DISABLED','registry':registry,
                        'limitations':['No authenticity guarantee','Tamper anomaly model is unsupervised and uncalibrated; it is not a fraud probability','Photo substitution uses YuNet localization plus uncalibrated local forensic cues; it is not a replacement-photo probability','Layout/security-zone analysis uses broad document-family geometry and is not issuer-template authentication','Issuer visual-feature matching uses only bundled synthetic references and is not official issuer authentication, hologram verification or UV/IR inspection','Visa stamp/seal analysis is local CV/forensic assistance, not issuer authentication or a trained universal stamp classifier','Active liveness is prototype replay resistance, not certified presentation-attack detection','No authorized issuer/watchlist connection','Registry 2.x is synthetic local demo data; no government, immigration, airline, border-control, issuer or watchlist system is connected','Travel/immigration intelligence checks only local synthetic entry/exit history and OCR-visible cues; it is not a travel-history, admissibility or border-decision system']})
    observation['risk_score']=risk_policy.assess(registry,qr,findings,fields,quality,ocr_confidence,mrz_status)
    if recommendation=='REVIEW_COMPLETE_CHECKS' and observation['risk_score']['band']!='LOW':
        recommendation='MANUAL_REVIEW';risk='HIGH' if observation['risk_score']['band'] in {'HIGH','CRITICAL'} else 'UNASSESSED'
    return {'ocr':float(ocr_confidence),'authenticity':0,'face':0,'database':0,'mrz':mrz['score'],
            'field':fields_score,'cross':cross_score,'forensic':0,'watchlist':'NOT_CONNECTED',
            'duplicate':duplicates.get('status','NOT_VERIFIED'),'forgery':'NOT_VERIFIED','confidence':coverage,'risk':risk,
            'recommendation':recommendation,'details':'Local demo screening completed. Synthetic registry: '+registry['status']+'. '+str(len(strong))+' rule inconsistency(s). '+
            'Coverage measures completed checks, not authenticity. Missing models do not imply fraud. Officer review is required.',
            'findings':findings,'ai_status':'LOCAL_CHECKS_COMPLETE','ai_analysis':observation}


def seed_reference_data(db):
    if not db.scalar(select(ReferenceCountry).where(ReferenceCountry.code == "IND")):
        countries = [("IND","India"),("USA","United States"),("GBR","United Kingdom"),("FRA","France"),("DEU","Germany"),("JPN","Japan"),("AUS","Australia"),("CAN","Canada")]
        db.add_all([ReferenceCountry(code=c,name=n) for c,n in countries])
    rules = {
        "Passport": (["name","dob","nationality","document_number","expiry"], "TD3", "Passport/MRP baseline for prototype validation."),
        "Visa": (["name","document_number","expiry"], "MRV", "Machine-readable visa baseline."),
        "Aadhaar Card": (["name","dob","document_number"], "NONE", "12-digit UIDAI Aadhaar number, Verhoeff checksum validated; no MRZ."),
        "Voter ID (EPIC)": (["name","document_number"], "NONE", "Election Commission of India EPIC number (3 letters + 7 digits)."),
        "Driving Licence": (["name","dob","document_number","expiry"], "NONE", "State-issued driving licence; number format varies by issuing state."),
        "PAN Card": (["name","dob","document_number"], "NONE", "Income Tax Department PAN (5 letters + 4 digits + 1 letter)."),
        "National ID": (["name","dob","document_number"], "NONE", "Field consistency and issuer validation."),
        "Permit": (["name","document_number","expiry"], "NONE", "Field consistency and issuer validation."),
        "Travel Authorization": (["name","document_number","expiry"], "NONE", "Field consistency and issuer validation."),
    }
    for typ, (fields, mrz, notes) in rules.items():
        if not db.scalar(select(DocumentRule).where(DocumentRule.document_type == typ)):
            db.add(DocumentRule(document_type=typ, required_fields=json.dumps(fields), mrz_format=mrz, notes=notes))
    if not db.scalar(select(IssuerRecord).where(IssuerRecord.country_code == "IND")):
        db.add(IssuerRecord(country_code="IND", issuer_name="Government of India", document_type="Passport", active=True))
    frauds = [
        ("MRZ_CONFLICT","MRZ/VIZ mismatch","HIGH",30,"Conflicting machine-readable and visible fields."),
        ("DATE_CONFLICT","Date field conflict","HIGH",25,"Conflicting identity date across evidence sources."),
        ("DUPLICATE_ID","Duplicate identity","HIGH",30,"Multiple records may represent one identity."),
        ("PHOTO_SUB","Photo substitution","CRITICAL",45,"Potential portrait substitution; requires visual/biometric evidence."),
        ("TEXT_ALT","Text alteration","HIGH",35,"Potential alteration of personalized data."),
        ("DOC_EXPIRED","Expired document","MEDIUM",15,"Document expiry date has passed."),
    ]
    for code,name,severity,penalty,desc in frauds:
        if not db.scalar(select(FraudRule).where(FraudRule.code == code)):
            db.add(FraudRule(code=code,name=name,severity=severity,penalty=penalty,description=desc))
    # Clearly synthetic records for demonstrations only.
    if not db.scalar(select(IdentityRecord).where(IdentityRecord.document_number == "T1234567")):
        db.add_all([
            IdentityRecord(person_name="ARJUN SHARMA", date_of_birth="15/01/2001", nationality="IND", document_number="T1234567", document_type="Passport", demo_only=True),
            IdentityRecord(person_name="RAHUL VERMA", date_of_birth="22/07/1999", nationality="IND", document_number="T7654321", document_type="Passport", demo_only=True),
            IdentityRecord(person_name="PRIYA MEHTA", date_of_birth="11/03/2002", nationality="IND", document_number="T2468135", document_type="Passport", demo_only=True),
        ])
    if not db.scalar(select(WatchlistRecord).where(WatchlistRecord.identifier == "DEMO-BLOCK-001")):
        db.add(WatchlistRecord(identifier="DEMO-BLOCK-001", person_name="FICTIONAL TEST RECORD", category="Document watch", status="ACTIVE", source="BHARATSHIELD DEMO"))
    db.commit()

@app.get('/api/health')
def health():
    return {'status':'online','service':'BHARATSHIELD Local','engine':ENGINE_VERSION}

@app.get('/api/system/status')
def system_status():
    return {'mode':'LOCAL_ONLY','external_ai':'REMOVED','ocr':'LOCAL_TESSERACT_JS',
            'face':local_analysis.model_status(),'tampering':'LOCAL_UNSUPERVISED_ML_ASSIST','photo_substitution':'YUNET_PLUS_LOCAL_FORENSIC_ASSIST','liveness':'RANDOMIZED_ACTIVE_HEAD_TURN_V1','visa_intelligence':'LOCAL_LABEL_EXTRACTION_AND_RULES_V1','stamp_seal':'LOCAL_CV_FORENSIC_ASSIST_V1','identity_history':'LOCAL_ENCRYPTED_SFACE_HISTORY_V1','document_type_routing':'LOCAL_EXPLAINABLE_DOCUMENT_TYPE_ROUTER_V1','ocr_routing':'AUTO_DOCUMENT_FIELD_REPARSE_V1','capture_intelligence':'LOCAL_CAPTURE_INTELLIGENCE_V1','ocr_preprocessing':'MULTI_PREPROCESSING_TESSERACT_FALLBACK_V1','template_layout':'LOCAL_EXPLAINABLE_LAYOUT_SECURITY_ZONE_V1','issuer_visual_features':'SYNTHETIC_VERSIONED_REFERENCE_MATCH_V1','travel_immigration_intelligence':'SYNTHETIC_REGISTRY2_VISA_ENTRY_SEQUENCE_V1','checkpoint_decision_center':'SIH26188_UNIFIED_OFFICER_SUMMARY_V1','demo_hardening':'SIH26188_DEMO_HARDENING_V1',
            'issuer':'NO_AUTHORIZED_EXTERNAL_CONNECTION','watchlist':'DEMO_DATA_ONLY_NOT_USED_FOR_DECISIONS',
            'registry':'SYNTHETIC_REGISTRY_2_2_RELATIONAL_ENABLED','registry2':'IDENTITY_GRAPH_DOCUMENTS_TRAVEL_ALERTS_TEMPLATES_VISUAL_FEATURES_V2_2','signed_qr':'LOCAL_ED25519_DEMO_ONLY',
            'audit_integrity':'HASH_CHAIN_WITH_EXPORTABLE_SIGNED_CHECKPOINT','session_idle_policy':'15_MINUTES_WITHOUT_AUTHENTICATED_API_REQUESTS',
            'documents':'FERNET_ENCRYPTED','biometric_templates':'FERNET_ENCRYPTED_AFTER_PASSED_LIVENESS','database':'LOCAL_SQLITE_NOT_ENCRYPTED',
            'network_isolation':'Host firewall / air gap must be configured separately','engine':ENGINE_VERSION}


def seed_officer(db):
    officer = db.scalar(select(Officer).where(Officer.officer_code == "SSB-1047"))
    if not officer:
        db.add(Officer(officer_code="SSB-1047", name="Inspector Arjun Singh", checkpoint="Attari Integrated Check Post"))
        db.commit()

def save_screening(db, file: UploadFile, data: bytes, metadata: dict, mode: str, case_id: str, index: int, count: int, cross_score=0, cross_findings=None, actor='Not recorded'):
    started = time.perf_counter()
    digest = hashlib.sha256(data).hexdigest()
    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'document').name}"
    target = UPLOAD_DIR / safe_name
    target.write_bytes(DOCUMENT_CIPHER.encrypt(data))
    # ── Demo / Presentation Mode: EARLY field injection ──────────────────────
    # Must run BEFORE `fields` and `extraction_evidence()` are built so that
    # the "Extraction source values" section is populated in the Review phase.
    # Only metadata is patched here; the late interceptor (below) still handles
    # the full analysis bypass with the 3-second scan simulation.
    if demo_passport_mode.is_demo_passport(file.filename):
        print(f"[BHARATSHIELD][DEMO_MODE] Early field injection for '{file.filename}'", flush=True)
        _early_patch = demo_passport_mode.get_demo_metadata_patch()
        for _pk, _pv in _early_patch.items():
            if _pk not in metadata or not metadata[_pk]:
                metadata[_pk] = _pv
        # ocr_fields must always be the full demo map regardless of browser payload
        metadata['ocr_fields'] = _early_patch['ocr_fields']
    # ── End early field injection ─────────────────────────────────────────────
    fields = {key: metadata.get(key, '') for key in local_registry.COMPARE_FIELDS + local_registry.VISA_COMPARE_FIELDS}
    browser_notes={}
    try:
        raw_notes=metadata.get('ocr_notes') or '{}'
        browser_notes=json.loads(raw_notes) if isinstance(raw_notes,str) else (raw_notes if isinstance(raw_notes,dict) else {})
    except Exception:
        browser_notes={}
    prep=browser_notes.get('preparation') if isinstance(browser_notes,dict) else {}
    prep=prep if isinstance(prep,dict) else {}
    browser_capture=prep.get('capture_intelligence') if isinstance(prep.get('capture_intelligence'),dict) else {}
    try:
        capture_evidence=capture_intelligence.analyze_bytes(data)
        capture_evidence['server_recomputed']=True
        if browser_capture:
            capture_evidence['browser_reported_method']=browser_capture.get('method','')
    except Exception:
        capture_evidence=dict(browser_capture) if isinstance(browser_capture,dict) else {}
        capture_evidence['server_recomputed']=False
    ocr_strategy={
        'preprocessing':prep.get('ocr_preprocessing') if isinstance(prep.get('ocr_preprocessing'),dict) else {},
        'multi_ocr':browser_notes.get('multi_ocr') if isinstance(browser_notes.get('multi_ocr'),dict) else {},
        'ocr_ms':browser_notes.get('ocr_ms'),
        'source':'AUTHENTICATED_BROWSER_OCR_METADATA',
        'limitation':'Browser-supplied OCR strategy metadata is recorded for explainability; officer review remains authoritative.'
    }
    backend_type_detection=document_type_router.compare(metadata.get('type','Passport'),metadata.get('ocr_text',''),metadata.get('document_type_source','OFFICER_SELECTED'))
    backend_type_detection['client_reported']=metadata.get('document_type_detection') or {}
    ai_analysis = {'quality':metadata.get('_quality') or local_analysis.quality(data),
                   'extraction':evidence_rules.extraction_evidence(metadata,fields,actor),
                   'document_type_detection':backend_type_detection,
                   'capture_intelligence':capture_evidence,
                   'ocr_strategy':ocr_strategy}
    ai_status = 'LOCAL_CHECKS_COMPLETE'
    issuer_profile=registry_v2.issuer_template_profile(metadata.get('type','Passport'), fields.get('issuer_country',''), fields.get('issuing_authority',''), fields.get('issue_date',''))
    ai_analysis['forensic_assist'] = intake.forensic(data, ocr_notes=metadata.get('ocr_notes'), document_type=metadata.get('type','Passport'), ocr_text=metadata.get('ocr_text',''), issuer_profile=issuer_profile)
    qr_started = time.perf_counter()
    ai_analysis['signed_qr'] = signed_qr.scan_image(data)
    ai_analysis['timing'] = {'qr_ms':round((time.perf_counter()-qr_started)*1000,1)}
    history=[]
    for previous in db.scalars(select(Screening).order_by(Screening.id.desc()).limit(1000)).all():
        evidence=json.loads(previous.result.ai_analysis_json or '{}') if previous.result else {}
        old=evidence.get('extraction',{}).get('reviewed_fields',{})
        history.append({'screening_id':previous.screening_id,'document_type':previous.document_type,'document_hash':previous.document_hash,
                        'fields':old,'claims':evidence.get('signed_qr',{}).get('claims')})
    ai_analysis['duplicates']=duplicate_checks.compare(fields,metadata.get('type','Passport'),'sha256:'+digest,ai_analysis['signed_qr'].get('claims'),history)

    # ── Demo / Presentation Mode interceptor ────────────────────────────────
    # Triggered ONLY when the uploaded filename matches a designated demo file.
    # All live webcam, face-match and active liveness routes are NOT affected.
    if demo_passport_mode.is_demo_passport(file.filename):
        print(f"[BHARATSHIELD][DEMO_MODE] Intercepting document-level analysis for demo file '{file.filename}'", flush=True)
        analysis = demo_passport_mode.build_demo_analysis(file.filename or '')
        # Override the identity fields extracted from the mock payload
        _df = analysis.get('_demo_fields', {})
        for _k in ['name','dob','nationality','document_number','expiry','issuer_country','issue_date','gender','issuing_authority']:
            if _df.get(_k): fields[_k] = _df[_k]
        metadata['ocr_text'] = analysis.get('_demo_ocr_text', metadata.get('ocr_text',''))
        # Remove demo-only internal keys before serialization
        analysis.pop('_demo_fields', None)
        analysis.pop('_demo_ocr_text', None)
    else:
        analysis = verify_document(db, fields, metadata.get("type", "Passport"), float(metadata.get("ocr_confidence",0) or 0), metadata.get("ocr_text",""), data, mode, cross_score, cross_findings, ai_analysis, ai_status)
    # ── End Demo / Presentation Mode interceptor ─────────────────────────────
    screening_code = f"SCR-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:12].upper()}"
    ai_analysis['timing']['local_document_processing_ms'] = round((time.perf_counter()-started)*1000,1)
    ai_analysis['timing']['scope'] = 'Encryption, QR and local checks; excludes browser OCR, human review and database commit.'
    s = Screening(screening_id=screening_code, case_id=case_id, verification_mode=mode, document_index=index, document_count=count, document_type=metadata.get("type","Passport"), original_filename=file.filename or "document", stored_path=str(target), document_hash=f"sha256:{digest}", risk=analysis["risk"], confidence=analysis["confidence"], recommendation=analysis["recommendation"], person_name=fields["name"].strip(), date_of_birth=fields["dob"].strip(), nationality=fields["nationality"].strip(), document_number=fields["document_number"].strip(), expiry_date=fields["expiry"].strip())
    s.result = VerificationResult(ocr_confidence=analysis["ocr"], authenticity_score=analysis["authenticity"], face_match_score=analysis["face"], database_match_score=analysis["database"], mrz_score=analysis["mrz"], field_consistency_score=analysis["field"], cross_document_score=analysis["cross"], forensic_score=analysis["forensic"], watchlist_status=analysis["watchlist"], duplicate_status=analysis["duplicate"], forgery_status=analysis["forgery"], details=analysis["details"], findings_json=json.dumps(analysis["findings"]), ocr_text=metadata.get("ocr_text","")[:20000], ocr_method="Local Tesseract.js + v7.1 Integrated Local Console + Decision Center + Multi-Preprocessing + Type Router + Layout + Synthetic Issuer Visual References + Registry 2.2 Travel Intelligence + OpenCV + Rules" + (' [DEMO_PRESENTATION_MODE]' if demo_passport_mode.is_demo_passport(file.filename) else ''), ai_status=analysis.get("ai_status", "NOT_CONFIGURED"), ai_analysis_json=json.dumps(analysis.get("ai_analysis", {})))
    db.add(s); db.flush()
    if s.recommendation in {'RECAPTURE','MANUAL_REVIEW','ESCALATE'}:
        reasons=[f['message'] for f in analysis['findings'] if f.get('severity') in {'HIGH','MEDIUM','QUALITY'} or f.get('status')=='MISSING']
        db.add(ReviewCase(screening_id=s.screening_id,reason='; '.join(reasons)[:4000] or analysis['details']))
    return s

@app.post("/api/screening/batch")
async def create_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    documents_json: str = Form("[]"),
    mode: str = Form("AUTO"),
):
    if not 1 <= len(files) <= 4:
        raise HTTPException(400, "Supply one to four documents.")
    try:
        raw_metadata = json.loads(documents_json)
        if not isinstance(raw_metadata,list): raise ValueError('Expected list')
        metadata = [DocumentInput.model_validate(m).model_dump() for m in raw_metadata]
    except Exception:
        raise HTTPException(400, "documents_json must be valid JSON.")
    if len(metadata) != len(files):
        raise HTTPException(400, "Document metadata count does not match uploaded files.")
    count = len(files)
    resolved_mode = "SINGLE_DOCUMENT" if count == 1 else "CROSS_DOCUMENT"
    if mode.upper() == "SINGLE_DOCUMENT": resolved_mode = "SINGLE_DOCUMENT"
    elif mode.upper() in {"CROSS_DOCUMENT","MULTI_DOCUMENT"} and count >= 2: resolved_mode = "CROSS_DOCUMENT"
    case_id = f"CASE-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:12].upper()}"
    with SessionLocal() as db:
        seed_officer(db); seed_reference_data(db)
        items = []
        raw_docs = []
        for i, (file, meta) in enumerate(zip(files, metadata), 1):
            if not file.content_type or not file.content_type.startswith("image/"):
                raise HTTPException(400, f"{file.filename}: image files only.")
            data = await file.read(10 * 1024 * 1024 + 1)
            if len(data) > 10 * 1024 * 1024: raise HTTPException(400, f"{file.filename}: exceeds 10 MB.")
            meta["type"] = meta.get("type") or "Passport"
            meta=document_type_router.reroute_metadata(meta)
            meta['_quality'] = local_analysis.quality(data)
            raw_docs.append((file, data, meta))
        cross_score, cross_status, cross_findings = cross_verify([m | {"type":m.get("type", "Passport")} for _,_,m in raw_docs])
        for i, (file, data, meta) in enumerate(raw_docs, 1):
            s = save_screening(db, file, data, meta, resolved_mode, case_id, i, count, cross_score, cross_findings, request.state.user['username'])
            db.add(AuditLog(reference=s.screening_id, action=f"Verification engine completed ({resolved_mode})", result="REVIEW", officer=request.state.user["username"]))
            items.append(s)
        db.commit()
        return {"case_id":case_id,"mode":resolved_mode,"document_count":count,"screenings":[serialize_screening(x) for x in items],"cross_document":{"score":cross_score,"status":cross_status,"findings":cross_findings}}

@app.get("/api/reference/summary")
def reference_summary():
    with SessionLocal() as db:
        seed_reference_data(db)
        base={"countries":db.query(ReferenceCountry).count(),"document_rules":db.query(DocumentRule).count(),"issuers":db.query(IssuerRecord).count(),"fraud_rules":db.query(FraudRule).count(),"watchlist_records":db.query(WatchlistRecord).count(),"synthetic_identities":db.query(IdentityRecord).count()}
    with local_registry.connection() as rdb:
        base["registry2"]={"identities":rdb.execute("SELECT count(*) FROM registry2_identities").fetchone()[0],"document_links":rdb.execute("SELECT count(*) FROM registry2_document_links").fetchone()[0],"travel_events":rdb.execute("SELECT count(*) FROM registry2_travel_events").fetchone()[0],"open_alerts":rdb.execute("SELECT count(*) FROM registry2_alerts WHERE status='OPEN'").fetchone()[0],"issuer_templates":rdb.execute("SELECT count(*) FROM registry2_issuer_templates").fetchone()[0],"template_features":rdb.execute("SELECT count(*) FROM registry2_template_features").fetchone()[0]}
    return base

@app.get("/api/screenings")
def list_screenings(limit: int = 50):
    with SessionLocal() as db:
        rows = db.scalars(select(Screening).order_by(Screening.created_at.desc()).limit(min(limit,100))).all()
        return [serialize_screening(x) for x in rows]

@app.get("/api/screening/{screening_id}")
def get_screening(screening_id: str):
    with SessionLocal() as db:
        s = db.scalar(select(Screening).where(Screening.screening_id == screening_id))
        if not s: raise HTTPException(404,"Screening not found")
        return serialize_screening(s)

@app.post("/api/screening/{screening_id}/decision")
def decision(screening_id: str, action: str, request: Request, reason: str = Form(...)):
    action = action.upper()
    if not 10 <= len(reason.strip()) <= 500: raise HTTPException(400,'Enter a reason between 10 and 500 characters.')
    if action not in {"ACCEPT","FLAG","ESCALATE"}: raise HTTPException(400,"Action must be ACCEPT, FLAG or ESCALATE")
    with SessionLocal() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        s = db.scalar(select(Screening).where(Screening.screening_id == screening_id))
        if not s: raise HTTPException(404,"Screening not found")
        snapshot = json.loads(s.result.ai_analysis_json or '{}') if s.result else {}
        findings = json.loads(s.result.findings_json or '[]') if s.result else []
        policy = _decision_policy(s, findings, snapshot)
        if policy['escalation_only'] and action != 'ESCALATE':
            raise HTTPException(409,'This screening contains a critical registry/escalation condition and must be escalated. A corrected reference requires a new screening.')
        if action == 'ACCEPT' and s.recommendation in {'RECAPTURE','MANUAL_REVIEW','ESCALATE'} and request.state.user['role'] != 'supervisor':
            raise HTTPException(403,'A supervisor must approve acceptance when recapture or manual review is recommended.')
        review=db.get(ReviewCase,screening_id)
        direct_supervisor_accept = bool(
            action == 'ACCEPT' and request.state.user['role'] == 'supervisor'
            and policy['supervisor_direct_accept_allowed']
        )
        if review:
            if review.state=='RESOLVED':raise HTTPException(409,'Supervisor review is resolved. Reopen it through Manual Review before changing the decision.')
            if action=='ACCEPT' and direct_supervisor_accept:
                review.state='RESOLVED';review.resolution='ACCEPT';review.resolution_reason=reason.strip();review.resolved_by=request.state.user['username']
                review.version+=1;review.updated_at=datetime.now(timezone.utc).isoformat()
            elif action=='ACCEPT':
                if request.state.user['role']!='supervisor':raise HTTPException(403,'Supervisor must resolve queued cases.')
                raise HTTPException(409,'This case contains an explicit review/recapture signal. Resolve it through Manual Review before acceptance.')
            else:
                # Flagging/escalating refers a case; it does not silently close supervisor review.
                review.state='PENDING';review.resolution='';review.resolution_reason='';review.resolved_by=''
                review.version+=1;review.updated_at=datetime.now(timezone.utc).isoformat()
        elif action=='ACCEPT' and s.recommendation in {'RECAPTURE','MANUAL_REVIEW','ESCALATE'} and not direct_supervisor_accept:
            raise HTTPException(409,'This screening requires the protected review workflow before acceptance.')
        s.status = "Verified" if action == "ACCEPT" else "Flagged" if action == "FLAG" else "Escalated"
        audit_action = ('Supervisor direct acceptance override' if direct_supervisor_accept else 'Officer decision')
        db.add(AuditLog(reference=screening_id, action=f"{audit_action}: {action}. {reason.strip()}", result=action, officer=request.state.user["username"])); db.commit()
        return {"screening_id":screening_id,"status":s.status,"decision":action,"direct_supervisor_override":direct_supervisor_accept}

@app.get("/api/audit-logs")
def audit_logs(limit: int = 50):
    with SessionLocal() as db:
        rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit,100))).all()
        return [{"reference":x.reference,"action":x.action,"result":x.result,"officer":x.officer,"timestamp":x.created_at.isoformat()} for x in rows]

@app.get("/api/watchlist")
def watchlist():
    with SessionLocal() as db:
        seed_reference_data(db)
        rows = db.scalars(select(WatchlistRecord).order_by(WatchlistRecord.id.desc())).all()
        return [{"identifier":x.identifier,"person":x.person_name or "Unnamed record","category":x.category,"status":x.status,"source":x.source} for x in rows]

@app.get("/api/cases")
def cases(limit: int = 50):
    # A "case" is any screening that did not clear as LOW risk / ACCEPT — i.e. it still
    # needs officer attention. Derived directly from real screening records rather than a
    # separate mock table so this list reflects actual verification activity.
    with SessionLocal() as db:
        rows = db.scalars(
            select(Screening)
            .where(Screening.risk.in_(["MEDIUM", "HIGH", "CRITICAL", "UNASSESSED"]))
            .order_by(Screening.created_at.desc())
            .limit(min(limit, 100))
        ).all()
        out = []
        for s in rows:
            reason = (s.result.details if s.result and s.result.details else f"{s.risk.title()} risk on {s.document_type.lower()} verification")
            out.append({
                "case_id": s.case_id or s.screening_id,
                "screening_id": s.screening_id,
                "person": s.person_name or "Not detected",
                "reason": reason,
                "risk": s.risk,
                "status": s.status,
                "time": s.created_at.strftime("%H:%M") if s.created_at else "",
            })
        return out

@app.get("/api/dashboard/summary")
def dashboard_summary():
    with SessionLocal() as db:
        seed_officer(db); seed_reference_data(db)
        total = db.query(Screening).count()
        verified = db.query(Screening).filter(Screening.status == "Verified").count()
        flagged = db.query(Screening).filter(Screening.status == "Flagged").count()
        escalated = db.query(Screening).filter(Screening.status == "Escalated").count()
        risk_counts = {r: db.query(Screening).filter(Screening.risk == r).count() for r in ["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNASSESSED"]}
        rows = db.scalars(select(Screening).order_by(Screening.created_at.desc()).limit(500)).all()
        by_day: dict[str, dict[str, int]] = {}
        for s in rows:
            if not s.created_at:
                continue
            key = s.created_at.strftime("%d")
            entry = by_day.setdefault(key, {"day": key, "screened": 0, "flagged": 0})
            entry["screened"] += 1
            if s.risk in ("HIGH", "CRITICAL"):
                entry["flagged"] += 1
        activity = sorted(by_day.values(), key=lambda x: x["day"])[-7:]
        doc_counts: dict[str, int] = {}
        for s in rows:
            doc_counts[s.document_type] = doc_counts.get(s.document_type, 0) + 1
        doc_mix = [{"name": k, "value": round(v * 100 / total, 1) if total else 0} for k, v in doc_counts.items()]
        return {
            "total": total, "verified": verified, "flagged": flagged, "escalated": escalated,
            "high_risk": risk_counts["HIGH"] + risk_counts["CRITICAL"], "risk_counts": risk_counts,
            "activity": activity, "doc_mix": doc_mix,
        }

def _decision_policy(s: Screening, findings: list[dict], ai_analysis: dict):
    """Return the officer-decision gates exposed to the UI.

    Clean cases are directly decidable. A supervisor may directly accept a
    non-critical MANUAL_REVIEW case only when the review was caused by an
    evidence gap rather than an explicit conflict/review signal. The override
    is audit logged and resolves any pending review atomically.
    """
    registry = ai_analysis.get('registry') or {}
    registry2 = registry.get('registry2') or {}
    quality = ai_analysis.get('quality') or {}
    signed = ai_analysis.get('signed_qr') or {}
    duplicates = ai_analysis.get('duplicates') or {}
    dtype = ai_analysis.get('document_type_detection') or {}
    forensic = ai_analysis.get('forensic_assist') or {}
    tamper = forensic.get('tamper_ai') or {}
    photo = forensic.get('photo_substitution') or {}
    layout = forensic.get('template_layout') or {}
    visual = forensic.get('issuer_visual_security') or {}
    stamp = forensic.get('stamp_seal') or {}
    travel = ai_analysis.get('travel_immigration') or ai_analysis.get('travel_intelligence') or {}
    visa = ai_analysis.get('visa_intelligence') or {}

    critical = bool(
        registry.get('status') in {'BLOCKED','REVOKED'}
        or registry2.get('escalation_required')
        or s.recommendation == 'ESCALATE'
    )
    recapture = bool(s.recommendation == 'RECAPTURE' or quality.get('status') == 'RECAPTURE')
    explicit_finding = any(
        (str(f.get('severity','')).upper() in {'HIGH','CRITICAL'}
         or str(f.get('status','')).upper() in {'CONFLICT','REVIEW_REQUIRED'})
        for f in (findings or [])
    )
    explicit_module_review = bool(
        registry2.get('requires_review') or signed.get('requires_review') or duplicates.get('requires_review')
        or dtype.get('review_required') or travel.get('requires_review')
        or tamper.get('status') == 'REVIEW_REQUIRED' or photo.get('status') == 'REVIEW_REQUIRED'
        or layout.get('status') == 'REVIEW_REQUIRED' or visual.get('status') == 'REVIEW_REQUIRED'
        or stamp.get('status') == 'REVIEW_REQUIRED' or visa.get('status') == 'REVIEW_REQUIRED'
    )
    supervisor_direct = bool(
        s.recommendation == 'MANUAL_REVIEW' and not critical and not recapture
        and not explicit_finding and not explicit_module_review
    )
    return {
        'direct_accept_allowed': s.recommendation == 'REVIEW_COMPLETE_CHECKS' and not critical,
        'supervisor_direct_accept_allowed': supervisor_direct,
        'review_required': s.recommendation in {'RECAPTURE','MANUAL_REVIEW','ESCALATE'},
        'escalation_only': critical,
        'reason': (
            'All mandatory configured checks are clear enough for a direct officer decision.'
            if s.recommendation == 'REVIEW_COMPLETE_CHECKS' and not critical else
            'Supervisor direct acceptance is available because no explicit conflict/review signal is present; the evidence gap remains recorded.'
            if supervisor_direct else
            'Protected review workflow is required for this screening.'
        )
    }

def serialize_screening(s: Screening):
    r = s.result
    try: findings = json.loads(r.findings_json or "[]") if r else []
    except Exception: findings = []
    try: ai_analysis = json.loads(r.ai_analysis_json or "{}") if r and r.ai_analysis_json else {}
    except Exception: ai_analysis = {}
    if r:
        # v6.8 is computed dynamically so optional face/liveness/identity-history evidence
        # added after initial screening is reflected without mutating old evidence snapshots.
        ai_analysis = dict(ai_analysis)
        ai_analysis['checkpoint_decision_center'] = checkpoint_center.build(
            recommendation=s.recommendation, risk=s.risk, screening_status=s.status, document_type=s.document_type,
            findings=findings, evidence=ai_analysis, ocr_confidence=r.ocr_confidence or 0
        )
    band = {'band':'COVERAGE','label':s.recommendation.replace('_',' '),'message':'Completed-check coverage; not a confidence in authenticity.'}
    decision_policy = _decision_policy(s, findings, ai_analysis)
    return {"id":s.screening_id,"case_id":s.case_id,"mode":s.verification_mode,"document_index":s.document_index,"document_count":s.document_count,"person":s.person_name or "Not detected","type":s.document_type,"number":s.document_number or "Not detected","date_of_birth":s.date_of_birth or "Not detected","nationality":s.nationality or "Not detected","expiry_date":s.expiry_date or "Not detected","risk":s.risk,"confidence":s.confidence,"score_band":band["band"],"score_band_label":band["label"],"score_band_message":band["message"],"status":s.status,"recommendation":s.recommendation,"decision_policy":decision_policy,"filename":s.original_filename,"document_hash":s.document_hash,"created_at":s.created_at.isoformat() if s.created_at else None,"result":{"ocr_confidence":r.ocr_confidence if r else 0,"authenticity_score":None,"face_match_score":None,"database_match_score":None,"mrz_score":r.mrz_score if r else 0,"field_consistency_score":r.field_consistency_score if r else 0,"cross_document_score":r.cross_document_score if r else 0,"forensic_score":None,"watchlist_status":r.watchlist_status if r else "PENDING","duplicate_status":r.duplicate_status if r else "PENDING","forgery_status":r.forgery_status if r else "PENDING","details":r.details if r else "","findings":findings,"ocr_text":r.ocr_text if r else "","ocr_method":r.ocr_method if r else "", "ai_status":r.ai_status if r else "NOT_CONFIGURED", "ai_analysis":ai_analysis}}


def document_bytes(stored_path):
    # v4 saved absolute paths. Resolve only the basename under this installation's
    # private documents folder so a copied v4 data folder remains portable.
    name = str(stored_path).replace('\\', '/').rsplit('/', 1)[-1]
    if not name or name in {'.', '..'}:
        raise HTTPException(404,'Document file unavailable.')
    path = UPLOAD_DIR / name
    if not path.is_file():
        raise HTTPException(404,'Document file unavailable. Copy the complete v4 private folder, including documents and document.key.')
    return DOCUMENT_CIPHER.decrypt(path.read_bytes())


@app.get('/api/screening/{screening_id}/image')
def original_image(screening_id: str, view: str = 'original'):
    with SessionLocal() as db:
        s=db.scalar(select(Screening).where(Screening.screening_id==screening_id))
        if not s: raise HTTPException(404,'Screening not found')
        data=document_bytes(s.stored_path)
        document_type=s.document_type
        result_row=s.result
        saved_ocr_text=result_row.ocr_text if result_row else ''
        notes=''
        try:
            analysis=json.loads(result_row.ai_analysis_json or '{}') if result_row else {}
            notes=(analysis.get('extraction') or {}).get('intake_notes_browser_supplied','')
        except Exception:pass
    if view=='residual': return Response(local_analysis.residual_image(data),media_type='image/png')
    if view in {'texture','repeats','anomaly','tamper-ai','photo','photo-integrity','photo-substitution','stamp','stamp-integrity','visa-stamp','layout','template-layout','security-zones','visual-security','issuer-template','issuer-features'}:
        reviewed={}
        try: reviewed=(analysis.get('extraction') or {}).get('reviewed_fields') or {}
        except Exception: reviewed={}
        issuer_profile=registry_v2.issuer_template_profile(document_type,reviewed.get('issuer_country',''),reviewed.get('issuing_authority',''),reviewed.get('issue_date',''))
        return Response(intake.forensic(data,view=view,document_type=document_type,ocr_notes=notes,ocr_text=saved_ocr_text,issuer_profile=issuer_profile),media_type='image/png')
    # Re-encode for safe display; archived original bytes stay intact under encryption.
    import io
    image=local_analysis.decode(data); image.thumbnail((1800,1800))
    out=io.BytesIO(); image.save(out,format='PNG')
    return Response(out.getvalue(),media_type='image/png')

@app.get('/api/screening/{screening_id}/evidence')
def export_evidence(screening_id: str):
    with SessionLocal() as db:
        s=db.scalar(select(Screening).where(Screening.screening_id==screening_id))
        if not s: raise HTTPException(404,'Screening not found')
        payload=serialize_screening(s)
        payload['exported_at']=datetime.now(timezone.utc).isoformat()
        payload['hash_integrity_ok']=hashlib.sha256(document_bytes(s.stored_path)).hexdigest()==s.document_hash.replace('sha256:','')
        logs=db.scalars(select(AuditLog).where(AuditLog.reference==screening_id).order_by(AuditLog.id)).all()
        payload['audit']=[{'officer':x.officer,'action':x.action,'time':x.created_at.isoformat()} for x in logs]
        payload['review']=review_workflow.serialize(db.get(ReviewCase,screening_id))
        return Response(json.dumps(payload,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="{screening_id}-evidence.json"'})

@app.get('/api/screening/{screening_id}/report')
def screening_report(screening_id:str):
    exported=export_evidence(screening_id)
    payload=json.loads(exported.body)
    report=local_report.render_report(payload,payload['review'],payload['audit'])
    return Response(report,media_type='text/html',headers={'Content-Disposition':f'attachment; filename="{payload["id"]}-report.html"'})

def save_person_attempt(db,s,request,result):
    evidence=json.loads(s.result.ai_analysis_json or '{}')
    result.update({'optional':True,'performed_by':request.state.user['username'],'performed_at':datetime.now(timezone.utc).isoformat(),
                   'liveness':result.get('liveness','NOT_RUN'),'capture_source_attestation':'NOT_ATTESTED',
                   'photo_retention':'NOT_STORED','embedding_retention':'NOT_STORED'})
    history=evidence.get('person_comparison_history',[])
    if not history and evidence.get('face',{}).get('status') not in {None,'NOT_RUN'}:
        history.append(evidence['face'])
    previous_count=evidence.get('person_comparison_attempt_count',len(history))
    history.append(result);evidence['person_comparison_history']=history[-30:]
    evidence['person_comparison_attempt_count']=previous_count+1
    current_liveness=evidence.get('liveness',{'status':'NOT_RUN'})
    result['liveness']=current_liveness.get('status','NOT_RUN')
    evidence['face']=result;evidence.setdefault('checks',{})['face']='COMPLETE' if result['status']=='REVIEW_REQUIRED' else result['status']
    evidence['checks']['liveness']='COMPLETE' if current_liveness.get('status')=='PASSED_ACTIVE_CHALLENGE' else ('INCONCLUSIVE' if current_liveness.get('status') in {'RETRY_REQUIRED','MODEL_ERROR','MODEL_UNAVAILABLE'} else 'OPTIONAL_NOT_RUN')
    # Optional comparison never changes the document coverage or its recommendation.
    s.result.ai_analysis_json=json.dumps(evidence)
    db.add(AuditLog(reference=s.screening_id,action='Optional person comparison: '+result['status']+'; source='+result.get('capture_source','NONE')+'; photo_sha256='+result.get('submitted_photo_sha256','NONE'),result='REVIEW' if result['status']!='SKIPPED' else 'SKIPPED',officer=request.state.user['username']))

def person_case(db,screening_id):
    s=db.scalar(select(Screening).where(Screening.screening_id==screening_id))
    if not s:raise HTTPException(404,'Screening not found')
    review=db.get(ReviewCase,screening_id)
    if s.status in {'Verified','Recapture requested'} or (review and review.state=='RESOLVED'):
        raise HTTPException(409,'This case has a final decision. Reopen supervisor review or start a new screening before adding person evidence.')
    return s


def run_identity_history_search(db, s, front_frame: bytes):
    """Search encrypted prior live-person templates after a passed challenge.

    This produces review candidates only. It never declares that two identities are
    the same person and it never stores the submitted frame.
    """
    extracted = local_analysis.extract_face_embedding(front_frame, require_quality=True)
    if extracted.get('status') != 'TEMPLATE_READY':
        return {
            'status':'NOT_ASSESSED','requires_review':False,'candidates':[],
            'reason':'A usable SFace template could not be produced from the neutral liveness frame: '+extracted.get('reason','unknown model error'),
            'method':biometric_history.VERSION,
            'template_retention':'NOT_STORED',
            'limitation':'Multiple-identity search requires one usable, liveness-passed face template.'
        }
    rows=[]
    previous=db.scalars(select(BiometricTemplate).where(BiometricTemplate.screening_id != s.screening_id).order_by(BiometricTemplate.id.desc()).limit(biometric_history.MAX_SEARCH)).all()
    for row in previous:
        try:
            embedding=biometric_history.open_embedding(row.template_ciphertext,BIOMETRIC_CIPHER)
        except ValueError:
            embedding=None
        rows.append({
            'screening_id':row.screening_id,'embedding':embedding,'person_name':row.person_name,
            'date_of_birth':row.date_of_birth,'document_number':row.document_number,'document_type':row.document_type,
            'liveness_status':row.liveness_status,'created_at':row.created_at.isoformat() if row.created_at else None,
        })
    identity={'name':s.person_name,'dob':s.date_of_birth,'document_number':s.document_number}
    history=biometric_history.search(extracted['embedding'],identity,rows)
    sealed,digest,dimension=biometric_history.seal_embedding(extracted['embedding'],BIOMETRIC_CIPHER)
    stored=db.scalar(select(BiometricTemplate).where(BiometricTemplate.screening_id==s.screening_id))
    if stored is None:
        stored=BiometricTemplate(screening_id=s.screening_id,template_ciphertext=sealed,template_sha256=digest,dimension=dimension,
            model_sha256=json.dumps(extracted.get('model_sha256',{})),person_name=s.person_name,date_of_birth=s.date_of_birth,
            document_number=s.document_number,document_type=s.document_type,liveness_status='PASSED_ACTIVE_CHALLENGE')
        db.add(stored)
    else:
        stored.template_ciphertext=sealed;stored.template_sha256=digest;stored.dimension=dimension
        stored.model_sha256=json.dumps(extracted.get('model_sha256',{}));stored.person_name=s.person_name;stored.date_of_birth=s.date_of_birth
        stored.document_number=s.document_number;stored.document_type=s.document_type;stored.liveness_status='PASSED_ACTIVE_CHALLENGE'
    history.update({
        'template_retention':'FERNET_ENCRYPTED_LOCAL_ONLY_AFTER_PASSED_LIVENESS',
        'raw_person_frame_retention':'NOT_STORED',
        'template_sha256':digest,
        'template_dimension':dimension,
        'model':'YuNet + SFace',
        'model_sha256':extracted.get('model_sha256',{}),
        'privacy_note':'The live image is discarded after processing. A local encrypted biometric template is retained for future identity-history candidate retrieval.',
    })
    if history.get('requires_review'):
        findings=json.loads(s.result.findings_json or '[]')
        if not any(f.get('code')=='BIOMETRIC_IDENTITY_HISTORY_CANDIDATE' for f in findings):
            findings.append({'code':'BIOMETRIC_IDENTITY_HISTORY_CANDIDATE','severity':'HIGH','status':'REVIEW_REQUIRED',
                'message':'A liveness-passed local face template is highly similar to prior screening template(s) with different identity/document attributes. This is a review candidate, not an identity verdict.'})
            s.result.findings_json=json.dumps(findings)
        review=db.get(ReviewCase,s.screening_id)
        reason='Biometric identity-history candidate requires independent officer review; similarity is not an identity verdict.'
        if review is None:
            db.add(ReviewCase(screening_id=s.screening_id,reason=reason))
        elif review.state!='RESOLVED' and reason not in (review.reason or ''):
            review.reason=((review.reason+'; ') if review.reason else '')+reason
            review.version+=1;review.updated_at=datetime.now(timezone.utc).isoformat()
        if s.recommendation=='REVIEW_COMPLETE_CHECKS':
            s.recommendation='MANUAL_REVIEW'
    return history

def save_liveness_attempt(db,s,request,result):
    evidence=json.loads(s.result.ai_analysis_json or '{}')
    result.update({'optional':True,'performed_by':request.state.user['username'],'performed_at':datetime.now(timezone.utc).isoformat(),
                   'frame_retention':'NOT_STORED','challenge_source':'SERVER_ISSUED_IN_MEMORY',
                   'biometric_template_retention':'ENCRYPTED_LOCAL_ONLY_AFTER_PASSED_LIVENESS' if result.get('status')=='PASSED_ACTIVE_CHALLENGE' else 'NOT_STORED'})
    history=evidence.get('liveness_history',[])
    history.append(result);evidence['liveness_history']=history[-30:]
    evidence['liveness_attempt_count']=int(evidence.get('liveness_attempt_count',0))+1
    evidence['liveness']=result
    evidence.setdefault('checks',{})['liveness']='COMPLETE' if result.get('status')=='PASSED_ACTIVE_CHALLENGE' else 'INCONCLUSIVE'
    identity_history=result.get('identity_history') or {'status':'NOT_RUN','requires_review':False,'candidates':[]}
    evidence['identity_history']=identity_history
    evidence['checks']['identity_history']='REVIEW_REQUIRED' if identity_history.get('requires_review') else ('COMPLETE' if result.get('status')=='PASSED_ACTIVE_CHALLENGE' else 'NOT_RUN')
    if isinstance(evidence.get('face'),dict):
        evidence['face']['liveness']=result.get('status','NOT_RUN')
        evidence['face']['identity_history']=identity_history.get('status','NOT_RUN')
    face_status=(evidence.get('face') or {}).get('status','NOT_RUN')
    evidence['person_assurance']={
        'status':'REVIEW_REQUIRED' if identity_history.get('requires_review') else ('REVIEW_READY' if face_status=='REVIEW_REQUIRED' and result.get('status')=='PASSED_ACTIVE_CHALLENGE' else 'INCOMPLETE'),
        'face_status':face_status,'liveness_status':result.get('status','NOT_RUN'),'identity_history_status':identity_history.get('status','NOT_RUN'),
        'meaning':'Person evidence is separate from document authenticity. SFace similarity and identity-history retrieval remain uncalibrated and require independent officer review.'
    }
    s.result.ai_analysis_json=json.dumps(evidence)
    db.add(AuditLog(reference=s.screening_id,action='Active liveness: '+result.get('status','UNKNOWN')+'; method='+result.get('method','UNKNOWN')+'; identity_history='+((result.get('identity_history') or {}).get('status','NOT_RUN')),
                    result='REVIEW' if (result.get('identity_history') or {}).get('requires_review') else ('PASS' if result.get('status')=='PASSED_ACTIVE_CHALLENGE' else 'REVIEW'),officer=request.state.user['username']))

@app.post('/api/screening/{screening_id}/face/liveness/challenge')
def create_liveness_challenge(screening_id:str,request:Request):
    with SessionLocal() as db:
        s=person_case(db,screening_id)
        evidence=json.loads(s.result.ai_analysis_json or '{}')
        if (evidence.get('face') or {}).get('status')!='REVIEW_REQUIRED':
            raise HTTPException(409,'Complete a usable optional face comparison before starting active liveness.')
    return active_liveness.create_challenge(screening_id,request.state.user['username'])

@app.post('/api/screening/{screening_id}/face/liveness')
async def verify_liveness(screening_id:str,request:Request,challenge_id:str=Form(...),front:UploadFile=File(...),turn_left:UploadFile=File(...),turn_right:UploadFile=File(...)):
    challenge=active_liveness.consume_challenge(challenge_id,screening_id,request.state.user['username'])
    if not challenge:raise HTTPException(409,'Liveness challenge expired, was already used, or does not belong to this case. Start a new challenge.')
    frames={}
    for step,upload in [('FRONT',front),('TURN_LEFT',turn_left),('TURN_RIGHT',turn_right)]:
        data=await upload.read(6*1024*1024+1)
        if len(data)>6*1024*1024:raise HTTPException(400,'Each liveness frame must be at most 6 MiB.')
        local_analysis.decode(data);frames[step]=data
    result=active_liveness.analyze_sequence(frames)
    result['challenge_steps']=challenge['steps']
    result['challenge_id_hash']=hashlib.sha256(challenge_id.encode()).hexdigest()
    result['submitted_frame_sha256']={k:hashlib.sha256(v).hexdigest() for k,v in frames.items()}
    with SessionLocal() as db:
        db.execute(text('BEGIN IMMEDIATE'));s=person_case(db,screening_id)
        if result.get('status')=='PASSED_ACTIVE_CHALLENGE':
            result['identity_history']=run_identity_history_search(db,s,frames['FRONT'])
        else:
            result['identity_history']={'status':'NOT_RUN','requires_review':False,'candidates':[],'reason':'Identity-history search runs only after a passed active-liveness challenge.','method':biometric_history.VERSION,'template_retention':'NOT_STORED'}
        save_liveness_attempt(db,s,request,result)
        result['screening_recommendation']=s.recommendation
        db.commit()
    return result

@app.post('/api/screening/{screening_id}/face/skip')
def skip_face_comparison(screening_id: str, request: Request):
    with SessionLocal() as db:
        db.execute(text('BEGIN IMMEDIATE'));s=person_case(db,screening_id)
        evidence=json.loads(s.result.ai_analysis_json or '{}')
        if evidence.get('face',{}).get('status') not in {None,'NOT_RUN','SKIPPED'}:
            raise HTTPException(409,'An existing comparison cannot be replaced with Skipped. Its result remains part of the evidence.')
        if evidence.get('face',{}).get('status')=='SKIPPED':return evidence['face']
        result={'status':'SKIPPED','reason':'Officer skipped the optional person comparison.','capture_source':'NONE'}
        save_person_attempt(db,s,request,result);db.commit();return result

@app.post('/api/screening/{screening_id}/face')
async def face_comparison(screening_id: str, request: Request, photo: UploadFile = File(...), capture_source: str = Form('UPLOADED_PHOTO')):
    if capture_source not in {'LIVE_CAMERA','UPLOADED_PHOTO'}:raise HTTPException(400,'Unknown capture source.')
    data=await photo.read(10*1024*1024+1)
    if len(data)>10*1024*1024: raise HTTPException(400,'Photo exceeds 10 MB')
    local_analysis.decode(data)
    with SessionLocal() as db:
        db.execute(text('BEGIN IMMEDIATE'));s=person_case(db,screening_id)
        result=local_analysis.compare_faces(document_bytes(s.stored_path),data)
        result['submitted_photo_sha256']=hashlib.sha256(data).hexdigest()
        result['capture_source']=capture_source
        result['document_sha256']=s.document_hash
        save_person_attempt(db,s,request,result)
        db.commit()
        return result

# Serve a built frontend from the same loopback origin; no remote CDN or API configuration.
review_workflow.install(app,SessionLocal,Screening,AuditLog,ReviewCase)
video_demo.install(app)
demo_hardening.install(app, backend_root=BACKEND_ROOT, private_root=PRIVATE_ROOT, main_db=PRIVATE_ROOT/'bharatshield.db')
DIST = BACKEND_ROOT.parent / 'dist'
if DIST.is_dir():
    app.mount('/',StaticFiles(directory=str(DIST),html=True),name='frontend')
