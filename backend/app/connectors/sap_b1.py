"""SAP Business One read connector (Part C4/G, P4-03).

Reads from a local SAP B1 Service Layer (OData) endpoint using httpx.
Designed for a localhost mock Service Layer in tests and customer installs;
never makes outbound network calls beyond the configured base URL.

Endpoints consumed (read-only):
- Items: /Items
- Business Partners (suppliers): /BusinessPartners
- Purchase Orders: /PurchaseOrders

All responses are mapped to SCM canonical fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

# Canonical field mapping: SAP B1 OData property -> SCM canonical field
ITEM_MAP: dict[str, str] = {
    "ItemCode": "sku",
    "ItemName": "name",
    "InventoryItem": "is_inventory_item",
    "SellUnit": "uom",
}

BP_MAP: dict[str, str] = {
    "CardCode": "code",
    "CardName": "name",
    "CardType": "card_type",
    "Balance": "balance",
}

PO_MAP: dict[str, str] = {
    "DocNum": "po_number",
    "CardCode": "supplier_code",
    "DocDate": "order_date",
    "DocTotal": "total_amount",
    "DocStatus": "status",
}

REQUIRED_SAP_FIELDS: dict[str, list[str]] = {
    "items": ["sku"],
    "business_partners": ["code"],
    "purchase_orders": ["po_number"],
}

MAX_PAGE_SIZE = 1000
REQUEST_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class SapImportResult:
    """Result of importing SAP B1 data.

    accepted: list of canonical dicts.
    rejected: list of {row, reason}.
    endpoint: the OData endpoint queried.
    """

    accepted: list[dict[str, Any]]
    rejected: list[dict[str, Any]]
    endpoint: str


class SapError(Exception):
    """Raised when SAP B1 connector operations fail."""


def _map_fields(raw: dict[str, Any], field_map: dict[str, str]) -> dict[str, str]:
    """Map SAP OData property names to SCM canonical names."""
    return {canon: str(raw.get(tally, "")) for tally, canon in field_map.items()}


def _fetch_page(client: httpx.Client, endpoint: str, skip: int = 0) -> dict[str, Any]:
    """Fetch a single page of OData results from the SAP Service Layer."""
    url = f"{endpoint}?$skip={skip}&$top={MAX_PAGE_SIZE}"
    try:
        resp = client.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except httpx.RequestError as exc:
        raise SapError(f"SAP Service Layer request failed: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise SapError(f"SAP Service Layer returned {exc.response.status_code}") from exc
    data: dict[str, Any] = resp.json()
    return data


def import_items(client: httpx.Client, base_url: str) -> SapImportResult:
    """Import SAP B1 Items into canonical item records."""
    return _import_generic(client, f"{base_url.rstrip('/')}/Items", ITEM_MAP, "items", ["sku"])


def import_business_partners(client: httpx.Client, base_url: str) -> SapImportResult:
    """Import SAP B1 Business Partners (suppliers) into canonical records."""
    return _import_generic(
        client,
        f"{base_url.rstrip('/')}/BusinessPartners",
        BP_MAP,
        "business_partners",
        ["code"],
    )


def import_purchase_orders(client: httpx.Client, base_url: str) -> SapImportResult:
    """Import SAP B1 Purchase Orders into canonical PO records."""
    return _import_generic(
        client,
        f"{base_url.rstrip('/')}/PurchaseOrders",
        PO_MAP,
        "purchase_orders",
        ["po_number"],
    )


def _import_generic(
    client: httpx.Client,
    endpoint: str,
    field_map: dict[str, str],
    entity: str,
    required_fields: list[str],
) -> SapImportResult:
    """Paginate through an OData endpoint and map to canonical fields."""
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    skip = 0

    while True:
        page = _fetch_page(client, endpoint, skip)
        records = page.get("value", [])
        if not records:
            break

        for idx, raw in enumerate(records, start=1):
            canon = _map_fields(raw, field_map)
            missing = [f for f in required_fields if not canon.get(f)]
            if missing:
                rejected.append(
                    {
                        "row": skip + idx,
                        "reason": f"missing required field: {','.join(missing)}",
                    }
                )
                continue
            accepted.append(canon)

        skip += len(records)
        # OData v4: nextLink present when more pages exist.
        if not page.get("odata.nextLink"):
            break

    return SapImportResult(accepted=accepted, rejected=rejected, endpoint=endpoint)
