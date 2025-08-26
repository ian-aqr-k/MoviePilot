"""
Plugin Database Base Classes

Provides convenient base classes for plugin database models with automatic
table name generation and validation.
"""

from typing import Any, Dict, Optional
from sqlalchemy import Column, Integer, Sequence, Identity
from sqlalchemy.orm import declared_attr
from app.core.config import settings
from app.core.plugin_db import plugin_db_manager
from app.db import db_query, db_update, async_db_query, async_db_update


def get_plugin_id_column():
    """
    Get appropriate ID column definition based on database type (same as main app).
    
    Returns:
        SQLAlchemy Column for ID field
    """
    if settings.DB_TYPE.lower() == "postgresql":
        # PostgreSQL uses SERIAL type, let database handle sequence
        return Column(Integer, Identity(start=1, cycle=True), primary_key=True, index=True)
    else:
        # SQLite uses Sequence
        return Column(Integer, Sequence('id'), primary_key=True, index=True)


class PluginModelMixin:
    """
    Mixin class providing common functionality for plugin models.
    
    This mixin provides the same database operation methods as the main Base class,
    but works with plugin-specific base classes.
    """
    
    # Allow unmapped annotations for compatibility
    __allow_unmapped__ = True
    
    # ID column
    id = get_plugin_id_column()
    
    @declared_attr
    def __tablename__(cls) -> str:
        """
        Generate table name following plugin naming convention.
        
        Format: plugin_{plugin_id}_{model_name}
        
        Returns:
            Generated table name
        """
        # Extract plugin_id from class module path
        module_path = cls.__module__
        if 'plugins.' in module_path:
            # Extract plugin ID from module path like 'plugins.myplugin.models'
            parts = module_path.split('.')
            plugin_id = None
            for i, part in enumerate(parts):
                if part == 'plugins' and i + 1 < len(parts):
                    plugin_id = parts[i + 1]
                    break
            
            if plugin_id:
                model_name = cls.__name__.lower()
                return f"plugin_{plugin_id.lower()}_{model_name}"
        
        # Fallback to default naming if plugin ID cannot be determined
        return f"plugin_unknown_{cls.__name__.lower()}"
    
    @db_update
    def create(self, db):
        """Create record in database."""
        db.add(self)
    
    @async_db_update
    async def async_create(self, db):
        """Create record in database (async)."""
        db.add(self)
        await db.flush()
        return self
    
    @classmethod
    @db_query
    def get(cls, db, rid: int):
        """Get record by ID."""
        return db.query(cls).filter(cls.id == rid).first()
    
    @classmethod
    @async_db_query
    async def async_get(cls, db, rid: int):
        """Get record by ID (async)."""
        from sqlalchemy import select
        result = await db.execute(select(cls).where(cls.id == rid))
        return result.scalars().first()
    
    @db_update
    def update(self, db, payload: Dict[str, Any]):
        """Update record with payload."""
        payload = {k: v for k, v in payload.items() if v is not None}
        for key, value in payload.items():
            setattr(self, key, value)
        from sqlalchemy import inspect
        if inspect(self).detached:
            db.add(self)
    
    @async_db_update
    async def async_update(self, db, payload: Dict[str, Any]):
        """Update record with payload (async)."""
        payload = {k: v for k, v in payload.items() if v is not None}
        for key, value in payload.items():
            setattr(self, key, value)
        from sqlalchemy import inspect
        if inspect(self).detached:
            db.add(self)
    
    @classmethod
    @db_update
    def delete(cls, db, rid):
        """Delete record by ID."""
        db.query(cls).filter(cls.id == rid).delete()
    
    @classmethod
    @async_db_update
    async def async_delete(cls, db, rid):
        """Delete record by ID (async)."""
        from sqlalchemy import select
        result = await db.execute(select(cls).where(cls.id == rid))
        record = result.scalars().first()
        if record:
            await db.delete(record)
    
    @classmethod
    @db_update
    def truncate(cls, db):
        """Delete all records."""
        db.query(cls).delete()
    
    @classmethod
    @async_db_update
    async def async_truncate(cls, db):
        """Delete all records (async)."""
        from sqlalchemy import delete
        await db.execute(delete(cls))
    
    @classmethod
    @db_query
    def list(cls, db):
        """List all records."""
        return db.query(cls).all()
    
    @classmethod
    @async_db_query
    async def async_list(cls, db):
        """List all records (async)."""
        from sqlalchemy import select
        result = await db.execute(select(cls))
        return result.scalars().all()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary."""
        return {c.name: getattr(self, c.name, None) for c in self.__table__.columns}


def create_plugin_base(plugin_id: str):
    """
    Create a base class for plugin database models.
    
    Args:
        plugin_id: Unique plugin identifier
        
    Returns:
        Base class for plugin models with isolated metadata
        
    Example:
        ```python
        # In your plugin code:
        from app.core.plugin_models import create_plugin_base
        
        Base = create_plugin_base("my_plugin")
        
        class MyModel(Base, PluginModelMixin):
            __tablename__ = "plugin_my_plugin_mymodel"
            
            name = Column(String(100))
            value = Column(String(500))
        ```
    """
    return plugin_db_manager.create_plugin_base(plugin_id)


def get_plugin_base(plugin_id: str):
    """
    Get existing base class for a plugin.
    
    Args:
        plugin_id: Unique plugin identifier
        
    Returns:
        Base class for plugin models, or None if not found
    """
    return plugin_db_manager.get_plugin_base(plugin_id)


class PluginDatabaseHelper:
    """
    Helper class for plugin database operations.
    """
    
    @staticmethod
    def create_tables(plugin_id: str):
        """Create all tables for a plugin."""
        plugin_db_manager.create_plugin_tables(plugin_id)
    
    @staticmethod
    def drop_tables(plugin_id: str):
        """Drop all tables for a plugin."""
        plugin_db_manager.drop_plugin_tables(plugin_id)
    
    @staticmethod
    def get_schema_info(plugin_id: str) -> Dict[str, Any]:
        """Get schema information for a plugin."""
        return plugin_db_manager.get_plugin_schema_info(plugin_id)
    
    @staticmethod
    def validate_table_name(plugin_id: str, table_name: str) -> bool:
        """Validate table name follows plugin conventions."""
        return plugin_db_manager.validate_table_name(plugin_id, table_name)
    
    @staticmethod
    def load_metadata_config(plugin_id: str) -> Dict[str, Any]:
        """Load plugin metadata configuration."""
        return plugin_db_manager.load_plugin_metadata_config(plugin_id)
    
    @staticmethod
    def save_metadata_config(plugin_id: str, config: Dict[str, Any]):
        """Save plugin metadata configuration."""
        plugin_db_manager.save_plugin_metadata_config(plugin_id, config)