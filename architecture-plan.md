# SCM Agent Architecture Plan

This document is a new architecture plan derived from the repository’s product and system specification. It is meant to supplement the existing architectural description without modifying the canonical documents already in the project.

## 1. Architecture goals

The architecture is designed around five principles:
1. Offline-first operation and privacy by default.
2. Deterministic business logic with trusted numbers.
3. Human approval as the default control point.
4. Small, maintainable, and auditable runtime components.
5. Clear separation between customer data, system services, and external connectors.

## 2. System context

The system runs as a customer-hosted application on the user’s own server.

```text
Customer environment
  ├─ ERP / SQL databases / local files / spreadsheets
  ├─ Supplier communication and purchase records
  └─ Admin-managed installation and support bundle

                 ┌─────────────────────────────┐
                 │    Web Browser / UI         │
                 │  React + TypeScript         │
                 └──────────────┬──────────────┘
                                │ HTTPS
                                ▼
                 ┌─────────────────────────────┐
                 │  API Layer                  │
                 │  FastAPI + RBAC + session   │
                 └──────────────┬──────────────┘
                                │
                                ▼
                 ┌─────────────────────────────┐
                 │  Core Application Services  │
                 │  orchestrator, auth, audit  │
                 │  workflow, approvals,       │
                 │  forecasting, actions       │
                 └───────┬──────────────┬──────┘
                         │              │
                         │              │
             ┌───────────▼───────┐   ┌──────▼───────────┐
             │ Data + Forecasting│   │  Connectors      │
             │ Agents & Repos    │   │ CSV/SQL/Tally    │
             │ + DB access       │   │ SAP B1 / Zoho    │
             └───────────┬──────┘   └──────┬───────────┘
                         │                  │
                         └──────────┬───────┘
                                    │
                                    ▼
                 ┌─────────────────────────────┐
                 │  Local LLM Layer            │
                 │  llama.cpp + JSON schema    │
                 │  explanation and wording    │
                 └──────────────┬──────────────┘
                                │
                                ▼
                 ┌─────────────────────────────┐
                 │  Storage & Runtime          │
                 │  PostgreSQL + /data        │
                 │  inbox, outbox, models     │
                 └─────────────────────────────┘
```

## 3. Architectural layers

### 3.1 Presentation layer
- React + TypeScript frontend served by the backend.
- Dashboard, alerts, item detail, supplier detail, approvals, admin pages, and chat.
- UI is a client of the API only; it never connects directly to the database or business services.

### 3.2 API layer
- FastAPI app with authentication, RBAC, session management, rate limiting, CSRF protections, and OpenAPI generation.
- Thin endpoints that validate and route requests.
- Central error handling for permission errors, validation errors, license enforcement, and pipeline concurrency issues.

### 3.3 Service layer
This is the business logic core of the product.

Core capabilities:
- Auth and user management
- Pipeline orchestration and scheduling
- Data quality and normalization
- Forecasting, inventory logic, and alerting
- Supplier and logistics analysis
- Recommendation generation and action execution control
- Learning update governance
- Savings analysis and reporting
- Audit and integrity verification

### 3.4 Data access layer
- SQLAlchemy models and repositories for canonical tables.
- PostgreSQL as the production database.
- SQLite only in dev/test profiles.
- All writes and updates are validated through service logic and audit hooks.

### 3.5 Connector layer
The connector layer abstracts ingestion and write operations behind a common protocol.

Supported connector types:
- CSV/Excel
- SQL read-only connector
- Tally connector
- SAP Business One connector
- Optional Zoho connector, disabled by default

Connector responsibilities:
- test connection,
- fetch normalized data,
- reject unsafe SQL or non-permitted operations,
- optionally write only when explicitly enabled.

### 3.6 LLM layer
- local model through `llama-cpp-python`
- prompt-driven explanation and phrasing only
- number validator ensures LLM output contains only values present in the computed facts payload
- template fallback on validation failure

### 3.7 Runtime resources and storage
- Postgres database for transactions and audit tables
- `/data/inbox` for file-based imports
- `/data/outbox` for generated recommendations and export files
- model files stored locally and separate from customer business data
- logs with rotation and minimal metadata

## 4. Runtime components

| Component | Purpose | Key rule |
|---|---|---|
| API service | serves the UI and admin interfaces | no direct database access |
| Worker | executes pipeline jobs and model operations | single-run lock and retries |
| Scheduler | triggers periodic runs | in-process, no external broker |
| DB | stores transactional and audit data | auditable and protected |
| Data pipeline | normalizes, scores, forecasts, and generates alerts | deterministic and testable |
| LLM runtime | generates explanation text only | no decision-making or action capability |
| Outbox | holds approved outputs for human review or import | default write target |
| Connector manager | handles data integration and safety checks | explicit enablement for writes |
| CLI (`scmctl`) | install, verify, backup, restore, support-bundle tooling | offline operations |

## 5. Data-flow architecture

