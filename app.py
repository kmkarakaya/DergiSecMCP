from __future__ import annotations

from io import BytesIO
import json
import math
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import pandas as pd
from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
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
OLLAMA_JUDGE_POOL_LIMIT = 15
OLLAMA_JUDGE_ENABLED = os.environ.get("OLLAMA_JUDGE_ENABLED", "1") != "0"
OLLAMA_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "ordered_candidate_ids": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 20,
        },
    },
    "required": ["ordered_candidate_ids"],
    "additionalProperties": False,
}
OLLAMA_CLOUD_HOST = os.environ.get("OLLAMA_HOST", "https://ollama.com")
OLLAMA_CLOUD_MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss:120b")
BLOCKED_SHORT_SEARCH_TERMS = {
    "ai",
    "ml",
    "dl",
    "nlp",
    "llm",
    "cv",
    "rl",
}
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
    limit: int = Field(default=3, ge=1, le=15)


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
        if cleaned in BLOCKED_SHORT_SEARCH_TERMS:
            continue
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            terms.append(cleaned)
        if len(terms) >= limit:
            break
    return terms


def _extract_json_object(content: str) -> dict[str, Any] | None:
    if not content:
        return None

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(payload, dict):
        return None

    return payload


def parse_ollama_terms(content: str) -> tuple[list[str], list[str]]:
    payload = _extract_json_object(content)
    if payload is None:
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
        "These terms will be used to scan journal titles from Excel lists, so prefer terms and short phrases that are likely to literally appear in journal titles. "
        "Return only a JSON object with exactly two keys: required_terms and optional_terms. "
        "Each value must be an array of lowercase English-only canonical terms or short phrases, with at most 7 items each. "
        "required_terms must be very strict and minimal: include only indispensable anchor concepts that should be mandatory in journal title matching, often 0 to 2 items. "
        "optional_terms should contain broader field phrases, methods, disease names, imaging modalities, and adjacent concepts that are still plausible in journal titles and useful for ranking. "
        "Prefer journal-scope phrases such as software engineering, machine learning, radiology, medical imaging, education technology, information systems, or artificial intelligence. "
        "Avoid long task descriptions or paper-specific problem statements that are unlikely to appear in journal titles. "
        "Do not include Turkish. Do not explain. Do not use short abbreviations such as ai, ml, dl, nlp, llm, cv, or rl. "
        "Prefer explicit academic phrases such as artificial intelligence, machine learning, deep learning, computer vision, natural language processing, medical imaging, medical image analysis, image processing, neuroradiology, radiology, hemorrhage, brain, mri, detection."
    )
    user_prompt = (
        "Extract required_terms and optional_terms for journal search from this query. "
        "The terms will be matched against journal titles in Excel-based journal lists, so choose phrases that are likely to appear in journal names. "
        "Return the JSON object only.\n\n"
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
            options={"temperature": 0},
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


def parse_ollama_rerank(content: str) -> list[str]:
    payload = _extract_json_object(content)
    if payload is None:
        return []

    ordered_ids = payload.get("ordered_candidate_ids")
    if not isinstance(ordered_ids, list):
        return []

    unique_ids: list[str] = []
    seen: set[str] = set()
    for item in ordered_ids:
        candidate_id = str(item or "").strip()
        if candidate_id and candidate_id not in seen:
            seen.add(candidate_id)
            unique_ids.append(candidate_id)
    return unique_ids


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


def candidate_matched_terms(candidate: dict[str, Any]) -> list[str]:
    match_reason = candidate.get("local_match_reason", {})
    return merge_unique_terms(
        match_reason.get("matched_required_terms", []),
        match_reason.get("matched_optional_terms", []),
    )


def fit_reason(candidate: dict[str, Any]) -> str:
    matched = candidate_matched_terms(candidate)
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


def judge_candidate_payload(candidate: dict[str, Any], local_rank: int) -> dict[str, Any]:
    scope_hints = candidate.get("scope_hints", {})
    local_match_reason = candidate.get("local_match_reason", {})
    return {
        "candidate_id": candidate.get("candidate_id"),
        "local_rank": local_rank,
        "title": candidate.get("canonical_title"),
        "matched_terms": candidate_matched_terms(candidate)[:5],
        "match_score": local_match_reason.get("match_score"),
        "fit_reason": fit_reason(candidate),
        "subjects": (scope_hints.get("subjects") or [])[:2],
        "disciplines": (scope_hints.get("disciplines") or [])[:2],
        "index_label": journal_index_label(candidate),
        "apc_supported": bool(candidate.get("apc_funding_eligible", False)),
    }


def rerank_candidates_with_ollama(query: str, candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(candidates) < 2:
        return candidates, {
            "enabled": OLLAMA_JUDGE_ENABLED,
            "attempted": False,
            "host": OLLAMA_CLOUD_HOST,
            "model": OLLAMA_CLOUD_MODEL,
            "status": "skipped_small_pool",
            "status_text": "Aday havuzu çok küçük olduğu için yerel sıralama korundu.",
        }

    if not OLLAMA_JUDGE_ENABLED:
        return candidates, {
            "enabled": False,
            "attempted": False,
            "host": OLLAMA_CLOUD_HOST,
            "model": OLLAMA_CLOUD_MODEL,
            "status": "disabled",
            "status_text": "Ollama judge kapalı; yerel sıralama kullanıldı.",
        }

    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        return candidates, {
            "enabled": False,
            "attempted": False,
            "host": OLLAMA_CLOUD_HOST,
            "model": OLLAMA_CLOUD_MODEL,
            "status": "disabled",
            "status_text": "OLLAMA_API_KEY bulunamadı; yerel sıralama kullanıldı.",
        }

    try:
        from ollama import Client
    except ImportError:
        return candidates, {
            "enabled": True,
            "attempted": False,
            "host": OLLAMA_CLOUD_HOST,
            "model": OLLAMA_CLOUD_MODEL,
            "status": "import_error",
            "status_text": "Ollama judge istemcisi yüklenemedi; yerel sıralama kullanıldı.",
        }

    candidate_payloads = [judge_candidate_payload(candidate, index) for index, candidate in enumerate(candidates, start=1)]
    system_prompt = (
        "You are a journal reranking judge for academic journal recommendation. "
        "Reorder only the candidate journals provided by the system. "
        "Return only a JSON object with one key: ordered_candidate_ids. "
        "Use only the provided candidate_id values. Do not invent journals, do not rename titles, and do not remove candidates. "
        "Hard filters such as UBYT inclusion, APC, payment, and index are already applied by the system and must not be overridden. "
        "Rank candidates by topical fit to the user's original query. Prefer topic fit over prestige. "
        "Use title, matched_terms, fit_reason, subjects, and disciplines as the main evidence. "
        "If evidence is weak or ambiguous, stay close to the local_rank order. Return JSON only."
    )
    user_prompt = (
        "Re-rank the following journal candidates for the user's original request. Return JSON only.\n\n"
        f"User query:\n{query}\n\n"
        f"Candidates:\n{json.dumps(candidate_payloads, ensure_ascii=False)}"
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
            format=OLLAMA_JUDGE_SCHEMA,
            options={"temperature": 0},
        )
    except Exception:
        return candidates, {
            "enabled": True,
            "attempted": True,
            "host": OLLAMA_CLOUD_HOST,
            "model": OLLAMA_CLOUD_MODEL,
            "status": "request_failed",
            "status_text": "Ollama judge sıralaması alınamadı; yerel sıralama korundu.",
        }

    if isinstance(response, dict):
        content = response.get("message", {}).get("content", "")
    else:
        message = getattr(response, "message", None)
        content = getattr(message, "content", "") if message is not None else ""

    ranked_candidate_ids = parse_ollama_rerank(content)
    candidate_map = {
        candidate.get("candidate_id"): candidate
        for candidate in candidates
        if candidate.get("candidate_id")
    }
    local_candidate_ids = [candidate.get("candidate_id") for candidate in candidates if candidate.get("candidate_id")]

    valid_ranked_ids: list[str] = []
    seen_ids: set[str] = set()
    for candidate_id in ranked_candidate_ids:
        if candidate_id in candidate_map and candidate_id not in seen_ids:
            seen_ids.add(candidate_id)
            valid_ranked_ids.append(candidate_id)

    if not valid_ranked_ids:
        return candidates, {
            "enabled": True,
            "attempted": True,
            "host": OLLAMA_CLOUD_HOST,
            "model": OLLAMA_CLOUD_MODEL,
            "status": "invalid_response",
            "status_text": "Ollama judge geçerli bir sıralama döndüremedi; yerel sıralama korundu.",
        }

    final_ids = valid_ranked_ids + [candidate_id for candidate_id in local_candidate_ids if candidate_id not in seen_ids]
    reranked_candidates = [candidate_map[candidate_id] for candidate_id in final_ids if candidate_id in candidate_map]
    reranked_candidates.extend(candidate for candidate in candidates if not candidate.get("candidate_id"))

    return reranked_candidates, {
        "enabled": True,
        "attempted": True,
        "host": OLLAMA_CLOUD_HOST,
        "model": OLLAMA_CLOUD_MODEL,
        "status": "success",
        "status_text": f"Ollama judge sıralaması uygulandı ({OLLAMA_CLOUD_MODEL}). Yerel shortlist yeniden sıralandı.",
    }


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
        "matched_terms": candidate_matched_terms(candidate),
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


def build_recommendation_response(
    payload: RecommendationRequest,
    export_all: bool = False,
) -> dict[str, Any]:
    required_terms, optional_terms, term_source, llm_info = extract_search_terms_with_source(payload.query)
    result_limit = max(len(JOURNALS.index), payload.limit) if export_all else max(payload.limit, OLLAMA_JUDGE_POOL_LIMIT)
    shortlist = prepare_scope_review_candidates(
        required_terms=required_terms,
        optional_terms=optional_terms,
        indexes=payload.indexes,
        require_apc=payload.require_apc,
        apc_providers=payload.apc_providers,
        max_payment_tl=payload.max_payment_tl,
        sort_by="relevance",
        limit=result_limit,
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
            limit=result_limit,
        )
        ranking_mode = "relaxed-required-to-optional"

    shortlisted_candidates = shortlist.get("candidates", [])
    judge_info = {
        "enabled": OLLAMA_JUDGE_ENABLED,
        "attempted": False,
        "host": OLLAMA_CLOUD_HOST,
        "model": OLLAMA_CLOUD_MODEL,
        "status": "skipped_export",
        "status_text": "Export akışında yerel sıralama korundu.",
    }
    if not export_all:
        shortlisted_candidates, judge_info = rerank_candidates_with_ollama(payload.query, shortlisted_candidates)

    candidate_pool_count = len(shortlisted_candidates)
    visible_candidates = shortlisted_candidates if export_all else shortlisted_candidates[:payload.limit]
    results = [card_payload(candidate, payload.indexes, term_source) for candidate in visible_candidates]
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
            "apc_providers": payload.apc_providers,
            "max_payment_tl": payload.max_payment_tl,
            "indexes": payload.indexes,
            "keyword_source": term_source,
            "candidate_pool_count": candidate_pool_count,
            "llm": llm_info,
            "rerank": judge_info,
            "rerank_source": "ollama-judge" if judge_info.get("status") == "success" else "local-shortlist",
        },
        "results": results,
        "closed_set_only": shortlist.get("closed_set_only", True),
    }


