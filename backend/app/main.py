import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .groq_service import analyze_document as groq_analyze_document, configured as groq_configured

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bharatshield.db")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
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

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(120))
    result: Mapped[str] = mapped_column(String(40))
    officer: Mapped[str] = mapped_column(String(120), default="Inspector Arjun Singh")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(engine)

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

app = FastAPI(title="BHARATSHIELD API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


def norm(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())

def norm_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())

def name_key(value: str) -> str:
    parts = [p for p in re.sub(r"[^A-Z0-9 ]", " ", (value or "").upper()).split() if p]
    return " ".join(sorted(parts))

def parse_date(value: str) -> Optional[tuple[int, int, int]]:
    v = (value or "").strip().upper()
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", v)
    if m:
        return int(m.group(3)), int(m.group(2)), int(m.group(1))
    m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", v)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r"(\d{1,2})\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+(\d{4})", v)
    if m:
        months = {x: i for i, x in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
        return int(m.group(3)), months[m.group(2)], int(m.group(1))
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
    findings = []
    if len(documents) < 2:
        return 0, "NOT_APPLICABLE", []
    fields = ["name", "dob", "nationality"]
    comparisons = 0
    matches = 0
    for field in fields:
        values = [d.get(field, "") for d in documents if d.get(field, "")]
        if len(values) >= 2:
            comparisons += 1
            if field == "dob":
                ok = all(date_equal(values[0], x) for x in values[1:])
            elif field == "name":
                ok = all(norm_name(values[0]) == norm_name(x) for x in values[1:])
            else:
                ok = all(norm(values[0]) == norm(x) for x in values[1:])
            matches += int(ok)
            findings.append({"code":"CROSS_"+field.upper(), "severity":"PASS" if ok else "HIGH", "message":f"{field.replace('_',' ').title()} {'consistent' if ok else 'conflict detected'} across provided documents."})
    # Document relationship checks: a visa can legitimately reference the passport number.
    passports = [d for d in documents if d.get("type", "").lower() == "passport" and d.get("document_number")]
    for d in documents:
        if d.get("type", "").lower() == "visa" and d.get("document_number") and passports:
            if any(norm(d["document_number"]) == norm(p["document_number"]) for p in passports):
                findings.append({"code":"CROSS_PASSPORT_LINK","severity":"PASS","message":"Visa document number links to the supplied passport."})
            else:
                findings.append({"code":"CROSS_PASSPORT_LINK","severity":"HIGH","message":"Visa document number does not link to any supplied passport."})
    score = round(matches / comparisons * 100, 1) if comparisons else 0
    status = "CONSISTENT" if score >= 80 and not any(x["severity"] == "HIGH" for x in findings) else "CONFLICT"
    return score, status, findings

def score_band(value: float) -> dict:
    """Percentage-banded, human-readable read on a confidence score.

    This is presentation-layer sugar on top of the existing 4-tier
    risk/recommendation logic below — it doesn't change any decision,
    it just gives the officer a clearer, more granular label than a
    bare 4-bucket risk tag when a score is e.g. 64% vs 38%.
    """
    v = max(0.0, min(100.0, float(value)))
    if v >= 90:
        return {"band": "VERY_GOOD", "label": "Very Good", "message": "Strong, consistent evidence across all checks. Minimal risk."}
    if v >= 75:
        return {"band": "GOOD", "label": "Good", "message": "Solid evidence with only minor gaps. Low risk."}
    if v >= 60:
        return {"band": "FAIR", "label": "Fair", "message": "Acceptable evidence but with notable gaps or unverifiable fields. Manual review recommended."}
    if v >= 40:
        return {"band": "POOR", "label": "Poor", "message": "Weak or conflicting evidence. High risk — recapture or manual review recommended."}
    if v >= 20:
        return {"band": "VERY_POOR", "label": "Very Poor", "message": "Very weak evidence with significant conflicts or missing checks. Very high risk."}
    return {"band": "CRITICAL", "label": "Critical", "message": "Little to no verifiable evidence, or a hard failure (e.g. watchlist match). Escalation required."}


def verify_document(db, fields: dict, document_type: str, ocr_confidence: float, ocr_text: str, data: bytes, mode: str, cross_score: float = 0, cross_findings: Optional[list] = None, ai_analysis: Optional[dict] = None, ai_status: str = "NOT_CONFIGURED"):
    required_by_type = {
        "Passport": ["name", "dob", "nationality", "document_number", "expiry"],
        "Visa": ["name", "document_number", "expiry"],
        "Aadhaar Card": ["name", "dob", "document_number"],
        "Voter ID (EPIC)": ["name", "document_number"],
        "Driving Licence": ["name", "dob", "document_number", "expiry"],
        "PAN Card": ["name", "dob", "document_number"],
        "National ID": ["name", "dob", "document_number"],
        "Permit": ["name", "document_number", "expiry"],
        "Travel Authorization": ["name", "document_number", "expiry"],
    }
    fields_score = field_completeness(fields, required_by_type.get(document_type, ["name", "document_number"]))
    doc_format = validate_document_number_format(document_type, fields.get("document_number", ""))
    country_valid = True
    nationality = norm(fields.get("nationality", ""))[:3]
    if nationality:
        country_valid = db.scalar(select(ReferenceCountry).where(ReferenceCountry.code == nationality)) is not None
    rules_score = 100 if country_valid else 40
    if doc_format.get("checked") and not doc_format.get("valid"):
        rules_score = max(0, rules_score - 30)
    mrz = validate_passport_mrz(ocr_text, fields) if document_type == "Passport" else {"score":0,"detected":False,"valid":False,"findings":[]}
    # Pass ocr_confidence and doc_format so check_reference can compute a structural fallback
    # score when no trusted identity record exists (prevents the score from being a hard 0).
    ref = check_reference(db, fields, document_type, ocr_confidence=ocr_confidence, doc_format=doc_format)
    watch_status, watch_findings = check_watchlist(db, fields)

    print(
        f"[BHARATSHIELD][VERIFY] type='{document_type}' "
        f"fields_score={fields_score} mrz_score={mrz.get('score',0)} "
        f"rules_score={rules_score} ref_score={ref.get('score',0)} "
        f"ref_status={ref.get('status','?')} ref_fallback={ref.get('fallback', False)} "
        f"ocr_confidence={ocr_confidence:.1f} watch={watch_status}",
        flush=True,
    )

    findings = list(mrz.get("findings", [])) + list(ref.get("findings", [])) + watch_findings + (cross_findings or []) + list(doc_format.get("findings", []))
    # Until Groq/forensic model is connected, do not invent a visual authenticity score.
    forensic_score = 0.0
    forensic_status = "AWAITING AI VISUAL ANALYSIS"
    ai_findings = []
    if ai_analysis:
        va = ai_analysis.get("visual_analysis", {})
        # tamper_indicators is intentionally inverted: higher means more suspicious.
        visual_quality = (
            float(va.get("image_quality", 0)) * 0.15 +
            float(va.get("layout_consistency", 0)) * 0.15 +
            float(va.get("print_quality", 0)) * 0.20 +
            float(va.get("text_alignment", 0)) * 0.15 +
            float(va.get("photo_region_integrity", 0)) * 0.10 +
            float(va.get("mrz_visual_quality", 0)) * 0.10 +
            float(va.get("security_features_visible", 0)) * 0.15
        )
        tamper = float(va.get("tamper_indicators", 0))
        forensic_score = round(max(0, min(100, visual_quality * 0.75 + (100 - tamper) * 0.25)), 1)
        forensic_status = "AI VISUAL ANALYSIS COMPLETE"
        for issue in va.get("issues", []):
            ai_findings.append({"code": "AI_VISUAL_SIGNAL", "severity": "HIGH" if tamper >= 70 else "MEDIUM", "message": issue})
        for positive in va.get("positive_signals", []):
            ai_findings.append({"code": "AI_VISUAL_POSITIVE", "severity": "PASS", "message": positive})
        for limitation in va.get("limitations", []):
            ai_findings.append({"code": "AI_VISUAL_LIMITATION", "severity": "INFO", "message": limitation})
        ai_findings.append({"code": "AI_FIELDS_CONFIDENCE", "severity": "INFO", "message": f"Groq structured field confidence: {ai_analysis.get('fields_confidence', 0):.0f}%."})

    findings.extend(ai_findings)

    # Only passports (and some visas) actually carry an MRZ. For Aadhaar/Voter ID/PAN/Driving
    # Licence etc. mrz.score is structurally 0 (there is nothing to read) — previously that 0
    # was still weighted at 20-24% of the total score, which meant a perfectly genuine Aadhaar
    # card could never score above ~76-80% no matter how clean the capture was. Fix: only include
    # the MRZ term in the weighted average when the document type actually has an MRZ, and
    # redistribute its weight onto the signals that *do* apply to that document type.
    has_mrz = document_type in ("Passport", "Visa")

    if mode == "SINGLE_DOCUMENT":
        # Evidence coverage, not a claim of physical authenticity.
        if has_mrz:
            coverage = round(fields_score * 0.24 + mrz.get("score", 0) * 0.24 + max(0, min(100, ocr_confidence)) * 0.10 + rules_score * 0.12 + forensic_score * 0.25 + (5 if watch_status == "CLEAR" else 0), 1)
        else:
            coverage = round(fields_score * 0.34 + max(0, min(100, ocr_confidence)) * 0.10 + rules_score * 0.12 + forensic_score * 0.39 + (5 if watch_status == "CLEAR" else 0), 1)
        confidence = min(100, coverage)
        penalty = 0
        if not country_valid: penalty += 20
        if mrz.get("detected") and not mrz.get("valid"): penalty += 25
        if doc_format.get("checked") and not doc_format.get("valid"): penalty += 20
        if watch_status == "MATCH": penalty += 45
        risk_score = max(0, confidence - penalty)
        details = "Single-document mode: field/rule evidence is checked locally." + (" MRZ cross-checked." if has_mrz else "") + " Physical printing, substrate and optical security features remain pending the AI visual-analysis layer."
    else:
        cross_component = cross_score
        if has_mrz:
            confidence = round(fields_score * 0.25 + mrz.get("score", 0) * 0.20 + cross_component * 0.35 + rules_score * 0.10 + max(0, min(100, ocr_confidence)) * 0.10, 1)
        else:
            confidence = round(fields_score * 0.35 + cross_component * 0.45 + rules_score * 0.10 + max(0, min(100, ocr_confidence)) * 0.10, 1)
        penalty = 0
        if cross_score < 80: penalty += 25
        if mrz.get("detected") and not mrz.get("valid"): penalty += 20
        if doc_format.get("checked") and not doc_format.get("valid"): penalty += 20
        if ref.get("status") == "CONFLICT": penalty += 25
        if watch_status == "MATCH": penalty += 45
        risk_score = max(0, confidence - penalty)
        details = f"{mode.replace('_',' ').title()}: cross-document consistency is weighted heavily. {len(cross_findings or [])} cross-document findings were generated."

    if watch_status == "MATCH" or risk_score < 40:
        risk, recommendation = "CRITICAL", "ESCALATE"
    elif risk_score < 65 or any(x.get("severity") == "HIGH" for x in findings):
        risk, recommendation = "HIGH", "FLAG"
    elif risk_score < 82:
        risk, recommendation = "MEDIUM", "FLAG"
    else:
        risk, recommendation = "LOW", "ACCEPT"

    # Authenticity is deliberately limited to evidence-backed document checks until visual AI is live.
    if has_mrz:
        authenticity = round((fields_score * 0.4 + mrz.get("score", 0) * 0.4 + rules_score * 0.2), 1)
    else:
        authenticity = round((fields_score * 0.6 + rules_score * 0.4), 1)
    db_score = ref.get("score", 0)
    duplicate = "NO CONFLICT"
    if ref.get("status") == "CONFLICT": duplicate = "IDENTITY CONFLICT"
    if watch_status == "MATCH": duplicate = "WATCHLIST CONFLICT"
    band = score_band(risk_score)
    return {
        "ocr": max(0, min(100, float(ocr_confidence))), "authenticity": authenticity,
        "face": 0, "database": db_score, "mrz": mrz.get("score", 0),
        "field": fields_score, "cross": cross_score, "forensic": forensic_score,
        "watchlist": watch_status, "duplicate": duplicate, "forgery": forensic_status,
        "confidence": round(risk_score, 1), "risk": risk, "recommendation": recommendation,
        "score_band": band["band"], "score_band_label": band["label"], "score_band_message": band["message"],
        "details": details, "findings": findings, "ai_status": ai_status, "ai_analysis": ai_analysis or {},
    }


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

@app.get("/api/health")
def health():
    with SessionLocal() as db:
        seed_officer(db); seed_reference_data(db)
    return {"status":"online","service":"BHARATSHIELD API","database":"connected","verification_engine":"v3 + Groq Vision adapter","reference_data":"loaded"}

def seed_officer(db):
    officer = db.scalar(select(Officer).where(Officer.officer_code == "SSB-1047"))
    if not officer:
        db.add(Officer(officer_code="SSB-1047", name="Inspector Arjun Singh", checkpoint="Attari Integrated Check Post"))
        db.commit()

def save_screening(db, file: UploadFile, data: bytes, metadata: dict, mode: str, case_id: str, index: int, count: int, cross_score=0, cross_findings=None):
    digest = hashlib.sha256(data).hexdigest()
    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'document').name}"
    target = UPLOAD_DIR / safe_name
    target.write_bytes(data)
    fields = {"name":metadata.get("name",""),"dob":metadata.get("dob",""),"nationality":metadata.get("nationality",""),"document_number":metadata.get("document_number",""),"expiry":metadata.get("expiry","")}
    ai_analysis = metadata.get("_ai_analysis")
    ai_status = metadata.get("_ai_status", "NOT_CONFIGURED")
    if ai_analysis and not isinstance(ai_analysis, dict):
        ai_analysis = None
    # If the batch route has not already prepared AI output, prepare it here (legacy endpoint).
    if ai_analysis is None and groq_configured():
        try:
            ai_analysis = groq_analyze_document(data, getattr(file, "content_type", None) or "image/jpeg", metadata.get("type", "Passport"), metadata.get("ocr_text", ""))
            ai_status = "GROQ COMPLETE"
        except Exception as exc:
            ai_status = "GROQ ERROR / LOCAL FALLBACK"
            ai_analysis = {"error": str(exc)[:500]}
    if ai_analysis and not ai_analysis.get("error"):
        # AI is an extraction/observation layer. It may improve missing fields, but it does not override
        # deterministic MRZ/reference checks or declare authenticity by itself.
        ai_name = ai_analysis.get("full_name", "").strip()
        if ai_name and len(ai_name) >= 3: fields["name"] = ai_name
        if ai_analysis.get("date_of_birth"): fields["dob"] = ai_analysis["date_of_birth"]
        if ai_analysis.get("nationality"): fields["nationality"] = ai_analysis["nationality"]
        if ai_analysis.get("passport_or_document_number"): fields["document_number"] = ai_analysis["passport_or_document_number"]
        if ai_analysis.get("date_of_expiry"): fields["expiry"] = ai_analysis["date_of_expiry"]
        if ai_analysis.get("mrz_text") and not metadata.get("ocr_text"): metadata["ocr_text"] = ai_analysis["mrz_text"]
    analysis = verify_document(db, fields, metadata.get("type", "Passport"), float(metadata.get("ocr_confidence",0) or 0), metadata.get("ocr_text",""), data, mode, cross_score, cross_findings, ai_analysis, ai_status)
    screening_code = f"SCR-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    s = Screening(screening_id=screening_code, case_id=case_id, verification_mode=mode, document_index=index, document_count=count, document_type=metadata.get("type","Passport"), original_filename=file.filename or "document", stored_path=str(target), document_hash=f"sha256:{digest}", risk=analysis["risk"], confidence=analysis["confidence"], recommendation=analysis["recommendation"], person_name=fields["name"].strip(), date_of_birth=fields["dob"].strip(), nationality=fields["nationality"].strip(), document_number=fields["document_number"].strip(), expiry_date=fields["expiry"].strip())
    s.result = VerificationResult(ocr_confidence=analysis["ocr"], authenticity_score=analysis["authenticity"], face_match_score=analysis["face"], database_match_score=analysis["database"], mrz_score=analysis["mrz"], field_consistency_score=analysis["field"], cross_document_score=analysis["cross"], forensic_score=analysis["forensic"], watchlist_status=analysis["watchlist"], duplicate_status=analysis["duplicate"], forgery_status=analysis["forgery"], details=analysis["details"], findings_json=json.dumps(analysis["findings"]), ocr_text=metadata.get("ocr_text","")[:20000], ocr_method="Tesseract.js + Verification Engine + Groq Vision", ai_status=analysis.get("ai_status", "NOT_CONFIGURED"), ai_analysis_json=json.dumps(analysis.get("ai_analysis", {}))[:30000])
    db.add(s); db.flush()
    return s

