"""Optional Zoho Inventory connector (Part G2.5, P4-07).

**Disabled by default.** Enabling it is an explicit owner decision because it
is the only connector that leaves the machine. When enabled, requests go only
to the configured API host (which must match ``SCM_ZOHO_API_BASE`` and be
HTTPS); credentials are read from the encrypted connector config and never
logged.

The write path creates one purchase order for an approved ``create_draft_po``
recommendation. Failures never mutate the recommendation: the action agent
records the failure and leaves the human in control.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.connectors.base import (
    ConnectorError,
    ConnectorRunResult,
    ConnectorTestResult,
    WriteResult,
)

OUTBOUND_WARNING = (
    "The Zoho connector sends data to Zoho over the network. Enable it only if "
    "the customer has approved outbound access to the Zoho API host."
)

_TIMEOUT = 15.0


class ZohoConnector:
    """Read purchase orders and create approved POs in Zoho Inventory."""

    type = "zoho"

    def __init__(
        self,
        config: dict[str, Any],
        *,
        enabled: bool | None = None,
        api_base: str | None = None,
    ) -> None:
        self.config = config
        self.enabled = settings.zoho_enabled if enabled is None else enabled
        self.api_base = (api_base or str(config.get("api_base") or settings.zoho_api_base)).rstrip(
            "/"
        )

    # ---- guards -----------------------------------------------------------
    def _require_enabled(self) -> None:
        if not self.enabled:
            raise ConnectorError("zoho connector is disabled (SCM_ZOHO_ENABLED=false)")

    def _require_allowed_host(self) -> None:
        parsed = urlparse(self.api_base)
        allowed = urlparse(settings.zoho_api_base)
        if parsed.scheme != "https":
            raise ConnectorError("zoho api_base must use https")
        if parsed.hostname != allowed.hostname:
            raise ConnectorError("zoho api_base host is not allowlisted")

    def _headers(self) -> dict[str, str]:
        token = self.config.get("access_token")
        if not token:
            raise ConnectorError("zoho access_token is missing")
        return {"Authorization": f"Zoho-oauthtoken {token}", "Accept": "application/json"}

    def _organization(self) -> str:
        org = self.config.get("organization_id")
        if not org:
            raise ConnectorError("zoho organization_id is missing")
        return str(org)

    # ---- connector protocol ----------------------------------------------
    def test(self) -> ConnectorTestResult:
        """Validate configuration and host policy without sending data."""
        try:
            self._require_enabled()
            self._require_allowed_host()
            self._headers()
            self._organization()
        except ConnectorError as exc:
            return ConnectorTestResult(ok=False, message=str(exc))
        return ConnectorTestResult(
            ok=True,
            message="zoho configuration looks valid",
            details={"api_base": self.api_base, "outbound": True},
        )

    def run(self, session: Any) -> ConnectorRunResult:
        """Fetch purchase orders and report counts (read-only preview)."""
        self._require_enabled()
        self._require_allowed_host()
        url = f"{self.api_base}/inventory/v1/purchaseorders"
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(
                    url,
                    headers=self._headers(),
                    params={"organization_id": self._organization(), "per_page": 200},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ConnectorError(f"zoho read failed: {exc}") from exc
        records = data.get("purchaseorders", []) if isinstance(data, dict) else []
        return ConnectorRunResult(
            status="ok",
            imported=0,
            warnings=(
                "zoho read returns a preview; canonical import needs a field-mapping review",
            ),
            metrics={"fetched": len(records)},
        )

    def write(self, session: Any, payload: dict[str, Any]) -> WriteResult:
        """Create one purchase order from an approved recommendation payload."""
        self._require_enabled()
        self._require_allowed_host()
        supplier = payload.get("supplier_name") or payload.get("supplier_code")
        item = payload.get("sku") or payload.get("item_code")
        quantity = payload.get("qty") or payload.get("quantity")
        if not supplier or not item or quantity in (None, ""):
            raise ConnectorError("payload needs supplier, item and quantity")

        body = {
            "supplier_name": str(supplier),
            "line_items": [
                {
                    "name": str(item),
                    "quantity": float(quantity),
                    "rate": float(payload.get("unit_cost") or 0),
                }
            ],
            "notes": "Created by SCM Agent from an approved recommendation",
        }
        url = f"{self.api_base}/inventory/v1/purchaseorders"
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(
                    url,
                    headers={**self._headers(), "Content-Type": "application/json"},
                    params={"organization_id": self._organization()},
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ConnectorError(f"zoho write failed: {exc}") from exc

        po = data.get("purchaseorder", {}) if isinstance(data, dict) else {}
        reference = str(po.get("purchaseorder_number") or po.get("purchaseorder_id") or "")
        if not reference:
            return WriteResult(ok=False, reference="", message="zoho returned no PO reference")
        return WriteResult(ok=True, reference=reference, message="purchase order created in zoho")
