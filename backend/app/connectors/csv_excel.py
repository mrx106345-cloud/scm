"""CSV/Excel connector (Part C4/G, P1-05).

Column mapping user->canonical; idempotent upserts by natural key;
reject rows with missing required fields into an import report.
Cells treated as data: strip control chars, cap 32000 chars.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

REQUIRED: dict[str, list[str]] = {
    "items": ["sku", "name"],
    "suppliers": ["code", "name", "contract_lead_time_days"],
    "stock": ["sku", "site_code", "snapshot_date", "on_hand", "allocated"],
    "consumption": ["sku", "site_code", "date", "qty", "source"],
    "purchase_orders": [
        "po_number",
        "supplier_code",
        "site_code",
        "order_date",
        "promised_date",
        "status",
    ],
}

NATURAL_KEY: dict[str, list[str]] = {
    "items": ["sku"],
    "suppliers": ["code"],
    "stock": ["sku", "site_code", "snapshot_date"],
    "consumption": ["sku", "site_code", "date", "source"],
    "purchase_orders": ["po_number"],
}


def clean_cell(value: object) -> str:
    """Strip control chars and cap cell length (security-guardrails)."""
    s = "" if value is None else str(value)
    s = "".join(ch for ch in s if ord(ch) >= 32 or ch in ("\n", "\t"))
    return s[:32000]


def sanitize_export_cell(value: str) -> str:
    """Prefix formula-trigger cells with ' on export (CSV injection guard)."""
    if value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def import_csv(entity: str, path: str | Path, mapping: dict[str, str]) -> dict[str, object]:
    """Import a CSV with user-column -> canonical mapping.

    Returns {accepted, rejected:[{row, reason}], file_hash, natural_keys}.
    Idempotent: callers upsert by natural key; re-import yields same keys.
    """
    if entity not in REQUIRED:
        raise ValueError(f"unknown entity {entity}")
    p = Path(path)
    raw = p.read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()
    accepted: list[dict[str, str]] = []
    rejected: list[dict[str, str | int]] = []
    seen: set[tuple[str, ...]] = set()
    with open(p, newline="", encoding="utf-8-sig") as f:
        for lineno, row in enumerate(csv.DictReader(f), start=2):
            canon = {cf: clean_cell(row.get(uc, "")) for cf, uc in mapping.items()}
            missing = [c for c in REQUIRED[entity] if not canon.get(c)]
            if missing:
                rejected.append({"row": lineno, "reason": f"missing: {','.join(missing)}"})
                continue
            key = tuple(canon.get(k, "") for k in NATURAL_KEY[entity])
            if key in seen:
                rejected.append({"row": lineno, "reason": "duplicate_keys"})
                continue
            seen.add(key)
            accepted.append(canon)
    return {"accepted": accepted, "rejected": rejected, "file_hash": file_hash, "keys": len(seen)}