@app.post("/api/screening/batch")
async def create_batch(
    files: list[UploadFile] = File(...),
    documents_json: str = Form("[]"),
    mode: str = Form("AUTO"),
):
    if not files:
        raise HTTPException(400, "At least one document is required.")
    try:
        metadata = json.loads(documents_json)
    except Exception:
        raise HTTPException(400, "documents_json must be valid JSON.")
    if len(metadata) != len(files):
        raise HTTPException(400, "Document metadata count does not match uploaded files.")
    count = len(files)
    resolved_mode = "SINGLE_DOCUMENT" if count == 1 else "CROSS_DOCUMENT"
    if mode.upper() == "SINGLE_DOCUMENT": resolved_mode = "SINGLE_DOCUMENT"
    elif mode.upper() in {"CROSS_DOCUMENT","MULTI_DOCUMENT"} and count >= 2: resolved_mode = "CROSS_DOCUMENT"
    case_id = f"CASE-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    with SessionLocal() as db:
        seed_officer(db); seed_reference_data(db)
        items = []
        raw_docs = []
        for i, (file, meta) in enumerate(zip(files, metadata), 1):
            if not file.content_type or not file.content_type.startswith("image/"):
                raise HTTPException(400, f"{file.filename}: image files only.")
            data = await file.read()
            if len(data) > 10 * 1024 * 1024: raise HTTPException(400, f"{file.filename}: exceeds 10 MB.")
            meta["type"] = meta.get("type") or "Passport"
            # Run Groq once per document before cross-verification so AI-extracted fields can participate
            # in the cross-document comparison. If Groq is unavailable, local OCR remains the source.
            if groq_configured():
                try:
                    ai = groq_analyze_document(data, file.content_type or "image/jpeg", meta["type"], meta.get("ocr_text", ""))
                    meta["_ai_analysis"] = ai
                    meta["_ai_status"] = "GROQ COMPLETE"
                    print(f"[BHARATSHIELD][GROQ] Vision analysis complete using {os.getenv('GROQ_MODEL', 'qwen/qwen3.6-27b')}", flush=True)
                    if not ai.get("error"):
                        if ai.get("full_name"): meta["name"] = ai["full_name"]
                        if ai.get("date_of_birth"): meta["dob"] = ai["date_of_birth"]
                        if ai.get("nationality"): meta["nationality"] = ai["nationality"]
                        if ai.get("passport_or_document_number"): meta["document_number"] = ai["passport_or_document_number"]
                        if ai.get("date_of_expiry"): meta["expiry"] = ai["date_of_expiry"]
                except Exception as exc:
                    # Keep the API response clean, but print the sanitized provider error to the
                    # backend terminal so integration failures can be diagnosed without exposing
                    # the API key.
                    error_text = str(exc)[:1000]
                    print(f"[BHARATSHIELD][GROQ ERROR] {error_text}", flush=True)
                    meta["_ai_status"] = "GROQ ERROR / LOCAL FALLBACK"
                    meta["_ai_analysis"] = {"error": error_text}
            else:
                meta["_ai_status"] = "NOT_CONFIGURED"
            raw_docs.append((file, data, meta))
        cross_score, cross_status, cross_findings = cross_verify([m | {"type":m.get("type", "Passport")} for _,_,m in raw_docs])
        for i, (file, data, meta) in enumerate(raw_docs, 1):
            s = save_screening(db, file, data, meta, resolved_mode, case_id, i, count, cross_score, cross_findings)
            db.add(AuditLog(reference=s.screening_id, action=f"Verification engine completed ({resolved_mode})", result="PASS" if s.risk == "LOW" else "REVIEW"))
            items.append(s)
        db.commit()
        return {"case_id":case_id,"mode":resolved_mode,"document_count":count,"screenings":[serialize_screening(x) for x in items],"cross_document":{"score":cross_score,"status":cross_status,"findings":cross_findings}}