### 5.1 Daily pipeline flow
1. Scheduler triggers a run or user manually starts a run.
2. Orchestrator locks the pipeline and starts the run.
3. Data agent imports or reads source data.
4. Data quality checks reject or quarantine bad records.
5. Forecasting agents generate demand and inventory projections.
6. Supplier and logistics agents compute trend and delay metrics.
7. Alert agent ranks and deduplicates events.
8. Explainer agent builds computed facts and asks the LLM for phrasing.
9. Action agent prepares recommendations and writes outbox artifacts when approved.
10. Audit log records the complete run and approvals.

### 5.2 Recommendation and approval flow
1. Alert is raised with evidence and facts.
2. Recommendation is prepared with cost and benefit estimates.
3. Planner or purchaser decides approve, reject, or edit and approve.
4. Approved action goes to the outbox or connector write path if permitted.
5. Execution result is stored and later evaluated for outcome tracking.

### 5.3 Chat flow
1. User asks a supported question.
2. Rule-based intent matcher interprets the request.
3. Fixed query function reads the database with role enforcement.
4. Structured facts are returned to the LLM as text-generation input only.
5. LLM output is vetted by the number validator before presentation.

## 6. Security architecture

### 6.1 Trust zones
- Browser: untrusted
- API and worker: trusted application code
- Database: trusted system data store
- Customer data files: untrusted, sanitized, and role-limited
- LLM output: untrusted text requiring validation
- Outbox: semi-trusted output generated by the app

### 6.2 Enforcement points
- role-based access checks on every API route
- strict validation of incoming payloads and file uploads
- allow-listing of SQL statements for connector reads
- secret redaction and encryption for credentials
- audit log with tamper-detection checks
- admin approval required for write actions and risky system settings

### 6.3 Security boundaries
- Data cannot leave the server except via explicit user-initiated exports or backups.
- The LLM receives computed facts only, never raw data or secrets.
- Outbound network use is off by default and must be explicitly enabled.
- Any optional outbound features are clearly labeled and logged.

## 7. Data architecture

### 7.1 Core data model groups
- Users, permissions, and settings
- Sites, items, suppliers, and item-supplier mappings
- Inventory snapshots, consumption history, and PO data
- Forecasts and computed inventory parameters
- Supplier metrics and lead-time trends
- Alerts, explanations, recommendations, approvals, and actions
- Param versions and learning updates
- Audit log records and integrity chain

### 7.2 Compliance and integrity model
- UTC timestamps for all records
- Money stored as numeric values in customer currency
- Every state change is written to the audit log
- Hash-chain or append-only verification protects the log against tampering
- System data retention and backup handling are policy-driven

## 8. Deployment architecture

### 8.1 Linux deployment
- Docker Compose environment for API, worker, and DB
- `/data` volume for inbox, outbox, model files, logs, and backups
- HTTPS with generated or admin-supplied certificate
- Offline-bundle packaging for installation and update

### 8.2 Windows Server deployment
- Embedded Python runtime and service installation
- PostgreSQL or SQLite starter profile depending on deployment tier
- Equivalent CLI commands and operational flow

### 8.3 Hardware sizing
- Starter: up to 500 item-series, 8 GB minimum, 16 GB recommended
- Professional: up to 5,000 item-series, 16 GB recommended
- Regulated: 5,000+ and larger infrastructure, 32 GB recommended

## 9. Integration architecture

### 9.1 External integrations
- Read-only SQL and ERP connectors
- Supplier-side information sources
- Optional outbound connectors only when explicitly enabled

### 9.2 Integration quality rules
- connectors are behind a common interface,
- no connector may bypass the application’s validation layer,
- direct writes require the connector to support a write path and the action to be allowed,
- all connection credentials are encrypted and masked in APIs.

## 10. Engineering architecture

### 10.1 Code organization
The codebase is organized around modular responsibilities rather than a single giant service:
- `app/api` for REST endpoints
- `app/core` for system-level services
- `app/connectors` for data-source adapters
- `app/pipeline` for data operations and orchestration
- `app/forecasting` for statistical models and backtesting
- `app/agents` for item, supplier, alert, and recommendation logic
- `app/llm` for prompt, validation, and backend interfaces
- `app/reports` for savings and export logic
- `tests` for logic, security, and regression coverage

### 10.2 Observability and operational model
- Structured JSON logs
- health endpoint and system metrics view for admins
- no external monitoring or crash-reporting services
- support bundle generation with C2/C3/C4 filtering

## 11. Risks to architecture

### Main architectural risks
- Too much confidence placed on LLM-generated text
- Connector write paths becoming too permissive
- Unclear permission boundaries between system roles
- Heavy model runtime and memory pressure on low-end hardware
- Complexity growth from adding connectors before the core pipeline is stable

### Mitigations
- enforce strict validation and templates
- keep write mode default-off
- use role-based authorization mapping and endpoint tests
- benchmark model size and runtime on target hardware
- prefer phase-gated release readiness over broad feature expansion

## 12. Recommended implementation order

1. Build the core schema, pipeline, and forecasting engine.
2. Validate explainability with the LLM layer behind strict numeric controls.
3. Add approval and outbox flows.
4. Integrate connectors and protected write behavior.
5. Add installer, licensing, backup, and update workflows.
6. Finalize learning, savings, and hardening.

This order is intentional: without a stable core, the system cannot safely support approvals, connectors, or deployment operations.
