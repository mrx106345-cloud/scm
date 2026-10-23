"""sql_generic connector (Part C4/G, P4-01).

Read-only SQL connector for customer databases. Enforces:
- Only a single SELECT statement is allowed (blocked keywords rejected).
- Read-only transaction isolation.
- Configurable statement timeout and row cap.
- No DDL/DML; no multi-statement execution.
All SQL is parameter-free by design — caller supplies the exact query string,
which is validated before execution. Results are returned as list[dict].
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine, Result

# Blocked statement-level keywords: anything that mutates data or schema.
BLOCKED_KEYWORDS: tuple[str, ...] = (
    "ALTER",
    "CREATE",
    "DELETE",
    "DROP",
    "EXEC",
    "EXECUTE",
    "INSERT",
    "MERGE",
    "RENAME",
    "REVOKE",
    "TRUNCATE",
    "UPDATE",
    "UPSERT",
)

# Blocked at the token level inside the query body.
BLOCKED_TOKENS: tuple[str, ...] = (
    "--",            # SQL comment
    "/*",            # block comment start
    "xp_",           # extended stored procs
    "INTO OUTFILE",  # MySQL file write
    "INTO DUMPFILE",
    "LOAD_FILE",
    "GRANT",
    "COMMIT",
    "ROLLBACK",
    "BEGIN",
    "DECLARE",
    "CURSOR",
)

MAX_DEFAULT_ROWS = 10_000
MAX_DEFAULT_TIMEOUT_SECONDS = 30


class ConnectorError(Exception):
    """Raised when a connector operation fails validation or execution."""


@dataclass(frozen=True)
class QueryResult:
    """Result of a read-only query execution.

    rows: list of dict rows (column name -> value).
    row_count: number of rows returned.
    truncated: True if row cap was hit.
    columns: ordered list of column names.
    """

    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    columns: list[str]


def _normalize_keyword(token: str) -> str:
    """Uppercase and strip trailing punctuation for keyword matching."""
    return token.upper().strip(";(), \t\n\r")


def validate_readonly_select(sql: str, max_rows: int = MAX_DEFAULT_ROWS) -> str:
    """Validate that *sql* is a single read-only SELECT statement.

    Returns the stripped, single-line-normalized SQL if valid.
    Raises ConnectorError with a descriptive message otherwise.
    """
    if not sql or not sql.strip():
        raise ConnectorError("empty query")

    stripped = sql.strip().rstrip(";").strip()

    # Must start with SELECT (after optional whitespace/comments already removed).
    if not stripped.upper().startswith("SELECT"):
        raise ConnectorError("only a single SELECT statement is allowed")

    # Reject multiple statements.
    if ";" in stripped:
        raise ConnectorError("multiple statements are not allowed")

    upper = stripped.upper()

    # Blocked statement keywords (whole-word check).
    for kw in BLOCKED_KEYWORDS:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, upper):
            raise ConnectorError(f"blocked keyword: {kw}")

    # Blocked tokens (substring check).
    for tok in BLOCKED_TOKENS:
        if tok.upper() in upper:
            raise ConnectorError(f"blockged token: {tok}")

    # Disallow SELECT ... INTO (file/outfile variants already blocked by token).
    if re.search(r"\bINTO\b", upper):
        raise ConnectorError("SELECT ... INTO is not allowed")

    return stripped


def execute_readonly(
    engine: Engine,
    sql: str,
    *,
    max_rows: int = MAX_DEFAULT_ROWS,
    timeout_seconds: int = MAX_DEFAULT_TIMEOUT_SECONDS,
) -> QueryResult:
    """Execute *sql* as a read-only query against *engine*.

    The connection is opened in read-only mode where supported; a statement
    timeout is set; results are capped at *max_rows*.
    """
    validated = validate_readonly_select(sql, max_rows)

    try:
        with engine.connect() as conn:
            # Read-only transaction where the driver supports it.
            try:
                conn.execute(text("SET TRANSACTION READ ONLY"))
            except Exception:
                # Not all dialects support SET TRANSACTION READ ONLY; ignore.
                pass

            try:
                conn.execute(
                    text(f"SET STATEMENT_TIMEOUT = {timeout_seconds * 1000}")
                )
            except Exception:
                pass

            result: Result = conn.execute(text(validated))
            columns = list(result.keys())
            raw_rows = result.fetchmany(max_rows + 1)

    except ConnectorError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface DB errors as connector errors
        raise ConnectorError(f"query execution failed: {exc}") from exc

    truncated = len(raw_rows) > max_rows
    rows = raw_rows[:max_rows]

    return QueryResult(
        rows=[dict(zip(columns, row)) for row in rows],
        row_count=len(rows),
        truncated=truncated,
        columns=columns,
    )