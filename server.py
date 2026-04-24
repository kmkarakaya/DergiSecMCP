from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
from mcp.server.fastmcp import FastMCP


BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / "ubyt.xlsx"
ELSEVIER_PATH = BASE_DIR / "Elsevier.xlsx"
WILEY_PATH = BASE_DIR / "Wiley.xlsx"

EXPECTED_COLUMNS = [
    "Dergi Adı",
    "issn",
    "eissn",
    "Ödeme (TL)",
    "Dergi Mep Puanı",
    "SCIE",
    "SSCI",
    "AHCI",
    "Kaynak",
    "Yıl",
]

TURKISH_TRANSLATION = str.maketrans(
    {
        "ç": "c",
        "Ç": "c",
        "ğ": "g",
        "Ğ": "g",
        "ı": "i",
        "I": "i",
        "İ": "i",
        "ö": "o",
        "Ö": "o",
        "ş": "s",
        "Ş": "s",
        "ü": "u",
        "Ü": "u",
    }
)


def normalize_text(value: Any) -> str:
    """Normalize journal names for case-insensitive and Turkish-insensitive search."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).translate(TURKISH_TRANSLATION).casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def normalize_number(value: Any) -> str:
    """Normalize ISSN/eISSN values so hyphenated and non-hyphenated input both match."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return re.sub(r"[^0-9Xx]", "", str(value)).upper()


def json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def row_to_apc_journal(row: pd.Series) -> dict[str, Any]:
    journal = {
        "provider": json_value(row["provider"]),
        "journal_title": json_value(row["journal_title"]),
        "issn": json_value(row["issn"]),
        "eissn": json_value(row["eissn"]),
        "publisher_or_imprint": json_value(row["publisher_or_imprint"]),
        "discipline": json_value(row["discipline"]),
        "subject": json_value(row["subject"]),
        "publishing_model": json_value(row["publishing_model"]),
        "oa_license": json_value(row["oa_license"]),
        "url": json_value(row["url"]),
        "raw_source_file": json_value(row["raw_source_file"]),
    }
    for optional_field in ["wos_index", "quartile", "impact_factor", "journal_id"]:
        if optional_field in row.index:
            journal[optional_field] = json_value(row[optional_field])
    return journal


def apc_evidence_summary(apc_matches: list[dict[str, Any]]) -> dict[str, Any]:
    if not apc_matches:
        return {
            "match_count": 0,
            "source_files": [],
            "publishers_or_imprints": [],
            "match_types": [],
            "best_match": None,
        }

    best_match = max(
        apc_matches,
        key=lambda match: (
            int(match.get("match_score") or 0),
            normalize_text(match.get("journal_title")),
            normalize_text(match.get("publisher_or_imprint")),
        ),
    )
    return {
        "match_count": len(apc_matches),
        "source_files": sorted(
            {match["raw_source_file"] for match in apc_matches if match.get("raw_source_file")}
        ),
        "publishers_or_imprints": sorted(
            {
                match["publisher_or_imprint"]
                for match in apc_matches
                if match.get("publisher_or_imprint")
            }
        ),
        "match_types": sorted({match["match_type"] for match in apc_matches if match.get("match_type")}),
        "best_match": {
            "provider": best_match.get("provider"),
            "journal_title": best_match.get("journal_title"),
            "issn": best_match.get("issn"),
            "eissn": best_match.get("eissn"),
            "publisher_or_imprint": best_match.get("publisher_or_imprint"),
            "raw_source_file": best_match.get("raw_source_file"),
            "match_type": best_match.get("match_type"),
            "match_score": best_match.get("match_score"),
        },
    }


def attach_apc_support(
    payload: dict[str, Any],
    apc_matches: list[dict[str, Any]],
    *,
    ubyt_eligible: bool,
) -> dict[str, Any]:
    apc_providers = sorted({match["provider"] for match in apc_matches})
    payload["ubyt_incentive_eligible"] = ubyt_eligible
    payload["apc_funding_eligible"] = bool(apc_matches)
    payload["apc_providers"] = apc_providers
    payload["apc_matches"] = apc_matches
    payload["apc_evidence"] = apc_evidence_summary(apc_matches)
    payload["both_eligible"] = bool(ubyt_eligible and apc_matches)
    return payload


