# DEVELOPMENT SPEC: On-Premise AI Supply Chain Agent System ("SCM Agent")

Audience: an autonomous AI coding agent. Read this entire file first, then build the product phase by phase.
Owner: mrx. Product type: B2B software, one-time license + yearly maintenance, sold in India first.

---

## PART A. HOW YOU (THE AGENT) MUST WORK

### A1. Prime rules
1. This file is the source of truth. If something is unspecified, choose the simplest sensible default, write it in `DECISIONS.md` with the reason, and continue. Ask the owner only when truly blocked.
2. Build in the **phases in Part N**. Finish a phase completely (code, tests, docs, demo) before starting the next. At the end of each phase, stop and write a report in `PROGRESS.md`: what was built, test results, measured numbers, known gaps.
3. Never claim something works unless a test or a measured run proves it. Put real numbers in the report. If a target is missed, say so plainly.
4. Never invent data sources, ERP table names or API fields. Where this file says "VERIFY", read the vendor documentation available offline in the repo or ask the owner for sample exports. Build against sample files and mock servers until real samples exist.
5. All code is tested. All config is in files or env vars. No secrets in the repo.
6. Do not add features outside this file. Put ideas in `BACKLOG.md`.

### A2. Hard product constraints (never violate)
1. **Fully offline at runtime.** No outbound network calls, no telemetry, no external AI APIs. Optional named outbound features (see G5 Zoho) are OFF by default and require an admin to enable.
2. **CPU only.** Must run on 4 cores, 16 GB RAM, no GPU. Minimum supported: 4 cores, 8 GB RAM. The LLM uses at most about 4 GB RAM.
3. **Numbers come from classical code, not from the LLM.** The LLM only writes explanations and phrases answers. Every number it shows must come from computed facts passed in (see Part H).
4. **Human in the loop.** Default autonomy is level 1 (advise). Write access is OFF by default.
5. **Audit everything** in a tamper-evident log (Part C3).
6. **Software only.** No hardware, cloud hosting or SaaS billing.

### A3. Definition of done (per phase)
- All tasks in the phase checklist complete.
- `pytest` passes; coverage at least 80% for `agents/`, `forecasting/`, `core/`.
- Acceptance metrics in the phase are measured and written to `PROGRESS.md`.
- `README.md` and the relevant `docs/` pages updated.
- A demo script (`docs/demo_phaseN.md`) shows the feature on synthetic data.

---

## PART B. REPOSITORY STRUCTURE

```
scm-agent/
  README.md  DECISIONS.md  PROGRESS.md  BACKLOG.md  SPEC.md   (SPEC.md = this file)
  backend/
    pyproject.toml            # pinned dependencies (lockfile committed)
    alembic/                  # DB migrations
    app/
      main.py                 # FastAPI app factory
      config.py               # settings from env/file
      db/        models.py session.py
      core/      security.py audit.py licensing.py settings_store.py scheduler.py crypto.py
      connectors/ base.py csv_excel.py sql_generic.py tally.py sap_b1.py zoho_optional.py outbox.py
      pipeline/  ingest.py quality.py normalize.py
      forecasting/ classify.py methods.py backtest.py
      agents/    base.py orchestrator.py data_agent.py demand_agent.py inventory_agent.py
                 supplier_agent.py logistics_agent.py alert_agent.py explainer_agent.py
                 action_agent.py learning_agent.py
      llm/       base.py llamacpp_backend.py mock_backend.py validator.py intents.py prompts/
      api/       auth.py items.py alerts.py recs.py suppliers.py connectors.py admin.py chat.py reports.py
      reports/   savings.py
    tests/
  frontend/                    # React + TypeScript + Vite, built to static files served by backend
  tools/
    synth_data/                # synthetic data generator + ground truth
    licgen/                    # vendor-side license generator (NOT shipped to customers)
    scmctl/                    # CLI: precheck, install, update, backup, restore, verify-audit
  deploy/
    docker-compose.yml  offline_bundle.sh  windows/  linux/
  docs/                        # admin guide, user guide, connector guide, security guide
```

---

## PART C. DATA MODEL

### C1. Database
PostgreSQL 15+ (SQLite allowed only for the dev/test profile). Use SQLAlchemy 2.x + Alembic. All timestamps UTC. Money in the customer's currency (default INR), stored as NUMERIC(18,2). All tables have `id` primary keys (UUID unless stated).

### C2. Tables (create exactly these; add indexes on every foreign key and on date columns)

```
users(id, username UNIQUE, password_hash, full_name, role CHECK IN ('admin','planner','purchaser','viewer'),
      active BOOL, created_at, last_login)
settings(key PK, value JSONB, updated_by, updated_at)
connectors(id, name, type CHECK IN ('csv','sql','tally','sap_b1','zoho'), config_encrypted BYTEA,
           write_enabled BOOL DEFAULT false, schedule_cron, last_run_at, last_status)
sites(id, code UNIQUE, name)
suppliers(id, code UNIQUE, name, contract_lead_time_days INT, active BOOL)
items(id, sku UNIQUE, name, uom, unit_cost NUMERIC, category, criticality CHECK IN ('A','B','C'),
      moq NUMERIC DEFAULT 1, lot_multiple NUMERIC DEFAULT 1,
      stockout_cost_per_unit NUMERIC NULL, service_level_target NUMERIC NULL, active BOOL)
item_suppliers(item_id, supplier_id, is_primary BOOL, contract_lead_time_days INT, price NUMERIC)
stock_snapshots(id, item_id, site_id, snapshot_date DATE, on_hand, allocated, UNIQUE(item_id,site_id,snapshot_date))
consumption(id, item_id, site_id, date DATE, qty, source CHECK IN ('sales','production','issue'),
            UNIQUE(item_id,site_id,date,source))
purchase_orders(id, po_number UNIQUE, supplier_id, site_id, order_date, promised_date, status
                CHECK IN ('open','partial','closed','cancelled'))
po_lines(id, po_id, item_id, qty_ordered, qty_received, unit_price)
receipts(id, po_line_id, receipt_date DATE, qty)
shipments(id, po_id NULL, reference, carrier, origin, destination, ship_date, eta, actual_arrival NULL, status)
data_quality_runs(id, run_at, connector_id, score INT, critical_count INT, details JSONB)
forecasts(id, item_id, site_id, run_id, generated_at, method, horizon_weeks INT, params JSONB,
          wape_backtest NUMERIC, bias_backtest NUMERIC, series JSONB)   -- series: [{week_start, mean, lo80, hi80}]
inventory_params(id, item_id, site_id, param_version_id NULL, computed_at, avg_daily_demand, sigma_daily,
                 lead_time_days, sigma_lead_time, service_level, safety_stock, reorder_point, order_qty)
supplier_metrics(id, supplier_id, computed_at, mean_lt_recent, mean_lt_prior, drift_pct, on_time_rate,
                 dependency_share, risk_score INT, trend_flag BOOL, details JSONB)
alerts(id, created_at, item_id, site_id, supplier_id NULL, type CHECK IN
       ('stockout_risk','supplier_delay','excess_stock','dead_stock','data_quality'),
       severity CHECK IN ('critical','high','medium','low'), prob_stockout NUMERIC NULL,
       days_to_stockout NUMERIC NULL, expected_loss NUMERIC, score NUMERIC,
       status CHECK IN ('open','acknowledged','resolved','expired'),
       dedupe_key TEXT, facts JSONB, explanation JSONB NULL)
       -- UNIQUE partial index on dedupe_key WHERE status IN ('open','acknowledged')
recommendations(id, alert_id, action_type CHECK IN ('create_draft_po','raise_reorder_request','draft_supplier_message'),
                payload JSONB, est_cost NUMERIC, est_benefit NUMERIC, autonomy_level INT,
                status CHECK IN ('pending','approved','rejected','executed','failed','cancelled'), created_at)
approvals(id, recommendation_id, user_id, decision CHECK IN ('approve','reject','edit_approve'),
          edited_payload JSONB NULL, comment, decided_at)
actions(id, recommendation_id, executed_at, target CHECK IN ('outbox','connector'), result JSONB, status)
outcomes(id, recommendation_id, evaluated_at, stockout_occurred BOOL, realized_cost NUMERIC,
         est_saving NUMERIC, notes JSONB)
param_versions(id, created_at, created_by, kind CHECK IN ('forecast_method','service_level','lead_time'),
               scope JSONB, before JSONB, after JSONB, backtest JSONB,
               status CHECK IN ('proposed','approved','applied','rolled_back'), approved_by NULL)
licenses(id, license_json JSONB, signature TEXT, installed_at, active BOOL)
notes_inbox(id, supplier_id NULL, received_at, raw_text, extracted JSONB NULL,
            status CHECK IN ('new','confirmed','dismissed'))
audit_log(id BIGSERIAL PK, ts, actor_type CHECK IN ('user','agent','system'), actor_id NULL,
          event_type, entity_type, entity_id, payload JSONB, prev_hash CHAR(64), hash CHAR(64))
```

### C3. Audit log (tamper-evident)
- Append only. A Postgres rule/trigger must block UPDATE and DELETE on `audit_log`.
- `hash = sha256(prev_hash || canonical_json({ts, actor_type, actor_id, event_type, entity_type, entity_id, payload}))`. First row uses 64 zeros as `prev_hash`.
- Log: login/logout/failed login, user changes, connector create/edit/test/run, data import runs, every alert creation/status change, every recommendation state change, every approval, every action, every settings change, license install, update/rollback, param version changes, exports.
- Provide `scmctl verify-audit` and `GET /api/v1/admin/audit/verify` that recompute the chain and report the first broken row, if any.
- Never store passwords, secrets or full credentials in audit payloads.

### C4. Canonical import files (CSV/Excel connector, phase 1)
The user maps their columns to these fields in the UI. Required fields marked `*`.

| File | Columns |
|---|---|
| items | sku*, name*, uom*, unit_cost*, category, criticality, moq, lot_multiple, stockout_cost_per_unit |
| suppliers | code*, name*, contract_lead_time_days* |
| item_suppliers | sku*, supplier_code*, is_primary, contract_lead_time_days, price |
| stock | sku*, site_code*, snapshot_date*, on_hand*, allocated |
| consumption | sku*, site_code*, date*, qty*, source |
| purchase_orders | po_number*, supplier_code*, site_code*, order_date*, promised_date*, status |
| po_lines | po_number*, sku*, qty_ordered*, qty_received, unit_price |
| receipts | po_number*, sku*, receipt_date*, qty* |
| shipments | reference*, po_number, carrier, origin, destination, ship_date, eta*, actual_arrival, status |

Import rules: idempotent upserts by natural key; reject rows with missing required fields and list them in an import report; keep the raw file hash and row counts in the audit log.

---

## PART D. DATA QUALITY (pipeline/quality.py)

Run after every import. Produce `data_quality_runs.score` (0 to 100) and a fix list.

| Check | Severity | Rule |
|---|---|---|
| Missing required field | critical | any NULL in required column of used entities |
| Item without any consumption history | warning | no rows in last 365 days |
| History too short | warning | fewer than 52 weeks of consumption for item |
| Negative stock or quantity | critical | on_hand < 0 or qty < 0 |
| Duplicate keys | critical | duplicate natural keys after mapping |
| Outliers | warning | consumption > median + 8 x MAD for that item (flag, do not delete) |
| Missing lead-time data | warning | supplier has no receipts with PO dates in last 365 days and no contract lead time |
| Unit mismatch suspicion | warning | same sku with a unit_cost changing by more than 10x between loads |
| Stale data | critical | latest stock snapshot older than `stale_days` (default 3) |
| Orphan references | critical | PO line, receipt or shipment referencing unknown sku, supplier or PO |

Score = 100 - (20 x min(critical_types,3)) - (3 x min(warning_types,10)). Floor 0.
Gate: if any **critical** check fails for an entity, the agents skip the affected items and raise a `data_quality` alert. The UI shows the exact fix list.

---

## PART E. FORECASTING AND INVENTORY LOGIC (exact methods)

