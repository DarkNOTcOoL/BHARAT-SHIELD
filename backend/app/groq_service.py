"""Optional Groq vision adapter for BHARATSHIELD.

The API key is intentionally NOT bundled with the project. Put it in backend/.env
as GROQ_API_KEY=... before starting FastAPI.
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "qwen/qwen3.6-27b"

SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {"type": "string"},
        "surname": {"type": "string"},
        "given_names": {"type": "string"},
        "full_name": {"type": "string"},
        "passport_or_document_number": {"type": "string"},
        "nationality": {"type": "string"},
        "date_of_birth": {"type": "string"},
        "date_of_issue": {"type": "string"},
        "date_of_expiry": {"type": "string"},
        "sex": {"type": "string"},
        "mrz_text": {"type": "string"},
        "fields_confidence": {"type": "number"},
        "visual_analysis": {
            "type": "object",
            "properties": {
                "image_quality": {"type": "number"},
                "layout_consistency": {"type": "number"},
                "print_quality": {"type": "number"},
                "text_alignment": {"type": "number"},
                "photo_region_integrity": {"type": "number"},
                "tamper_indicators": {"type": "number"},
                "mrz_visual_quality": {"type": "number"},
                "security_features_visible": {"type": "number"},
                "issues": {"type": "array", "items": {"type": "string"}},
                "positive_signals": {"type": "array", "items": {"type": "string"}},
                "limitations": {"type": "array", "items": {"type": "string"}}
            },
            "required": [
                "image_quality", "layout_consistency", "print_quality", "text_alignment",
                "photo_region_integrity", "tamper_indicators", "mrz_visual_quality",
                "security_features_visible", "issues", "positive_signals", "limitations"
            ],
            "additionalProperties": False
        }
    },
    "required": [
        "document_type", "surname", "given_names", "full_name",
        "passport_or_document_number", "nationality", "date_of_birth",
        "date_of_issue", "date_of_expiry", "sex", "mrz_text",
        "fields_confidence", "visual_analysis"
    ],
    "additionalProperties": False
}


def _load_local_env():
    # Lightweight .env loader so the user can simply paste the key into backend/.env.
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
    except OSError:
        pass


_load_local_env()


def configured() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def _clamp(value, default=0.0):
    try:
        return max(0.0, min(100.0, float(value)))
    except Exception:
        return default


def _normalize(result: dict) -> dict:
    result = result or {}
    visual = result.get("visual_analysis") or {}
    visual = {
        "image_quality": _clamp(visual.get("image_quality")),
        "layout_consistency": _clamp(visual.get("layout_consistency")),
        "print_quality": _clamp(visual.get("print_quality")),
        "text_alignment": _clamp(visual.get("text_alignment")),
        "photo_region_integrity": _clamp(visual.get("photo_region_integrity")),
        "tamper_indicators": _clamp(visual.get("tamper_indicators")),
        "mrz_visual_quality": _clamp(visual.get("mrz_visual_quality")),
        "security_features_visible": _clamp(visual.get("security_features_visible")),
        "issues": [str(x) for x in (visual.get("issues") or [])][:10],
        "positive_signals": [str(x) for x in (visual.get("positive_signals") or [])][:10],
        "limitations": [str(x) for x in (visual.get("limitations") or [])][:10],
    }
    result["visual_analysis"] = visual
    result["fields_confidence"] = _clamp(result.get("fields_confidence"))
    for key in ("surname", "given_names", "full_name", "passport_or_document_number", "nationality", "date_of_birth", "date_of_issue", "date_of_expiry", "sex", "mrz_text", "document_type"):
        result[key] = str(result.get(key) or "").strip()
    return result


MAX_COMPLETION_TOKENS_DEFAULT = 900
MAX_COMPLETION_TOKENS_RETRY = 980


def analyze_document(image_bytes: bytes, mime_type: str, document_type: str, ocr_text: str = "") -> dict:
    """Analyze an image with Groq vision. Raises RuntimeError on configuration/API failure."""
    if not configured():
        raise RuntimeError("GROQ_API_KEY is not configured")
    api_key = os.environ["GROQ_API_KEY"].strip()
    model = os.getenv("GROQ_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    mime = mime_type if mime_type in {"image/jpeg", "image/png", "image/webp"} else "image/jpeg"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    prompt = """Analyze this identity document image for BHARATSHIELD. Return ONLY one valid JSON object.
Do not decide genuine/fake. Extract only visible evidence. OCR is a secondary clue; prefer the image.

