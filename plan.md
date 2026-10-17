# SCM Agent Project Plan

This document is a new project plan created from the product and engineering requirements already defined in the repository: `prd.md`, `architecture.md`, `api-spec.md`, `tech-stack.md`, `security-guardrails.md`, and `DEVELOPMENT_SPEC_scm_agent.md`.

It does not replace or alter the existing plan artifacts; it complements them with a practical delivery roadmap and execution plan for the full product lifecycle.

## 1. Project purpose

SCM Agent is an on-premise AI supply-chain risk management system for mid-sized manufacturers. It detects stockout and supplier-delay risk early, explains the causes in plain language, recommends actions, and supports human approval before any write-back occurs.

The product is designed to:
- run fully offline on the customer’s own infrastructure,
- work on CPU-only hardware with modest capacity,
- use a local quantized model for explanation and text generation only,
- keep numbers and decisions generated from deterministic code rather than model output,
- maintain a tamper-evident audit trail for every operational action.

## 2. Strategic outcomes

The project must deliver the following outcomes in order:
1. A reliable forecasting and alerting foundation.
2. Human-in-the-loop approval and outbox-based actioning.
3. Local LLM explanation and chat capabilities without compromising data privacy.
4. Connector and import support across operational data sources.
5. Installer, licensing, update, and backup operations for real customer deployment.
6. Learning, savings reporting, and production hardening.

## 3. Product assumptions and constraints

The project is governed by these baseline constraints:
- Offline-first. No runtime outbound network calls by default.
- CPU-only support; target hardware is 4 cores and 16 GB RAM.
- Local LLM is for phrasing/explanation only; it never makes decisions or calculates numbers.
- Human approval is the default. Auto-act is opt-in and tightly limited.
- All data stays on customer infrastructure unless the user explicitly exports files or backups.
- Auditability is mandatory.
- Security and privacy are equal to product quality requirements.

## 4. Delivery model

The project is structured in six phases. Each phase ends with measurable acceptance checks. The team must finish a phase completely before moving to the next one.

## 5. Phase-by-phase plan

### Phase 1 — Core engine and foundation

Objective:
Build the operational core, data model, import pipeline, forecasting logic, and first alerting flow.

Scope:
- Repo skeleton and development tooling
- Python backend structure with FastAPI and SQLAlchemy
- PostgreSQL schema and Alembic migration setup
- Audit log and hash-chain protections
- User auth, roles, and RBAC
- Synthetic data generator and ground truth data
- CSV/Excel import flow with mapping and idempotent upsert
- Data quality scoring and defect detection
- Forecasting classification and backtesting
- Inventory logic and stockout expected-loss calculations
- Alert generation, ranking, deduplication, and expiry
- Scheduler/orchestrator and pipeline execution flow
- Initial dashboard and alerts UI
- Local dev environment via Docker Compose

Exit criteria:
- Synthetic-data pipeline detects injected stockout risks before simulated stockout.
- Forecasting beats naive baseline on target portion of items.
- Data defect detection rate meets threshold.
- Audit chain verification passes.
- Egress test passes.

### Phase 2 — Local LLM explainer and chat

Objective:
Add explainability and supported chat without violating data privacy or numerical integrity.

Scope:
- LLM interface abstraction with mock and local backend
- llama.cpp backend configuration and model path management
- Prompt design and fact extraction for alert explanations
- Numerical validator with retry and template fallback
- Chat intent matching and fixed supported query functions
- Explanation badge and chat experience in the UI
- Benchmarking tools for latency, memory, and validation performance

Exit criteria:
- Validator passes its cases with zero tolerance for invented numbers.
- Benchmark reports first-pass rate, fallback rate, memory, and speed.
- Supported chat intents behave as designed.
- Unknown queries return safe supported-intent guidance.

### Phase 3 — Supplier risk, approvals, and notes

Objective:
Expand the platform to supplier delay intelligence, operational decisions, and approval workflows.

Scope:
- Supplier metrics and trend detection
- Logistics delay prediction
- Recommendation generation for draft purchase orders and supplier messages
- Approval workflow and recommended action states
- Outbox export generation
- Notes inbox extraction workflow with confirmation gates
- Supplier and item detail pages

Exit criteria:
- Supplier delay warnings appear early enough to influence inventory risk.
- Recommendation transitions are audited and validated.
- Role enforcement matches the specification.
- Prompt-injection defensive tests pass.

### Phase 4 — Connectors, autonomy, and write control

Objective:
Bring in enterprise data sources and controlled execution flows.

Scope:
- SQL connector with read-only validation
- Tally and SAP Business One connector adapters
- Credential encryption and masked responses
- Action controls and autonomy levels
- Direct write path with guard rails and default off state
- Optional Zoho connector behind explicit admin approval and warning