All demand math uses **weekly buckets** (week starts Monday) built from daily consumption, zero-filled. Daily rate = weekly / 7.

### E1. Classification (forecasting/classify.py)
For each item-site series use only non-zero weeks:
- `ADI` = average number of weeks between non-zero demand weeks.
- `CV2` = (std/mean)^2 of non-zero demand sizes.
- Class: smooth (ADI < 1.32, CV2 < 0.49), erratic (ADI < 1.32, CV2 >= 0.49), intermittent (ADI >= 1.32, CV2 < 0.49), lumpy (both high).
- History under 8 weeks: class `new`, method moving average of available weeks, confidence `low`.

### E2. Methods and selection (forecasting/methods.py, backtest.py)
Candidates:
- smooth/erratic: `seasonal_naive` (needs 2 full years), `ets` (statsmodels ExponentialSmoothing, additive trend damped, optional seasonality 52 if at least 104 weeks), `moving_average_8`, `gradient_boosting` (scikit-learn, lag and calendar features) only when at least 104 weeks.
- intermittent/lumpy: `croston_sba`, `tsb`, `moving_average_13`.
Selection: rolling-origin backtest, 4 origins, horizon 4 weeks, metric **WAPE** = sum(|actual - forecast|) / sum(actual). Choose the lowest WAPE. Always also compute the naive baseline (last 4 weeks mean) and record both. If the best method does not beat naive by at least 3%, use naive and record that.
Prediction intervals: 80% interval from backtest residual quantiles. Horizon 13 weeks. Persist method, params, WAPE, bias.
Re-fit weekly (configurable) or when new data is imported.

### E3. Inventory parameters (agents/inventory_agent.py)
Per item-site:
- `d` = mean daily demand = mean of forecast over lead-time window / 7 (fallback: mean of last 13 weeks / 7).
- `sigma_d` = std of daily-equivalent forecast residuals from the backtest (fallback: std of last 26 weeks / sqrt(7)).
- `LT` = effective lead time in days = `max(contract_lead_time, mean(last 5 receipt lead times))`. If supplier trend_flag is true use `mean(last 3 receipt lead times)` if larger. Lead time of a receipt = receipt_date - PO order_date.
- `sigma_LT` = std of last 10 receipt lead times (0 if fewer than 3).
- Service level `SL`: item.service_level_target, else settings default by criticality (A 0.98, B 0.95, C 0.90). `z = NORMSINV(SL)`.
- **Safety stock** `SS = z * sqrt( LT * sigma_d^2 + d^2 * sigma_LT^2 )`.
- **Reorder point** `ROP = d * LT + SS`.
- **Order quantity**: `Q = max(MOQ, target_cover_days * d)` where `target_cover_days` default 30 (settings); use EOQ `sqrt(2*D*S/H)` only if both ordering cost S and holding rate H are set in settings and the item has `unit_cost`; round up to `lot_multiple`.
- **Available stock** `A = on_hand - allocated + open_po_qty_arriving_within(LT_window)`, where each open PO line arrives at `promised_date + supplier_expected_delay_days` (supplier delay = max(0, mean(actual - promised) over last 5 receipts)).
- **Days of cover** `DOC = (on_hand - allocated) / d`.

### E4. Stockout probability and expected loss
Over the protection window `W = LT` days (time until a new order placed today would arrive):
- Demand over window ~ Normal(mu = d * W, sd = sqrt(W * sigma_d^2 + d^2 * sigma_LT^2)).
- `z_a = (A - mu) / sd`. `P(stockout) = 1 - NORMCDF(z_a)`.
- Expected shortage units `ES = sd * (pdf(z_a) - z_a * (1 - cdf(z_a)))` (normal loss function).
- Impact per unit `I` = item.stockout_cost_per_unit if set, else `settings.default_stockout_cost_factor * unit_cost` (default factor 2.0, an editable **estimate**; show it as such in the UI).
- `expected_loss = ES * I`.
- `days_to_stockout = max(0, (on_hand - allocated) / d)` (shown as expected, not guaranteed).
If `sd = 0`, use a step function: P = 1 if A < mu else 0.

### E5. Excess and dead stock
- Excess: `DOC > excess_days` (default 120) and `on_hand > ROP + Q`. Excess units = `on_hand - (ROP + Q)`. Excess value = units * unit_cost.
- Dead: no consumption in `dead_days` (default 180) and `on_hand > 0`.
- Carrying cost estimate = excess value * `settings.carrying_rate` (default 20% per year, editable estimate).

---

## PART F. AGENTS

### F1. Common interface (agents/base.py)
```python
class Agent(Protocol):
    name: str
    def run(self, ctx: RunContext) -> AgentResult: ...
# RunContext: db session, run_id, as_of_date, settings, audit logger, llm backend
# AgentResult: status ('ok','partial','failed'), items_processed, warnings[], metrics{}
```
Every run is audited with duration and counts. Agents are idempotent for the same `run_id`.

### F2. Orchestrator (agents/orchestrator.py)
Pipeline order for a full run:
`data_agent -> quality gate -> demand_agent -> supplier_agent -> logistics_agent -> inventory_agent -> alert_agent -> explainer_agent -> action_agent(prepare only)`.
- Triggered by schedule (default daily 06:00 local) and by manual "Run now" and after each import.
- Per-agent timeout (default 20 min) and 2 retries with backoff; a failed agent marks the run `partial`, later agents that depend on it are skipped with a clear warning.
- Single active run lock (DB advisory lock). Learning agent runs separately (monthly).
- Scale target: 5,000 item-site series per run in under 10 minutes on 4 cores; parallelize forecasting with a process pool (default workers = cores - 1).

### F3. Agent specifications

**data_agent**: runs connectors due by schedule, normalizes into canonical tables, runs quality checks, returns the quality score.

**demand_agent**: E1 and E2 for every active item-site; stores `forecasts`.