Use exactly these keys:
{"document_type":"Passport","surname":"","given_names":"","full_name":"","passport_or_document_number":"","nationality":"","date_of_birth":"","date_of_issue":"","date_of_expiry":"","sex":"","mrz_text":"","fields_confidence":0,"visual_analysis":{"image_quality":0,"layout_consistency":0,"print_quality":0,"text_alignment":0,"photo_region_integrity":0,"tamper_indicators":0,"mrz_visual_quality":0,"security_features_visible":0,"issues":[],"positive_signals":[],"limitations":[]}}

Rules:
- Keep all string fields short and evidence-based. If uncertain, use "".
- Dates: DD/MM/YYYY. Nationality: 3-letter ICAO code if visible (leave blank for non-passport Indian IDs like Aadhaar/Voter ID/PAN/Driving Licence that don't print one).
- passport_or_document_number: use whatever the document's own ID number is (Aadhaar number, EPIC number, PAN, DL number, passport number, etc.) — the field name is historical, not a restriction.
- mrz_text: only passports and some visas carry a machine-readable zone; leave "" for Aadhaar/Voter ID/PAN/Driving Licence.
- Do not merge OCR fragments into names.
- Scores are 0-100. tamper_indicators: higher = more suspicious; all other visual scores: higher = better observed quality.
- issues, positive_signals and limitations: maximum 2 short items each, maximum 60 characters per item.
- Do not describe security features that cannot be verified in a normal RGB image; put them in limitations.
- Output compact JSON with no markdown, no explanation, and no extra keys.

DOCUMENT_TYPE: """ + str(document_type) + """
OCR:
""" + str(ocr_text[:5000])
    prompt = prompt.strip()

    def build_body(max_tokens: int) -> dict:
        return {
            "model": model,
            "temperature": 0,
            "reasoning_effort": "none",
            "reasoning_format": "hidden",
            "max_completion_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": "You are a precise document-analysis engine. Never fabricate evidence. Return only JSON; no markdown or explanation."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}
                ]}
            ],
            "response_format": {"type": "json_object"},
        }

    def call(max_tokens: int) -> dict:
        request = urllib.request.Request(
            GROQ_URL,
            data=json.dumps(build_body(max_tokens)).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "BHARATSHIELD/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def is_token_exhaustion(detail: str) -> bool:
        d = detail.lower()
        return "max completion tokens" in d or "max_completion_tokens" in d or "length" in d

    def parse_otpm_limit(detail: str):
        # Groq's 429 body for this error looks like: "... (OTPM): Limit 1000, Requested 2200 ..."
        # Extract the account's actual per-minute output-token ceiling so we can clamp to it
        # instead of guessing, in case it's ever lower/higher than our defaults.
        m = re.search(r"OTPM\)?:\s*Limit\s+(\d+)", detail, re.IGNORECASE)
        return int(m.group(1)) if m else None

    def retry_after_seconds(exc: urllib.error.HTTPError) -> float:
        try:
            val = exc.headers.get("Retry-After") if exc.headers else None
            return max(1.0, min(30.0, float(val))) if val else 3.0
        except Exception:
            return 3.0

    payload = None
    last_error = None
    otpm_ceiling = None
    token_plan = [MAX_COMPLETION_TOKENS_DEFAULT, MAX_COMPLETION_TOKENS_RETRY]
    attempt = 0
    # The vision model can occasionally need more room than the default budget to finish a
    # valid JSON document (this previously caused HTTP 400 json_validate_failed errors with a
    # too-small max_completion_tokens). It can also hit the account's own per-minute output-token
    # cap (HTTP 429 OTPM) if max_completion_tokens is requested above that cap, or if the account
    # is briefly saturated. Handle both: retry once with a bigger budget on 400 token-exhaustion,
    # and back off + retry (clamped to the account's real ceiling) on 429.
    while attempt < 3:
        attempt_tokens = token_plan[min(attempt, len(token_plan) - 1)]
        if otpm_ceiling is not None:
            attempt_tokens = min(attempt_tokens, max(200, otpm_ceiling - 20))
        try:
            payload = call(attempt_tokens)
            last_error = None
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            last_error = f"Groq API HTTP {exc.code}: {detail}"
            if exc.code == 400 and is_token_exhaustion(detail) and attempt == 0:
                attempt += 1
                continue  # retry once with a bigger token budget
            if exc.code == 429:
                ceiling = parse_otpm_limit(detail)
                if ceiling is not None:
                    otpm_ceiling = ceiling
                if attempt < 2:
                    time.sleep(retry_after_seconds(exc))
                    attempt += 1
                    continue
            raise RuntimeError(last_error) from exc
        except Exception as exc:
            raise RuntimeError(f"Groq API request failed: {exc}") from exc
    if payload is None:
        raise RuntimeError(last_error or "Groq API request failed after retry")
    try:
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except Exception as exc:
        raise RuntimeError("Groq returned an unexpected response format") from exc
    return _normalize(parsed)
