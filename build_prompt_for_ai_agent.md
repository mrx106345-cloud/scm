# BUILD BRIEF: On-premise AI Supply Chain Agent System

Paste this whole file to a coding AI agent (for example Claude Code) as the first message. Work phase by phase. Do not start the next phase until the current phase's acceptance tests pass.

---

## 0. Your role and how to work

You are a senior software engineer building a product from scratch. Build it in small, tested steps.

- Work in **phases** (section 6). After each phase: run all tests, write a short `PROGRESS.md` entry, and stop for review.
- Make sensible default decisions yourself and record them in `DECISIONS.md`. Ask me a question only if you are blocked.
- Write tests for every module. Keep functions small and documented.
- Never add a dependency that needs internet at runtime. Pin all versions.
- Never hardcode secrets. Never send data outside the machine.

## 1. Product in one paragraph

An **on-premise, fully offline** AI system for manufacturers' supply chains. It installs on the customer's own server, reads their data (ERP exports, databases, spreadsheets), finds problems early (stockouts, supplier delays, excess stock), explains them in plain language using a **small local LLM (about 2GB, runs in 4GB RAM, CPU only)**, recommends actions, and executes approved actions. Nothing leaves the customer's server. Sold as a one-time license plus yearly maintenance. **Software only: no hardware, no cloud, no SaaS, no external AI APIs.**

## 2. Hard constraints

1. **No external network calls at runtime.** No cloud APIs, no telemetry. (The installer may optionally fetch packages from a signed package source; an **offline bundle** must also exist.)
2. **CPU only.** Must run on a server with 16GB RAM and 4 cores, no GPU. The LLM must use at most about 4GB RAM.
3. **Numbers come from classical methods, not the LLM.** Forecasting, safety stock and optimization use statistical and OR methods. The LLM is only for summarizing text, explaining alerts, answering chat questions and handling exceptions. Never let the LLM invent numbers: all figures it shows must be passed in from computed data.
4. **Human in the loop.** Three autonomy levels per action type: 1 Advise, 2 Approve then execute, 3 Auto-act within customer-set limits. Default is level 1. Write access to external systems is OFF by default.
5. **Read-only first.** Connectors read only until a customer admin explicitly enables write actions.
6. **Auditability.** Every alert, recommendation, approval, action, model or rule change is logged immutably with user, time and reason.
7. **Controlled learning.** The system may learn from outcomes, but every parameter or model update is versioned, back-tested on historical data, shown to an admin, applied only after approval, and reversible.
8. **Multi-user with roles:** Admin, Planner, Purchaser, Viewer.

## 3. Suggested tech stack (change it if you have a better reason, and record why)

- Language: Python 3.11+ for backend and agents.
- API: FastAPI. Database: PostgreSQL (SQLite allowed for the dev profile).
- Task scheduling: APScheduler or a simple internal job queue (no external broker required).
- Forecasting: statsmodels / scikit-learn / statsforecast-style methods (ETS, ARIMA, Croston for intermittent demand, simple gradient boosting). Optimization: OR-Tools or PuLP.
- Local LLM: `llama-cpp-python` loading a quantized GGUF model of about 2GB. Make the model path configurable and the LLM layer swappable behind an interface.
- Frontend: a simple web app (React or server-rendered templates) served by the backend. Charts with a local library, no CDN.
- Packaging: Docker Compose with an **offline bundle** option (all images and wheels included) plus a native installer script for Linux and Windows Server.
- Auth: local accounts, password hashing, role-based access, session or JWT, optional LDAP later.

## 4. Architecture

```
Connectors (ERP/CSV/DB) -> Data Layer (clean, validate, store)
   -> Agents (coordinated by Orchestrator)
   -> Alert Ranker -> Explainer (local LLM) -> Approval Queue (UI)
   -> Action Agent (writes back only if enabled) -> Audit Log
   -> Learning Agent (measures outcomes, proposes versioned updates)
```

### Agents (each one: clear inputs, outputs, tests)

| Agent | Job |
|---|---|
| Data agent | Pull from connectors on schedule, clean, validate, store |
| Demand agent | Forecast demand per item/site, with error metrics |
| Inventory agent | Reorder points, safety stock, shortage and excess detection |
| Supplier risk agent | Lead-time drift, late-delivery rate, single-supplier dependence |
| Logistics agent | Shipment delay patterns from the customer's own transport data |
| Alert agent | Rank issues by money at risk and urgency |
| Explainer agent | Uses local LLM to write what / why / suggested action, using only supplied facts |
| Action agent | Creates draft POs, reorders and supplier messages; executes only at allowed autonomy level |
| Learning agent | Compare predictions to outcomes, propose versioned parameter updates |

An **Orchestrator** decides run order, handles failures and retries, and routes outputs to humans.

### Connectors (build in this order)

1. CSV/Excel import (with column mapping UI)
2. Generic SQL database (read-only)
3. Tally Prime export / ODBC
4. Zoho and SAP Business One (read first)
5. SAP / Oracle later

Every connector implements one interface: `test_connection()`, `fetch(entity, since)`, and optional `write(entity, payload)` that is disabled by default. Credentials are stored encrypted on the server and never logged.

### Core data entities

Items, sites, suppliers, stock levels, purchase orders, sales/consumption history, lead times, shipments, bills of material (optional), customer orders.