def build_export_filename(query: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_text(query)).strip("-")[:60]
    if not slug:
        slug = "dergi-sonuclari"
    return f"{slug}-dergi-sonuclari.xlsx"


def build_export_journal_url(result: dict[str, Any]) -> str:
    preferred_url = result.get("preferred_url")
    if preferred_url:
        return preferred_url

    query_parts = [result.get("title"), result.get("issn"), result.get("eissn"), "journal"]
    cleaned_parts = [str(value).strip() for value in query_parts if value and str(value).strip() != "-"]
    if not cleaned_parts:
        return "-"

    return f"https://www.google.com/search?q={quote_plus(' '.join(cleaned_parts))}"


def build_export_summary_rows(response_payload: dict[str, Any]) -> list[dict[str, Any]]:
    summary = response_payload.get("query_summary", {})
    return [
        {
            "Sorgu": response_payload.get("query") or "-",
            "Sonuc Sayisi": summary.get("result_count", 0),
            "Siralama Modu": summary.get("ranking_mode", "strict-required"),
            "Anahtar Kelime Kaynagi": summary.get("keyword_source", "cloud/local"),
            "Modelin Cikardigi Zorunlu Terimler": ", ".join(summary.get("required_terms", [])) or "yok",
            "Uygulanan Zorunlu Filtre": ", ".join(summary.get("applied_required_terms", [])) or "yok",
            "Siralama Terimleri": ", ".join(summary.get("applied_optional_terms", [])) or "yok",
            "APC Filtresi": "Acik" if summary.get("require_apc") else "Kapali",
            "APC Yayinevleri": ", ".join(summary.get("apc_providers", [])) or "-",
            "Maksimum Destek": format_payment(summary.get("max_payment_tl")),
            "Indeks": ", ".join(summary.get("indexes", [])) or "Tumu",
        }
    ]


