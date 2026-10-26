"""Tests for sql_generic connector (P4-01)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.connectors.sql_generic import (
    BLOCKED_KEYWORDS,
    MAX_DEFAULT_ROWS,
    ConnectorError,
    QueryResult,
    execute_readonly,
    validate_readonly_select,
)


class TestValidateReadonlySelect:
    def test_valid_select(self) -> None:
        result = validate_readonly_select("SELECT id, name FROM items")
        assert result == "SELECT id, name FROM items"

    def test_valid_select_with_where(self) -> None:
        result = validate_readonly_select("SELECT * FROM suppliers WHERE active = 1")
        assert result.startswith("SELECT")

    def test_empty_query(self) -> None:
        with pytest.raises(ConnectorError, match="empty query"):
            validate_readonly_select("")

    def test_only_whitespace(self) -> None:
        with pytest.raises(ConnectorError, match="empty query"):
            validate_readonly_select("   ")

    def test_trailing_semicolon_stripped(self) -> None:
        result = validate_readonly_select("SELECT 1;")
        assert result == "SELECT 1"

    def test_multiple_statements_rejected(self) -> None:
        with pytest.raises(ConnectorError, match="multiple statements"):
            validate_readonly_select("SELECT 1; SELECT 2")

    def test_non_select_rejected(self) -> None:
        for bad in [
            "INSERT INTO t (x) VALUES (1)",
            "UPDATE t SET x = 1",
            "DELETE FROM t",
            "DROP TABLE t",
            "CREATE TABLE t (x INT)",
            "ALTER TABLE t ADD COLUMN y INT",
            "TRUNCATE t",
        ]:
            with pytest.raises(ConnectorError, match="only a single SELECT"):
                validate_readonly_select(bad)

    def test_blocked_keywords_in_select(self) -> None:
        for kw in BLOCKED_KEYWORDS:
            sql = f"SELECT * FROM t WHERE {kw.lower()} = 1"
            with pytest.raises(ConnectorError, match=f"blocked keyword: {kw}"):
                validate_readonly_select(sql)

    def test_blocked_tokens(self) -> None:
        for tok in (
            "--",
            "/*",
            "xp_",
            "INTO OUTFILE",
            "LOAD_FILE",
            "GRANT",
            "COMMIT",
            "ROLLBACK",
            "BEGIN",
            "DECLARE",
        ):
            sql = f"SELECT 1 {tok}"
            with pytest.raises(ConnectorError, match=f"blocked token: {tok}"):
                validate_readonly_select(sql)

    def test_select_into_rejected(self) -> None:
        with pytest.raises(ConnectorError, match="blocked token"):
            validate_readonly_select("SELECT * INTO OUTFILE 'file.txt' FROM t")

    def test_comment_rejected(self) -> None:
        with pytest.raises(ConnectorError, match="blocked token"):
            validate_readonly_select("SELECT 1 -- comment")


class TestExecuteReadonly:
    def test_successful_query(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE items (id INTEGER, name TEXT)"))
            conn.execute(text("INSERT INTO items VALUES (1, 'widget')"))
            conn.execute(text("INSERT INTO items VALUES (2, 'gadget')"))
            conn.commit()

        result = execute_readonly(engine, "SELECT id, name FROM items")
        assert result.row_count == 2
        assert result.columns == ["id", "name"]
        assert result.rows == [
            {"id": 1, "name": "widget"},
            {"id": 2, "name": "gadget"},
        ]
        assert result.truncated is False

    def test_row_cap(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE items (id INTEGER, name TEXT)"))
            for i in range(5):
                conn.execute(text(f"INSERT INTO items VALUES ({i}, 'item{i}')"))
            conn.commit()

        result = execute_readonly(engine, "SELECT * FROM items", max_rows=3)
        assert result.row_count == 3
        assert result.truncated is True

    def test_empty_result(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE items (id INTEGER, name TEXT)"))
            conn.commit()

        result = execute_readonly(engine, "SELECT * FROM items")
        assert result.row_count == 0
        assert result.rows == []
        assert result.truncated is False

    def test_execution_error(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        with pytest.raises(ConnectorError, match="query execution failed"):
            execute_readonly(engine, "SELECT * FROM nonexistent_table")

    def test_default_max_rows(self) -> None:
        assert MAX_DEFAULT_ROWS == 10_000

    def test_returns_query_result_dataclass(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE t (x INTEGER)"))
            conn.execute(text("INSERT INTO t VALUES (42)"))
            conn.commit()

        result = execute_readonly(engine, "SELECT x FROM t")
        assert isinstance(result, QueryResult)
        assert result.rows == [{"x": 42}]
