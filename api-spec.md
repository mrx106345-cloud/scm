# api-spec.md: API and Tool Interface Specification

Two interfaces are defined here:
1. **Part A: the REST API** that the web UI and admin tools use.
2. **Part B: the internal tool interface** that the product's runtime agents may call (the allowed actions and their limits).

The FastAPI app must generate an OpenAPI 3.1 document (`/api/v1/openapi.json`, admin-only). A contract test compares the generated document with this file's endpoint list and fails on any undocumented endpoint.

---

# PART A: REST API

## A1. Conventions

| Item | Rule |
|---|---|
| Base path | `/api/v1` |
| Format | JSON, UTF-8. Unknown request fields are rejected (HTTP 422) |
| Auth | HTTP-only, Secure, SameSite=Strict session cookie; CSRF token header `X-CSRF-Token` on all non-GET requests |
| Time | ISO 8601 UTC strings (`2026-10-13T06:00:00Z`); dates `YYYY-MM-DD` |
| Money | Decimal **strings** with 2 decimals, e.g. `"240000.00"`; currency code in `meta.currency` (default `INR`) |
| Quantities | JSON numbers (decimal allowed) |
| IDs | UUID strings (alerts and recommendations also have a human number `display_id`) |
| Pagination | `page` (default 1), `page_size` (default 25, max 200). Response: `{items, page, page_size, total}` |
| Sorting | `sort=field` or `sort=-field` |
| Rate limits | Login: 5 failures then 15-minute lockout; chat: 30 requests per minute per user; others 300 per minute per user |
| Idempotency | `POST` endpoints that create actions accept `Idempotency-Key`; repeated key returns the first result |

### Standard error body
```json
{
  "error_code": "FORBIDDEN_ROLE",
  "message": "Your role cannot approve learning proposals.",
  "details": {"required_role": "admin"},
  "request_id": "b5f0..."
}
```
Common codes: `UNAUTHENTICATED` (401), `FORBIDDEN_ROLE` (403), `NOT_FOUND` (404), `VALIDATION_ERROR` (422), `CONFLICT` (409, for example duplicate or invalid state transition), `LICENSE_FEATURE_DISABLED` (402), `PIPELINE_BUSY` (409), `WRITE_DISABLED` (409), `RATE_LIMITED` (429), `INTERNAL_ERROR` (500, no stack trace).

### Roles
`admin`, `planner`, `purchaser`, `viewer`. The full matrix is in `permissions-map.yaml`. Every endpoint below states its minimum role.

---

## A2. Authentication

| Method and path | Role | Request | Response |
|---|---|---|---|
| `POST /auth/login` | public | `{username, password}` | `200 {user:{id,username,full_name,role}, csrf_token}`; sets session cookie. Failures return 401 with a generic message and count toward lockout |
| `POST /auth/logout` | any | none | `204` |
| `GET /auth/me` | any | none | `{user, license:{tier,features,maintenance_expires_at}, csrf_token}` |
| `POST /auth/change-password` | any | `{current_password, new_password}` | `204`; password rules: at least 12 characters, not in a common-password list |

---

## A3. Dashboard

### `GET /dashboard/summary` (viewer)
```json
{
  "as_of": "2026-10-13T06:00:00Z",
  "alerts": {"critical": 3, "high": 9, "medium": 21},
  "expected_loss_at_risk": {"amount": "1250000.00", "label": "estimate"},
  "data_quality": {"score": 86, "critical_issues": 0, "warnings": 4},
  "last_run": {"id": "…", "status": "ok", "finished_at": "…"},
  "next_run_at": "2026-10-14T06:00:00Z",
  "pending_recommendations": 7,
  "top_alerts": [ /* up to 10 AlertSummary */ ],
  "savings_snapshot": {"measured": "…", "estimated": "…", "period": "last_90_days"}
}
```

---

## A4. Alerts

### Schemas
```json
// AlertSummary
{"id":"uuid","display_id":77,"type":"stockout_risk","severity":"critical",
 "item":{"id":"uuid","sku":"HB-M8","name":"Hex Bolt M8"},"site":{"id":"uuid","code":"P1"},
 "supplier":{"id":"uuid","name":"Alpha Steels"} ,
 "p_stockout":0.62,"days_to_stockout":4.0,"expected_loss":"240000.00","score":"342857.14",
 "status":"open","created_at":"…","explanation_source":"ai|template"}
```
`AlertDetail` adds: `facts` (object), `explanation` (`{summary,why,suggested_action,source,validator:{passed,retries}}`), `charts` (`stock_projection`, `forecast`, `supplier_lead_time`), `recommendations[]`, `history[]`.