def build_export_result_rows(query: str, response_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    results = response_payload.get("results", [])

    for order, result in enumerate(results, start=1):
        apc_details = result.get("apc_details") or []
        providers = [badge for badge in result.get("badges", []) if badge != "UBYT"]
        apc_urls = [detail.get("url") for detail in apc_details if detail.get("url") and detail.get("url") != "-"]
        apc_files = [detail.get("raw_source_file") for detail in apc_details if detail.get("raw_source_file") and detail.get("raw_source_file") != "-"]
        apc_imprints = [detail.get("publisher_or_imprint") for detail in apc_details if detail.get("publisher_or_imprint") and detail.get("publisher_or_imprint") != "-"]
        scope_hints = result.get("scope_hints") or {}
        hint_terms = merge_unique_terms(scope_hints.get("subjects", []) or [], scope_hints.get("disciplines", []) or [])

        rows.append(
            {
                "Sorgu": query,
                "Sira": order,
                "Dergi Basligi": result.get("title") or "-",
                "Uygunluk Ozeti": result.get("fit_reason") or "-",
                "Rozetler": ", ".join(result.get("badges", [])) or "-",
                "APC Destegi": "Var" if result.get("apc_supported") else "Yok",
                "APC Saglayicilari": ", ".join(providers) or "-",
                "ISSN": result.get("issn") or "-",
                "eISSN": result.get("eissn") or "-",
                "Tesvik Tutari": result.get("support_amount") or "-",
                "MEP Puani": result.get("mep_score") or "-",
                "Indeks": result.get("index_label") or "-",
                "Program": result.get("source_program") or "-",
                "Yil": result.get("source_year") or "-",
                "Eslesen Terimler": ", ".join(result.get("matched_terms", [])) or "-",
                "Konu Ipuclari": ", ".join(hint_terms) or "-",
                "Dergi Sayfasi": build_export_journal_url(result),
                "Model Kaynagi": (result.get("provenance") or {}).get("model_source") or "-",
                "Kaynaklar": ", ".join((result.get("provenance") or {}).get("sources", [])) or "-",
                "APC Kaynak Dosyalari": ", ".join(sorted(dict.fromkeys(apc_files))) or "-",
                "APC Imprint": ", ".join(sorted(dict.fromkeys(apc_imprints))) or "-",
                "APC Kayit Sayisi": len(apc_details),
                "APC URLleri": ", ".join(sorted(dict.fromkeys(apc_urls))) or "-",
            }
        )

    return rows


def export_results_workbook(response_payload: dict[str, Any]) -> BytesIO:
    summary_df = pd.DataFrame(build_export_summary_rows(response_payload))
    result_rows = build_export_result_rows(response_payload.get("query") or "-", response_payload)
    results_df = pd.DataFrame(result_rows)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Ozet", index=False)
        results_df.to_excel(writer, sheet_name="Dergi Sonuclari", index=False)

    output.seek(0)
    return output


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
    return build_recommendation_response(payload)


@app.post("/export-results")
def export_results(payload: dict[str, Any]) -> StreamingResponse:
    has_current_results = isinstance(payload.get("results"), list) and isinstance(payload.get("query_summary"), dict)
    if has_current_results:
        response_payload = {
            "query": payload.get("query") or "-",
            "query_summary": payload.get("query_summary") or {},
            "results": payload.get("results") or [],
        }
    else:
        recommendation_payload = RecommendationRequest.model_validate(payload)
        response_payload = build_recommendation_response(recommendation_payload, export_all=True)

    workbook = export_results_workbook(response_payload)
    filename = build_export_filename(response_payload.get("query") or "dergi-sonuclari")
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )