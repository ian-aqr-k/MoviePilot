"""
Plugin Orphan Version Management

This module provides utilities to detect and clean up orphaned alembic versions
from deleted plugins, ensuring database consistency.
"""

from pathlib import Path
from typing import List, Dict, Set, Optional, Any
from sqlalchemy import text, inspect, MetaData
from sqlalchemy.exc import NoSuchTableError

from app.core.config import settings
from app.core.plugin_alembic import plugin_alembic_manager
from app.db import Engine
from app.log import logger


class PluginOrphanManager:
    """
    Manages detection and cleanup of orphaned plugin database artifacts.
    """
    
    def __init__(self):
        self.plugins_migrations_dir = Path(settings.ROOT_PATH) / "plugins_migrations"
        self.plugins_dir = Path(settings.ROOT_PATH) / "plugins"
    
    def get_all_plugin_version_tables(self) -> List[str]:
        """
        Get all plugin alembic version tables from the database.
        
        Returns:
            List of plugin version table names
        """
        version_tables = []
        
        try:
            with Engine.connect() as connection:
                inspector = inspect(connection)
                all_tables = inspector.get_table_names()
                
                for table_name in all_tables:
                    if table_name.startswith('plugin_') and table_name.endswith('_alembic_version'):
                        version_tables.append(table_name)
                        
        except Exception as e:
            logger.error(f"Failed to get plugin version tables: {e}")
        
        return version_tables
    
    def get_all_plugin_tables(self) -> Dict[str, List[str]]:
        """
        Get all plugin tables grouped by plugin ID.
        
        Returns:
            Dictionary mapping plugin IDs to their table names
        """
        plugin_tables = {}
        
        try:
            with Engine.connect() as connection:
                inspector = inspect(connection)
                all_tables = inspector.get_table_names()
                
                for table_name in all_tables:
                    if table_name.startswith('plugin_'):
                        # Extract plugin ID from table name
                        parts = table_name.split('_')
                        if len(parts) >= 3:
                            plugin_id = parts[1]  # plugin_{plugin_id}_{model_name}
                            if plugin_id not in plugin_tables:
                                plugin_tables[plugin_id] = []
                            plugin_tables[plugin_id].append(table_name)
                            
        except Exception as e:
            logger.error(f"Failed to get plugin tables: {e}")
        
        return plugin_tables
    
    def get_active_plugins(self) -> Set[str]:
        """
        Get set of active plugin IDs from plugins directory.
        
        Returns:
            Set of active plugin IDs
        """
        active_plugins = set()
        
        if self.plugins_dir.exists():
            for plugin_path in self.plugins_dir.iterdir():
                if plugin_path.is_dir() and not plugin_path.name.startswith('.'):
                    # Check if it has plugin files
                    if (plugin_path / "__init__.py").exists():
                        active_plugins.add(plugin_path.name.lower())
        
        return active_plugins
    
    def get_plugins_with_migrations(self) -> Set[str]:
        """
        Get set of plugin IDs that have migration configurations.
        
        Returns:
            Set of plugin IDs with migration configurations
        """
        plugins_with_migrations = set()
        
        if self.plugins_migrations_dir.exists():
            for migration_path in self.plugins_migrations_dir.iterdir():
                if migration_path.is_dir() and (migration_path / "alembic.ini").exists():
                    plugins_with_migrations.add(migration_path.name.lower())
        
        return plugins_with_migrations
    
    def detect_orphaned_version_tables(self) -> List[str]:
        """
        Detect orphaned plugin version tables.
        
        Returns:
            List of orphaned version table names
        """
        orphaned_tables = []
        version_tables = self.get_all_plugin_version_tables()
        active_plugins = self.get_active_plugins()
        
        for version_table in version_tables:
            # Extract plugin ID from version table name
            # Format: plugin_{plugin_id}_alembic_version
            if version_table.startswith('plugin_') and version_table.endswith('_alembic_version'):
                plugin_id = version_table[7:-16]  # Remove 'plugin_' and '_alembic_version'
                
                if plugin_id not in active_plugins:
                    orphaned_tables.append(version_table)
        
        return orphaned_tables
    
    def detect_orphaned_plugin_tables(self) -> Dict[str, List[str]]:
        """
        Detect orphaned plugin tables by plugin ID.
        
        Returns:
            Dictionary mapping orphaned plugin IDs to their table names
        """
        orphaned_tables = {}
        all_plugin_tables = self.get_all_plugin_tables()
        active_plugins = self.get_active_plugins()
        
        for plugin_id, tables in all_plugin_tables.items():
            if plugin_id not in active_plugins:
                orphaned_tables[plugin_id] = tables
        
        return orphaned_tables
    
    def detect_orphaned_migration_configs(self) -> List[str]:
        """
        Detect orphaned migration configuration directories.
        
        Returns:
            List of orphaned plugin IDs with migration configs
        """
        orphaned_configs = []
        plugins_with_migrations = self.get_plugins_with_migrations()
        active_plugins = self.get_active_plugins()
        
        for plugin_id in plugins_with_migrations:
            if plugin_id not in active_plugins:
                orphaned_configs.append(plugin_id)
        
        return orphaned_configs
    
    def get_orphan_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive summary of all orphaned artifacts.
        
        Returns:
            Dictionary containing orphan summary information
        """
        return {
            "orphaned_version_tables": self.detect_orphaned_version_tables(),
            "orphaned_plugin_tables": self.detect_orphaned_plugin_tables(),
            "orphaned_migration_configs": self.detect_orphaned_migration_configs(),
            "active_plugins": list(self.get_active_plugins()),
            "plugins_with_migrations": list(self.get_plugins_with_migrations()),
            "total_plugin_version_tables": len(self.get_all_plugin_version_tables())
        }
    
    def cleanup_orphaned_version_table(self, version_table: str) -> bool:
        """
        Clean up a specific orphaned version table.
        
        Args:
            version_table: Name of the version table to clean up
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with Engine.connect() as connection:
                # Check if table exists
                inspector = inspect(connection)
                if version_table not in inspector.get_table_names():
                    logger.warning(f"Version table {version_table} does not exist")
                    return True
                
                # Drop the table
                connection.execute(text(f"DROP TABLE {version_table}"))
                connection.commit()
                logger.info(f"Cleaned up orphaned version table: {version_table}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to cleanup version table {version_table}: {e}")
            return False
    
    def cleanup_orphaned_plugin_tables(self, plugin_id: str, table_names: List[str]) -> bool:
        """
        Clean up orphaned tables for a specific plugin.
        
        Args:
            plugin_id: Plugin identifier
            table_names: List of table names to clean up
            
        Returns:
            True if successful, False otherwise
        """
        success = True
        
        try:
            with Engine.connect() as connection:
                inspector = inspect(connection)
                existing_tables = inspector.get_table_names()
                
                for table_name in table_names:
                    if table_name in existing_tables:
                        try:
                            connection.execute(text(f"DROP TABLE {table_name}"))
                            logger.info(f"Dropped orphaned table: {table_name}")
                        except Exception as e:
                            logger.error(f"Failed to drop table {table_name}: {e}")
                            success = False
                
                connection.commit()
                
        except Exception as e:
            logger.error(f"Failed to cleanup tables for plugin {plugin_id}: {e}")
            success = False
        
        return success
    
    def cleanup_orphaned_migration_config(self, plugin_id: str) -> bool:
        """
        Clean up orphaned migration configuration for a plugin.
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            plugin_alembic_manager.remove_plugin_migrations(plugin_id)
            logger.info(f"Cleaned up orphaned migration config for plugin: {plugin_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup migration config for plugin {plugin_id}: {e}")
            return False
    
    def cleanup_all_orphans(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Clean up all orphaned artifacts.
        
        Args:
            confirm: If True, actually perform cleanup. If False, just return what would be cleaned.
            
        Returns:
            Dictionary with cleanup results
        """
        orphan_summary = self.get_orphan_summary()
        cleanup_results = {
            "would_cleanup" if not confirm else "cleaned_up": orphan_summary,
            "success": True,
            "errors": []
        }
        
        if not confirm:
            logger.info("Dry run - would clean up the following orphans:")
            logger.info(f"Version tables: {orphan_summary['orphaned_version_tables']}")
            logger.info(f"Plugin tables: {orphan_summary['orphaned_plugin_tables']}")
            logger.info(f"Migration configs: {orphan_summary['orphaned_migration_configs']}")
            return cleanup_results
        
        # Clean up version tables
        for version_table in orphan_summary['orphaned_version_tables']:
            if not self.cleanup_orphaned_version_table(version_table):
                cleanup_results["success"] = False
                cleanup_results["errors"].append(f"Failed to cleanup version table: {version_table}")
        
        # Clean up plugin tables
        for plugin_id, tables in orphan_summary['orphaned_plugin_tables'].items():
            if not self.cleanup_orphaned_plugin_tables(plugin_id, tables):
                cleanup_results["success"] = False
                cleanup_results["errors"].append(f"Failed to cleanup tables for plugin: {plugin_id}")
        
        # Clean up migration configs
        for plugin_id in orphan_summary['orphaned_migration_configs']:
            if not self.cleanup_orphaned_migration_config(plugin_id):
                cleanup_results["success"] = False
                cleanup_results["errors"].append(f"Failed to cleanup migration config for plugin: {plugin_id}")
        
        if cleanup_results["success"]:
            logger.info("Successfully cleaned up all orphaned artifacts")
        else:
            logger.warning(f"Cleanup completed with errors: {cleanup_results['errors']}")
        
        return cleanup_results
    
    def validate_plugin_isolation(self, plugin_id: str) -> Dict[str, Any]:
        """
        Validate that a plugin's database artifacts are properly isolated.
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "plugin_id": plugin_id,
            "is_valid": True,
            "issues": []
        }
        
        plugin_id_lower = plugin_id.lower()
        
        try:
            with Engine.connect() as connection:
                inspector = inspect(connection)
                all_tables = inspector.get_table_names()
                
                # Check if plugin tables follow naming convention
                for table_name in all_tables:
                    if table_name.startswith(f"plugin_{plugin_id_lower}_"):
                        # Validate naming pattern
                        import re
                        pattern = re.compile(rf'^plugin_{plugin_id_lower}_[a-z0-9_]+$')
                        if not pattern.match(table_name):
                            validation_results["is_valid"] = False
                            validation_results["issues"].append(
                                f"Table {table_name} does not follow proper naming convention"
                            )
                
                # Check version table isolation
                expected_version_table = f"plugin_{plugin_id_lower}_alembic_version"
                if expected_version_table in all_tables:
                    # Verify version table only contains versions for this plugin
                    try:
                        result = connection.execute(
                            text(f"SELECT version_num FROM {expected_version_table}")
                        )
                        versions = [row[0] for row in result]
                        
                        # Check if there are any migration files for this plugin
                        migration_history = plugin_alembic_manager.get_plugin_migration_history(plugin_id)
                        expected_versions = {rev["revision"] for rev in migration_history}
                        
                        # Validate that database versions match migration files
                        db_versions = set(versions)
                        if expected_versions and not expected_versions.issuperset(db_versions):
                            validation_results["is_valid"] = False
                            validation_results["issues"].append(
                                f"Database contains unknown versions: {db_versions - expected_versions}"
                            )
                            
                    except Exception as e:
                        validation_results["issues"].append(f"Could not validate version table: {e}")
        
        except Exception as e:
            validation_results["is_valid"] = False
            validation_results["issues"].append(f"Validation failed: {e}")
        
        return validation_results


# Global plugin orphan manager instance
plugin_orphan_manager = PluginOrphanManager()