**supplier_agent** (supplier_metrics):
- `mean_lt_recent` = mean lead time of last 5 receipts; `mean_lt_prior` = mean of the 10 receipts before those (needs at least 8 receipts total, else risk_score from available parts and flag `low_data`).
- `drift_pct = (recent - prior) / prior`.
- `on_time_rate` = share of last 10 receipts with receipt_date <= promised_date + grace (default 1 day).
- `dependency_share` = for critical (A) items supplied: max share of that item's last-12-month purchase quantity coming from this supplier, averaged over A items weighted by spend.
- `trend_flag` = true when the last 3 receipts each had lead time greater than the one before, or drift_pct >= 0.25.
- `risk_score = round(100 * (0.40*clip(drift_pct/0.5,0,1) + 0.35*(1 - on_time_rate) + 0.25*dependency_share))`.
- Create `supplier_delay` alerts when `trend_flag` is true or risk_score >= 60, with the list of items exposed (A and B items with open POs or low cover).

**logistics_agent**: from `shipments`: per carrier/lane mean and std of (actual_arrival - eta); flag open shipments where `today > eta` or predicted arrival = eta + lane mean delay is later than the linked PO promised_date; feed predicted delay into inventory_agent's "arriving within window" logic and raise `supplier_delay` alerts of subtype `shipment_late`.

**inventory_agent**: E3 to E5; stores `inventory_params`; outputs stockout probability, expected loss, excess and dead lists.

**alert_agent**:
- Create alerts from inventory and supplier results.
- Severity: `critical` if P >= 0.50 or days_to_stockout <= 3 (for A items) ; `high` if P >= 0.25; `medium` if P >= 0.10 or excess_value above settings threshold; below that not alerted (except dead stock informational `low`).
- `urgency = 1 + max(0, 14 - days_to_stockout) / 14` (range 1 to 2).
- `score = expected_loss * urgency` for stockout alerts; excess alerts use carrying cost estimate.
- Deduplicate with `dedupe_key = type:item:site` while open; update the existing alert instead of creating a new one; auto-expire alerts when the condition clears for 2 consecutive runs.
- Top-N per day shown first, sorted by score.

**explainer_agent**: Part H.

**action_agent** (Part I): builds recommendations and executes only as allowed.

**learning_agent** (Part J): monthly, proposes versioned updates.

### F4. Recommendation generation (in action_agent "prepare")
For a `stockout_risk` alert:
- `create_draft_po`: supplier = primary supplier (or the alternate supplier with the lowest recent lead time and price if the primary has trend_flag); qty = `max(Q, ROP + Q - A)` rounded to lot multiple; `est_cost` = qty * price; `est_benefit` = expected_loss avoided estimate = `expected_loss` (labeled estimate).
- If an alternate supplier is used, include an `extra_cost` = (alt_price - primary_price) * qty and show it.
For `supplier_delay` alerts: `draft_supplier_message` (template text asking for confirmed dates, see I3) and, if exposed items are at risk, linked `create_draft_po` recommendations.
For `excess_stock`: `raise_reorder_request` is NOT generated; show an advisory only ("pause new orders for these items").

---

## PART G. CONNECTORS

### G1. Interface (connectors/base.py)
```python
class Connector(Protocol):
    def test_connection(self) -> TestResult: ...
    def fetch(self, entity: str, since: datetime | None) -> Iterable[dict]: ...   # canonical field names
    def write(self, entity: str, payload: dict) -> WriteResult: ...              # raises WriteDisabled unless connector.write_enabled
```
Credentials: encrypted with AES-256-GCM using a key held in the OS keystore or a root-only key file created at install; never logged; never returned by the API (only masked).

### G2. Build order and behavior
1. **csv_excel**: upload or watched folder (`/data/inbox`); column mapping saved per connector; Excel via openpyxl.
2. **sql_generic**: SQLAlchemy to a customer database using a **read-only account**; the admin supplies one SELECT query per entity returning canonical column names; the app rejects any query that is not a single SELECT and sets a read-only transaction and a statement timeout.
3. **tally**: Tally Prime exposes an XML-over-HTTP interface on the local network (VERIFY port and request format in Tally documentation); implement export of masters (stock items, parties) and vouchers (sales, purchase, stock journal) and stock summary; parse to canonical entities. Build against recorded XML samples; ask the owner for real sample exports.
4. **sap_b1**: SAP Business One Service Layer (REST) or direct SQL (VERIFY version); read-only first.
5. **zoho_optional**: Zoho products are cloud services, so this connector requires an outbound call and **breaks the offline rule**. Build it last, mark it "Optional outbound feature", OFF by default, and show a clear admin warning when enabled.

### G3. Write-back (default: outbox)
Default write target is the **outbox**: approved actions produce a file in `/data/outbox` (XLSX and CSV for draft POs; TXT/HTML for supplier messages) that the user imports or sends. Direct ERP write is allowed only for a connector that implements `write` AND `write_enabled = true` AND the action type's autonomy level permits it. Add negative tests proving writes are impossible otherwise.

---

## PART H. LOCAL LLM LAYER

### H1. Interface and backend
```python
class LLMBackend(Protocol):
    def generate(self, prompt: str, max_tokens: int, temperature: float = 0.2,
                 json_schema: dict | None = None, stop: list[str] | None = None) -> str: ...
```
- `LlamaCppBackend`: `llama-cpp-python`, GGUF file path from config, `n_ctx` 4096, `n_threads` = cores, use grammar-constrained JSON output when a schema is given.
- `MockBackend`: deterministic outputs for tests.
- Model candidates (owner chooses; VERIFY each license permits commercial redistribution before shipping): a 3B-class instruction model quantized to Q4 (about 2 GB), for example Qwen2.5-3B-Instruct or Llama-3.2-3B-Instruct. Provide `tools/llm_bench.py` to run 50 fixed explanation prompts and report RAM, tokens/second and validator pass rate so the owner can compare models.

### H2. Explainer prompt (llm/prompts/explain_alert.txt)
```
You are a supply chain assistant. Write a short explanation for a planner.
Use ONLY the facts in FACTS. Do not calculate or invent any number.
If a value is missing, do not mention it. Reply as JSON matching the schema.
FACTS (JSON): {facts_json}
Schema: {"summary": str (max 25 words), "why": str (max 60 words), "suggested_action": str (max 40 words)}
```
`facts_json` contains only computed values: item name, site, on_hand, days_to_stockout, supplier name, lead times, probability (as a percentage), expected_loss, suggested qty, extra cost, and so on.