| Method and path | Role | Notes |
|---|---|---|
| `GET /alerts` | viewer | filters: `severity`, `status`, `type`, `supplier_id`, `site_id`, `item_id`, `q`, plus pagination and sort (default `-score`) |
| `GET /alerts/{id}` | viewer | returns `AlertDetail` |
| `POST /alerts/{id}/acknowledge` | planner | body `{comment?}`; status `acknowledged` |
| `POST /alerts/{id}/resolve` | planner | body `{comment}` required; status `resolved` |
| `POST /alerts/bulk-acknowledge` | planner | body `{ids:[…]}` max 100 |

---

## A5. Recommendations and approvals

### Schema `Recommendation`
```json
{"id":"uuid","display_id":55,"alert_id":"uuid","action_type":"create_draft_po",
 "payload":{"supplier_id":"uuid","item_id":"uuid","qty":850,"unit_price":"250.00","need_by_date":"2026-11-02"},
 "est_cost":"212500.00","est_benefit":"240000.00","benefit_label":"estimate",
 "autonomy_level":2,"status":"pending","created_at":"…"}
```
Action types: `create_draft_po`, `raise_reorder_request`, `draft_supplier_message`.

| Method and path | Role | Notes |
|---|---|---|
| `GET /recommendations` | viewer | filters `status`, `action_type`, `supplier_id` |
| `GET /recommendations/{id}` | viewer | includes evidence and approval history |
| `POST /recommendations/{id}/decision` | planner, purchaser (purchaser limited to `create_draft_po` and `draft_supplier_message`) | body `{decision:"approve|reject|edit_approve", edited_payload?, comment?}`; invalid transitions return 409 `CONFLICT`; response includes the resulting `action` (target `outbox` or `connector`) |
| `GET /outbox` | planner, purchaser | lists generated files (name, type, created_at, recommendation_id) |
| `GET /outbox/{file_id}/download` | planner, purchaser | file download, audited |

Edit rules: only `qty`, `supplier_id`, `need_by_date`, `message_text` may be edited; edited values are validated against item MOQ/lot rules.

---

## A6. Items and suppliers

| Method and path | Role | Returns |
|---|---|---|
| `GET /items` | viewer | list with sku, name, class, days_of_cover, p_stockout, open_alerts |
| `GET /items/{id}` | viewer | parameters (`safety_stock`, `reorder_point`, `order_qty`, `service_level`), forecast series with interval, method and WAPE, recent history, open POs, alert history |
| `GET /suppliers` | viewer | list with risk_score, trend_flag, on_time_rate |
| `GET /suppliers/{id}` | viewer | metric history, lead-time series, receipts, exposed items |

---

## A7. Pipeline and data

| Method and path | Role | Notes |
|---|---|---|
| `POST /pipeline/run` | planner | starts a full run; 409 `PIPELINE_BUSY` if one is active; returns `{run_id}` |
| `GET /pipeline/runs` | viewer | recent runs with status, duration, counts |
| `GET /pipeline/runs/{id}` | viewer | per-agent status, warnings, metrics |
| `POST /imports` | admin | multipart: `file`, `connector_id`, `entity`; returns `{import_id}`; processing is asynchronous |
| `GET /imports/{id}/report` | admin | `{status, rows_total, rows_ok, rows_rejected, rejected:[{row,reason}], file_sha256}` |
| `GET /data-quality/latest` | viewer | score, checks fired with counts, fix list |

Upload limits: 200 MB, allowed types `.csv`, `.xlsx`; content type and magic bytes both verified.

---

## A8. Connectors (admin)

| Method and path | Notes |
|---|---|
| `GET /connectors` | list; secrets are always masked (`"password":"********"`) |
| `POST /connectors` | `{name,type,config,schedule_cron?}`; `config` is encrypted at rest; type in `csv|sql|tally|sap_b1|zoho` |
| `PATCH /connectors/{id}` | update config, schedule, `write_enabled` (requires typed confirmation `{"confirm":"ENABLE WRITE"}` and is audited) |
| `POST /connectors/{id}/test` | `{ok, message, latency_ms}`; no data returned |
| `POST /connectors/{id}/run` | start an ingestion run |
| `DELETE /connectors/{id}` | soft delete; keeps audit history |

`sql` connector config includes `queries` per entity. The server rejects any query that is not a single `SELECT` (see `security-guardrails.md`).

---

## A9. Notes inbox

| Method and path | Role | Notes |
|---|---|---|
| `POST /notes` | planner, purchaser | `{supplier_id?, raw_text}`; max 8,000 characters; stored as untrusted text |
| `GET /notes` | planner, purchaser | list with status |
| `POST /notes/{id}/confirm` | planner | `{supplier_id, new_delay_days, affected_item_ids?}`; applies the human-confirmed values only |
| `POST /notes/{id}/dismiss` | planner, purchaser | |

