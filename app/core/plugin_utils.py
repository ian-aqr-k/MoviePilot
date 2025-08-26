"""
Plugin Database Utilities

This module provides a unified API for plugin developers to easily use
the plugin database management system.
"""

from typing import Type, Dict, Any, List, Optional
from pathlib import Path

from app.core.plugin_db import plugin_db_manager
from app.core.plugin_models import PluginModelMixin, create_plugin_base, PluginDatabaseHelper
from app.core.plugin_alembic import plugin_alembic_manager
from app.core.plugin_orphan import plugin_orphan_manager
from app.log import logger


class PluginDatabaseAPI:
    """
    Unified API for plugin database operations.
    
    This class provides a simple interface for plugin developers to:
    - Create isolated database models
    - Run migrations
    - Manage plugin database lifecycle
    """
    
    def __init__(self, plugin_id: str):
        """
        Initialize plugin database API.
        
        Args:
            plugin_id: Unique plugin identifier
        """
        self.plugin_id = plugin_id.lower()
        self._base = None
    
    @property
    def Base(self) -> Type:
        """
        Get the SQLAlchemy Base class for this plugin.
        
        Returns:
            Plugin-specific Base class with isolated metadata
        """
        if self._base is None:
            self._base = create_plugin_base(self.plugin_id)
        return self._base
    
    def create_model(self, model_name: str, **columns) -> Type:
        """
        Create a database model for this plugin.
        
        Args:
            model_name: Name of the model (will be used in table name)
            **columns: SQLAlchemy column definitions
            
        Returns:
            SQLAlchemy model class
            
        Example:
            ```python
            api = PluginDatabaseAPI("my_plugin")
            
            # Create a model
            MyModel = api.create_model("mymodel",
                name=Column(String(100), nullable=False),
                value=Column(Text),
                created_at=Column(DateTime, default=func.now())
            )
            ```
        """
        from sqlalchemy import Column
        
        # Create table name following convention
        table_name = f"plugin_{self.plugin_id}_{model_name.lower()}"
        
        # Create model class
        attrs = {
            "__tablename__": table_name,
            **columns
        }
        
        # Create the model class inheriting from Base and PluginModelMixin
        model_class = type(model_name, (self.Base, PluginModelMixin), attrs)
        
        logger.info(f"Created model {model_name} for plugin {self.plugin_id}")
        return model_class
    
    def create_tables(self):
        """Create all tables for this plugin in the database."""
        PluginDatabaseHelper.create_tables(self.plugin_id)
    
    def drop_tables(self):
        """Drop all tables for this plugin from the database."""
        PluginDatabaseHelper.drop_tables(self.plugin_id)
    
    def create_migration(self, message: str, autogenerate: bool = True) -> Optional[str]:
        """
        Create a new migration for this plugin.
        
        Args:
            message: Migration message
            autogenerate: Whether to autogenerate migration content
            
        Returns:
            Revision ID of created migration or None on failure
        """
        return plugin_alembic_manager.create_plugin_migration(
            self.plugin_id, message, autogenerate
        )
    
    def upgrade_database(self, revision: str = "head"):
        """
        Upgrade plugin database to specific revision.
        
        Args:
            revision: Target revision (default: "head")
        """
        plugin_alembic_manager.upgrade_plugin_database(self.plugin_id, revision)
    
    def downgrade_database(self, revision: str):
        """
        Downgrade plugin database to specific revision.
        
        Args:
            revision: Target revision
        """
        plugin_alembic_manager.downgrade_plugin_database(self.plugin_id, revision)
    
    def get_current_revision(self) -> Optional[str]:
        """
        Get current database revision for this plugin.
        
        Returns:
            Current revision ID or None
        """
        return plugin_alembic_manager.get_current_plugin_revision(self.plugin_id)
    
    def get_migration_history(self) -> List[Dict[str, Any]]:
        """
        Get migration history for this plugin.
        
        Returns:
            List of migration information dictionaries
        """
        return plugin_alembic_manager.get_plugin_migration_history(self.plugin_id)
    
    def get_schema_info(self) -> Dict[str, Any]:
        """
        Get schema information for this plugin.
        
        Returns:
            Dictionary containing schema information
        """
        return PluginDatabaseHelper.get_schema_info(self.plugin_id)
    
    def validate_isolation(self) -> Dict[str, Any]:
        """
        Validate that this plugin's database artifacts are properly isolated.
        
        Returns:
            Dictionary with validation results
        """
        return plugin_orphan_manager.validate_plugin_isolation(self.plugin_id)
    
    def cleanup_on_uninstall(self):
        """
        Clean up all database artifacts when plugin is uninstalled.
        This should be called during plugin uninstallation.
        """
        # Drop all tables
        self.drop_tables()
        
        # Remove migration configuration
        plugin_alembic_manager.remove_plugin_migrations(self.plugin_id)
        
        # Unregister plugin from manager
        plugin_db_manager.unregister_plugin(self.plugin_id)
        
        logger.info(f"Cleaned up all database artifacts for plugin: {self.plugin_id}")
    
    def setup_database(self):
        """
        Set up database for this plugin.
        This should be called during plugin installation/initialization.
        """
        # Create alembic configuration
        plugin_alembic_manager.create_plugin_alembic_config(self.plugin_id)
        
        # Create tables
        self.create_tables()
        
        # Initialize migration history if needed
        current_revision = self.get_current_revision()
        if current_revision is None:
            # Stamp current state
            try:
                plugin_alembic_manager.upgrade_plugin_database(self.plugin_id, "head")
            except Exception as e:
                logger.warning(f"Could not stamp initial revision for plugin {self.plugin_id}: {e}")
        
        logger.info(f"Set up database for plugin: {self.plugin_id}")