@app.post("/api/screening/upload")
async def create_screening_legacy(
    file: UploadFile = File(...), document_type: str = Form("Passport"), ocr_text: str = Form(""), ocr_confidence: float = Form(0),
    extracted_name: str = Form(""), extracted_dob: str = Form(""), extracted_nationality: str = Form(""), extracted_document_number: str = Form(""), extracted_expiry: str = Form(""),
):
    metadata = {"type":document_type,"ocr_text":ocr_text,"ocr_confidence":ocr_confidence,"name":extracted_name,"dob":extracted_dob,"nationality":extracted_nationality,"document_number":extracted_document_number,"expiry":extracted_expiry}
    data = await file.read()
    if not file.content_type or not file.content_type.startswith("image/"): raise HTTPException(400,"Please upload an image document.")
    if len(data) > 10 * 1024 * 1024: raise HTTPException(400,"File exceeds the 10 MB limit.")
    with SessionLocal() as db:
        seed_officer(db); seed_reference_data(db)
        case_id = f"CASE-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        s = save_screening(db,file,data,metadata,"SINGLE_DOCUMENT",case_id,1,1)
        db.add(AuditLog(reference=s.screening_id, action="Verification engine completed (SINGLE_DOCUMENT)", result="PASS" if s.risk == "LOW" else "REVIEW"))
        db.commit()
        return serialize_screening(s)

