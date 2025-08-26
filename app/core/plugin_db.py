"""
Plugin Database Management System

This module provides a decoupled, isolated database management system for plugins.
Each plugin gets its own Base class with isolated metadata to prevent conflicts.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, Type, List
from sqlalchemy import MetaData, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeMeta

from app.core.config import settings
from app.db import Engine, AsyncEngine, SessionFactory, AsyncSessionFactory
from app.log import logger


class PluginDatabaseManager:
    """
    Plugin Database Management System
    
    Manages isolated database models for plugins with enforced naming conventions
    and metadata isolation.
    """
    
    def __init__(self):
        # Registry of plugin base classes
        self._plugin_bases: Dict[str, Type] = {}
        # Registry of plugin metadata
        self._plugin_metadata: Dict[str, Dict[str, Any]] = {}
        # Naming convention pattern
        self._table_name_pattern = re.compile(r'^plugin_([a-z0-9_]+)_([a-z0-9_]+)$')
        
    def create_plugin_base(self, plugin_id: str) -> Type:
        """
        Create an isolated Base class for a plugin with its own metadata.
        
        Args:
            plugin_id: Unique plugin identifier (will be converted to lowercase)
            
        Returns:
            SQLAlchemy declarative base class for the plugin
        """
        plugin_id_lower = plugin_id.lower()
        
        # Check if base already exists
        if plugin_id_lower in self._plugin_bases:
            return self._plugin_bases[plugin_id_lower]
            
        # Create isolated metadata for this plugin
        metadata = MetaData(naming_convention={
            "ix": f"ix_plugin_{plugin_id_lower}_%(column_0_label)s",
            "uq": f"uq_plugin_{plugin_id_lower}_%(table_name)s_%(column_0_name)s",
            "ck": f"ck_plugin_{plugin_id_lower}_%(table_name)s_%(column_0_name)s",
            "fk": f"fk_plugin_{plugin_id_lower}_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": f"pk_plugin_{plugin_id_lower}_%(table_name)s"
        })
        
        # Create declarative base with isolated metadata
        PluginBase = declarative_base(metadata=metadata)
        
        # Add custom table name validation
        def validate_table_name(cls):
            expected_pattern = f"plugin_{plugin_id_lower}_"
            if hasattr(cls, '__tablename__'):
                table_name = cls.__tablename__
                if not table_name.startswith(expected_pattern):
                    raise ValueError(
                        f"Plugin '{plugin_id}' table name '{table_name}' must start with "
                        f"'{expected_pattern}'. Expected format: 'plugin_{plugin_id_lower}_{{model_name_lowercase}}'"
                    )
                
                # Validate full pattern
                if not self._table_name_pattern.match(table_name):
                    raise ValueError(
                        f"Plugin '{plugin_id}' table name '{table_name}' does not match required pattern: "
                        f"'plugin_{{plugin_id_lowercase}}_{{model_name_lowercase}}'"
                    )
            return cls
            
        # Store original __init_subclass__ if it exists
        original_init_subclass = getattr(PluginBase, '__init_subclass__', None)
        
        # Override __init_subclass__ to add validation
        @classmethod
        def __init_subclass__(cls, **kwargs):
            if original_init_subclass:
                original_init_subclass(**kwargs)
            validate_table_name(cls)
            
        PluginBase.__init_subclass__ = __init_subclass__
        
        # Store the base class
        self._plugin_bases[plugin_id_lower] = PluginBase
        
        logger.info(f"Created isolated database base for plugin: {plugin_id}")
        return PluginBase
    
    def get_plugin_base(self, plugin_id: str) -> Optional[Type]:
        """
        Get the Base class for a plugin.
        
        Args:
            plugin_id: Unique plugin identifier
            
        Returns:
            SQLAlchemy declarative base class for the plugin, or None if not found
        """
        return self._plugin_bases.get(plugin_id.lower())
    
    def get_plugin_metadata(self, plugin_id: str) -> Optional[MetaData]:
        """
        Get the metadata object for a plugin.
        
        Args:
            plugin_id: Unique plugin identifier
            
        Returns:
            SQLAlchemy MetaData object for the plugin, or None if not found
        """
        base = self.get_plugin_base(plugin_id)
        return base.metadata if base else None
    
    def get_plugin_tables(self, plugin_id: str) -> List[Table]:
        """
        Get all tables for a plugin.
        
        Args:
            plugin_id: Unique plugin identifier
            
        Returns:
            List of SQLAlchemy Table objects for the plugin
        """
        metadata = self.get_plugin_metadata(plugin_id)
        if not metadata:
            return []
        return list(metadata.tables.values())
    
    def create_plugin_tables(self, plugin_id: str):
        """
        Create all tables for a plugin in the database.
        
        Args:
            plugin_id: Unique plugin identifier
        """
        metadata = self.get_plugin_metadata(plugin_id)
        if metadata:
            metadata.create_all(bind=Engine)
            logger.info(f"Created tables for plugin: {plugin_id}")
        else:
            logger.warning(f"No metadata found for plugin: {plugin_id}")
    
    def drop_plugin_tables(self, plugin_id: str):
        """
        Drop all tables for a plugin from the database.
        
        Args:
            plugin_id: Unique plugin identifier
        """
        metadata = self.get_plugin_metadata(plugin_id)
        if metadata:
            metadata.drop_all(bind=Engine)
            logger.info(f"Dropped tables for plugin: {plugin_id}")
        else:
            logger.warning(f"No metadata found for plugin: {plugin_id}")
    
    def validate_table_name(self, plugin_id: str, table_name: str) -> bool:
        """
        Validate a table name follows the plugin naming convention.
        
        Args:
            plugin_id: Plugin identifier
            table_name: Table name to validate
            
        Returns:
            True if valid, False otherwise
        """
        expected_prefix = f"plugin_{plugin_id.lower()}_"
        return table_name.startswith(expected_prefix) and self._table_name_pattern.match(table_name)
    
    def load_plugin_metadata_config(self, plugin_id: str) -> Dict[str, Any]:
        """
        Load plugin metadata configuration from JSON file in plugin directory.
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            Plugin metadata configuration dictionary
        """
        plugin_dir = Path(settings.ROOT_PATH) / "plugins" / plugin_id.lower()
        metadata_file = plugin_dir / "metadata.json"
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self._plugin_metadata[plugin_id.lower()] = config
                logger.info(f"Loaded metadata config for plugin: {plugin_id}")
                return config
            except Exception as e:
                logger.error(f"Failed to load metadata config for plugin {plugin_id}: {e}")
                return {}
        else:
            logger.debug(f"No metadata config file found for plugin: {plugin_id}")
            return {}
    
    def save_plugin_metadata_config(self, plugin_id: str, config: Dict[str, Any]):
        """
        Save plugin metadata configuration to JSON file in plugin directory.
        
        Args:
            plugin_id: Plugin identifier
            config: Metadata configuration dictionary
        """
        plugin_dir = Path(settings.ROOT_PATH) / "plugins" / plugin_id.lower()
        plugin_dir.mkdir(exist_ok=True)
        metadata_file = plugin_dir / "metadata.json"
        
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self._plugin_metadata[plugin_id.lower()] = config
            logger.info(f"Saved metadata config for plugin: {plugin_id}")
        except Exception as e:
            logger.error(f"Failed to save metadata config for plugin {plugin_id}: {e}")
    
    def unregister_plugin(self, plugin_id: str):
        """
        Unregister a plugin and clean up its base class and metadata.
        
        Args:
            plugin_id: Plugin identifier
        """
        plugin_id_lower = plugin_id.lower()
        self._plugin_bases.pop(plugin_id_lower, None)
        self._plugin_metadata.pop(plugin_id_lower, None)
        logger.info(f"Unregistered plugin: {plugin_id}")
    
    def list_registered_plugins(self) -> List[str]:
        """
        List all registered plugin IDs.
        
        Returns:
            List of plugin IDs
        """
        return list(self._plugin_bases.keys())
    
    def get_plugin_schema_info(self, plugin_id: str) -> Dict[str, Any]:
        """
        Get schema information for a plugin including table names and structure.
        
        Args:
            plugin_id: Plugin identifier
            
        Returns:
            Dictionary containing schema information
        """
        metadata = self.get_plugin_metadata(plugin_id)
        if not metadata:
            return {}
        
        schema_info = {
            "plugin_id": plugin_id,
            "tables": {},
            "table_count": len(metadata.tables)
        }
        
        for table_name, table in metadata.tables.items():
            schema_info["tables"][table_name] = {
                "columns": [col.name for col in table.columns],
                "primary_key": [col.name for col in table.primary_key],
                "foreign_keys": [{"column": fk.parent.name, "references": f"{fk.column.table.name}.{fk.column.name}"} 
                               for fk in table.foreign_keys]
            }
        
        return schema_info


# Global plugin database manager instance
plugin_db_manager = PluginDatabaseManager()