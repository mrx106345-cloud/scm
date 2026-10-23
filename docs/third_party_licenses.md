# Third-Party Licenses — SCM Agent

This file lists all third-party dependencies used in the SCM Agent project and their licenses. 
All licenses are permissive (MIT, BSD, Apache-2.0, or PSF) as required by `tech-stack.md` section 109.

## Frontend Dependencies (frontend/package.json)

| Package | License | Notes |
|---|---|---|
| react | MIT | Frontend framework |
| react-dom | MIT | DOM rendering |
| react-router-dom | MIT | Routing (v7.18.4, upgraded from 6.28.0 per security audit) |
| react-hook-form | MIT | Form handling |
| react-hot-toast | MIT | Toast notifications |
| zod | MIT | Schema validation |
| @tanstack/react-query | MIT | Data fetching |
| @tanstack/react-table | MIT | Data tables |
| recharts | MIT | Charts |
| tailwind-merge | MIT | Tailwind class merging |
| clsx | MIT | Class name utility |
| @tailwindcss/vite | MIT | Tailwind Vite plugin |
| @testing-library/react | MIT | Testing |
| @testing-library/j-dom | MIT | Testing |
| @testing-library/dom | MIT | Testing |
| @testing-library/user-event | MIT | Testing |
| @commitlint/cli | MIT | Commit linting |
| @commitlint/config-conventional | MIT | Commit linting |
| @eslint/js | MIT | ESLint config |
| @playwright/test | Apache-2.0 | E2E testing |
| vitest | MIT | Test runner |
| eslint | MIT | Linting |
| prettier | MIT | Formatting |
| typescript | Apache-2.0 | Type checking |
| @types/node | MIT | Node.js types |

## Backend Dependencies (backend/pyproject.toml / requirements)

| Package | License | Notes |
|---|---|---|
| FastAPI | MIT | Web framework |
| uvicorn | MIT | ASGI server |
| Gunicorn | MIT | WSGI server |
| SQLAlchemy | MIT | ORM |
| Pydantic | MIT | Validation |
| pydantic-settings | MIT | Settings management |
| Alembic | MIT | Migrations |
| psycopg | MIT | PostgreSQL driver |
| argon2-cffi | BSD-3 | Password hashing |
| PyJWT | MIT | JWT tokens |
| cryptography | MIT | Crypto library |
| structlog | MIT | Logging |
| pytest | MIT | Testing |
| pytest-cov | MIT | Coverage |
| hypothesis | MIT | Property-based testing |
| freezegun | MIT | Time freezing |
| ruff | MIT | Linting |
| mypy | MIT | Type checking |
| bandit | GPL-2.0+ | Security scanning (allowed per tech-stack §109 with approval) |
| pip-audit | MIT | Dependency audit |

## System Libraries (Allowed per tech-stack.md)

| Library | License | Notes |
|---|---|---|
| pandas | BSD-3 | Data analysis |
| numpy | BSD-3 | Numerical computing |
| statsmodels | BSD-3 | Statistics |
| scikit-learn | BSD-3 | ML |
| scipy | BSD-3 | Scientific computing |
| lxml | MIT | XML parsing |
| openpyxl | MIT | Excel reading |
| XlsxWriter | BSD-3 | Excel writing |
| reportlab | BSD-2 | PDF generation |
| matplotlib | MIT | Charts |
| argon2-cffi | BSD-3 | Auth hashing |
| psutil | MIT | System info |

## Local LLM Model

| Item | License | Notes |
|---|---|---|
| Model format | GGUF | 4-bit quantized, ~2 GB |
| llama-cpp-python | MIT | LLM runtime (CPU-only) |
| Model candidates (owner to choose) | Varies | Must permit commercial redistribution; record in `docs/model_selection.md` |

*No hosted AI APIs, telemetry, or analytics at runtime. All data stays on the customer's server per the privacy policy.*

---
*Generated: 2026-10-23. Review on each dependency upgrade.*