class PluginDatabaseManager:
    """
    Global plugin database manager providing system-wide operations.
    """
    
    @staticmethod
    def get_plugin_api(plugin_id: str) -> PluginDatabaseAPI:
        """
        Get database API for a specific plugin.
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            PluginDatabaseAPI instance
        """
        return PluginDatabaseAPI(plugin_id)
    
    @staticmethod
    def list_plugins_with_databases() -> List[str]:
        """
        List all plugins that have database configurations.
        
        Returns:
            List of plugin IDs
        """
        return plugin_db_manager.list_registered_plugins()
    
    @staticmethod
    def get_orphan_summary() -> Dict[str, Any]:
        """
        Get summary of orphaned database artifacts.
        
        Returns:
            Dictionary containing orphan summary
        """
        return plugin_orphan_manager.get_orphan_summary()
    
    @staticmethod
    def cleanup_orphans(confirm: bool = False) -> Dict[str, Any]:
        """
        Clean up orphaned database artifacts.
        
        Args:
            confirm: If True, actually perform cleanup
            
        Returns:
            Dictionary with cleanup results
        """
        return plugin_orphan_manager.cleanup_all_orphans(confirm)
    
    @staticmethod
    def validate_all_plugins() -> Dict[str, Dict[str, Any]]:
        """
        Validate database isolation for all plugins.
        
        Returns:
            Dictionary mapping plugin IDs to validation results
        """
        validation_results = {}
        plugins = PluginDatabaseManager.list_plugins_with_databases()
        
        for plugin_id in plugins:
            validation_results[plugin_id] = plugin_orphan_manager.validate_plugin_isolation(plugin_id)
        
        return validation_results
    
    @staticmethod
    def get_system_status() -> Dict[str, Any]:
        """
        Get overall system status for plugin databases.
        
        Returns:
            Dictionary with system status information
        """
        orphan_summary = PluginDatabaseManager.get_orphan_summary()
        validation_results = PluginDatabaseManager.validate_all_plugins()
        
        total_issues = sum(
            len(result["issues"]) 
            for result in validation_results.values()
        )
        
        return {
            "active_plugins": orphan_summary["active_plugins"],
            "plugins_with_migrations": orphan_summary["plugins_with_migrations"],
            "total_plugin_version_tables": orphan_summary["total_plugin_version_tables"],
            "orphaned_artifacts": {
                "version_tables": len(orphan_summary["orphaned_version_tables"]),
                "plugin_tables": len(orphan_summary["orphaned_plugin_tables"]),
                "migration_configs": len(orphan_summary["orphaned_migration_configs"])
            },
            "validation": {
                "total_plugins_validated": len(validation_results),
                "plugins_with_issues": sum(1 for r in validation_results.values() if not r["is_valid"]),
                "total_issues": total_issues
            },
            "health_status": "healthy" if total_issues == 0 and all(
                len(orphan_summary[key]) == 0 
                for key in ["orphaned_version_tables", "orphaned_plugin_tables", "orphaned_migration_configs"]
            ) else "issues_detected"
        }


# Convenience functions for plugin developers
def get_plugin_database(plugin_id: str) -> PluginDatabaseAPI:
    """
    Get database API for a plugin.
    
    Args:
        plugin_id: Plugin identifier
        
    Returns:
        PluginDatabaseAPI instance
    """
    return PluginDatabaseManager.get_plugin_api(plugin_id)


def create_plugin_model_base(plugin_id: str) -> Type:
    """
    Create Base class for plugin models.
    
    Args:
        plugin_id: Plugin identifier
        
    Returns:
        SQLAlchemy Base class with PluginModelMixin
    """
    base = create_plugin_base(plugin_id)
    
    # Create a combined base class
    class PluginBase(base, PluginModelMixin):
        __abstract__ = True
    
    return PluginBase