@app.get("/api/reference/summary")
def reference_summary():
    with SessionLocal() as db:
        seed_reference_data(db)
        return {"countries":db.query(ReferenceCountry).count(),"document_rules":db.query(DocumentRule).count(),"issuers":db.query(IssuerRecord).count(),"fraud_rules":db.query(FraudRule).count(),"watchlist_records":db.query(WatchlistRecord).count(),"synthetic_identities":db.query(IdentityRecord).count()}

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
def decision(screening_id: str, action: str):
    action = action.upper()
    if action not in {"ACCEPT","FLAG","ESCALATE"}: raise HTTPException(400,"Action must be ACCEPT, FLAG or ESCALATE")
    with SessionLocal() as db:
        s = db.scalar(select(Screening).where(Screening.screening_id == screening_id))
        if not s: raise HTTPException(404,"Screening not found")
        s.recommendation = action; s.status = "Verified" if action == "ACCEPT" else "Flagged" if action == "FLAG" else "Escalated"
        db.add(AuditLog(reference=screening_id, action=f"Officer decision: {action}", result=action)); db.commit()
        return {"screening_id":screening_id,"status":s.status,"decision":action}

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
            .where(Screening.risk.in_(["MEDIUM", "HIGH", "CRITICAL"]))
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
        risk_counts = {r: db.query(Screening).filter(Screening.risk == r).count() for r in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]}
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

