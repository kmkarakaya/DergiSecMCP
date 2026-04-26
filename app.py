from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from journal_engine import JOURNALS
from journal_engine import prepare_scope_review_candidates


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

DEFAULT_INDEXES: list[str] = []
DEFAULT_APC_PROVIDERS = ["elsevier", "wiley"]
INDEX_FILTER_OPTIONS = [
    {"value": "", "label": "Tümü"},
    {"value": "SCIE", "label": "SCIE"},
    {"value": "SCI", "label": "SCI"},
    {"value": "AHCI", "label": "AHCI"},
]
OLLAMA_TERM_SCHEMA = {
    "type": "object",
    "properties": {
        "required_terms": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 7,
        },
        "optional_terms": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 7,
        },
    },
    "required": ["required_terms", "optional_terms"],
    "additionalProperties": False,
}
OLLAMA_CLOUD_HOST = os.environ.get("OLLAMA_HOST", "https://ollama.com")
OLLAMA_CLOUD_MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss:120b")
STOPWORDS = {
    "bir",
    "ve",
    "veya",
    "ile",
    "icin",
    "icin",
    "olan",
    "olarak",
    "gibi",
    "daha",
    "en",
    "bu",
    "su",
    "da",
    "de",
    "mi",
    "mu",
    "mü",
    "mü",
    "hangi",
    "gonderebilirim",
    "gelistirdim",
    "yapan",
    "yapayan",
    "tespit",
    "zaman",
    "olustugunu",
}

METHOD_HINTS = {
    "mri": ["medical imaging"],
    "mr": ["medical imaging"],
    "image": ["medical imaging", "image processing", "medical image analysis"],
    "imaging": ["medical imaging", "medical image analysis"],
    "algorithm": ["image processing", "medical image analysis"],
    "deep": ["medical image analysis", "image processing"],
    "learning": ["medical image analysis", "image processing"],
    "vision": ["image processing", "medical image analysis"],
    "brain": ["neuroimaging"],
    "hemorrhage": ["radiology", "neuroimaging"],
    "kanama": ["radiology", "neuroimaging"],
    "goruntu": ["medical imaging", "image processing"],
    "goruntuleme": ["medical imaging", "medical image analysis"],
}

TOKEN_TRANSLATIONS = {
    "beyin": ["brain", "neuroimaging"],
    "beyindeki": ["brain", "neuroimaging"],
    "kanama": ["hemorrhage"],
    "kanamasi": ["hemorrhage"],
    "goruntu": ["image", "medical imaging"],
    "goruntuleme": ["imaging", "medical imaging"],
    "goruntulerinden": ["imaging", "medical imaging"],
    "goruntuleri": ["imaging", "medical imaging"],
    "isleme": ["image processing"],
    "algoritma": ["algorithm"],
    "algoritmasi": ["algorithm"],
    "derin": ["deep learning"],
    "ogrenme": ["deep learning", "machine learning"],
    "tespit": ["detection"],
    "tespiti": ["detection"],
    "zaman": ["temporal", "onset"],
    "olustugu": ["onset"],
    "olustugunu": ["onset"],
    "yapay": ["artificial intelligence"],
    "zeka": ["artificial intelligence"],
    "yayin": ["journal"],
    "nororadyoloji": ["neuroradiology"],
    "norogoruntuleme": ["neuroimaging"],
}

CANONICAL_ENGLISH_TERMS = {
    "medical imaging",
    "medical image analysis",
    "image processing",
    "computer assisted radiology",
    "radiology",
    "neuroimaging",
    "neuroradiology",
    "brain",
    "hemorrhage",
    "mri",
    "mr",
    "algorithm",
    "deep learning",
    "machine learning",
    "artificial intelligence",
    "detection",
    "onset",
    "temporal",
    "image",
    "imaging",
    "journal",
}


