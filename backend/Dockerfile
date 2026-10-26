# SCM Agent backend image (offline, CPU-only).
# Build: docker build -t scm-agent-backend ../backend
# The app never makes outbound calls; this image only runs uvicorn locally.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

# Install project (production extras only; dev tooling stays out of the image).
COPY pyproject.toml ./
# app must exist before metadata build (setuptools packages.find include=["app*"]).
COPY app ./app
RUN pip install --no-cache-dir --no-build-isolation -e .

# Migrations are applied by SCHEMA via alembic at deployment time; the image
# itself is stateless. Expose the API port only.
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