Extraction output (`extracted`) is a suggestion and never changes calculations before confirmation.

---

## A10. Chat

### `POST /chat` (viewer; subject to role data limits)
Request: `{"message":"How is item HB-M8 doing?"}`
Response:
```json
{"intent":"item_status","entity":"HB-M8",
 "answer":"HB-M8 has 4 days of cover and a 62% chance of a stockout.",
 "answer_source":"ai|template",
 "facts":{"days_of_cover":4,"p_stockout_pct":62},
 "table":{"columns":["Metric","Value"],"rows":[["Days of cover","4"],["Stockout probability","62%"]]},
 "links":[{"type":"item","id":"uuid"}]}
```
Supported intents: `item_status`, `list_alerts`, `supplier_summary`, `forecast`, `explain_alert`, `savings_report`. Unknown intent returns `{"intent":"unknown","supported_examples":[…]}`. Chat never changes data and never executes SQL.

---

## A11. Reports

| Method and path | Role | Notes |
|---|---|---|
| `GET /reports/savings?from=&to=` | viewer | `{measured:{…}, estimated:{…}, one_time:{released_cash}, yearly:{carrying_cost_saving_estimate}, assumptions:{…}, period}`; never returns a combined single total of one-time and yearly figures |
| `GET /reports/savings/export?format=xlsx|pdf` | planner | file download, audited |

---

## A12. Learning

| Method and path | Role | Notes |
|---|---|---|
| `GET /learning/proposals` | admin | list with `before`, `after`, `backtest`, `status` |
| `POST /learning/proposals/{id}/approve` | admin | applies the version; audited |
| `POST /learning/proposals/{id}/rollback` | admin | restores the previous version |

---

## A13. Administration

| Method and path | Notes |
|---|---|
| `GET/POST /admin/users`, `PATCH /admin/users/{id}` | create, change role, deactivate, reset password (cannot delete; cannot remove the last admin) |
| `GET/PATCH /admin/settings` | thresholds, service levels, estimate factors, autonomy settings (`autonomy.<action_type>`) |
| `PATCH /admin/settings/autonomy/{action_type}` | level 3 requires `{limits:{…}, acknowledge:true}` and the 30-day rule; otherwise 409 |
| `GET /admin/audit` | filter by date, actor, event, entity; paginated |
| `GET /admin/audit/verify` | `{ok, checked, first_broken_id?}` |
| `GET /admin/license`, `POST /admin/license` | view status, upload a signed license file |
| `GET /admin/system` | RAM, CPU, disk, model status, versions, queue state |
| `POST /admin/backup`, `GET /admin/backups` | create and list encrypted backups |
| `GET /health` | public: `{"status":"ok"}` only |

---

## A14. Webhooks and external callbacks
None. The product exposes no inbound webhooks and makes no outbound webhook calls in v1.

---

# PART B: INTERNAL TOOL INTERFACE FOR RUNTIME AGENTS

These are the only tools the product's runtime agents (not the coding agent) may call. They are Python interfaces, not network endpoints. Anything not listed is not allowed.

| Tool | Callable by | Effect | Limits and guards |
|---|---|---|---|
| `db.read(entity, filters)` | all agents | Read from the application database through repositories | No raw SQL; row caps per call (default 10,000) |
| `connector.fetch(entity, since)` | data agent | Read from a customer system | Read-only account; per-run row cap; credentials never exposed to the agent |
| `forecast.run(series, method)` | demand agent | Deterministic forecast | CPU time limit per series |
| `inventory.compute(params)` | inventory agent | Deterministic calculations | Pure function |
| `alerts.upsert(alert)` | alert agent | Create or update alerts using dedupe key | Writes audit event |
| `llm.generate(prompt, schema)` | explainer agent, chat, notes extractor | Text only | Max tokens, timeout, JSON schema, number validator on output; output cannot reach any tool |
| `recommendations.create(rec)` | action agent (prepare) | Create a pending recommendation | Status `pending`; cannot approve |
| `actions.execute(rec_id)` | action service only | Write to outbox or connector | Requires approved status or valid level 3 gate; connector write only if `write_enabled` and supported; audited |
| `outbox.write(file)` | action service only | Create export file | Sanitizes spreadsheet formulas; filename allow-list |
| `audit.log(event)` | all | Append to audit log | Append-only |
| `learning.propose(change)` | learning agent | Create `param_versions` row as `proposed` | Cannot apply; admin approval required |

Never available to any runtime agent: shell execution, file access outside `/data`, network access, user/role management, license changes, direct database writes outside the tools above, changing autonomy settings, deleting audit entries.

Tool call logging: every tool call from an agent is recorded with agent name, tool, argument summary (no secrets) and result status, in the run's metrics.
