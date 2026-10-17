# prd.md: Product Requirements Document

Product: **SCM Agent** (working name). Owner: mrx. Version: 1.0 draft.
Status of numbers: all prices, targets and assumptions here are planning assumptions to be tested with real buyers.

---

## 1. Summary

An on-premise AI system for mid-sized manufacturers that detects supply chain risks early (stockouts, supplier delays, excess stock), explains them in plain language, recommends actions, and, with human approval, prepares or executes them. It runs fully offline on the customer's own server with a small local language model. It is sold as software only (no hardware) under a one-time license plus a yearly maintenance contract.

## 2. Problem

Planners in mid-sized manufacturers run on spreadsheets, ERP reports and email. Late discovery of supplier delays and demand changes causes stockouts, emergency freight and excess inventory. Big planning suites are expensive and cloud-based; many buyers cannot or will not send supply chain data to the cloud.

## 3. Goals and non-goals

### Goals
1. Detect stockout and supplier-delay risk at least 7 days before it happens (measured on synthetic data, then on pilot data).
2. Turn each risk into a clear, ranked alert with a recommended action and the evidence behind it.
3. Keep all customer data on the customer's server; work with no internet.
4. Run on an ordinary mid-size server (4 cores, 16 GB RAM, no GPU).
5. Make installation fast: pre-check, one-command install, guided connection to the customer's data.
6. Prove value in money terms through a savings report with measured and estimated figures kept separate.

### Non-goals (v1)
- Cloud hosting, SaaS billing, mobile apps.
- Selling or configuring hardware.
- Forecasting global markets from internet data.
- Fully autonomous operation by default.
- Replacing the ERP or the planner.

## 4. Users and their needs

