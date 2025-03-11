import asyncio
import socket
import typing
from logging.config import fileConfig

import sqlalchemy as sa
import sqlalchemy.exc as sa_exc
import sqlalchemy.ext.asyncio as sa_async
from alembic import context, script
from alembic.operations.ops import MigrationScript
from alembic.runtime.migration import MigrationContext
from pydantic_core import MultiHostUrl

from config import AppConfig
from config.users import RDBMSProvider
from services.users.providers.rdbms.models import BaseModel
from utils import password


alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)


target_metadata = BaseModel.metadata


def include_object(
    object: sa.schema.SchemaItem,
    name: str | None,
    type_: typing.Literal["schema", "table", "column", "index", "unique_constraint", "foreign_key_constraint"],
    reflected: bool,
    compare_to: sa.schema.SchemaItem | None,
) -> bool:
    """Allow for an independent migration tree of the current service.

    Works together with a service-specific alembic version table.

    If another service uses the same DB server and schema, the two will not interfere with each other.
    """
    if type_ == "table" and name in target_metadata.tables.keys():
        return True
    return False


def process_revision_directives(
    context: MigrationContext,
    revision: str | typing.Iterable[str] | typing.Iterable[str | None],
    directives: list[MigrationScript],
) -> None:
    """ """
    is_skipped = skip_empty_migration(directives)
    if not is_skipped:
        set_revision_id_to_sequential_int(context, directives)


def skip_empty_migration(directives: list[MigrationScript]) -> bool:
    """ """
    assert alembic_config.cmd_opts is not None
    if getattr(alembic_config.cmd_opts, "autogenerate", False):
        script = directives[0]
        assert script.upgrade_ops is not None
        if script.upgrade_ops.is_empty():
            directives[:] = []
            return True
    return False


def set_revision_id_to_sequential_int(context: MigrationContext, directives: list[MigrationScript]) -> None:
    """ """
    assert context.config is not None
    head_revision = script.ScriptDirectory.from_config(context.config).get_current_head()
    directives[0].rev_id = "{0:04}".format(1 if head_revision is None else int(head_revision) + 1)


def run_migrations_offline(url: MultiHostUrl) -> None:
    """Run migrations in 'offline' mode.

    Configures the `alembic.context` with just a URL and not an `Engine`,
    though an `Engine` is acceptable here as well.
    By skipping the `Engine` creation, there's no need for a DBAPI to be available.

    Calls to `context.execute()` here emit the given string to the script output.
    """
    print(f"\n[MODE: OFF-line] Simulating connection to:\n  {password.get_obscured_password_db_url(url)}\n")
    context.configure(
        url=url.unicode_string(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives,
        # see DocString of 'include_object()' on why we need custom 'include_object' and 'version_table':
        include_object=include_object,
        version_table="alembic_version_users_service",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online(url: MultiHostUrl) -> None:
    """Run migrations in 'online' mode."""

    async def run_async_migrations() -> None:
        """Create an Engine and a new Connection."""

        def run_migrations(connection: sa.Connection) -> None:
            """Associate a Connection with the Context and run the migrations."""
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                process_revision_directives=process_revision_directives,
                # see DocString of 'include_object()' on why we need custom 'include_object' and 'version_table':
                include_object=include_object,
                version_table="alembic_version_users_service",
            )
            with context.begin_transaction():
                context.run_migrations()

        print(f"\n[MODE ON-line] Attempting connection to:\n  {password.get_obscured_password_db_url(url)}\n")
        configuration = alembic_config.get_section(alembic_config.config_ini_section, {})
        configuration["sqlalchemy.url"] = url.unicode_string()
        engine = sa_async.async_engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=sa.pool.NullPool,
        )
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
        await engine.dispose()

    asyncio.run(run_async_migrations())


try:
    url = typing.cast(RDBMSProvider, AppConfig.USERS.PROVIDER_CONFIG).DB_CONNECT_URL
except AttributeError:
    print("\nERROR: cannot find configuration for RDBMS connection\n")
    exit(1)
try:
    if context.is_offline_mode():
        run_migrations_offline(url)
    else:
        run_migrations_online(url)
except (ConnectionRefusedError, sa_exc.OperationalError, socket.gaierror) as err:
    print(f"\nERROR: could not connect to DB:\n  {err}\n")
    exit(1)
