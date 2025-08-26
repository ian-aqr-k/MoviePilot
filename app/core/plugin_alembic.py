"""
Plugin Alembic Integration

This module provides Alembic migration support for plugin database models.
Each plugin gets its own isolated migration environment with branch support.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from alembic.runtime.environment import EnvironmentContext
from alembic.runtime.migration import MigrationContext

from app.core.config import settings
from app.core.plugin_db import plugin_db_manager
from app.db import Engine, AsyncEngine
from app.log import logger


class PluginAlembicManager:
    """
    Manages Alembic configurations and migrations for plugins.
    """
    
    def __init__(self):
        self.main_alembic_dir = Path(settings.ROOT_PATH) / "database"
        self.plugins_migrations_dir = Path(settings.ROOT_PATH) / "plugins_migrations"
        
        # Ensure plugins migrations directory exists
        self.plugins_migrations_dir.mkdir(exist_ok=True)
    
    def create_plugin_alembic_config(self, plugin_id: str) -> Path:
        """
        Create Alembic configuration for a plugin.
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            Path to the plugin's migration directory
        """
        plugin_id_lower = plugin_id.lower()
        plugin_migrations_dir = self.plugins_migrations_dir / plugin_id_lower
        
        # Create plugin migration directory
        plugin_migrations_dir.mkdir(exist_ok=True)
        
        # Create versions directory
        versions_dir = plugin_migrations_dir / "versions"
        versions_dir.mkdir(exist_ok=True)
        
        # Copy and customize env.py
        self._create_plugin_env_py(plugin_id, plugin_migrations_dir)
        
        # Create script.py.mako (reuse from main database)
        self._copy_script_template(plugin_migrations_dir)
        
        # Create alembic.ini for plugin
        self._create_plugin_alembic_ini(plugin_id, plugin_migrations_dir)
        
        logger.info(f"Created Alembic configuration for plugin: {plugin_id}")
        return plugin_migrations_dir
    
    def _create_plugin_env_py(self, plugin_id: str, plugin_dir: Path):
        """Create customized env.py for plugin."""
        env_content = f'''"""
Plugin {plugin_id} Alembic Environment

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
    plugin_base = get_plugin_base("{plugin_id}")
    if plugin_base is not None:
        target_metadata = plugin_base.metadata
    else:
        target_metadata = None
        
except ImportError as e:
    print(f"Warning: Could not import plugin models for {plugin_id}: {{e}}")
    target_metadata = None

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Plugin-specific branch label
branch_labels = "{plugin_id}_plugin"


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
        dialect_opts={{"paramstyle": "named"}},
        render_as_batch=True,  # Support for SQLite
        version_table=f"plugin_{plugin_id}_alembic_version",
        version_table_schema=None,
        include_schemas=False,
        include_object=lambda obj, name, type_, reflected, compare_to: _include_plugin_object(obj, name, type_, reflected, compare_to, "{plugin_id}")
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
            version_table=f"plugin_{plugin_id}_alembic_version",
            version_table_schema=None,
            include_schemas=False,
            include_object=lambda obj, name, type_, reflected, compare_to: _include_plugin_object(obj, name, type_, reflected, compare_to, "{plugin_id}")
        )

        with context.begin_transaction():
            context.run_migrations()


