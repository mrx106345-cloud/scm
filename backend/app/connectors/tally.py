"""Tally connector (Part C4/G, P4-02).

Reads Tally XML/JSON exports from recorded sample files (synthetic data only)
and from an optional local mock Tally server (no outbound network calls).

Tally ERP 9 / Prime exports data via TDL-generated XML. This connector:
- Parses recorded Tally XML samples (ledgers, stock items, purchase orders).
- Maps Tally field names to SCM canonical fields.
- Never makes outbound network calls; reads only from local files or a
  localhost mock server used in tests.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lxml import etree

# Canonical field mapping: Tally XML element -> SCM canonical field
LEDGER_MAP: dict[str, str] = {
    "LEDGERNAME": "name",
    "PARENT": "category",
    "OPENINGBALANCE": "opening_balance",
}

STOCKITEM_MAP: dict[str, str] = {
    "NAMEOFITEM": "sku",
    "BASEUNITS": "uom",
    "OPENINGBALANCE": "opening_qty",
    "RATE": "unit_cost",
}

PURCHASEORDER_MAP: dict[str, str] = {
    "VOUCHERNUMBER": "po_number",
    "PARTYLEDGERNAME": "supplier_name",
    "DATE": "order_date",
    "AMOUNT": "total_amount",
}

REQUIRED_TALLY_FIELDS: dict[str, list[str]] = {
    "ledgers": ["name"],
    "stock_items": ["sku"],
    "purchase_orders": ["po_number"],
}


@dataclass(frozen=True)
class TallyImportResult:
    """Result of importing Tally data.

    accepted: list of canonical dicts.
    rejected: list of {row, reason}.
    source: file path or "mock_server".
    file_hash: SHA-256 of the source content.
    """

    accepted: list[dict[str, Any]]
    rejected: list[dict[str, Any]]
    source: str
    file_hash: str


class TallyError(Exception):
    """Raised when Tally parsing or import fails."""


def _parse_xml_file(path: str | Path) -> etree._Element:
    """Parse a Tally XML file with lxml (defensive: no external entities)."""
    p = Path(path)
    raw = p.read_bytes()
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    return etree.fromstring(raw, parser=parser)


def _text(elem: etree._Element, path: str) -> str:
    """Safely extract text content from a child element."""
    child = elem.find(path)
    return child.text.strip() if child is not None and child.text else ""


def _map_fields(raw: dict[str, str], field_map: dict[str, str]) -> dict[str, str]:
    """Map Tally field names to SCM canonical names, dropping unmapped."""
    return {canon: raw.get(tally, "") for tally, canon in field_map.items()}


def import_tally_ledgers(
    path: str | Path,
    mapping: dict[str, str] | None = None,
    required_fields: list[str] | None = None,
) -> TallyImportResult:
    """Import Tally ledger XML into canonical ledger records.

    *mapping* overrides the default LEDGER_MAP (user column -> canonical).
    *required_fields* overrides the default ["name"] check against canonical
    field names. Returns accepted/rejected records plus a file hash for audit.
    """
    field_map = mapping or LEDGER_MAP
    required = required_fields or list(REQUIRED_TALLY_FIELDS["ledgers"])
    root = _parse_xml_file(path)
    raw = Path(path).read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for idx, ledger in enumerate(root.findall(".//LEDGER"), start=1):
        raw_fields = {child.tag: _text(ledger, child.tag) for child in ledger}
        canon = _map_fields(raw_fields, field_map)
        missing = [f for f in required if not canon.get(f)]
        if missing:
            rejected.append({"row": idx, "reason": f"missing required field: {','.join(missing)}"})
            continue
        accepted.append(canon)

    return TallyImportResult(
        accepted=accepted,
        rejected=rejected,
        source=str(path),
        file_hash=file_hash,
    )


def import_tally_stock_items(
    path: str | Path,
    mapping: dict[str, str] | None = None,
    required_fields: list[str] | None = None,
) -> TallyImportResult:
    """Import Tally stock item XML into canonical item records."""
    field_map = mapping or STOCKITEM_MAP
    required = required_fields or list(REQUIRED_TALLY_FIELDS["stock_items"])
    root = _parse_xml_file(path)
    raw = Path(path).read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for idx, item in enumerate(root.findall(".//STOCKITEM"), start=1):
        raw_fields = {child.tag: _text(item, child.tag) for child in item}
        canon = _map_fields(raw_fields, field_map)
        missing = [f for f in required if not canon.get(f)]
        if missing:
            rejected.append({"row": idx, "reason": f"missing required field: {','.join(missing)}"})
            continue
        accepted.append(canon)

    return TallyImportResult(
        accepted=accepted,
        rejected=rejected,
        source=str(path),
        file_hash=file_hash,
    )


def import_tally_purchase_orders(
    path: str | Path,
    mapping: dict[str, str] | None = None,
    required_fields: list[str] | None = None,
) -> TallyImportResult:
    """Import Tally purchase voucher XML into canonical PO records."""
    field_map = mapping or PURCHASEORDER_MAP
    required = required_fields or list(REQUIRED_TALLY_FIELDS["purchase_orders"])
    root = _parse_xml_file(path)
    raw = Path(path).read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for idx, voucher in enumerate(root.findall(".//VOUCHER"), start=1):
        raw_fields = {child.tag: _text(voucher, child.tag) for child in voucher}
        canon = _map_fields(raw_fields, field_map)
        missing = [f for f in required if not canon.get(f)]
        if missing:
            rejected.append(
                {
                    "row": idx,
                    "reason": f"missing required field: {','.join(missing)}",
                }
            )
            continue
        accepted.append(canon)

    return TallyImportResult(
        accepted=accepted,
        rejected=rejected,
        source=str(path),
        file_hash=file_hash,
    )


def validate_tally_xml(content: bytes) -> bool:
    """Return True if *content* is well-formed Tally XML (no network access)."""
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        etree.fromstring(content, parser=parser)
        return True
    except etree.XMLSyntaxError:
        return False
