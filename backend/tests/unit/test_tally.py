"""Tests for Tally connector (P4-02)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from lxml import etree

from app.connectors.tally import (
    LEDGER_MAP,
    TallyError,
    import_tally_ledgers,
    import_tally_purchase_orders,
    import_tally_stock_items,
    validate_tally_xml,
)

LEDGER_XML = """<ENVELOPE>
<HEADER><VERSION>1</VERSION><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL>
<TDLMESSAGE>
<LEDGER>
<LEDGERNAME>Supplier A</LEDGERNAME>
<PARENT>Sundry Creditors</PARENT>
<OPENINGBALANCE>50000</OPENINGBALANCE>
</LEDGER>
<LEDGER>
<LEDGERNAME>Supplier B</LEDGERNAME>
<PARENT>Sundry Creditors</PARENT>
<OPENINGBALANCE>30000</OPENINGBALANCE>
</LEDGER>
<LEDGER>
<PARENT>Sundry Creditors</PARENT>
<OPENINGBALANCE>10000</OPENINGBALANCE>
</LEDGER>
</TDLMESSAGE>
</TDL>
</DESC>
</BODY>
</ENVELOPE>"""

STOCKITEM_XML = """<ENVELOPE>
<HEADER><VERSION>1</VERSION></HEADER>
<BODY>
<DESC>
<TDL>
<TDLMESSAGE>
<STOCKITEM>
<NAMEOFITEM>ITEM-001</NAMEOFITEM>
<BASEUNITS>Nos</BASEUNITS>
<OPENINGBALANCE>100</OPENINGBALANCE>
<RATE>250.00</RATE>
</STOCKITEM>
<STOCKITEM>
<NAMEOFITEM>ITEM-002</NAMEOFITEM>
<BASEUNITS>Nos</BASEUNITS>
<OPENINGBALANCE>50</OPENINGBALANCE>
<RATE>120.00</RATE>
</STOCKITEM>
<STOCKITEM>
<BASEUNITS>Nos</BASEUNITS>
<OPENINGBALANCE>10</OPENINGBALANCE>
</STOCKITEM>
</TDLMESSAGE>
</TDL>
</DESC>
</BODY>
</ENVELOPE>"""

PURCHASEORDER_XML = """<ENVELOPE>
<HEADER><VERSION>1</VERSION></HEADER>
<BODY>
<DESC>
<TDL>
<TDLMESSAGE>
<VOUCHER>
<VOUCHERNUMBER>PO-2026-001</VOUCHERNUMBER>
<PARTYLEDGERNAME>Supplier A</PARTYLEDGERNAME>
<DATE>2026-10-01</DATE>
<AMOUNT>50000.00</AMOUNT>
</VOUCHER>
<VOUCHER>
<VOUCHERNUMBER>PO-2026-002</VOUCHERNUMBER>
<PARTYLEDGERNAME>Supplier B</PARTYLEDGERNAME>
<DATE>2026-10-05</DATE>
<AMOUNT>30000.00</AMOUNT>
</VOUCHER>
<VOUCHER>
<PARTYLEDGERNAME>Supplier C</PARTYLEDGERNAME>
<DATE>2026-10-10</DATE>
<AMOUNT>10000.00</AMOUNT>
</VOUCHER>
</TDLMESSAGE>
</TDL>
</DESC>
</BODY>
</ENVELOPE>"""

MALFORMED_XML = "<ENVELOPE><BODY><DESC>unclosed</DESC>"


def _write_tmp(content: str) -> Path:
    tmp = Path(tempfile.mkdtemp()) / "tally.xml"
    tmp.write_text(content, encoding="utf-8")
    return tmp


class TestValidateTallyXml:
    def test_valid_xml(self) -> None:
        assert validate_tally_xml(LEDGER_XML.encode("utf-8")) is True

    def test_malformed_xml(self) -> None:
        assert validate_tally_xml(MALFORMED_XML.encode("utf-8")) is False

    def test_empty_content(self) -> None:
        assert validate_tally_xml(b"") is False


class TestImportTallyLedgers:
    def test_import_all_valid(self) -> None:
        path = _write_tmp(LEDGER_XML)
        result = import_tally_ledgers(path)

        assert result.source == str(path)
        assert len(result.accepted) == 2
        assert len(result.rejected) == 1
        assert result.rejected[0]["reason"] == "missing required field: name"
        assert result.accepted[0]["name"] == "Supplier A"
        assert result.accepted[0]["category"] == "Sundry Creditors"
        assert result.accepted[0]["opening_balance"] == "50000"
        assert len(result.file_hash) == 64  # SHA-256 hex

    def test_custom_mapping(self) -> None:
        path = _write_tmp(LEDGER_XML)
        result = import_tally_ledgers(
            path,
            mapping={"LEDGERNAME": "supplier_name"},
            required_fields=["supplier_name"],
        )
        assert result.accepted[0]["supplier_name"] == "Supplier A"
        assert "name" not in result.accepted[0]


class TestImportTallyStockItems:
    def test_import_all_valid(self) -> None:
        path = _write_tmp(STOCKITEM_XML)
        result = import_tally_stock_items(path)

        assert len(result.accepted) == 2
        assert len(result.rejected) == 1
        assert result.rejected[0]["reason"] == "missing required field: sku"
        assert result.accepted[0]["sku"] == "ITEM-001"
        assert result.accepted[0]["uom"] == "Nos"
        assert result.accepted[0]["opening_qty"] == "100"
        assert result.accepted[0]["unit_cost"] == "250.00"


class TestImportTallyPurchaseOrders:
    def test_import_all_valid(self) -> None:
        path = _write_tmp(PURCHASEORDER_XML)
        result = import_tally_purchase_orders(path)

        assert len(result.accepted) == 2
        assert len(result.rejected) == 1
        assert result.rejected[0]["reason"] == "missing required field: po_number"
        assert result.accepted[0]["po_number"] == "PO-2026-001"
        assert result.accepted[0]["supplier_name"] == "Supplier A"
        assert result.accepted[0]["order_date"] == "2026-10-01"
        assert result.accepted[0]["total_amount"] == "50000.00"