"""Alembic env. Runs on Postgres (prod) and SQLite (dev/test)."""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run in offline (SQL script) mode."""
    url = os.environ.get("SCM_DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run in online (engine) mode."""
    url = os.environ.get("SCM_DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    engine = create_engine(url, future=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