def serialize_screening(s: Screening):
    r = s.result
    try: findings = json.loads(r.findings_json or "[]") if r else []
    except Exception: findings = []
    band = score_band(s.confidence)
    return {"id":s.screening_id,"case_id":s.case_id,"mode":s.verification_mode,"document_index":s.document_index,"document_count":s.document_count,"person":s.person_name or "Not detected","type":s.document_type,"number":s.document_number or "Not detected","date_of_birth":s.date_of_birth or "Not detected","nationality":s.nationality or "Not detected","expiry_date":s.expiry_date or "Not detected","risk":s.risk,"confidence":s.confidence,"score_band":band["band"],"score_band_label":band["label"],"score_band_message":band["message"],"status":s.status,"recommendation":s.recommendation,"filename":s.original_filename,"document_hash":s.document_hash,"created_at":s.created_at.isoformat() if s.created_at else None,"result":{"ocr_confidence":r.ocr_confidence if r else 0,"authenticity_score":r.authenticity_score if r else 0,"face_match_score":r.face_match_score if r else 0,"database_match_score":r.database_match_score if r else 0,"mrz_score":r.mrz_score if r else 0,"field_consistency_score":r.field_consistency_score if r else 0,"cross_document_score":r.cross_document_score if r else 0,"forensic_score":r.forensic_score if r else 0,"watchlist_status":r.watchlist_status if r else "PENDING","duplicate_status":r.duplicate_status if r else "PENDING","forgery_status":r.forgery_status if r else "PENDING","details":r.details if r else "","findings":findings,"ocr_text":r.ocr_text if r else "","ocr_method":r.ocr_method if r else "", "ai_status":r.ai_status if r else "NOT_CONFIGURED", "ai_analysis":(json.loads(r.ai_analysis_json or "{}") if r and r.ai_analysis_json else {})}}