## 5. Features per module

**Data quality checker:** completeness, duplicates, outliers, missing lead times, unit mismatches, item-code inconsistencies. Output a score and a fix list. Block downstream agents on critical failures with a clear message.

**Demand forecasting:** pick the method per item by back-test (fast moving, slow moving, intermittent). Output forecast, prediction interval and error metrics (MAPE/WAPE). Show which method was chosen.

**Inventory logic:** safety stock from demand variability and lead-time variability and a target service level; reorder point; days of cover; excess and dead stock flags.

**Supplier risk:** score from lead-time trend, on-time rate, dependency share. Flag trends early (for example three slower deliveries in a row).

**Alert ranking:** expected money at risk = probability x impact, plus urgency (days to stockout). Deduplicate related alerts.

**Explainer:** prompt templates that receive structured facts and return a short explanation and suggestion. A validator checks that every number in the LLM output exists in the input facts; if not, fall back to a template text. Also supports a chat box limited to the customer's own data.

**Approval queue:** approve, edit, reject with comment. Each item shows the evidence (data and chart).

**Action agent:** draft PO creation, reorder request, supplier message draft. Write-back through connectors only when write mode and autonomy level allow. Every action has an undo or cancel note where the target system allows it.

**Savings report:** tracks decisions taken, outcome, and estimated savings (avoided stockouts, lower expedite cost, lower inventory) so the owner can see payback. Mark estimates clearly as estimates.

**Learning agent:** monthly job. Computes forecast error and decision outcome stats, proposes parameter changes, back-tests them, and puts them in an admin approval screen with before/after comparison.

**Admin:** user and role management, connector setup wizard, autonomy settings per action type, audit log viewer, backup and restore, license status.

## 6. Phases and acceptance criteria

### Phase 1: Core MVP (advise mode only)
Build: project skeleton, DB schema, CSV/Excel connector with mapping, data quality checker, demand agent, inventory agent, alert ranking, simple UI (dashboard, alert list, alert detail), audit log, roles, **synthetic data generator** (at least 200 items, 3 years history, injected supplier delays and demand spikes).
Accept when: running on synthetic data detects the injected stockout risks with at least 80% recall, all tests pass, and the app runs on 16GB RAM with no GPU and no internet.

### Phase 2: Local LLM explainer and chat
Build: LLM interface plus llama.cpp backend, prompt templates, number validator, chat limited to local data, performance limits.
Accept when: every explanation's numbers match computed facts (validator test with 100 cases), LLM peak RAM is at most 4GB, and a response arrives within a stated time on a 4-core CPU (record the measured time).

### Phase 3: Supplier risk, logistics, approval workflow
Build: supplier risk agent, logistics agent, approval queue, orchestrator with retries, notifications inside the app (email via customer SMTP optional).
Accept when: injected supplier delays are flagged at least 7 days before the stockout in synthetic tests, and approval states are fully audited.

### Phase 4: Connectors and action agent
Build: SQL and Tally connectors, Zoho/SAP B1 read connectors, action agent with write mode OFF by default, autonomy settings, draft PO creation.
Accept when: connector tests run against mock servers, write calls are impossible while write mode is off (negative tests), and credentials never appear in logs.

### Phase 5: Installer, pre-check and licensing
Build: server pre-check (RAM, CPU, disk, OS with pass or fail report and tier suggestion), installer script, offline bundle, license key with **offline activation** (signed key, tier, expiry, version), update mechanism with signed packages and rollback, backup and restore.
Accept when: a clean VM installs with one command, pre-check reports correctly on an underpowered machine, an invalid or expired license limits features gracefully, and an update can be rolled back.

### Phase 6: Learning, savings report, hardening
Build: learning agent with versioned updates and approval, savings report, security review (dependency audit, input validation, role checks), documentation (admin guide, user guide, connector guide).
Accept when: a proposed update is back-tested, approved, applied and rolled back in a test, and the savings report reconciles with decisions logged.

## 7. Security requirements

- Passwords hashed (argon2 or bcrypt). Role checks on every endpoint.
- Secrets encrypted at rest; key managed by the installer.
- Signed installers and updates; verify checksums.
- Input validation on all imports; protect against CSV injection and SQL injection.
- Prompt-injection safety: text from emails or notes is treated as data, never as instructions to the LLM or agents.
- No outbound network connections unless an admin enables a named optional feature. Provide a test that fails if the app opens an unexpected outbound connection.

## 8. Testing rules

- Unit tests for each agent and connector; integration tests for the full flow on synthetic data.
- Back-test harness for forecasting methods with stored metrics.
- Performance tests for RAM and response time on a 4-core, 16GB, no-GPU environment.
- Keep test data synthetic. Never include real customer data.

## 9. Out of scope (do NOT build)

Cloud hosting, SaaS billing, hardware sales or appliances, external AI APIs, global market prediction from internet data, mobile apps, anything that sends customer data out.

## 10. Deliverables after each phase

Working code, tests passing, updated `README.md`, `PROGRESS.md`, `DECISIONS.md`, and a short demo script showing the new features on synthetic data.

## 11. Start now

Begin with **Phase 1**. First, write a short plan (folder structure, DB schema, list of modules) in `DECISIONS.md`, then build.
