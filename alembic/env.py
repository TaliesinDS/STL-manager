import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

# Import your project's metadata object
try:
    from db.models import Base
except Exception:
    # If db package path differs, try alternative import
    from db import models
    Base = models.Base

target_metadata = Base.metadata


def get_url():
    """Resolve the SQLAlchemy URL for migrations.

    Precedence:
    1) URL provided in alembic.ini via Config (set by bootstrap_db.py)
    2) Environment variable STLMGR_DB_URL
    3) Project default SQLite path
    """
    # Prefer value already present in Alembic config
    cfg_url = config.get_main_option('sqlalchemy.url')
    if cfg_url and cfg_url.strip() and cfg_url.strip().lower() != 'driver://user:pass@localhost/dbname':
        return cfg_url
    # Next prefer env var
    env_url = os.environ.get('STLMGR_DB_URL')
    if env_url and env_url.strip():
        return env_url
    # Fallback default: use v1 DB by convention
    return 'sqlite:///./data/stl_manager_v1.db'


def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