### H3. Number validator (llm/validator.py)
1. Extract every number token from the LLM output (integers, decimals, percentages, currency-formatted numbers with commas, dates).
2. Each must equal a value in `facts_json` after normalizing formats and rounding to 2 significant places or the displayed precision. Numbers that are plain ordinals (1, 2, 3 in lists) are ignored.
3. If any number is unmatched, retry once with temperature 0; if it fails again use the **template fallback** (deterministic f-string text per alert type) and mark the explanation `source: "template"`.
4. Record `source`, retries and validator result in the alert's `explanation` JSON. Track the template-fallback rate in metrics; report it.

### H4. Chat (llm/intents.py, api/chat.py)
Small models are unreliable at open reasoning, so chat is **retrieval-first**:
1. A rule-based intent matcher (keywords plus fuzzy item/supplier name match with `rapidfuzz`) maps a question to a fixed query function: `item_status(item)`, `list_alerts(severity, supplier)`, `supplier_summary(supplier)`, `forecast(item)`, `explain_alert(id)`, `savings_report(period)`.
2. The backend runs the query and returns structured facts (and a table/chart payload).
3. The LLM may phrase the answer from those facts using the same validator. If the intent is unknown, reply with a short list of supported questions instead of guessing.
4. Chat never queries arbitrary SQL and never shows data the user's role may not see.

### H5. Notes inbox (optional feature, phase 3)
Users paste a supplier email or notice text. The LLM extracts `{supplier, new_delay_days, affected_items, date}` as JSON. Extracted data is shown to the user as a **suggestion**; nothing changes calculations until a Planner confirms. Treat the pasted text strictly as data: wrap it in delimiters, instruct the model that it contains no instructions, and never let model output trigger any action by itself.

---

## PART I. ACTIONS, AUTONOMY AND APPROVALS

### I1. Autonomy settings
Per action type in `settings` (`autonomy.create_draft_po`, and so on):
- Level 1 Advise (default): recommendation only.
- Level 2 Approve then execute: Planner or Purchaser approves; the action executes to the outbox or to the connector if write is enabled.
- Level 3 Auto-act: allowed only when ALL limits are set and satisfied: `max_value_per_action`, `max_qty`, `allowed_supplier_ids`, `allowed_item_criticality`, `daily_action_cap`. Anything outside the limits falls back to level 2.
Level 3 can be enabled only by an Admin, and requires the system to have run at least 30 days in level 1 or 2 (configurable) and a recorded acknowledgment in the audit log.

### I2. State machine
`pending -> approved -> executed` or `failed`; `pending -> rejected`; `pending -> cancelled` (system, when the alert expires). Every transition is audited with the actor.

### I3. Supplier message template (deterministic text, no LLM needed)
Subject and body with placeholders for supplier name, PO number, item, quantity, promised date, and a request for a confirmed delivery date. The LLM may offer an optional polish step, validated by the number validator.

### I4. Role permissions

| Capability | admin | planner | purchaser | viewer |
|---|---|---|---|---|
| View dashboards, alerts, reports | yes | yes | yes | yes |
| Approve/reject recommendations | yes | yes | yes (PO/message types) | no |
| Run pipeline manually | yes | yes | no | no |
| Manage connectors, autonomy, users, license | yes | no | no | no |
| Approve learning updates | yes | no | no | no |
| View audit log | yes | no | no | no |

---

## PART J. LEARNING (agents/learning_agent.py)

Monthly job, never auto-applies:
1. **Outcome tracking**: for each executed recommendation, after the horizon passes record `outcomes` (did a stockout occur; actual cost if known from data).
2. **Forecast accuracy**: WAPE and bias per item and per class; list worst 20 items.
3. **Proposals** (each creates a `param_versions` row with status `proposed`):
   - method change for an item where another method beats the current one by at least 5% WAPE on the last 8 weeks of holdout;
   - service level adjustment for items with repeated stockouts despite alerts;
   - lead-time estimate change per supplier when mean actual differs by more than 15% from the one in use.
4. Each proposal stores `before`, `after` and a back-test result on historical data.
5. Admin screen shows proposals with before/after metrics; Admin approves, then it is applied (`applied`) and logged. One-click **rollback** restores the previous version (`rolled_back`).

---

## PART K. SAVINGS REPORT (reports/savings.py)

Show clearly what is measured and what is estimated.
- **Decisions taken**: count of approved/executed recommendations.
- **Estimated avoided stockout loss** = sum of `expected_loss` for executed recommendations where no stockout occurred within the horizon (label: estimate).
- **Expedite cost avoided**: only if the customer provides expedite cost data; otherwise show "not available".
- **Inventory reduction**: (average inventory value in the 90 days before go-live) minus (current 90-day average) = released cash (one-time); and `released cash * carrying_rate` = yearly carrying cost saving (estimate).
- Never sum one-time cash release and yearly saving into one number.
- Export to XLSX and PDF. Each report shows the assumptions used and the data period.

---

## PART L. API (FastAPI, prefix `/api/v1`, JSON, OpenAPI docs enabled only for admins)

Auth: `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` (HTTP-only secure cookie session or short-lived JWT + refresh; CSRF protection if cookies).

