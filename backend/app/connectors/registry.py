"""Connector factory/registry (P4-04/P4-06).

Only connectors with a verified write path are registered as write-capable.
Everything else is read-only regardless of the ``write_enabled`` flag.
"""

from __future__ import annotations

from app.connectors.base import Connector, ConnectorError
from app.connectors.zoho import ZohoConnector
from app.core.crypto import decrypt_config
from app.db.models import Connector as ConnectorRow

WRITE_CAPABLE_TYPES = frozenset({"zoho"})
CONNECTOR_TYPES = ("csv", "sql", "tally", "sap_b1", "zoho")


def is_write_capable(connector_type: str) -> bool:
    """True when this connector type can write approved actions back."""
    return connector_type in WRITE_CAPABLE_TYPES


def build_connector(row: ConnectorRow) -> Connector:
    """Build a live connector from a stored row (config decrypted in memory)."""
    if row.type == "zoho":
        return ZohoConnector(decrypt_config(row.config_encrypted))
    raise ConnectorError(f"connector type {row.type} is read-only in this release")