def row_to_journal(row: pd.Series, include_apc: bool = True) -> dict[str, Any]:
    journal = {
        "dergi_adi": json_value(row["Dergi Adı"]),
        "issn": json_value(row["issn"]),
        "eissn": json_value(row["eissn"]),
        "odeme_tl": json_value(row["Ödeme (TL)"]),
        "dergi_mep_puani": json_value(row["Dergi Mep Puanı"]),
        "scie": bool(row["SCIE"]),
        "ssci": bool(row["SSCI"]),
        "ahci": bool(row["AHCI"]),
        "kaynak": json_value(row["Kaynak"]),
        "yil": json_value(row["Yıl"]),
        "ubyt_incentive_eligible": True,
    }
    if include_apc and "APC_JOURNALS" in globals():
        apc_matches = _find_apc_matches_for_journal_row(row)
        attach_apc_support(journal, apc_matches, ubyt_eligible=True)
    return journal


def load_journals() -> pd.DataFrame:
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Excel file not found: {EXCEL_PATH}")

    df = pd.read_excel(EXCEL_PATH)
    missing_columns = [column for column in EXPECTED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing expected columns in {EXCEL_PATH.name}: {missing_columns}")

    df = df[EXPECTED_COLUMNS].copy()
    df["_dergi_adi_norm"] = df["Dergi Adı"].map(normalize_text)
    df["_issn_norm"] = df["issn"].map(normalize_number)
    df["_eissn_norm"] = df["eissn"].map(normalize_number)
    return df


def _require_columns(df: pd.DataFrame, columns: list[str], source_name: str) -> None:
    missing_columns = [column for column in columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing expected columns in {source_name}: {missing_columns}")


def _apc_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(
            columns=[
                "provider",
                "journal_title",
                "issn",
                "eissn",
                "publisher_or_imprint",
                "discipline",
                "subject",
                "publishing_model",
                "oa_license",
                "url",
                "raw_source_file",
            ]
        )

    df["_journal_title_norm"] = df["journal_title"].map(normalize_text)
    df["_issn_norm"] = df["issn"].map(normalize_number)
    df["_eissn_norm"] = df["eissn"].map(normalize_number)
    return df


def load_wiley_journals() -> pd.DataFrame:
    if not WILEY_PATH.exists():
        raise FileNotFoundError(f"APC file not found: {WILEY_PATH}")

    df = pd.read_excel(WILEY_PATH, sheet_name=0, header=2)
    _require_columns(
        df,
        [
            "Dergi Adı",
            "eISSN",
            "WOS\n Indeks",
            "Derginin Modeli",
            "URL",
            "Genel Konu",
            "Özel Konu",
            "Yayıncı",
        ],
        WILEY_PATH.name,
    )

    rows = []
    for _, row in df.iterrows():
        journal_title = json_value(row["Dergi Adı"])
        if not journal_title:
            continue
        rows.append(
            {
                "provider": "wiley",
                "journal_title": journal_title,
                "issn": None,
                "eissn": json_value(row["eISSN"]),
                "publisher_or_imprint": json_value(row["Yayıncı"]),
                "discipline": json_value(row["Genel Konu"]),
                "subject": json_value(row["Özel Konu"]),
                "publishing_model": json_value(row["Derginin Modeli"]),
                "oa_license": None,
                "url": json_value(row["URL"]),
                "raw_source_file": WILEY_PATH.name,
                "wos_index": json_value(row["WOS\n Indeks"]),
                "quartile": json_value(row.get("Q Değeri\n2024")),
                "impact_factor": json_value(row.get("IF Değeri\n2024")),
            }
        )
    return _apc_dataframe(rows)


def load_elsevier_journals() -> pd.DataFrame:
    if not ELSEVIER_PATH.exists():
        raise FileNotFoundError(f"APC file not found: {ELSEVIER_PATH}")

    df = pd.read_excel(
        ELSEVIER_PATH,
        sheet_name="Eligible journals-OA publishing",
        header=5,
    )
    _require_columns(
        df,
        [
            "Journal Title",
            "eISSN",
            "Journal Imprint",
            "Main Discipline",
            "Subject Area",
            "Publishing Model",
            "OA License",
            "URL",
        ],
        ELSEVIER_PATH.name,
    )

    rows = []
    for _, row in df.iterrows():
        journal_title = json_value(row["Journal Title"])
        if not journal_title:
            continue
        rows.append(
            {
                "provider": "elsevier",
                "journal_title": journal_title,
                "issn": None,
                "eissn": json_value(row["eISSN"]),
                "publisher_or_imprint": json_value(row["Journal Imprint"]),
                "discipline": json_value(row["Main Discipline"]),
                "subject": json_value(row["Subject Area"]),
                "publishing_model": json_value(row["Publishing Model"]),
                "oa_license": json_value(row["OA License"]),
                "url": json_value(row["URL"]),
                "raw_source_file": ELSEVIER_PATH.name,
                "journal_id": json_value(row.get("Journal ID")),
            }
        )
    return _apc_dataframe(rows)


def load_apc_journals() -> pd.DataFrame:
    return pd.concat(
        [load_elsevier_journals(), load_wiley_journals()],
        ignore_index=True,
    )


def build_apc_lookups(df: pd.DataFrame) -> dict[str, dict[str, list[int]]]:
    lookups: dict[str, dict[str, list[int]]] = {"eissn": {}, "issn": {}, "title": {}}
    for index, row in df.iterrows():
        keys = {
            "eissn": row["_eissn_norm"],
            "issn": row["_issn_norm"],
            "title": row["_journal_title_norm"],
        }
        for lookup_name, key in keys.items():
            if key:
                lookups[lookup_name].setdefault(key, []).append(index)
    return lookups


JOURNALS = load_journals()
APC_JOURNALS = load_apc_journals()
APC_LOOKUPS = build_apc_lookups(APC_JOURNALS)

mcp = FastMCP(
    "ubyt",
    instructions=(
        "UBYT yayin tesvik listesini ve Elsevier/Wiley APC destek listelerini arar. "
        "Dergi adi, ISSN veya eISSN ile sorgu yapilabilir."
    ),
)


def _safe_limit(limit: int) -> int:
    try:
        limit_value = int(limit)
    except (TypeError, ValueError):
        return 10
    return min(max(limit_value, 1), 100)


def _score_row(row: pd.Series, query_text: str, query_number: str) -> int:
    score = 0
    journal_name = row["_dergi_adi_norm"]
    issn = row["_issn_norm"]
    eissn = row["_eissn_norm"]

    if query_number:
        if query_number in {issn, eissn}:
            score = max(score, 100)
        elif query_number in issn or query_number in eissn:
            score = max(score, 80)

    if query_text:
        if query_text == journal_name:
            score = max(score, 90)
        elif journal_name.startswith(query_text):
            score = max(score, 70)
        elif query_text in journal_name:
            score = max(score, 50)

    return score


VALID_INDEXES = {"SCIE", "SSCI", "AHCI"}
VALID_SORTS = {"relevance", "mep_desc", "payment_desc", "name_asc"}
VALID_APC_PROVIDERS = {"elsevier", "wiley"}


def _normalize_terms(terms: Any) -> list[str]:
    if terms is None:
        return []
    if isinstance(terms, str):
        terms = [terms]

    normalized_terms: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = normalize_text(term)
        if normalized and normalized not in seen:
            normalized_terms.append(normalized)
            seen.add(normalized)
    return normalized_terms


def _normalize_indexes(indexes: Any) -> list[str]:
    if indexes is None:
        return []
    if isinstance(indexes, str):
        indexes = [indexes]

    normalized_indexes: list[str] = []
    for index in indexes:
        normalized = str(index).strip().upper()
        if normalized in VALID_INDEXES and normalized not in normalized_indexes:
            normalized_indexes.append(normalized)
    return normalized_indexes


def _normalize_providers(providers: Any) -> list[str]:
    if providers is None:
        return []
    if isinstance(providers, str):
        providers = [providers]

    normalized_providers: list[str] = []
    for provider in providers:
        normalized = normalize_text(provider)
        if normalized in VALID_APC_PROVIDERS and normalized not in normalized_providers:
            normalized_providers.append(normalized)
    return normalized_providers


def _contains_all_terms(journal_name: str, terms: list[str]) -> bool:
    return all(term in journal_name for term in terms)


def _matched_terms(journal_name: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term in journal_name]


def _numeric_filter(value: Any, minimum: float | None = None, maximum: float | None = None) -> bool:
    value = json_value(value)
    if value is None:
        return False
    numeric_value = float(value)
    if minimum is not None and numeric_value < float(minimum):
        return False
    if maximum is not None and numeric_value > float(maximum):
        return False
    return True


def _candidate_sort_key(
    item: tuple[int, int, pd.Series, list[str], list[str], list[dict[str, Any]]],
    sort_by: str,
):
    score, index, row, _, _, _ = item
    mep_score = json_value(row["Dergi Mep Puanı"]) or 0
    payment = json_value(row["Ödeme (TL)"]) or 0
    journal_name = normalize_text(row["Dergi Adı"])

    if sort_by == "mep_desc":
        return (-float(mep_score), -score, index)
    if sort_by == "payment_desc":
        return (-float(payment), -score, index)
    if sort_by == "name_asc":
        return (journal_name, index)
    return (-score, -float(mep_score), index)


def _topic_tokens(topic: str) -> list[str]:
    topic_text = normalize_text(topic)
    return sorted({token for token in re.findall(r"[a-z0-9]+", topic_text) if len(token) >= 4})


def _filter_apc_providers(df: pd.DataFrame, providers: list[str]) -> pd.DataFrame:
    if not providers:
        return df
    return df[df["provider"].isin(providers)]


def _apc_match_records(df: pd.DataFrame, match_type: str, score: int) -> list[dict[str, Any]]:
    matches = []
    for _, row in df.iterrows():
        match = row_to_apc_journal(row)
        match["match_type"] = match_type
        match["match_score"] = score
        matches.append(match)
    return matches


def _apc_match_records_from_indices(
    indices: list[int],
    match_type: str,
    score: int,
    providers: list[str],
) -> list[dict[str, Any]]:
    matches = []
    seen: set[int] = set()
    for index in indices:
        if index in seen:
            continue
        seen.add(index)
        row = APC_JOURNALS.loc[index]
        if providers and row["provider"] not in providers:
            continue
        match = row_to_apc_journal(row)
        match["match_type"] = match_type
        match["match_score"] = score
        matches.append(match)
    return matches


def _find_apc_matches(
    title: Any = None,
    issn: Any = None,
    eissn: Any = None,
    providers: list[str] | None = None,
    allow_title_contains: bool = False,
) -> list[dict[str, Any]]:
    provider_filter = providers or []
    df = _filter_apc_providers(APC_JOURNALS, provider_filter)
    title_norm = normalize_text(title)
    issn_norm = normalize_number(issn)
    eissn_norm = normalize_number(eissn)

    if eissn_norm:
        matches = _apc_match_records_from_indices(
            APC_LOOKUPS["eissn"].get(eissn_norm, []),
            "eissn",
            100,
            provider_filter,
        )
        if matches:
            return matches

    if issn_norm:
        matches = _apc_match_records_from_indices(
            APC_LOOKUPS["issn"].get(issn_norm, []),
            "issn",
            95,
            provider_filter,
        )
        if matches:
            return matches

    if title_norm:
        matches = _apc_match_records_from_indices(
            APC_LOOKUPS["title"].get(title_norm, []),
            "title_exact",
            90,
            provider_filter,
        )
        if matches:
            return matches

        if allow_title_contains:
            matches = df[df["_journal_title_norm"].str.contains(re.escape(title_norm), na=False)]
            if not matches.empty:
                return _apc_match_records(matches, "title_contains", 60)

    return []


def _find_apc_matches_for_journal_row(
    row: pd.Series,
    providers: list[str] | None = None,
) -> list[dict[str, Any]]:
    return _find_apc_matches(
        title=row["Dergi Adı"],
        issn=row["issn"],
        eissn=row["eissn"],
        providers=providers,
    )


def _find_ubyt_matches(
    title: Any = None,
    number: Any = None,
    allow_title_contains: bool = False,
) -> list[dict[str, Any]]:
    title_norm = normalize_text(title)
    number_norm = normalize_number(number)

    if number_norm:
        matches = JOURNALS[
            (JOURNALS["_issn_norm"] == number_norm) | (JOURNALS["_eissn_norm"] == number_norm)
        ]
        if not matches.empty:
            return [row_to_journal(row) for _, row in matches.iterrows()]

    if title_norm:
        matches = JOURNALS[JOURNALS["_dergi_adi_norm"] == title_norm]
        if not matches.empty:
            return [row_to_journal(row) for _, row in matches.iterrows()]

        if allow_title_contains:
            matches = JOURNALS[
                JOURNALS["_dergi_adi_norm"].str.contains(re.escape(title_norm), na=False)
            ]
            if not matches.empty:
                return [row_to_journal(row) for _, row in matches.iterrows()]

    return []


@mcp.tool()
def search_journals(query: str, limit: int = 10) -> dict[str, Any]:
    """Search journals by name, ISSN, or eISSN."""
    query_text = normalize_text(query)
    query_number = normalize_number(query)
    if not any(ch.isdigit() for ch in query_number) or len(query_number) < 4:
        query_number = ""
    result_limit = _safe_limit(limit)

    if not query_text and not query_number:
        return {"query": query, "total": 0, "matches": []}

    rows: list[tuple[int, int, pd.Series]] = []
    for index, row in JOURNALS.iterrows():
        score = _score_row(row, query_text, query_number)
        if score > 0:
            rows.append((score, index, row))

    rows.sort(key=lambda item: (-item[0], item[1]))
    matches = [row_to_journal(row) for _, _, row in rows[:result_limit]]
    return {"query": query, "total": len(rows), "matches": matches}


@mcp.tool()
def get_journal_by_number(number: str) -> dict[str, Any]:
    """Find journals by exact ISSN or eISSN."""
    normalized_number = normalize_number(number)
    if not normalized_number:
        return {"number": number, "total": 0, "matches": []}

    mask = (JOURNALS["_issn_norm"] == normalized_number) | (
        JOURNALS["_eissn_norm"] == normalized_number
    )
    matches = [row_to_journal(row) for _, row in JOURNALS[mask].iterrows()]
    return {"number": number, "total": len(matches), "matches": matches}


@mcp.tool()
def search_apc_supported_journals(
    query: str,
    providers: list[str] = [],
    limit: int = 20,
) -> dict[str, Any]:
    """Search Elsevier/Wiley APC supported journal lists by title, ISSN, or eISSN."""
    result_limit = _safe_limit(limit)
    selected_providers = _normalize_providers(providers)
    query_text = normalize_text(query)
    query_number = normalize_number(query)
    if not any(ch.isdigit() for ch in query_number):
        query_number = ""

    if not query_text and not query_number:
        return {"query": query, "providers": selected_providers, "total": 0, "matches": []}

    df = _filter_apc_providers(APC_JOURNALS, selected_providers)
    rows: list[tuple[int, int, pd.Series, str]] = []
    for index, row in df.iterrows():
        score = 0
        match_type = ""
        if query_number:
            if query_number == row["_eissn_norm"]:
                score = 100
                match_type = "eissn"
            elif query_number == row["_issn_norm"]:
                score = 95
                match_type = "issn"
            elif query_number in row["_eissn_norm"] or query_number in row["_issn_norm"]:
                score = 80
                match_type = "number_contains"

        if query_text:
            journal_title = row["_journal_title_norm"]
            if query_text == journal_title:
                if score < 90:
                    score = 90
                    match_type = "title_exact"
            elif journal_title.startswith(query_text):
                if score < 70:
                    score = 70
                    match_type = "title_startswith"
            elif query_text in journal_title:
                if score < 60:
                    score = 60
                    match_type = "title_contains"

        if score > 0:
            rows.append((score, index, row, match_type))

    rows.sort(key=lambda item: (-item[0], item[1]))
    matches = []
    for score, _, row, match_type in rows[:result_limit]:
        match = row_to_apc_journal(row)
        match["match_type"] = match_type
        match["match_score"] = score
        matches.append(match)

    return {
        "query": query,
        "providers": selected_providers,
        "total": len(rows),
        "matches": matches,
    }


@mcp.tool()
def check_journal_support(
    query: str | None = None,
    number: str | None = None,
) -> dict[str, Any]:
    """Check whether a journal is in UBYT incentive and Elsevier/Wiley APC funding lists."""
    lookup_text = query or ""
    lookup_number = number or ""
    ubyt_matches = _find_ubyt_matches(
        title=lookup_text,
        number=lookup_number,
        allow_title_contains=True,
    )

    apc_matches = _find_apc_matches(
        title=lookup_text,
        issn=lookup_number,
        eissn=lookup_number,
        allow_title_contains=True,
    )

    if ubyt_matches and not apc_matches:
        apc_seen: set[tuple[str, str]] = set()
        for ubyt_match in ubyt_matches:
            row_matches = _find_apc_matches(
                title=ubyt_match["dergi_adi"],
                issn=ubyt_match["issn"],
                eissn=ubyt_match["eissn"],
            )
            for match in row_matches:
                key = (match["provider"], normalize_number(match["eissn"]) or normalize_text(match["journal_title"]))
                if key not in apc_seen:
                    apc_matches.append(match)
                    apc_seen.add(key)

    result = {
        "query": query,
        "number": number,
        "ubyt_matches": ubyt_matches,
    }
    attach_apc_support(result, apc_matches, ubyt_eligible=bool(ubyt_matches))
    return result


@mcp.tool()
def check_multiple_journal_support(
    queries: list[str] = [],
    numbers: list[str] = [],
) -> dict[str, Any]:
    """Check UBYT and APC support for multiple journals in one call."""
    results = []
    for query in queries:
        if query:
            results.append(check_journal_support(query=query))
    for number in numbers:
        if number:
            results.append(check_journal_support(number=number))

    return {
        "queries": queries,
        "numbers": numbers,
        "total": len(results),
        "ubyt_incentive_eligible_count": sum(1 for result in results if result["ubyt_incentive_eligible"]),
        "apc_funding_eligible_count": sum(1 for result in results if result["apc_funding_eligible"]),
        "both_eligible_count": sum(1 for result in results if result["both_eligible"]),
        "results": results,
    }


@mcp.tool()
def find_journal_candidates(
    required_terms: list[str] = [],
    optional_terms: list[str] = [],
    exclude_terms: list[str] = [],
    indexes: list[str] = [],
    require_ubyt: bool = False,
    require_apc: bool = False,
    apc_providers: list[str] = [],
    source: str | None = None,
    min_mep_score: float | None = None,
    max_payment_tl: int | None = None,
    sort_by: str = "relevance",
    limit: int = 20,
) -> dict[str, Any]:
    """Find candidate journals with explicit terms, filters, and sorting preferences."""
    result_limit = _safe_limit(limit)
    required = _normalize_terms(required_terms)
    optional = _normalize_terms(optional_terms)
    excluded = _normalize_terms(exclude_terms)
    selected_indexes = _normalize_indexes(indexes)
    selected_apc_providers = _normalize_providers(apc_providers)
    normalized_source = normalize_text(source) if source is not None else None
    sort = sort_by if sort_by in VALID_SORTS else "relevance"

    rows: list[tuple[int, int, pd.Series, list[str], list[str], list[dict[str, Any]]]] = []
    for index, row in JOURNALS.iterrows():
        journal_name = row["_dergi_adi_norm"]
        if required and not _contains_all_terms(journal_name, required):
            continue
        if excluded and _matched_terms(journal_name, excluded):
            continue
        if selected_indexes and not any(bool(row[index_name]) for index_name in selected_indexes):
            continue
        if normalized_source is not None and normalize_text(row["Kaynak"]) != normalized_source:
            continue
        if min_mep_score is not None and not _numeric_filter(
            row["Dergi Mep Puanı"], minimum=min_mep_score
        ):
            continue
        if max_payment_tl is not None and not _numeric_filter(
            row["Ödeme (TL)"], maximum=max_payment_tl
        ):
            continue
        apc_matches = _find_apc_matches_for_journal_row(row, selected_apc_providers)
        if require_apc and not apc_matches:
            continue

        matched_required = _matched_terms(journal_name, required)
        matched_optional = _matched_terms(journal_name, optional)
        if optional and not matched_optional and not required:
            continue

        score = (len(matched_required) * 25) + (len(matched_optional) * 10)
        if bool(row["SCIE"]):
            score += 5
        if bool(row["SSCI"]):
            score += 3
        if bool(row["AHCI"]):
            score += 3

        rows.append((score, index, row, matched_required, matched_optional, apc_matches))

    rows.sort(key=lambda item: _candidate_sort_key(item, sort))
    matches = []
    for score, _, row, matched_required, matched_optional, apc_matches in rows[:result_limit]:
        journal = row_to_journal(row, include_apc=False)
        attach_apc_support(journal, apc_matches, ubyt_eligible=True)
        journal["match_score"] = score
        journal["matched_required_terms"] = matched_required
        journal["matched_optional_terms"] = matched_optional
        matches.append(journal)

    return {
        "required_terms": required,
        "optional_terms": optional,
        "exclude_terms": excluded,
        "indexes": selected_indexes,
        "require_ubyt": require_ubyt,
        "require_apc": require_apc,
        "apc_providers": selected_apc_providers,
        "source": source,
        "min_mep_score": min_mep_score,
        "max_payment_tl": max_payment_tl,
        "sort_by": sort,
        "total": len(rows),
        "matches": matches,
    }


@mcp.tool()
def recommend_journals_for_topic(topic: str, limit: int = 20) -> dict[str, Any]:
    """Compatibility helper: tokenizes topic text without domain-specific expansions."""
    tokens = _topic_tokens(topic)
    result = find_journal_candidates(optional_terms=tokens, sort_by="relevance", limit=limit)
    result["topic"] = topic
    result["note"] = (
        "This helper only tokenizes the topic text. For better results, the agent should extract "
        "field-specific English journal keywords and call find_journal_candidates directly."
    )
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
