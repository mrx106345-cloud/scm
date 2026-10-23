"""Tests for SAP B1 connector (P4-03)."""

from __future__ import annotations

import httpx
import pytest

from app.connectors.sap_b1 import (
    ITEM_MAP,
    SapError,
    import_business_partners,
    import_items,
    import_purchase_orders,
)

ITEMS_PAGE = {
    "value": [
        {
            "ItemCode": "ITEM-001",
            "ItemName": "Widget",
            "InventoryItem": "tYES",
            "SellUnit": "NOS",
        },
        {
            "ItemCode": "ITEM-002",
            "ItemName": "Gadget",
            "InventoryItem": "tYES",
            "SellUnit": "NOS",
        },
        {"ItemName": "NoCode", "InventoryItem": "tYES", "SellUnit": "NOS"},
    ],
    "odata.nextLink": None,
}

BP_PAGE = {
    "value": [
        {
            "CardCode": "SUP-001",
            "CardName": "Supplier A",
            "CardType": "Supplier",
            "Balance": "50000.00",
        },
        {
            "CardCode": "SUP-002",
            "CardName": "Supplier B",
            "CardType": "Supplier",
            "Balance": "30000.00",
        },
        {"CardName": "NoCode", "CardType": "Supplier", "Balance": "10000.00"},
    ],
    "odata.nextLink": None,
}

PO_PAGE = {
    "value": [
        {
            "DocNum": "1001",
            "CardCode": "SUP-001",
            "DocDate": "2026-10-01",
            "DocTotal": "50000.00",
            "DocStatus": "Open",
        },
        {
            "DocNum": "1002",
            "CardCode": "SUP-002",
            "DocDate": "2026-10-05",
            "DocTotal": "30000.00",
            "DocStatus": "Open",
        },
        {
            "CardCode": "SUP-003",
            "DocDate": "2026-10-10",
            "DocTotal": "10000.00",
            "DocStatus": "Open",
        },
    ],
    "odata.nextLink": None,
}

PAGINATED_PAGE_1 = {
    "value": [
        {"ItemCode": "PAGE1-1", "ItemName": "Page1 Item 1", "SellUnit": "NOS"},
        {"ItemCode": "PAGE1-2", "ItemName": "Page1 Item 2", "SellUnit": "NOS"},
    ],
    "odata.nextLink": "Items?$skip=2&$top=1000",
}

PAGINATED_PAGE_2 = {
    "value": [
        {"ItemCode": "PAGE2-1", "ItemName": "Page2 Item 1", "SellUnit": "NOS"},
    ],
    "odata.nextLink": None,
}


def _make_handler(pages: dict[str, dict]) -> httpx.MockTransport:
    """Build a MockTransport that routes /{endpoint} to the given page dict."""

    def handler(request: httpx.Request) -> httpx.Response:
        # Construct key from path + query (matching how pages dict keys are formed)
        url_key = request.url.path
        if request.url.query:
            url_key += "?" + request.url.query.decode()
        page = pages.get(url_key)
        if page is None:
            # Try path only (without query)
            page = pages.get(request.url.path)
        if page is None:
            return httpx.Response(404, json={"error": {"message": "not found"}})
        return httpx.Response(200, json=page)

    return httpx.MockTransport(handler)


class TestImportItems:
    def test_import_all_valid(self) -> None:
        client = httpx.Client(transport=_make_handler({"/Items": ITEMS_PAGE}))
        result = import_items(client, "http://localhost:50000")

        assert result.endpoint == "http://localhost:50000/Items"
        assert len(result.accepted) == 2
        assert len(result.rejected) == 1
        assert result.rejected[0]["reason"] == "missing required field: sku"
        assert result.accepted[0]["sku"] == "ITEM-001"
        assert result.accepted[0]["name"] == "Widget"
        assert result.accepted[0]["uom"] == "NOS"

    def test_custom_field_map(self) -> None:
        client = httpx.Client(transport=_make_handler({"/Items": ITEMS_PAGE}))
        from app.connectors.sap_b1 import _map_fields

        raw = {"ItemCode": "X-1", "ItemName": "Test Item"}
        canon = _map_fields(raw, {"ItemCode": "custom_sku"})
        assert canon == {"custom_sku": "X-1"}


class TestImportBusinessPartners:
    def test_import_all_valid(self) -> None:
        client = httpx.Client(
            transport=_make_handler({"/BusinessPartners": BP_PAGE})
        )
        result = import_business_partners(client, "http://localhost:50000")

        assert len(result.accepted) == 2
        assert len(result.rejected) == 1
        assert result.accepted[0]["code"] == "SUP-001"
        assert result.accepted[0]["name"] == "Supplier A"
        assert result.accepted[0]["card_type"] == "Supplier"


class TestImportPurchaseOrders:
    def test_import_all_valid(self) -> None:
        client = httpx.Client(transport=_make_handler({"/PurchaseOrders": PO_PAGE}))
        result = import_purchase_orders(client, "http://localhost:50000")

        assert len(result.accepted) == 2
        assert len(result.rejected) == 1
        assert result.accepted[0]["po_number"] == "1001"
        assert result.accepted[0]["supplier_code"] == "SUP-001"
        assert result.accepted[0]["order_date"] == "2026-10-01"


class TestPagination:
    def test_paginates_through_pages(self) -> None:
        pages = {
            "/Items?$skip=0&$top=1000": PAGINATED_PAGE_1,
            "/Items?$skip=2&$top=1000": PAGINATED_PAGE_2,
        }
        client = httpx.Client(transport=_make_handler(pages))
        result = import_items(client, "http://localhost:50000")

        assert len(result.accepted) == 3
        assert result.rejected == []


class TestErrorHandling:
    def test_connection_error(self) -> None:
        client = httpx.Client(transport=_make_handler({}))
        with pytest.raises(SapError, match="404"):
            import_items(client, "http://localhost:50000")