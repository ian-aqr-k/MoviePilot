"""
Plugin test_comprehensive Alembic Environment

This is a plugin-specific Alembic environment that operates independently
from the main application migrations.
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import plugin base and models
try:
    from app.core.plugin_db import plugin_db_manager
    from app.core.plugin_models import get_plugin_base
    
    # Get plugin base and metadata
    plugin_base = get_plugin_base("test_comprehensive")
    if plugin_base is not None:
        target_metadata = plugin_base.metadata
    else:
        target_metadata = None
        
except ImportError as e:
    print(f"Warning: Could not import plugin models for test_comprehensive: {e}")
    target_metadata = None

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Plugin-specific branch label
branch_labels = "test_comprehensive_plugin"


def get_plugin_url():
    """Get database URL for plugin migrations."""
    # Use same database as main app but with plugin branch isolation
    main_url = config.get_main_option("sqlalchemy.url")
    return main_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_plugin_url()
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Support for SQLite
        version_table=f"plugin_test_comprehensive_alembic_version",
        version_table_schema=None,
        include_schemas=False,
        include_object=lambda obj, name, type_, reflected, compare_to: _include_plugin_object(obj, name, type_, reflected, compare_to, "test_comprehensive")
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Create connectable
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # Support for SQLite
            version_table=f"plugin_test_comprehensive_alembic_version",
            version_table_schema=None,
            include_schemas=False,
            include_object=lambda obj, name, type_, reflected, compare_to: _include_plugin_object(obj, name, type_, reflected, compare_to, "test_comprehensive")
        )

        with context.begin_transaction():
            context.run_migrations()


def _include_plugin_object(obj, name, type_, reflected, compare_to, plugin_id):
    """
    Filter objects to only include those belonging to this plugin.
    """
    if type_ == "table":
        # Only include tables that belong to this plugin
        expected_prefix = f"plugin_{plugin_id.lower()}_"
        return name.startswith(expected_prefix)
    elif type_ == "index":
        # Include indexes for plugin tables
        if hasattr(obj, 'table') and obj.table is not None:
            expected_prefix = f"plugin_{plugin_id.lower()}_"
            return obj.table.name.startswith(expected_prefix)
    elif type_ == "unique_constraint":
        # Include unique constraints for plugin tables
        if hasattr(obj, 'table') and obj.table is not None:
            expected_prefix = f"plugin_{plugin_id.lower()}_"
            return obj.table.name.startswith(expected_prefix)
    elif type_ == "foreign_key_constraint":
        # Include foreign keys for plugin tables
        if hasattr(obj, 'table') and obj.table is not None:
            expected_prefix = f"plugin_{plugin_id.lower()}_"
            return obj.table.name.startswith(expected_prefix)
    
    return True


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
