"""Rule-based chat intent matcher (P2-05, spec Part H4).

Maps a free-text question to one of six fixed read-only intents (plus
``unknown``) and extracts the target entity. This module is *pure
classification*: it only interprets text. It never executes anything, never
touches the database, and never changes state.

Safety invariants (enforced here, and again by the read-only chat layer):
  - SQL / command / prompt-injection / mutation inputs are classified as
    ``unknown`` so the downstream layer treats them as unsupported.
  - No intent in the vocabulary can ``run_sql``, ``execute_state_change`` or
    ``reveal_other_role_data``; those are impossible by construction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

INTENT_ITEM_STATUS = "item_status"
INTENT_FORECAST = "forecast"
INTENT_LIST_ALERTS = "list_alerts"
INTENT_EXPLAIN_ALERT = "explain_alert"
INTENT_SUPPLIER_SUMMARY = "supplier_summary"
INTENT_SAVINGS_REPORT = "savings_report"
INTENT_UNKNOWN = "unknown"

VALID_INTENTS: frozenset[str] = frozenset(
    {
        INTENT_ITEM_STATUS,
        INTENT_FORECAST,
        INTENT_LIST_ALERTS,
        INTENT_EXPLAIN_ALERT,
        INTENT_SUPPLIER_SUMMARY,
        INTENT_SAVINGS_REPORT,
        INTENT_UNKNOWN,
    }
)

# Supported questions surfaced to the user when an intent cannot be matched.
SUPPORTED_INTENTS: tuple[str, ...] = (
    INTENT_ITEM_STATUS,
    INTENT_FORECAST,
    INTENT_LIST_ALERTS,
    INTENT_EXPLAIN_ALERT,
    INTENT_SUPPLIER_SUMMARY,
    INTENT_SAVINGS_REPORT,
)

_SEVERITIES = ("critical", "high", "medium", "low")
_REASON_SAFETY = "safety_rejected"
_REASON_NO_MATCH = "no_match"


@dataclass(frozen=True)
class ParsedQuery:
    """Result of matching a question to an intent."""

    intent: str
    entity: str | None
    reason: str | None = None

    @property
    def is_unknown(self) -> bool:
        return self.intent == INTENT_UNKNOWN


# ---- safety pre-check ------------------------------------------------------
_SQL_RE = re.compile(
    r"\bselect\b[\s\S]*\bfrom\b"
    r"|\bdrop\s+table\b"
    r"|\binsert\s+into\b"
    r"|\bdelete\s+from\b"
    r"|\bupdate\b[\s\S]*\bset\b"
    r"|\bunion\b[\s\S]*\bselect\b"
    r"|\*\s*from\b",
    re.IGNORECASE,
)
_INJECTION_RE = re.compile(
    r"ignore\s+(all\s+|the\s+)?(previous|prior|above|your)?\s*instructions?"
    r"|disregard\s+(all|the|your)\b[\s\S]*instructions?"
    r"|forget\s+(all\s+|your\s+)?instructions?"
    r"|\bsystem\s+prompt\b"
    r"|reveal\s+(your\s+)?(prompt|instructions|system)",
    re.IGNORECASE,
)
_MUTATION_RE = re.compile(
    r"\b(delete|remove|approve|reject|cancel|update|insert|drop|create|modify"
    r"|disable|enable|reset|archive|purge|wipe|erase|truncate)\b",
    re.IGNORECASE,
)


def _is_unsafe(text: str) -> str | None:
    """Return a reason string if the input must be rejected, else ``None``."""
    if _SQL_RE.search(text):
        return "sql"
    if _INJECTION_RE.search(text):
        return "prompt_injection"
    if _MUTATION_RE.search(text):
        return "mutation"
    return None


def _clean(s: str) -> str:
    """Trim trailing punctuation / filler verbs from an extracted entity."""
    s = s.strip().strip("?.!;,").strip()
    return re.sub(r"\s+(raised|doing|please)\s*$", "", s, flags=re.IGNORECASE).strip()


def _extract_supplier(text: str) -> str | None:
    m = re.search(r"supplier\s+(.+?)(?:\?|$)", text, re.IGNORECASE)
    if m:
        return _clean(m.group(1))
    return None


def _detect_severity(text: str) -> str | None:
    for sev in _SEVERITIES:
        if re.search(rf"\b{sev}\b", text, re.IGNORECASE):
            return sev
    return None


def _detect_period(text: str) -> str | None:
    """Map a natural-language period to a canonical savings token."""
    rules: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"last\s+(quarter|q)\b", re.I), "last_quarter"),
        (re.compile(r"this\s+quarter|current\s+quarter", re.I), "this_quarter"),
        (re.compile(r"this\s+year|ytd|year\s+to\s+date", re.I), "this_year"),
        (re.compile(r"last\s+year|previous\s+year", re.I), "last_year"),
        (re.compile(r"last\s+month|previous\s+month", re.I), "last_month"),
        (re.compile(r"this\s+month|current\s+month", re.I), "this_month"),
    ]
    for rx, token in rules:
        if rx.search(text):
            return token
    return None


# ---- intent discriminators -------------------------------------------------
_EXPLAIN_RE = re.compile(
    r"\bexplain\b[^\n]*\balert\b|\bwhy\b[^\n]*\balert\b", re.IGNORECASE
)
_ALERT_ID_RE = re.compile(r"\balert\s+#?\d+", re.IGNORECASE)
_ALERT_WORD_RE = re.compile(r"\balerts?\b", re.IGNORECASE)
_SAVINGS_RE = re.compile(r"\bsav(?:e|ed|ing|ings)\b", re.IGNORECASE)
_SUPPLIER_RE = re.compile(r"\bsupplier\b|\breliab\w*", re.IGNORECASE)
_FORECAST_RE = re.compile(r"\bforecast\b", re.IGNORECASE)
_ITEM_RE = re.compile(
    r"\bitem\b|\bstatus\b|\bhow\s+is\b[^\n]*\bdoing\b", re.IGNORECASE
)
_LEAD_KW_RE = re.compile(r"^(?:sku|item|part|part\s+number|product)\s+", re.IGNORECASE)


# ---- entity extractors -----------------------------------------------------
def _extract_alert_id(text: str) -> str | None:
    m = re.search(r"\balert\s+#?(\d+)", text, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"#?(\d+)", text)
    return m.group(1) if m else None


def _extract_supplier_entity(text: str) -> str | None:
    m = re.search(r"supplier\s+(.+?)(?:\?|$)", text, re.IGNORECASE)
    if m:
        return _clean(m.group(1)) or None
    m = re.search(r"reliab\w*\s+is\s+(.+?)\??$", text, re.IGNORECASE)
    if m:
        return _clean(m.group(1)) or None
    return None


def _extract_forecast_target(text: str) -> str | None:
    m = re.search(r"forecast\s+(?:for|of|on)\s+(.+?)\??$", text, re.IGNORECASE)
    if not m:
        return None
    target = _LEAD_KW_RE.sub("", _clean(m.group(1))).strip()
    return _clean(target) or None


def _extract_item_target(text: str) -> str | None:
    m = re.search(r"\bitem\s+(.+?)(?:\s+doing|\?|$)", text, re.IGNORECASE)
    if m:
        return _clean(m.group(1)) or None
    m = re.search(r"status\s+(?:of|for)\s+(.+?)\??$", text, re.IGNORECASE)
    if m:
        return _clean(m.group(1)) or None
    m = re.search(r"how\s+is\s+(.+?)\s+doing", text, re.IGNORECASE)
    if m:
        return _clean(m.group(1)) or None
    return None


def _build_list_entity(text: str) -> str | None:
    parts: list[str] = []
    sev = _detect_severity(text)
    if sev:
        parts.append(f"severity={sev}")
    supplier = _extract_supplier_entity(text)
    if supplier:
        parts.append(f"supplier={supplier}")
    return "; ".join(parts) if parts else None


# ---- public matcher --------------------------------------------------------
def match(text: str) -> ParsedQuery:
    """Classify a free-text question into a fixed read-only intent.

    Priority order is chosen so combined questions resolve like the golden
    set (e.g. "high alerts for supplier X" is ``list_alerts``, not
    ``supplier_summary``). Safety rejects win over everything.
    """
    if not text or not text.strip():
        return ParsedQuery(INTENT_UNKNOWN, None, _REASON_NO_MATCH)
    if _is_unsafe(text) is not None:
        return ParsedQuery(INTENT_UNKNOWN, None, _REASON_SAFETY)
    # 1. explain_alert: explicit "explain/why ... alert" or a numbered alert id.
    if _EXPLAIN_RE.search(text) or _ALERT_ID_RE.search(text):
        return ParsedQuery(INTENT_EXPLAIN_ALERT, _extract_alert_id(text))
    # 2. savings_report: "saved / savings" + period.
    if _SAVINGS_RE.search(text):
        return ParsedQuery(INTENT_SAVINGS_REPORT, _detect_period(text))
    # 3. list_alerts: any alert list request (severity / supplier filters).
    if _ALERT_WORD_RE.search(text):
        return ParsedQuery(INTENT_LIST_ALERTS, _build_list_entity(text))
    # 4. supplier_summary.
    if _SUPPLIER_RE.search(text):
        return ParsedQuery(INTENT_SUPPLIER_SUMMARY, _extract_supplier_entity(text))
    # 5. forecast.
    if _FORECAST_RE.search(text):
        return ParsedQuery(INTENT_FORECAST, _extract_forecast_target(text))
    # 6. item_status.
    if _ITEM_RE.search(text):
        return ParsedQuery(INTENT_ITEM_STATUS, _extract_item_target(text))
    return ParsedQuery(INTENT_UNKNOWN, None, _REASON_NO_MATCH)