Exit criteria:
- Non-SELECT SQL attempts are rejected.
- Write actions are disabled unless explicit enablement and limits allow them.
- Credentials never leak to logs, responses, or audit payloads.
- Connector sample tests pass.

### Phase 5 — Installer, licensing, update, backup, and operations

Objective:
Prepare the product for customer deployment and long-term support.

Scope:
- `scmctl` precheck, install, update, rollback, backup, and restore utilities
- Linux deployment via Docker Compose and offline bundle packaging
- License generation, validation, tier checks, feature gating
- Signed updates with rollback safety
- Encrypted backups and restore verification
- Support bundle generation and log rotation
- Windows Server stretch support package
- HTTPS setup and admin first-run flow

Exit criteria:
- Offline install works on a clean environment with no internet.
- Update and rollback tests pass.
- License misuse and tampering behaviors match policy.
- Support bundle generation is privacy-safe.

### Phase 6 — Learning, savings, hardening, and documentation

Objective:
Validate business value and harden the product for real-world operation.

Scope:
- Learning agent and controlled parameter version updates
- Savings report with measured vs estimated views and exports
- Final security hardening
- End-to-end regression and performance validation
- User/admin documentation, operational playbooks, and rollout guides

Exit criteria:
- Learning proposals require approval and are reversible.
- Savings reporting is auditable and explainable.
- Performance and resilience meet planned thresholds.
- Product documentation is complete and usable by non-developers.

## 6. Cross-functional workstreams

### Engineering and product
- Product backlog management against phase acceptance criteria
- Architecture decisions and design reviews
- Release readiness checks before each phase gate

### Data and forecasting
- Statistical model selection and synthetic data validation
- Backtesting, threshold calibration, and KPI measurement
- Alert quality validation and false-positive analysis

### Security and governance
- Read-only connector controls
- Secret handling and encryption review
- Audit-chain validation and prompt-injection tests
- Access control reviews and admin approval enforcement

### Frontend and UX
- Dashboard, alert, and approval flows
- Explainability UI and charting
- Role-aware screens and support for operational decisions

### Operations and deployment
- Offline bundle generation
- Precheck and install automation
- Backup/restore validation and support-bundle workflow

## 7. Key milestones and checkpoints

- Milestone 1: Data and forecast foundation working end-to-end
- Milestone 2: Alert generation and explainability usable by planners
- Milestone 3: Supplier and decision workflow ready for approval flows
- Milestone 4: Real connectors and action controls integrated
- Milestone 5: Production installation, licensing, and backup safeguards ready
- Milestone 6: Learning and savings metrics validated for release readiness

## 8. Quality gates

The project must maintain the following gates before each release boundary:
- Unit tests for logic and policy paths
- Integration tests for import, forecasting, and approvals
- Security review for connectors, LLM safety, and file handling
- Audit verification tests for tamper detection
- Performance checks on synthetic data at 200 and 5,000 item scales
- Egress and privacy tests confirming offline-only behavior by default

## 9. Risk register

### Risk: false-positive or false-negative alerts
Mitigation:
- Use backtesting and synthetic-event scoring
- Tune thresholds with explicit acceptance metrics
- Keep alert severity and deduplication logic verified in tests

### Risk: LLM explanation introduces fabricated numbers
Mitigation:
- Require facts-based validation and deterministic fallback text
- Reject any explanation with mismatched numbers
- Keep the LLM outside the calculations path

### Risk: connector or SQL misuse creates data exposure or integrity issues
Mitigation:
- Enforce read-only database access and parse validation
- Mask secrets and never log credentials
- Require human approval for write-enabled paths

### Risk: deployment complexity slows adoption
Mitigation:
- Build installer and precheck early
- Keep offline bundle and update process testable from the start
- Validate compatibility with target OS and hardware limits

## 10. Dependencies and sequencing

Critical dependencies:
- Database and schema before import and forecasting
- Forecasting before alert generation
- Alert generation before approvals and actions
- LLM safety and validation before user-facing explanations
- Connector security before read/write integration
- Installation and license setup before deployment readiness

## 11. Success definition

The project is considered successful when:
- the platform detects risk earlier than the user traditionally sees it,
- users trust explanations and actions because the numbers are computed and validated,
- the system remains offline and secure by default,
- a customer can install, run, back up, and update without requiring network access,
- all phase acceptance tests pass in a reproducible way.

## 12. Recommended next step

Begin implementation with Phase 1 and keep the work aligned to the acceptance measurements in the specification. The order is important: a strong data and forecasting foundation is the prerequisite for operational alerts, approvals, and deployment readiness.