class RecommendationRequest(BaseModel):
    query: str = Field(min_length=8, max_length=6000)
    require_apc: bool = False
    indexes: list[str] = Field(default_factory=lambda: DEFAULT_INDEXES.copy())
    apc_providers: list[str] = Field(default_factory=lambda: DEFAULT_APC_PROVIDERS.copy())
    max_payment_tl: int | None = Field(default=None, ge=0)
    limit: int = Field(default=3, ge=1, le=12)


def build_max_payment_options() -> list[dict[str, Any]]:
    payment_values = [
        int(float(value))
        for value in JOURNALS["Ödeme (TL)"].dropna().tolist()
        if value not in (None, "")
    ]
    if not payment_values:
        return [{"value": "", "label": "Tümü"}]

    min_payment = min(payment_values)
    max_payment = max(payment_values)
    start = max(10000, int(math.floor(min_payment / 10000) * 10000))
    end = int(math.ceil(max_payment / 10000) * 10000)
    if start > end:
        start = end

    options = [{"value": "", "label": "Tümü"}]
    for amount in range(start, end + 1, 10000):
        formatted = f"{amount:,.0f}".replace(",", ".")
        options.append({"value": amount, "label": f"{formatted} TL ve altı"})
    return options


def fallback_optional_terms(query: str) -> list[str]:
    normalized_query = normalize_text(query)
    tokens = sorted(
        {
            token
            for token in re.findall(r"[a-z0-9]+", normalized_query)
            if len(token) >= 4 and token not in STOPWORDS
        }
    )

    expanded_terms: list[str] = [
        "medical imaging",
        "medical image analysis",
        "image processing",
    ]
    if any(token in tokens for token in {"brain", "mri", "mr", "hemorrhage", "kanama"}):
        expanded_terms.extend(["neuroimaging", "radiology"])
    if any(token in tokens for token in {"image", "imaging", "algorithm", "vision", "deep", "learning"}):
        expanded_terms.append("computer assisted radiology")

    for token in tokens:
        translated_terms = TOKEN_TRANSLATIONS.get(token, [])
        expanded_terms.extend(translated_terms)
        expanded_terms.extend(METHOD_HINTS.get(token, []))
        if token in CANONICAL_ENGLISH_TERMS:
            expanded_terms.append(token)

    unique_terms: list[str] = []
    seen: set[str] = set()
    for term in expanded_terms:
        cleaned = normalize_text(term)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique_terms.append(cleaned)
    return unique_terms


def fallback_search_terms(query: str) -> tuple[list[str], list[str]]:
    return [], fallback_optional_terms(query)[:7]


def normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    replacements = {
        "c": "c",
        "g": "g",
        "i": "i",
        "o": "o",
        "s": "s",
        "u": "u",
        "\u00e7": "c",
        "\u011f": "g",
        "\u0131": "i",
        "\u00f6": "o",
        "\u015f": "s",
        "\u00fc": "u",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def _normalized_term_list(values: Any, limit: int = 7) -> list[str]:
    if not isinstance(values, list):
        return []

    terms: list[str] = []
    seen: set[str] = set()
    for item in values:
        cleaned = normalize_text(item)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            terms.append(cleaned)
        if len(terms) >= limit:
            break
    return terms


def parse_ollama_terms(content: str) -> tuple[list[str], list[str]]:
    if not content:
        return [], []

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return [], []
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return [], []

    if not isinstance(payload, dict):
        return [], []

    required_terms = _normalized_term_list(payload.get("required_terms"), limit=7)
    optional_terms = [
        term for term in _normalized_term_list(payload.get("optional_terms"), limit=7)
        if term not in required_terms
    ]
    return required_terms, optional_terms


def extract_terms_with_ollama(query: str) -> tuple[list[str], list[str], dict[str, Any]]:
    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        return [], [], {
            "enabled": False,
            "attempted": False,
            "host": OLLAMA_CLOUD_HOST,
            "model": OLLAMA_CLOUD_MODEL,
            "status": "disabled",
            "status_text": "OLLAMA_API_KEY bulunamadı; yerel gerekli ve opsiyonel arama terimleri kurallı fallback ile üretildi.",
        }

    try:
        from ollama import Client
    except ImportError:
        return [], [], {
            "enabled": True,
            "attempted": False,
            "host": OLLAMA_CLOUD_HOST,
            "model": OLLAMA_CLOUD_MODEL,
            "status": "import_error",
            "status_text": "Ollama istemcisi yüklenemedi; yerel gerekli ve opsiyonel arama terimleri kurallı fallback ile üretildi.",
        }

    system_prompt = (
        "You convert a Turkish or English academic journal query into structured search terms for journal discovery. "
        "Return only a JSON object with exactly two keys: required_terms and optional_terms. "
        "Each value must be an array of lowercase English-only canonical terms or short phrases, with at most 7 items each. "
        "required_terms must be very strict and minimal: include only indispensable anchor concepts that should be mandatory in title-based search, often 0 to 2 items. "
        "optional_terms should contain broader supporting concepts, methods, disease names, imaging modalities, and field phrases useful for ranking. "
        "Do not include Turkish. Do not explain. Prefer compact academic search phrases such as medical imaging, medical image analysis, image processing, neuroradiology, radiology, deep learning, machine learning, hemorrhage, brain, mri, detection."
    )
    user_prompt = (
        "Extract required_terms and optional_terms for journal search from this query. Return the JSON object only.\n\n"
        f"Query: {query}"
    )

    try:
        client = Client(
            host=OLLAMA_CLOUD_HOST,
            headers={"Authorization": "Bearer " + api_key},
        )
        response = client.chat(
            OLLAMA_CLOUD_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            format=OLLAMA_TERM_SCHEMA,
        )
    except Exception:
        return [], [], {
            "enabled": True,
            "attempted": True,
            "host": OLLAMA_CLOUD_HOST,
            "model": OLLAMA_CLOUD_MODEL,
            "status": "request_failed",
            "status_text": "Ollama Cloud'a erişildi ancak structured output alınamadı; yerel gerekli ve opsiyonel arama terimleri kullanıldı.",
        }

    if isinstance(response, dict):
        content = response.get("message", {}).get("content", "")
    else:
        message = getattr(response, "message", None)
        content = getattr(message, "content", "") if message is not None else ""
    required_terms, optional_terms = parse_ollama_terms(content)
    if required_terms or optional_terms:
        return required_terms, optional_terms, {
            "enabled": True,
            "attempted": True,
            "host": OLLAMA_CLOUD_HOST,
            "model": OLLAMA_CLOUD_MODEL,
            "status": "success",
            "status_text": f"Ollama Cloud yanıtı alındı ({OLLAMA_CLOUD_MODEL}). Gerekli ve opsiyonel İngilizce arama terimleri modelden çıkarıldı.",
        }

    return [], [], {
        "enabled": True,
        "attempted": True,
        "host": OLLAMA_CLOUD_HOST,
        "model": OLLAMA_CLOUD_MODEL,
        "status": "empty_response",
        "status_text": "Ollama Cloud yanıtı boş kaldı; yerel gerekli ve opsiyonel arama terimleri kullanıldı.",
    }


def extract_search_terms_with_source(query: str) -> tuple[list[str], list[str], str, dict[str, Any]]:
    required_terms, optional_terms, llm_info = extract_terms_with_ollama(query)
    if required_terms or optional_terms:
        return required_terms, optional_terms, "ollama-cloud", llm_info

    llm_info = {
        **llm_info,
        "fallback_source": "local-rules",
    }
    fallback_required, fallback_optional = fallback_search_terms(query)
    return fallback_required, fallback_optional, "local-rules", llm_info


def extract_optional_terms(query: str) -> list[str]:
    _, optional_terms, _, _ = extract_search_terms_with_source(query)
    return optional_terms


def merge_unique_terms(*term_groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in term_groups:
        for term in group:
            cleaned = normalize_text(term)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                merged.append(cleaned)
    return merged


def orientation_for_title(title: str) -> str:
    normalized_title = normalize_text(title)
    if any(keyword in normalized_title for keyword in ["ieee", "image", "computer", "graphics", "analysis"]):
        return "method"
    if any(keyword in normalized_title for keyword in ["radiology", "neuroradiology", "neuroimaging"]):
        return "clinical"
    return "hybrid"


def fit_reason(candidate: dict[str, Any]) -> str:
    matched = candidate.get("local_match_reason", {}).get("matched_optional_terms", [])
    hints = candidate.get("scope_hints", {})
    subjects = hints.get("subjects") or []
    disciplines = hints.get("disciplines") or []
    focus_terms = matched[:3]

    parts: list[str] = []
    if focus_terms:
        parts.append("Local shortlist match: " + ", ".join(focus_terms) + ".")
    if subjects:
        parts.append("Subject hint: " + subjects[0] + ".")
    elif disciplines:
        parts.append("Discipline hint: " + disciplines[0] + ".")
    if not parts:
        parts.append("Matched from local UBYT/APC data based on topic overlap.")
    return " ".join(parts)


def build_badges(candidate: dict[str, Any]) -> list[str]:
    badges = ["UBYT"]
    for provider in candidate.get("apc_providers", []):
        provider_label = provider.title()
        if provider_label not in badges:
            badges.append(provider_label)
    return badges


def format_payment(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return str(value)
    formatted = f"{amount:,.0f}".replace(",", ".")
    return formatted + " TL"


def format_mep_score(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{numeric:.3f}".rstrip("0").rstrip(".")


def journal_index_label(candidate: dict[str, Any]) -> str:
    labels: list[str] = []
    if candidate.get("scie"):
        labels.append("SCIE")
    if candidate.get("ssci"):
        labels.append("SSCI")
    if candidate.get("ahci"):
        labels.append("AHCI")
    return ", ".join(labels) if labels else "-"


def apc_detail_payload(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": (match.get("provider") or "").title() or "-",
        "journal_title": match.get("journal_title") or "-",
        "issn": match.get("issn") or "-",
        "eissn": match.get("eissn") or "-",
        "publisher_or_imprint": match.get("publisher_or_imprint") or "-",
        "discipline": match.get("discipline") or "-",
        "subject": match.get("subject") or "-",
        "publishing_model": match.get("publishing_model") or "-",
        "oa_license": match.get("oa_license") or "-",
        "url": match.get("url") or "-",
        "raw_source_file": match.get("raw_source_file") or "-",
        "wos_index": match.get("wos_index") or "-",
        "quartile": match.get("quartile") or "-",
        "impact_factor": match.get("impact_factor") or "-",
        "journal_id": match.get("journal_id") or "-",
        "match_type": match.get("match_type") or "-",
        "match_score": match.get("match_score") or "-",
    }


def card_payload(candidate: dict[str, Any], indexes: list[str], term_source: str) -> dict[str, Any]:
    provenance_sources = ["UBYT 2026"]
    evidence = candidate.get("apc_providers", [])
    if evidence:
        provenance_sources.extend(provider.title() for provider in evidence)

    source_program = candidate.get("kaynak")
    if source_program in (None, "", "-"):
        source_program = "UBYT"

    return {
        "candidate_id": candidate.get("candidate_id"),
        "title": candidate.get("canonical_title"),
        "fit_reason": fit_reason(candidate),
        "orientation": orientation_for_title(candidate.get("canonical_title", "")),
        "ubyt_eligible": candidate.get("ubyt_incentive_eligible", True),
        "apc_supported": candidate.get("apc_funding_eligible", False),
        "badges": build_badges(candidate),
        "preferred_url": candidate.get("preferred_url"),
        "issn": candidate.get("issn"),
        "eissn": candidate.get("eissn"),
        "title_aliases": candidate.get("title_aliases", []),
        "support_amount": format_payment(candidate.get("odeme_tl")),
        "mep_score": format_mep_score(candidate.get("dergi_mep_puani")),
        "index_label": journal_index_label(candidate),
        "source_year": candidate.get("yil"),
        "source_program": source_program,
        "apc_evidence": candidate.get("apc_evidence", {}),
        "apc_details": [apc_detail_payload(match) for match in candidate.get("apc_matches", [])],
        "scope_hints": candidate.get("scope_hints", {}),
        "matched_terms": candidate.get("local_match_reason", {}).get("matched_optional_terms", []),
        "ubyt_details": {
            "support_amount": format_payment(candidate.get("odeme_tl")),
            "mep_score": format_mep_score(candidate.get("dergi_mep_puani")),
            "index_label": journal_index_label(candidate),
            "source_year": candidate.get("yil") or "-",
            "source_program": source_program,
            "issn": candidate.get("issn") or "-",
            "eissn": candidate.get("eissn") or "-",
        },
        "provenance": {
            "sources": provenance_sources,
            "scope_verified": False,
            "model_source": term_source,
        },
    }


app = FastAPI(title="Murat Karakaya Akademi Dergi Tarama", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def disable_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/filters")
def filters() -> dict[str, Any]:
    payment_values = [
        int(float(value))
        for value in JOURNALS["Ödeme (TL)"].dropna().tolist()
        if value not in (None, "")
    ]
    return {
        "index_options": INDEX_FILTER_OPTIONS,
        "max_payment_options": build_max_payment_options(),
        "payment_range": {
            "min": min(payment_values) if payment_values else None,
            "max": max(payment_values) if payment_values else None,
            "step": 10000,
        },
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/recommend")
def recommend(payload: RecommendationRequest) -> dict[str, Any]:
    required_terms, optional_terms, term_source, llm_info = extract_search_terms_with_source(payload.query)
    shortlist = prepare_scope_review_candidates(
        required_terms=required_terms,
        optional_terms=optional_terms,
        indexes=payload.indexes,
        require_apc=payload.require_apc,
        apc_providers=payload.apc_providers,
        max_payment_tl=payload.max_payment_tl,
        sort_by="relevance",
        limit=payload.limit,
    )

    applied_required_terms = required_terms.copy()
    applied_optional_terms = optional_terms.copy()
    ranking_mode = "strict-required"

    if not shortlist.get("candidates") and required_terms:
        applied_required_terms = []
        applied_optional_terms = merge_unique_terms(required_terms, optional_terms)
        shortlist = prepare_scope_review_candidates(
            required_terms=[],
            optional_terms=applied_optional_terms,
            indexes=payload.indexes,
            require_apc=payload.require_apc,
            apc_providers=payload.apc_providers,
            max_payment_tl=payload.max_payment_tl,
            sort_by="relevance",
            limit=payload.limit,
        )
        ranking_mode = "relaxed-required-to-optional"

    results = [card_payload(candidate, payload.indexes, term_source) for candidate in shortlist.get("candidates", [])]
    return {
        "query": payload.query,
        "query_summary": {
            "required_terms": required_terms,
            "optional_terms": optional_terms,
            "keywords": (required_terms + optional_terms)[:14],
            "applied_required_terms": applied_required_terms,
            "applied_optional_terms": applied_optional_terms,
            "ranking_mode": ranking_mode,
            "result_count": len(results),
            "require_apc": payload.require_apc,
            "max_payment_tl": payload.max_payment_tl,
            "indexes": payload.indexes,
            "keyword_source": term_source,
            "llm": llm_info,
        },
        "results": results,
        "closed_set_only": shortlist.get("closed_set_only", True),
    }