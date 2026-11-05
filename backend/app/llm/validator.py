"""Number validator (Part H3). Every number in LLM text must exist in facts.

Supported: plain, comma-grouped (Western or Indian), percentages (62% and
"62 percent"), hyphenated (18-day), decimals, and date strings that must
match a date-valued fact exactly. Ordinals after "Step" are ignored.
Unit words (lakh/crore/...) are never converted and fail validation (v1).
"""

from __future__ import annotations

import re

# Dates must be capitalized ("25 Oct"); lowercase "may" is an ordinary verb.
_MONTHS_CAP = (
    "Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    "Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    "Dec(?:ember)?"
)
_DATE_RE = re.compile(rf"\b\d{{1,2}}\s+(?:{_MONTHS_CAP})\b(?:\s+\d{{2,4}})?")
_STEP_RE = re.compile(r"\b[Ss]tep\s+\d+\s*:")
_UNIT_WORD_RE = re.compile(
    r"\d[\d,]*(?:\.\d+)?\s*(?:lakh|lakhs|crore|crores|thousand|million|billion|trillion)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(
    r"[₹$€£]?\s*\d[\d,]*(?:\.\d+)?\s*(?:%|percent)?",
    re.IGNORECASE,
)
_CURRENCY_SYMBOLS = "₹$€£"


def _normalize_date(text: str) -> str:
    """Lowercase, single spaces — for comparing date strings to fact values."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _to_float(value: object) -> float | None:
    """Parse a fact value to float; None when it is not numeric."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().lstrip(_CURRENCY_SYMBOLS).replace(",", "")
        cleaned = re.sub(r"\s*(%|percent)$", "", cleaned, flags=re.IGNORECASE).strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _parse_token(token: str) -> tuple[float, int]:
    """Numeric value plus displayed decimal places of one extracted token."""
    t = token.strip().lstrip(_CURRENCY_SYMBOLS).strip()
    t = re.sub(r"\s*(%|percent)$", "", t, flags=re.IGNORECASE).strip()
    body = t.replace(",", "")
    decimals = len(body.split(".")[1]) if "." in body else 0
    return float(body), decimals


def validate_numbers(text: str, facts: dict[str, object]) -> tuple[bool, list[str]]:
    """Check every number in text against facts.

    Returns (ok, unmatched): ok is True when all tokens match; unmatched
    lists the offending tokens (empty on success).
    """
    numeric_facts: list[float] = []
    string_facts: list[str] = []
    covered: list[tuple[int, int]] = []  # spans of string-valued facts in text
    for value in facts.values():
        parsed = _to_float(value)
        if parsed is not None:
            numeric_facts.append(parsed)
        elif isinstance(value, str) and value.strip():
            needle = str(value).strip()
            string_facts.append(_normalize_date(needle))
            # Digits inside an entity identifier ("M8", "Plant 1") are the
            # name itself, not measurements — skip their spans.
            pattern = re.compile(re.escape(needle), re.IGNORECASE)
            for match in pattern.finditer(text):
                covered.append((match.start(), match.end()))

    def _is_covered(start: int, end: int) -> bool:
        return any(start >= s and end <= e for s, e in covered)

    unmatched: list[str] = []

    # Date tokens must match a date-valued fact string exactly (normalized).
    work = text
    for match in _DATE_RE.finditer(text):
        token = match.group(0)
        if _normalize_date(token) not in string_facts:
            unmatched.append(token)
        work = work.replace(token, " ", 1)

    # Unit words (lakh/crore/...) are never converted in v1: any occurrence
    # attached to a number fails validation.
    unit_hit = _UNIT_WORD_RE.search(work)
    if unit_hit is not None:
        unmatched.append(unit_hit.group(0).strip())

    # "Step 1:" ordinals are not measurements.
    work = _STEP_RE.sub(" ", work)

    for match in _NUMBER_RE.finditer(work):
        token = match.group(0).strip()
        if not token or not re.search(r"\d", token):
            continue
        start = 0
        covered_hit = False
        while True:
            probe = text.find(token, start)
            if probe == -1:
                break
            if _is_covered(probe, probe + len(token)):
                covered_hit = True
                break
            start = probe + 1
        if covered_hit:
            continue
        value, decimals = _parse_token(token)
        hit = any(round(value, decimals) == round(fact, decimals) for fact in numeric_facts)
        if not hit:
            unmatched.append(token.strip())

    return (len(unmatched) == 0), unmatched