def _include_plugin_object(obj, name, type_, reflected, compare_to, plugin_id):
    """
    Filter objects to only include those belonging to this plugin.
    """
    if type_ == "table":
        # Only include tables that belong to this plugin
        expected_prefix = f"plugin_{{plugin_id.lower()}}_"
        return name.startswith(expected_prefix)
    elif type_ == "index":
        # Include indexes for plugin tables
        if hasattr(obj, 'table') and obj.table is not None:
            expected_prefix = f"plugin_{{plugin_id.lower()}}_"
            return obj.table.name.startswith(expected_prefix)
    elif type_ == "unique_constraint":
        # Include unique constraints for plugin tables
        if hasattr(obj, 'table') and obj.table is not None:
            expected_prefix = f"plugin_{{plugin_id.lower()}}_"
            return obj.table.name.startswith(expected_prefix)
    elif type_ == "foreign_key_constraint":
        # Include foreign keys for plugin tables
        if hasattr(obj, 'table') and obj.table is not None:
            expected_prefix = f"plugin_{{plugin_id.lower()}}_"
            return obj.table.name.startswith(expected_prefix)
    
    return True


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''
        
        env_file = plugin_dir / "env.py"
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(env_content)
    
    def _copy_script_template(self, plugin_dir: Path):
        """Copy script template from main alembic directory."""
        main_template = self.main_alembic_dir / "script.py.mako"
        plugin_template = plugin_dir / "script.py.mako"
        
        if main_template.exists():
            shutil.copy2(main_template, plugin_template)
        else:
            # Create default template if main one doesn't exist
            template_content = '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''
            with open(plugin_template, 'w', encoding='utf-8') as f:
                f.write(template_content)
    
    def _create_plugin_alembic_ini(self, plugin_id: str, plugin_dir: Path):
        """Create alembic.ini for plugin."""
        plugin_id_lower = plugin_id.lower()
        
        # Determine database URL based on configuration
        if settings.DB_TYPE.lower() == "postgresql":
            if settings.DB_POSTGRESQL_PASSWORD:
                db_url = f"postgresql://{settings.DB_POSTGRESQL_USERNAME}:{settings.DB_POSTGRESQL_PASSWORD}@{settings.DB_POSTGRESQL_HOST}:{settings.DB_POSTGRESQL_PORT}/{settings.DB_POSTGRESQL_DATABASE}"
            else:
                db_url = f"postgresql://{settings.DB_POSTGRESQL_USERNAME}@{settings.DB_POSTGRESQL_HOST}:{settings.DB_POSTGRESQL_PORT}/{settings.DB_POSTGRESQL_DATABASE}"
        else:
            db_location = settings.CONFIG_PATH / 'user.db'
            db_url = f"sqlite:///{db_location}"
        
        ini_content = f'''# Plugin {plugin_id} Alembic configuration file

[alembic]
# Path to migration scripts
script_location = {plugin_dir}

# Template used to generate migration file names
file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d_%%(rev)s_%%(slug)s

# sys.path path, will be prepended to sys.path if present.
prepend_sys_path = {settings.ROOT_PATH}

# Timezone to use when rendering the date within the migration file
# timezone = UTC

# max length of characters to apply to the "slug" field
truncate_slug_length = 40

# set to 'true' to run the environment during
# the 'revision' command, regardless of autogenerate
# revision_environment = false

# set to 'true' to allow .pyc and .pyo files without
# a source .py file to be detected as revisions in the
# versions/ directory
# sourceless = false

# version path separator; as mentioned above, this is the character used to split
# version_locations = %(here)s/bar:%(here)s/bat:alembic/versions

# version locations relative to the configuration file; defaults
# to the value of 'version_locations'
# version_path_separator = space

# the output encoding used when revision files
# are written from script.py.mako
# output_encoding = utf-8

sqlalchemy.url = {db_url}

[post_write_hooks]
# post_write_hooks defines scripts or Python functions that are run
# on newly generated revision scripts.  See the documentation for further
# detail and examples

# format using "black" - use the console_scripts runner, against the "black" entrypoint
# hooks = black
# black.type = console_scripts
# black.entrypoint = black
# black.options = -l 79 REVISION_SCRIPT_FILENAME

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
'''
        
        ini_file = plugin_dir / "alembic.ini"
        with open(ini_file, 'w', encoding='utf-8') as f:
            f.write(ini_content)
    
    def get_plugin_alembic_config(self, plugin_id: str) -> Optional[AlembicConfig]:
        """
        Get Alembic configuration for a plugin.
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            Alembic configuration object or None if not found
        """
        plugin_id_lower = plugin_id.lower()
        plugin_dir = self.plugins_migrations_dir / plugin_id_lower
        ini_file = plugin_dir / "alembic.ini"
        
        if not ini_file.exists():
            return None
        
        config = AlembicConfig(str(ini_file))
        return config
    
    def create_plugin_migration(self, plugin_id: str, message: str, autogenerate: bool = True) -> Optional[str]:
        """
        Create a new migration for a plugin.
        
        Args:
            plugin_id: Plugin identifier
            message: Migration message
            autogenerate: Whether to autogenerate migration content
            
        Returns:
            Revision ID of created migration or None on failure
        """
        try:
            config = self.get_plugin_alembic_config(plugin_id)
            if not config:
                # Create config if it doesn't exist
                self.create_plugin_alembic_config(plugin_id)
                config = self.get_plugin_alembic_config(plugin_id)
            
            if not config:
                logger.error(f"Could not create Alembic config for plugin: {plugin_id}")
                return None
            
            # Create revision
            if autogenerate:
                revision = command.revision(config, message, autogenerate=True)
            else:
                revision = command.revision(config, message)
            
            logger.info(f"Created migration for plugin {plugin_id}: {message}")
            return revision.revision if revision else None
            
        except Exception as e:
            logger.error(f"Failed to create migration for plugin {plugin_id}: {e}")
            return None
    
    def upgrade_plugin_database(self, plugin_id: str, revision: str = "head"):
        """
        Upgrade plugin database to specific revision.
        
        Args:
            plugin_id: Plugin identifier
            revision: Target revision (default: "head")
        """
        try:
            config = self.get_plugin_alembic_config(plugin_id)
            if not config:
                logger.warning(f"No Alembic config found for plugin: {plugin_id}")
                return
            
            command.upgrade(config, revision)
            logger.info(f"Upgraded plugin {plugin_id} database to {revision}")
            
        except Exception as e:
            logger.error(f"Failed to upgrade plugin {plugin_id} database: {e}")
    
    def downgrade_plugin_database(self, plugin_id: str, revision: str):
        """
        Downgrade plugin database to specific revision.
        
        Args:
            plugin_id: Plugin identifier
            revision: Target revision
        """
        try:
            config = self.get_plugin_alembic_config(plugin_id)
            if not config:
                logger.warning(f"No Alembic config found for plugin: {plugin_id}")
                return
            
            command.downgrade(config, revision)
            logger.info(f"Downgraded plugin {plugin_id} database to {revision}")
            
        except Exception as e:
            logger.error(f"Failed to downgrade plugin {plugin_id} database: {e}")
    
    def get_plugin_migration_history(self, plugin_id: str) -> List[Dict[str, Any]]:
        """
        Get migration history for a plugin.
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            List of migration information dictionaries
        """
        try:
            config = self.get_plugin_alembic_config(plugin_id)
            if not config:
                return []
            
            script_dir = ScriptDirectory.from_config(config)
            history = []
            
            # Get all revisions in chronological order
            for revision in script_dir.walk_revisions():
                history.append({
                    "revision": revision.revision,
                    "down_revision": revision.down_revision,
                    "branch_labels": revision.branch_labels,
                    "depends_on": revision.depends_on,
                    "doc": revision.doc,
                    "create_date": getattr(revision, 'create_date', None)
                })
            
            # Reverse to get chronological order (oldest first)
            history.reverse()
            return history
            
        except Exception as e:
            logger.error(f"Failed to get migration history for plugin {plugin_id}: {e}")
            return []
    
    def get_current_plugin_revision(self, plugin_id: str) -> Optional[str]:
        """
        Get current database revision for a plugin.
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            Current revision ID or None
        """
        try:
            config = self.get_plugin_alembic_config(plugin_id)
            if not config:
                return None
            
            with Engine.connect() as connection:
                context = MigrationContext.configure(
                    connection,
                    opts={
                        "version_table": f"plugin_{plugin_id.lower()}_alembic_version"
                    }
                )
                return context.get_current_revision()
                
        except Exception as e:
            logger.error(f"Failed to get current revision for plugin {plugin_id}: {e}")
            return None
    
    def remove_plugin_migrations(self, plugin_id: str):
        """
        Remove all migration files and configuration for a plugin.
        
        Args:
            plugin_id: Plugin identifier
        """
        try:
            plugin_id_lower = plugin_id.lower()
            plugin_dir = self.plugins_migrations_dir / plugin_id_lower
            
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
                logger.info(f"Removed migration configuration for plugin: {plugin_id}")
            
            # Also remove version table if it exists
            try:
                with Engine.connect() as connection:
                    version_table = f"plugin_{plugin_id_lower}_alembic_version"
                    connection.execute(f"DROP TABLE IF EXISTS {version_table}")
                    connection.commit()
                    logger.info(f"Removed version table for plugin: {plugin_id}")
            except Exception as e:
                logger.warning(f"Could not remove version table for plugin {plugin_id}: {e}")
                
        except Exception as e:
            logger.error(f"Failed to remove migrations for plugin {plugin_id}: {e}")


# Global plugin alembic manager instance
plugin_alembic_manager = PluginAlembicManager()