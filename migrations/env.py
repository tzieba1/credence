"""Alembic environment: the URL comes from Settings, the metadata from the models."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from credence.config import Settings
from credence.db.models import Base

config = context.config
if config.config_file_name is not None:
    # Not the template's default: the application's loggers must survive a
    # migration run inside the same process, as in the tests.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# The URL comes from, in order: `alembic -x url=...`, a sqlalchemy.url a test set
# on the Config object, and otherwise the application's settings.
url = (
    context.get_x_argument(as_dictionary=True).get("url")
    or config.get_main_option("sqlalchemy.url")
    or Settings().database_url
)
config.set_main_option("sqlalchemy.url", url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
