"""P1-05 tests: mapping, idempotent upsert, import report, injection guard."""

from __future__ import annotations

from pathlib import Path

from app.connectors.csv_excel import import_csv, sanitize_export_cell

MAP = {"sku": "ItemCode", "name": "ItemName"}


def _write(path: Path, rows: list[str]) -> Path:
    path.write_text("ItemCode,ItemName\n" + "\n".join(rows) + "\n")
    return path


def test_import_accepts_and_reports(tmp_path: object) -> None:
    p = _write(Path(str(tmp_path)) / "a.csv", ["A1,Bolt", ",NoSku", "A1,Bolt"])
    r = import_csv("items", p, MAP)
    assert len(r["accepted"]) == 1
    assert len(r["rejected"]) == 2
    reasons = " ".join(x["reason"] for x in r["rejected"])
    assert "missing" in reasons and "duplicate_keys" in reasons


def test_reimport_no_duplicates(tmp_path: object) -> None:
    p = _write(Path(str(tmp_path)) / "a.csv", ["A1,Bolt", "A2,Nut"])
    r1 = import_csv("items", p, MAP)
    r2 = import_csv("items", p, MAP)
    assert r1["file_hash"] == r2["file_hash"]
    assert r1["keys"] == r2["keys"] == 2


def test_export_formula_guard() -> None:
    assert sanitize_export_cell("=cmd(1)").startswith("'")
    assert sanitize_export_cell("ok") == "ok"