| Area | Endpoints |
|---|---|
| Dashboard | `GET /dashboard/summary` (counts by severity, total expected loss, data quality score, last run, savings snapshot) |
| Alerts | `GET /alerts?severity=&status=&supplier=&q=&page=`, `GET /alerts/{id}`, `POST /alerts/{id}/acknowledge`, `POST /alerts/{id}/resolve` |
| Recommendations | `GET /recommendations?status=`, `GET /recommendations/{id}`, `POST /recommendations/{id}/decision` body `{decision, edited_payload?, comment?}` |
| Items | `GET /items`, `GET /items/{id}` (params, forecast series, history, open POs, alerts) |
| Suppliers | `GET /suppliers`, `GET /suppliers/{id}` (metrics history, items exposed, receipts) |
| Pipeline | `POST /pipeline/run`, `GET /pipeline/runs`, `GET /pipeline/runs/{id}` |
| Data | `POST /imports` (file + connector), `GET /imports/{id}/report`, `GET /data-quality/latest` |
| Connectors | `GET/POST /connectors`, `POST /connectors/{id}/test`, `POST /connectors/{id}/run`, `PATCH /connectors/{id}` |
| Notes | `POST /notes`, `GET /notes`, `POST /notes/{id}/confirm`, `POST /notes/{id}/dismiss` |
| Chat | `POST /chat` body `{message}` -> `{answer, facts, table?, chart?}` |
| Reports | `GET /reports/savings?from=&to=`, `GET /reports/savings/export?format=xlsx|pdf` |
| Learning | `GET /learning/proposals`, `POST /learning/proposals/{id}/approve`, `POST /learning/proposals/{id}/rollback` |
| Admin | `GET/POST/PATCH /admin/users`, `GET/PATCH /admin/settings`, `GET /admin/audit`, `GET /admin/audit/verify`, `GET /admin/license`, `POST /admin/license`, `GET /admin/system` (RAM, CPU, disk, model status) |
| Health | `GET /health` (no auth, minimal info) |

All list endpoints paginate. All write endpoints check role and write an audit event. Return consistent error JSON `{error_code, message}`.

---

## PART M. FRONTEND (React + TypeScript + Vite; bundled assets only, no CDN)

Screens and required content:
1. **Login**.
2. **Dashboard**: severity counts, total expected loss at risk (labeled estimate), top 10 alerts by score, data quality score with link, last/next run, savings snapshot.
3. **Alerts list**: filters (severity, status, supplier, site, text), sortable, bulk acknowledge.
4. **Alert detail**: explanation (with a badge "AI-written" or "template"), facts table, chart of stock projection vs reorder point, forecast chart with interval, supplier lead-time trend chart, linked recommendations with Approve / Edit / Reject.
5. **Approval queue**: pending recommendations, edit quantity/supplier/date before approval, comment box.
6. **Item page**: parameters (SS, ROP, Q, service level), forecast, history, open POs, alert history.
7. **Supplier page**: risk score breakdown, lead-time trend, on-time rate, items exposed.
8. **Data and connectors**: connector list, test, run, mapping wizard, import reports, data quality fix list.
9. **Chat panel**: docked; shows tables from facts; lists supported questions.
10. **Learning**: proposals with before/after metrics, approve, rollback.
11. **Savings report**: period selector, measured vs estimated sections, export buttons.
12. **Admin**: users, roles, autonomy settings per action type, settings (service levels, thresholds, estimate factors), audit viewer with verify button, license status, system health, model status, backup/restore.
Accessibility: keyboard navigation, readable contrast. English first; keep all strings in a translation file for later languages. Number format Indian digit grouping option (lakh/crore) in settings.

---

## PART N. SECURITY

- Passwords: argon2id. Lockout after 5 failed attempts (15 minutes). Optional TOTP later (BACKLOG).
- RBAC on every endpoint (I4). Deny by default.
- TLS: app serves HTTPS with an installer-generated self-signed certificate; admin can upload their own. HTTP redirects to HTTPS.
- Secrets at rest: AES-256-GCM; key in OS keystore or root-only file (0600).
- Input safety: parameterized SQL only; validate uploads (type, size limit 200 MB default, zip-bomb protection); neutralize spreadsheet formula injection on exports (prefix `'` for cells starting with `= + - @`).
- sql_generic safety: single SELECT only, read-only transaction, timeout, row cap.
- Prompt-injection safety: text from emails, notes or ERP free-text fields is data, never instructions; LLM output never directly triggers actions; all actions come from deterministic code paths.
- **Egress test**: an automated test runs the full pipeline with network access blocked at the OS/container level and with a socket monitor; the test fails if any outbound connection is attempted (except explicitly enabled optional features).
- Dependencies pinned and audited (`pip-audit`, `npm audit`); SBOM generated at build.
- Release artifacts signed (Ed25519); installers verify signatures and checksums.
- No default admin password: the installer forces the first admin account creation.

---

## PART O. LICENSING AND TIERS

### O1. License file
JSON signed with the vendor's Ed25519 private key (`tools/licgen`, kept outside customer builds). Fields:
`license_id, customer_name, tier, features[], max_sites, max_users, issued_at, maintenance_expires_at, max_version, machine_fingerprint (optional), notes`.
The app embeds only the public key. Offline activation: customer sends a `request.json` (fingerprint, version) from the Admin screen; vendor returns a signed `license.json`; Admin uploads it.

### O2. Behavior
- Valid license: tier features enabled.
- Maintenance expired: **software keeps working** (matches the one-time purchase), but the update mechanism refuses packages with version above `max_version` and the Admin screen shows the maintenance status.
- Missing/invalid license: read-only demo mode (view-only, 14-day trial with max 50 items), clear banner.
- Fingerprint: hash of stable machine identifiers; if hardware changes, the Admin can re-activate (vendor re-issues). Be clear in docs that this deters casual copying and does not stop a determined attacker.

### O3. Tiers (feature flags)

| Flag | Starter | Professional | Regulated |
|---|---|---|---|
| Sites | 1 | up to 10 | unlimited |
| Users | 5 | 25 | unlimited |
| Agents | data, demand, inventory, alert, explainer | all | all |
| Autonomy levels | 1 | 1, 2, 3 | 1, 2, 3 |
| Supplier risk and logistics | no | yes | yes |
| Direct ERP write | no | yes | yes |
| Learning agent | no | yes | yes |
| Offline bundle | yes | yes | yes + extended audit exports |

---

## PART P. INSTALLATION, PRE-CHECK, UPDATES, BACKUP (tools/scmctl, deploy/)

### P1. `scmctl precheck`
Output human text and JSON. Checks and thresholds:

| Check | Pass | Warn | Fail |
|---|---|---|---|
| OS | Ubuntu 20.04+/Debian 11+/RHEL 8+/Windows Server 2016+ | other Linux | unsupported |
| RAM | >= 16 GB | 8 to 15 GB | < 8 GB |
| CPU cores | >= 4 | 2 to 3 | < 2 |
| Free disk | >= 100 GB | 50 to 99 GB | < 50 GB |
| CPU AVX2 support (needed by many quantized runtimes) | yes | n/a | no (warn with note and fallback build) |
| Ports free (443, 5432 internal) | yes | n/a | no |
| Container runtime or Python | present | install offered | n/a |
Result includes a **tier-fit suggestion**: e.g. "Fit for Starter and Professional (up to N item-sites)" based on measured RAM and cores. Run a 60-second **LLM speed test** if a model file exists and report tokens/second.

### P2. Install
- **Linux (primary)**: `docker compose` with services `api`, `worker`, `db`; frontend served by `api`. `scmctl install` = precheck, create data directories, generate keys and certificate, start services, create first admin via interactive prompt.
- **Offline bundle**: `deploy/offline_bundle.sh` produces one archive containing image tarballs (`docker save`), Python wheels, frontend build, model file, checksums and signature. `scmctl install --offline-bundle <file>` verifies and installs with no internet.
- **Online installer**: may fetch the same artifacts from a vendor package server, verifying signatures before use.
- **Windows Server (Phase 5 stretch, important for Tally users)**: a zip with embedded Python runtime and PostgreSQL (or SQLite profile for Starter), installed as Windows services (NSSM or native service wrapper), same `scmctl` commands. Document supported versions.

### P3. Update and rollback
- Update package: signed archive with `manifest.json` (version, checksums, migration list, min compatible version).
- `scmctl update <pkg>`: verify signature and license `max_version`, automatic backup, stop services, apply, run Alembic migrations, health check; on failure restore the backup automatically.
- `scmctl rollback` restores the previous version and DB backup. Keep the last 2 versions.

### P4. Backup and restore
`scmctl backup --out file --passphrase` creates an encrypted archive (pg_dump, settings, models, license, outbox). Daily automatic backups to a customer-chosen local path, retention 14 days. `scmctl restore`. Test restore in CI.

### P5. Logs and support bundle
Structured JSON logs with rotation. `scmctl support-bundle` creates a zip of logs, versions, precheck output and config with secrets removed, that the customer can send to the vendor. No automatic upload.

---

## PART Q. SYNTHETIC DATA AND TEST HARNESS (tools/synth_data)

Deterministic (seeded) generator; outputs canonical CSVs plus `ground_truth.json`.
- Size: 200 items (parameter for up to 5,000), 2 sites, 25 suppliers, 3 years of daily consumption, weekly stock snapshots (daily for the last 90 days), about 3,000 POs with receipts.
- Demand mix: 40% smooth with yearly seasonality, 20% erratic, 25% intermittent, 15% lumpy; random level and noise per item.
- Lead times: per supplier mean 7 to 45 days, std 10 to 25% of mean.
- **Injected events** (recorded in ground truth with start dates and affected items):
  - 15 supplier delay events: lead time grows 50 to 100% over 3 consecutive deliveries;
  - 10 demand spikes: x2 to x3 demand for 3 weeks;
  - 5 supplier outages: no deliveries for 3 to 6 weeks;
  - 20 data defects (missing lead times, negative stock, duplicates, unit-cost 10x jumps).
- A **simulation mode** replays the data week by week to the pipeline (`as_of_date` increases), so alert timing can be scored against the simulated stockout dates (stockout = on_hand reaching 0 before the next receipt).

---

## PART R. PHASES, TASKS AND ACCEPTANCE TESTS

Check off tasks in `PROGRESS.md`. Do not skip ahead.

### PHASE 1: Core engine, advise mode (foundation and demo)
Tasks:
- P1-01 Repo skeleton, config, logging, pyproject with pinned deps, pre-commit (ruff, mypy), CI script running tests.
- P1-02 DB models and Alembic migrations (Part C2), audit log with hash chain and block-update trigger (C3).
- P1-03 Auth, users, roles, RBAC middleware, lockout, first-admin creation.
- P1-04 Synthetic data generator and ground truth (Part Q).
- P1-05 CSV/Excel connector with mapping, idempotent upserts, import report (C4).
- P1-06 Data quality checks and score (Part D).
- P1-07 Forecasting: classification, methods, backtest, selection (E1, E2).
- P1-08 Inventory logic (E3 to E5), stockout probability and expected loss (E4).
- P1-09 Alert agent: severity, score, dedupe, expiry (F3).
- P1-10 Orchestrator with scheduler, locks, retries (F2).
- P1-11 API endpoints for dashboard, alerts, items, imports, pipeline, admin (Part L subset).
- P1-12 Frontend: login, dashboard, alerts list/detail (template explanations only), data and connectors, admin basics.
- P1-13 Docker Compose dev environment, README with run steps.
Acceptance (measure and report):
- A1 Simulation on synthetic data: at least **80%** of injected stockout-risk events (supplier delays, spikes, outages) produce a `high` or `critical` alert at least **7 days** before the simulated stockout.
- A2 False alerts: no more than **3** high/critical alerts per 100 items per week during event-free periods.
- A3 Forecast quality: selected method beats the naive baseline in WAPE for at least **70%** of items.
- A4 Data defects: at least **90%** of the 20 injected defects are detected by the quality checks.
- A5 Runs on 4 cores, 16 GB, no GPU; full pipeline for 200 items under 2 minutes; for 5,000 item-series under 10 minutes (report actual).
- A6 Audit chain verification passes; tampering test (modify a row in a copy) is detected.
- A7 Egress test passes (no outbound connections).

### PHASE 2: Local LLM explainer and chat
Tasks:
- P2-01 LLM interface, llama.cpp backend, mock backend, config for model path.
- P2-02 Explainer prompts and facts builders (H2).
- P2-03 Number validator with retry and template fallback (H3).
- P2-04 `tools/llm_bench.py` (RAM, speed, validator pass rate on 50 prompts).
- P2-05 Chat: intent matcher, query functions, phrasing with validation (H4).
- P2-06 Frontend: explanation badge, chat panel.
Acceptance:
- B1 Validator test suite of at least **100** cases (valid, invented numbers, rounding variants, percentages, currency formats); all expected outcomes correct.
- B2 On the 50-prompt benchmark: report validator first-pass rate and fallback rate; **no shown explanation contains a number absent from facts** (zero tolerance).
- B3 LLM process peak RAM at most **4 GB**; report tokens/second and median seconds per explanation on 4 cores.
- B4 Chat answers all 6 supported intents correctly on 30 scripted questions; unknown questions return the supported list.