| Persona | Needs | Main screens |
|---|---|---|
| **Planner** (supply chain or planning manager) | See what needs attention today, understand why, approve actions fast | Dashboard, Alerts, Approval queue, Item page |
| **Purchaser** | Get ready-to-send draft POs and supplier messages | Approval queue, Supplier page, Outbox |
| **Operations or plant head** | Know which production lines are at risk | Dashboard, Alert detail |
| **Owner or finance head** | See savings and payback in rupees, trust the numbers | Savings report |
| **IT admin** | Install, connect data, manage users, backups, updates, security | Admin, Data and connectors |
| **Vendor support** (the owner's team) | Diagnose problems from a support bundle without access to customer data | Support bundle, logs |

## 5. User stories and acceptance criteria

IDs are referenced in `tasks.md` and the test suite.

### Data and setup
- **US-01** As an Admin I can import my data from CSV/Excel with a column mapping so that the system can start without ERP integration.
  *Accept:* mapping saved and reused; import report lists rejected rows with reasons; re-importing the same file creates no duplicates.
- **US-02** As an Admin I see a data quality score and a fix list so that I know what to correct.
  *Accept:* score and checks follow the spec; critical failures block affected items with a clear message.
- **US-03** As an Admin I can connect a database, Tally or SAP Business One with read-only access.
  *Accept:* connection test; credentials stored encrypted and never shown; only SELECT-type reads possible.
- **US-04** As an Admin I can run a server pre-check before installing.
  *Accept:* pass/warn/fail per check and a tier-fit suggestion.

### Detection and alerts
- **US-05** As a Planner I see a ranked list of alerts so that I work on the most costly risks first.
  *Accept:* alerts ordered by score; severity per spec; duplicates merged; resolved conditions expire.
- **US-06** As a Planner I see why an alert was raised, with the underlying numbers and charts.
  *Accept:* alert detail shows facts, forecast chart, stock projection and supplier lead-time trend.
- **US-07** As a Planner I can read a short plain-language explanation that never contains a number the system did not compute.
  *Accept:* explanation badge shows "AI-written" or "template"; validator failures fall back to the template.
- **US-08** As a Planner I get an early warning when a supplier is getting slower.
  *Accept:* supplier trend flag raised at least 10 days before the resulting stockout in at least 80% of synthetic cases.

### Decisions and actions
- **US-09** As a Planner or Purchaser I can approve, edit or reject a recommendation.
  *Accept:* each decision is audited with user and time; edits are saved with the approval.
- **US-10** As a Purchaser I get a draft purchase order and a supplier message ready to use.
  *Accept:* outputs appear in the outbox as XLSX/CSV/TXT; no data is written to the ERP unless write mode and autonomy allow it.
- **US-11** As an Admin I control autonomy per action type.
  *Accept:* level 1 default; level 3 only when all limits are set, 30 days passed and the admin acknowledged the risk; any breach downgrades to approval.

### Insight and trust
- **US-12** As a Planner I can ask questions in a chat box about my own data.
  *Accept:* six supported intents answered from computed data; unknown questions return a list of supported ones; chat cannot change data.
- **US-13** As an Owner I see a savings report.
  *Accept:* measured vs estimated sections; one-time cash release and yearly saving never summed; assumptions shown; export to XLSX and PDF.
- **US-14** As an Admin I can review and approve system learning updates and roll them back.
  *Accept:* each proposal shows before/after back-test; nothing applies without approval; rollback restores the previous version.
- **US-15** As an Admin I can verify that the audit log has not been tampered with.
  *Accept:* a verify command and endpoint report the first broken record.

### Operations
- **US-16** As an Admin I can back up, restore, update and roll back.
  *Accept:* encrypted backups; update verifies signature and license `max_version`; failed update restores automatically.
- **US-17** As the vendor I can issue a signed license offline and the product enforces tiers.
  *Accept:* tiers and feature flags as in the spec; expired maintenance keeps the product working but blocks newer updates.
- **US-18** As a Customer I can generate a support bundle without secrets for the vendor.
  *Accept:* bundle contains logs, versions, pre-check output; no credentials, no business data.

## 6. Functional requirements (summary; details in `DEVELOPMENT_SPEC_scm_agent.md`)

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | CSV/Excel import with mapping and idempotent upsert | Must |
| FR-02 | Data quality checks and score | Must |
| FR-03 | Demand forecasting with method selection and backtest | Must |
| FR-04 | Inventory parameters, stockout probability, expected loss | Must |
| FR-05 | Alert ranking, dedupe and expiry | Must |
| FR-06 | Local LLM explanations with number validator and template fallback | Must |
| FR-07 | Supplier risk and logistics delay agents | Must (Professional tier) |
| FR-08 | Approval workflow, outbox exports | Must |
| FR-09 | Roles and permissions | Must |
| FR-10 | Tamper-evident audit log | Must |
| FR-11 | Connectors: SQL (read-only), Tally, SAP B1 | Should |
| FR-12 | Autonomy levels and limits | Should |
| FR-13 | Chat over the customer's data | Should |
| FR-14 | Savings report | Should |
| FR-15 | Learning agent with controlled updates | Should |
| FR-16 | Installer, pre-check, offline bundle, update, rollback, backup | Must |
| FR-17 | Licensing and tiers with offline activation | Must |
| FR-18 | Windows Server package | Could (important for Tally users) |
| FR-19 | Optional Zoho connector (outbound, off by default) | Could |

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Privacy | No telemetry, no outbound calls by default; data stays on the customer's server |
| Performance | 200 item-series full run under 2 minutes; 5,000 under 10 minutes on 4 cores; dashboard API p95 under 500 ms (200 items) |
| Resources | Runs on 4 cores, 16 GB RAM; minimum 8 GB; LLM at most about 4 GB RAM |
| Reliability | Pipeline failures isolated per agent; automatic retry; no partial writes that corrupt state |
| Security | See `security-guardrails.md`; encryption at rest for secrets; role-based access; signed releases |
| Auditability | Every state change logged in the hash-chained audit log |
| Usability | A planner can review and approve an alert in under 2 minutes; English first, strings translatable; Indian number grouping option |
| Maintainability | Test coverage at least 80% in core modules; documented migrations; supported-version matrix |
| Compatibility | Linux (primary), Windows Server (stretch); browsers: current Chrome, Edge, Firefox |

## 8. Success metrics

### Product quality (measured in tests)
- At least 80% of injected stockout-risk events flagged at least 7 days ahead (synthetic).
- No more than 3 high/critical false alerts per 100 items per week in event-free periods.
- Forecast method beats naive baseline in WAPE for at least 70% of items.
- Zero explanations shown with a number not present in the computed facts.

### Business (measured in pilots)
- Time from install to first useful alert under 5 working days.
- At least 3 of the first 10 approached buyers agree to a paid pilot.
- Pilot shows a measured or well-justified yearly saving of at least 3x the license price.

## 9. Pricing and packaging (assumptions to validate)

| Tier | Scope | Indicative one-time license (India, Rs lakh) |
|---|---|---|
| Starter | 1 site, 5 users, demand/inventory/alerts, advise mode | 12 |
| Professional | Up to 10 sites, 25 users, all agents, approvals, write-back, learning | 50 |
| Regulated | Unlimited, offline bundle, extended audit | Custom |

Implementation and onboarding guidance fee, and maintenance of about 20% of license per year, apply. Pilot fee is credited to the license on conversion.

## 10. Assumptions and risks

| # | Assumption or risk | How we test or reduce it |
|---|---|---|
| 1 | A 2 GB local model is good enough for explanations | `llm_bench` on real examples; template fallback always available |
| 2 | Buyers' existing servers can run the product | Pre-check report before the pilot |
| 3 | Buyers' data is clean enough | Data quality checker; paid cleanup service |
| 4 | Buyers will pay a one-time license | Paid pilots with 10 target buyers |
| 5 | ERP connectors work across customer versions | Sample exports per customer; mock-based tests; verify per site |
| 6 | Estimated savings are credible to finance heads | Show measured vs estimated; shadow-mode pilot |
| 7 | Small team can support installs | Installer automation, support bundle, scoped maintenance hours |

## 11. Release plan

Phases 1 to 6 in `tasks.md`. Suggested sales milestone: demo after Phase 1, pilot-ready after Phase 3, first licensed installs after Phase 5.

## 12. Open questions for the owner

1. Which industry and ERP first (steel/metals, auto components, other)?
2. Which 2 GB model, after benchmarking and license check?
3. Starter tier: advise-only enough, or does it need approvals?
4. Should the optional Zoho connector be built at all (it needs internet)?
5. Languages beyond English?
6. Default currency and number format (INR with lakh/crore grouping)?
