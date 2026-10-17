# architecture.md: System Architecture

Scope: how SCM Agent is structured, how data flows, and where the trust boundaries are. Exact tables, formulas and agent logic are in `DEVELOPMENT_SPEC_scm_agent.md`. Library choices are in `tech-stack.md`.

---

## 1. Architectural principles

1. **Offline-first.** Nothing leaves the customer's server at runtime. Optional outbound features are explicit, named, off by default and visibly flagged.
2. **Deterministic core, language layer on top.** Numbers, forecasts, risk and money come from tested code. The local LLM only phrases explanations and answers from computed facts.
3. **Human in the loop.** Recommendations are produced automatically; actions need approval unless an admin has granted limited auto-act.
4. **Everything auditable.** State changes go into a hash-chained, append-only log.
5. **Small footprint.** Runs on 4 cores, 16 GB RAM, no GPU.
6. **Replaceable edges.** Connectors and the LLM backend sit behind interfaces so they can be swapped or mocked.
7. **Simple operations.** One database, one application image, one worker, no external message broker.

## 2. System context

```
                    +---------------------------+
   Planner /        |      Browser (React UI)    |
   Purchaser /  --->|  served over HTTPS by API  |
   Admin            +-------------+-------------+
                                  |
 Customer systems                 v
 (ERP, DB, files)      +-------------------------+       +------------------+
        ^              |   SCM Agent server       |       | Local LLM (GGUF) |
        | read-only    |   (customer's own)       |<----->| in-process       |
        +------------->|  API + Worker + DB       |       +------------------+
        |              +-----------+-------------+
 write-back (off by default)       |
        +<-- outbox files / connector write (only if enabled)

 Vendor (offline): issues signed licenses and signed update packages; receives support bundles manually.
```

## 3. Runtime components

| Component | Responsibility | Notes |
|---|---|---|
| **API service** | REST API, auth, RBAC, serves the built frontend, runs the chat and approval endpoints | FastAPI, single process with several workers |
| **Worker** | Runs the pipeline (agents), scheduled jobs, imports, learning job | Same codebase, separate process; holds the run lock |
| **Scheduler** | Cron-style triggers for pipeline, backups, learning, alert expiry | In-process in the worker |
| **Database** | Transactional store and audit log | PostgreSQL (SQLite for dev/test only) |
| **LLM runtime** | Loads the quantized model and generates text | In-process in the worker via llama.cpp binding; model file on disk |
| **Outbox** | Folder of generated files (draft POs, messages) | `/data/outbox`, permissions restricted |
| **Inbox** | Watched folder for CSV/Excel drops | `/data/inbox` |
| **Frontend** | Single-page app, built to static files | No CDN, no external fonts |
| **scmctl** | CLI for precheck, install, update, rollback, backup, restore, verify-audit, support bundle | Runs on the host |

## 4. Logical layers (code structure)

```
UI (React)
  -> API routers (thin, validate input, check role)
    -> Services (business logic, transactions, audit)
      -> Agents (pipeline steps) and Forecasting library
      -> Connectors (read/write behind interfaces)
      -> LLM layer (backend interface, prompts, validator)
      -> Repositories (SQLAlchemy models, queries)
        -> PostgreSQL
```
Rules: UI never talks to the database; routers never contain business logic; agents never call the LLM for numbers; only the action service may call a connector's `write`.

## 5. Main data flows

### 5.1 Daily pipeline
1. Scheduler (or "Run now", or after an import) asks the orchestrator to start a run; it takes the single-run lock.
2. **Data agent** pulls from connectors or the inbox, normalizes into canonical tables, runs data quality checks and stores the score.
3. **Quality gate:** critical failures exclude affected items and raise data-quality alerts.
4. **Demand agent** classifies series, selects a method by backtest, stores forecasts.
5. **Supplier and logistics agents** compute supplier metrics and shipment delay predictions.
6. **Inventory agent** computes safety stock, reorder points, stockout probability, expected loss, excess and dead stock.
7. **Alert agent** creates, ranks, deduplicates and expires alerts.
8. **Explainer agent** builds a facts object per alert, asks the LLM for JSON text, validates numbers, falls back to a template when needed.
9. **Action agent (prepare)** creates recommendations (draft PO, supplier message).
10. Results and metrics are stored; the audit log records the run.

### 5.2 Approval and action
1. Planner or Purchaser opens a recommendation and approves, edits or rejects.
2. The decision is stored in `approvals` and audited.
3. The **action service** checks autonomy level, write mode and limits.
4. Executes to the **outbox** (default) or to the connector `write` (only when enabled and supported).
5. Result stored in `actions`; later the **outcomes** job evaluates whether the risk materialized.

### 5.3 Chat
1. Question -> rule-based intent matcher with fuzzy entity match.
2. Fixed query function runs against the database with the user's role.
3. Facts returned to the UI as table/chart; optional LLM phrasing validated by the number validator.
4. Unknown intent -> list of supported questions. No free SQL, no state change.

### 5.4 Learning
Monthly job measures accuracy and outcomes, back-tests candidate changes, writes `param_versions` as `proposed`. An Admin approves; the system applies; rollback restores the previous version.

## 6. Trust boundaries and security zones

| Zone | Trusted? | Notes |
|---|---|---|
| Browser | No | All input validated server-side; strict CSRF/session handling |
| Customer data (files, ERP fields, notes, emails) | **Untrusted data** | Never treated as instructions; sanitized; length-limited |
| API and worker | Trusted code | Authenticated, authorized, audited |
| LLM output | **Untrusted text** | Validated; cannot trigger actions; shown with an "AI-written" or "template" badge |
| Database | Trusted | Credentials in encrypted config; audit table protected by trigger |
| Outbox | Semi-trusted | Written by the app, consumed by humans or other systems; formula-injection safe |
| Vendor package server (optional) | Verified by signature only | Packages must carry a valid signature |

## 7. Deployment views

### 7.1 Linux (primary)
Docker Compose with services `api`, `worker`, `db`; volumes for `/data` (inbox, outbox, models, backups, certs). HTTPS on port 443 with an installer-generated certificate (admin can replace). The offline bundle contains image tarballs, wheels, frontend build, model file, checksums and a signature.

### 7.2 Windows Server (stretch, important for Tally users)
Zip with an embedded Python runtime and either PostgreSQL or the SQLite Starter profile; installed as Windows services; same `scmctl` commands.

### 7.3 Sizing guide

| Tier | Item-series | RAM | Cores | Disk |
|---|---|---|---|---|
| Starter | up to 500 | 8 GB min, 16 GB recommended | 4 | 50 GB min, 100 GB recommended |
| Professional | up to 5,000 | 16 GB | 4 to 8 | 100 GB |
| Regulated | 5,000+ | 32 GB | 8+ | 200 GB |
Numbers are targets to be measured in Phase 1 and Phase 5; update this table with measured results.

## 8. Cross-cutting concerns

- **Configuration:** environment variables and a config file; secrets only in the encrypted store.
- **Observability:** structured JSON logs with rotation; `/health` (minimal) and an admin-only system page with RAM, CPU, disk, model status, last runs; no external monitoring.
- **Error handling:** per-agent isolation; retries with backoff; partial runs flagged; user-friendly messages.
- **Scalability:** vertical scale first; process pool for forecasting; database indexes and a summary cache for the dashboard.
- **Backup and recovery:** encrypted backup of DB, settings, models, license, outbox; tested restore.
- **Updates:** signed packages, automatic pre-update backup, migrations, health check, automatic rollback on failure.
- **Licensing:** signed license, offline activation, feature flags; maintenance expiry blocks newer updates but not use.
- **Internationalization:** string table; number grouping option (lakh/crore).

## 9. Key architecture decisions (see `rfc.md`)

| ID | Decision |
|---|---|
| RFC-001 | Offline-first; local small LLM restricted to language tasks |
| RFC-002 | Three autonomy levels with limits and a downgrade rule |
| RFC-003 | Forecast method selected by backtest per item, with naive baseline |
| RFC-004 | Offline license activation using signed JSON |
| RFC-005 | Learning is proposal-based, versioned and reversible |
| RFC-006 | Outbox as the default write-back target |
| RFC-007 | Retrieval-first chat with a fixed set of intents |

## 10. Known architectural risks

1. Local small models can produce poor text; mitigation is the validator, short outputs and templates.
2. CPU-only inference limits concurrency; mitigation is queued generation and pre-computed explanations during the pipeline run.
3. ERP variety is large; mitigation is a canonical model and per-customer mapping.
4. A single worker holds the run lock; long runs delay manual runs; mitigation is run status in the UI and per-agent timeouts.
5. Windows support adds packaging effort; keep it a separate, later phase.
