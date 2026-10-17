# tech-stack.md: Approved Technology Stack

Purpose: stop the coding agent from guessing or adding incompatible libraries. If a library is not on the allowed list, the agent must ask (see `agents.md`).

**Version policy:** use the major version lines below. At build time, resolve to the latest stable release within each line, commit lockfiles (`uv.lock` or `requirements.lock`, `package-lock.json`), and never use `latest` or open ranges in production images. Choose releases at least 2 weeks old. Verify exact APIs from the installed package, not from memory. Every package must install **offline** from the bundle's wheel/npm cache.

---

## 1. Languages and runtimes

| Item | Choice |
|---|---|
| Backend language | Python 3.11 or 3.12 |
| Frontend language | TypeScript 5.x |
| Node (build time only) | Current LTS |
| Database | PostgreSQL 15 or 16 (production); SQLite only for dev/test |
| Containers | Docker Engine + Docker Compose v2 |
| OS targets | Ubuntu 20.04+/22.04+/24.04, Debian 11+, RHEL 8+; Windows Server 2016+ (stretch) |

## 2. Backend libraries (allowed)

| Area | Library | Notes |
|---|---|---|
| Web framework | FastAPI | with Uvicorn (and Gunicorn for multi-worker on Linux) |
| Validation | Pydantic 2.x, pydantic-settings | all inputs and outputs |
| ORM | SQLAlchemy 2.x | typed style; no raw string SQL |
| Migrations | Alembic | |
| DB driver | psycopg 3 | |
| Auth | argon2-cffi (hashing), PyJWT or itsdangerous (sessions/tokens) | no custom crypto |
| Crypto | cryptography | AES-256-GCM, Ed25519 for licenses/updates |
| Scheduling | APScheduler | in-process; no external broker |
| Data | pandas, numpy | |
| Excel | openpyxl, XlsxWriter | read with openpyxl, write with either |
| Forecasting | statsmodels, scikit-learn, scipy | ETS, ARIMA, gradient boosting; Croston/TSB implemented in-house with tests |
| Optimization | OR-Tools or PuLP (pick one in `DECISIONS.md`) | only where needed |
| Fuzzy matching | rapidfuzz | chat entity match |
| Local LLM | llama-cpp-python | GGUF models; configurable path |
| HTTP client | httpx | only for optional named features and tests; blocked by egress guard by default |
| PDF reports | reportlab | |
| Charts for PDF | matplotlib | |
| Templating | Jinja2 | message templates (autoescape on) |
| Logging | structlog or std logging with JSON formatter | |
| Testing | pytest, pytest-cov, pytest-asyncio, hypothesis, freezegun, respx (HTTP mocks) | |
| Quality | ruff, mypy, bandit, pip-audit | |
| CLI | typer | scmctl |
| System info | psutil | precheck |
| Connectors | SQLAlchemy engines for SQL; `lxml` for Tally XML; `zeep` or plain requests-style via httpx for SAP Service Layer (VERIFY) | Tally and SAP details must be verified against samples |

## 3. Frontend libraries (allowed)

| Area | Library |
|---|---|
| Framework | React 18 (or 19 if stable at build time), React Router |
| Build | Vite |
| Language | TypeScript |
| State/data | TanStack Query |
| Forms | React Hook Form + Zod |
| UI components | A small bundled component set (Radix UI primitives + own CSS or Tailwind); no remote assets |
| Charts | Recharts or uPlot (choose one) |
| Tables | TanStack Table |
| Tests | Vitest, React Testing Library, Playwright (end-to-end, dev only) |
| Lint/format | ESLint, Prettier |

Rules: all assets bundled, **no CDN, no Google Fonts, no analytics, no remote scripts**. Fonts shipped locally.

## 4. Packaging and operations

| Area | Choice |
|---|---|
| Linux install | Docker Compose; `scmctl install` |
| Offline bundle | `docker save` tarballs + pip wheelhouse + built frontend + model file + checksums + Ed25519 signature |
| Windows (stretch) | Embedded Python, services via NSSM or native wrapper |
| Backups | `pg_dump` + archive, encrypted with a passphrase (cryptography) |
| TLS | Self-signed certificate generated at install; admin can upload their own |
| SBOM | CycloneDX generation at build (`cyclonedx-bom`) |

## 5. Local LLM policy

| Item | Policy |
|---|---|
| Model size | About 2 GB file, 4-bit quantized GGUF; peak RAM at most 4 GB |
| Candidates | A 3B-class instruction model (examples: Qwen2.5-3B-Instruct, Llama-3.2-3B-Instruct). **The owner chooses after benchmarking and a license check.** The agent must not download or bundle a model without approval. |
| Context | 4096 tokens |
| Output | JSON with a schema; temperature 0.2 (0 on retry) |
| Use | Explanations, answer phrasing, note extraction. Never numbers, decisions, SQL or actions |
| Interface | `LLMBackend` protocol so models and runtimes can be swapped |
| Tests | Use `MockBackend` in unit tests; real model only in `llm_bench` and a few integration tests |

## 6. Explicitly forbidden

| Item | Reason |
|---|---|
| Any hosted AI API (OpenAI, Anthropic, Google, etc.) at runtime | Offline and privacy promise |
| Telemetry, analytics, crash reporters that send data | Privacy promise |
| CDN-loaded scripts, fonts or images | Offline operation |
| Celery, Redis, Kafka, RabbitMQ | Extra moving parts for small servers |
| GPU-only libraries (CUDA-required builds) | CPU-only target |
| LangChain, LlamaIndex, AutoGen and similar agent frameworks | Unneeded complexity; agents are plain Python classes |
| Vector databases and embeddings pipelines (v1) | Retrieval is rule-based; add later through an RFC |
| `eval`, `exec`, `pickle` of untrusted data, shell string commands with user input | Security |
| Unpinned dependencies, packages younger than 2 weeks | Supply-chain risk |
| ORMs other than SQLAlchemy; other web frameworks | Consistency |
| Copyleft-licensed (AGPL/GPL) libraries linked into the product without owner approval | Commercial licensing |

## 7. Licensing hygiene

- Every dependency's license is recorded in `docs/third_party_licenses.md` (generated).
- Allowed by default: MIT, BSD, Apache-2.0, PSF, ISC. Ask before using LGPL/GPL/AGPL, "non-commercial" or "research only" licenses.
- Model license must permit commercial redistribution inside a paid product; record it in `docs/model_selection.md`.

## 8. Compatibility notes the agent must respect

1. `llama-cpp-python` needs a compiler or prebuilt wheel; build wheels in the offline bundle step and test on a clean VM.
2. Many quantized runtimes need CPU AVX2. The pre-check must detect it and warn.
3. `statsmodels` and `scikit-learn` pin numpy ranges; keep one resolved lockfile and test installs from it.
4. Alembic migrations must run on PostgreSQL and (for dev) SQLite; avoid vendor-specific SQL unless guarded.
5. The audit-table "no update/delete" protection is PostgreSQL-specific (rule or trigger); on SQLite dev use a trigger as well and test it.
6. Windows paths and services need separate tests; do not assume POSIX paths in shared code.

## 9. How to change this file
Changes need the owner's approval. The agent proposes in `DECISIONS.md` with: need, alternatives considered, license, size, offline install check, security notes.