### PHASE 3: Supplier risk, logistics, approvals, notes
Tasks:
- P3-01 Supplier agent and metrics (F3).
- P3-02 Logistics agent (F3).
- P3-03 Recommendation generation (F4) and supplier message templates (I3).
- P3-04 Approval workflow, state machine, roles (I2, I4), approval queue UI.
- P3-05 Outbox export (XLSX/CSV/TXT) for approved actions (G3).
- P3-06 Notes inbox with LLM extraction and human confirmation (H5).
- P3-07 Supplier and item pages, charts.
Acceptance:
- C1 Supplier delay events in synthetic data flagged (`trend_flag` or risk >= 60) at least **10 days** before the first stockout they cause, in at least **80%** of cases.
- C2 Every recommendation state transition is audited; invalid transitions are rejected (tests).
- C3 Role tests: viewer cannot approve; purchaser cannot approve learning; admin-only endpoints reject others.
- C4 Prompt-injection tests: malicious text in notes and ERP free-text fields causes no state change and no instruction-following (at least 20 cases).

### PHASE 4: Connectors, action agent, autonomy
Tasks:
- P4-01 sql_generic connector with read-only guards (G2).
- P4-02 Tally connector against recorded XML samples and mock server (G2); parse to canonical entities.
- P4-03 SAP B1 read connector against mock Service Layer (G2).
- P4-04 Connector credential encryption and masked API responses (G1).
- P4-05 Autonomy settings, level 3 limits and 30-day gate, action agent execution (Part I).
- P4-06 Direct write path for connectors that support it, disabled by default (G3).
- P4-07 Optional Zoho connector with outbound warning (G2.5), disabled by default.
Acceptance:
- D1 Negative tests: writes are impossible when `write_enabled` is false, or autonomy is level 1, or limits are exceeded (at least **15** cases).
- D2 sql_generic rejects non-SELECT statements, multiple statements and comments hiding statements (at least **25** injection cases).
- D3 Credentials never appear in logs, audit payloads or API responses (automated scan).
- D4 Each connector's test suite passes against its mock/sample data; document what real-system verification is still required.

### PHASE 5: Installer, licensing, updates, backup
Tasks:
- P5-01 `scmctl precheck` (P1) with tier-fit suggestion and LLM speed test.
- P5-02 Linux install via Docker Compose; offline bundle build and install (P2).
- P5-03 Licensing: licgen tool, verification, tiers and feature flags, demo mode, offline activation (Part O).
- P5-04 Update, signature verification, automatic backup, rollback (P3).
- P5-05 Backup/restore with encryption, daily schedule (P4).
- P5-06 Support bundle (P5). Log rotation.
- P5-07 Windows Server package (stretch): embedded Python, services, same CLI.
- P5-08 HTTPS with generated certificate; first-run admin setup.
Acceptance:
- E1 Clean Ubuntu VM with no internet: offline install in one command; app reachable; demo data runs end-to-end.
- E2 Precheck correctly reports Pass/Warn/Fail on VMs sized 2GB, 8GB and 16GB (record results).
- E3 Invalid, expired-maintenance and tampered licenses behave as in O2 (tests).
- E4 A failed update (simulated) auto-restores; manual rollback works; restore test from encrypted backup passes.
- E5 Tampered installer or update package is rejected.

### PHASE 6: Learning, savings report, hardening, documentation
Tasks:
- P6-01 Learning agent: outcomes, accuracy, proposals, back-tests, approval, rollback (Part J).
- P6-02 Savings report with measured vs estimated sections and exports (Part K).
- P6-03 Security review pass: dependency audit, authorization test sweep, fuzz import parsers, SBOM.
- P6-04 Performance pass: indexes, query review, caching of dashboard summary.
- P6-05 Documentation: admin guide, user guide (planner workflow), connector guide, security and privacy guide, troubleshooting, minimum server requirements page, "How to read estimates" page.
- P6-06 Final end-to-end demo script and a 30-minute walkthrough checklist for sales pilots.
Acceptance:
- F1 A proposed update is back-tested, approved, applied and rolled back in an automated test; the audit log shows each step.
- F2 Savings report reconciles to logged recommendations/outcomes in a test dataset; one-time and yearly figures never combined.
- F3 `pip-audit`, `npm audit` show no known high/critical unresolved vulnerabilities (or documented exceptions).
- F4 Full regression: all tests pass; Phase 1 acceptance metrics A1 to A7 re-measured and not worse.

---

## PART S. DOCUMENTATION DELIVERABLES
`README.md` (quick start), `docs/admin_guide.md`, `docs/user_guide.md`, `docs/connector_guide.md`, `docs/security_privacy.md`, `docs/minimum_server_requirements.md`, `docs/how_estimates_work.md`, `docs/model_selection.md` (benchmarks and license notes), `docs/pilot_playbook.md` (shadow-mode steps, savings measurement), `docs/limitations.md` (honest list of what the product does not do).

---

## PART T. KNOWN LIMITS (write these in `docs/limitations.md`)
1. Forecasts depend on data quality and history; short or messy history lowers accuracy.
2. Expected loss and savings are **estimates** based on configurable assumptions.
3. The system detects demand and supplier risk from the customer's own data; it does not predict global market movements.
4. The small local model writes explanations only; it is not used for calculations.
5. ERP connectors need verification against each customer's version and customization.
6. License fingerprinting deters casual copying only.

## PART U. FINAL INSTRUCTION
Begin with **Phase 1**. First write a plan into `DECISIONS.md` (folder layout, library choices, module list, test strategy) and wait for the owner's go-ahead only if something in this spec conflicts with itself. Otherwise proceed and report at the end of Phase 1 with the measured acceptance results.
