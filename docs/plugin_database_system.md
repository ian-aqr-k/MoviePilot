# Plugin Database Management System Documentation

## Overview

The Plugin Database Management System provides isolated, maintainable database support for MoviePilot plugins. Each plugin gets its own database models with enforced naming conventions and migration support.

## Key Features

1. **Isolated metadata**: Each plugin has its own SQLAlchemy Base class and metadata
2. **Enforced naming**: Table names must follow `plugin_{plugin_id}_{model_name}` pattern
3. **Reusable templates**: Plugin alembic configs reuse main database templates
4. **Orphan cleanup**: Automatic detection and cleanup of orphaned database artifacts
5. **Branch isolation**: Plugin migrations operate independently from main app

## Quick Start

### 1. Basic Usage

```python
from app.core.plugin_utils import get_plugin_database
from sqlalchemy import Column, String, Integer, Text

# Get plugin database API
db_api = get_plugin_database("my_plugin")

# Get plugin base class
Base = db_api.Base

# Define model following naming convention
class MyPluginModel(Base):
    __tablename__ = "plugin_my_plugin_mymodel"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    content = Column(Text)

# Create tables
db_api.create_tables()
```

### 2. Using the Plugin Database API

```python
from app.core.plugin_utils import get_plugin_database

class MyPlugin(_PluginBase):
    def __init__(self):
        super().__init__()
        self.db_api = get_plugin_database("my_plugin")
        self._init_models()
    
    def _init_models(self):
        Base = self.db_api.Base
        
        class PluginMyModel(Base):
            __tablename__ = "plugin_my_plugin_model"
            
            id = Column(Integer, primary_key=True)
            name = Column(String(100))
        
        self.Model = PluginMyModel
        
        # Set up database
        self.db_api.create_tables()
```

### 3. Migration Management

```python
# Create a migration
revision_id = db_api.create_migration("Add new column", autogenerate=True)

# Upgrade database
db_api.upgrade_database()

# Get current revision
current = db_api.get_current_revision()

# Get migration history
history = db_api.get_migration_history()
```

## API Reference

### PluginDatabaseAPI

Main API class for plugin database operations.

#### Methods

- `Base`: Property returning SQLAlchemy Base class for the plugin
- `create_tables()`: Create all tables for the plugin
- `drop_tables()`: Drop all tables for the plugin
- `create_migration(message, autogenerate=True)`: Create new migration
- `upgrade_database(revision="head")`: Upgrade to specific revision
- `downgrade_database(revision)`: Downgrade to specific revision
- `get_current_revision()`: Get current database revision
- `get_migration_history()`: Get migration history
- `get_schema_info()`: Get schema information
- `validate_isolation()`: Validate database isolation
- `cleanup_on_uninstall()`: Clean up on plugin removal
- `setup_database()`: Set up database for plugin

### PluginDatabaseManager

System-wide management operations.

#### Static Methods

- `get_plugin_api(plugin_id)`: Get API for specific plugin
- `list_plugins_with_databases()`: List all plugins with databases
- `get_orphan_summary()`: Get orphaned artifacts summary
- `cleanup_orphans(confirm=False)`: Clean up orphaned artifacts
- `validate_all_plugins()`: Validate all plugins
- `get_system_status()`: Get overall system status

## Database Operations

### Creating Models

All plugin models must follow the naming convention:

```python
class MyModel(Base):
    __tablename__ = "plugin_{plugin_id_lowercase}_{model_name_lowercase}"
    
    id = Column(Integer, primary_key=True)
    # ... other columns
```

### Using Models

```python
from app.db import ScopedSession

# Create record
with ScopedSession() as db:
    record = MyModel(name="test")
    db.add(record)
    db.commit()

# Query records
with ScopedSession() as db:
    records = db.query(MyModel).all()
```

## Migration System

Each plugin has its own isolated migration environment:

- Migration files are stored in `plugins_migrations/{plugin_id}/versions/`
- Each plugin has its own version table: `plugin_{plugin_id}_alembic_version`
- Migrations only affect tables belonging to the plugin

### Creating Migrations

```python
# Auto-generate migration from model changes
revision = db_api.create_migration("Description of changes", autogenerate=True)

# Create empty migration
revision = db_api.create_migration("Manual migration", autogenerate=False)
```

### Running Migrations

```python
# Upgrade to latest
db_api.upgrade_database()

# Upgrade to specific revision
db_api.upgrade_database("abc123")

# Downgrade
db_api.downgrade_database("previous_revision")
```

## Orphan Management

The system automatically detects and can clean up orphaned database artifacts:

### Detection

```python
from app.core.plugin_utils import PluginDatabaseManager

# Get orphan summary
summary = PluginDatabaseManager.get_orphan_summary()

print(f"Orphaned version tables: {summary['orphaned_version_tables']}")
print(f"Orphaned plugin tables: {summary['orphaned_plugin_tables']}")
print(f"Orphaned migration configs: {summary['orphaned_migration_configs']}")
```

### Cleanup

```python
# Dry run (see what would be cleaned up)
results = PluginDatabaseManager.cleanup_orphans(confirm=False)

# Actually clean up
results = PluginDatabaseManager.cleanup_orphans(confirm=True)
```

## Best Practices

### 1. Plugin Structure

```
plugins/
├── my_plugin/
│   ├── __init__.py          # Plugin class
│   ├── models.py            # Database models (optional)
│   ├── metadata.json        # Plugin metadata (optional)
│   └── requirements.txt     # Plugin dependencies (optional)
└── plugins_migrations/
    └── my_plugin/
        ├── alembic.ini      # Auto-generated
        ├── env.py           # Auto-generated
        ├── script.py.mako   # Auto-generated
        └── versions/        # Migration files
```

### 2. Model Definition

```python
from app.core.plugin_utils import get_plugin_database
from sqlalchemy import Column, String, Integer, DateTime, func

class MyPlugin(_PluginBase):
    def __init__(self):
        super().__init__()
        self.db_api = get_plugin_database("my_plugin")
        self._init_models()
    
    def _init_models(self):
        Base = self.db_api.Base
        
        class PluginMyModel(Base):
            __tablename__ = "plugin_my_plugin_mymodel"
            
            id = Column(Integer, primary_key=True)
            name = Column(String(100), nullable=False, index=True)
            created_at = Column(DateTime, default=func.now())
        
        self.MyModel = PluginMyModel
        self.db_api.create_tables()
```

### 3. Error Handling

```python
def create_record(self, name):
    try:
        from app.db import ScopedSession
        
        with ScopedSession() as db:
            record = self.MyModel(name=name)
            db.add(record)
            db.commit()
            db.refresh(record)
            return record.id
    except Exception as e:
        logger.error(f"Failed to create record: {e}")
        return None
```

### 4. Plugin Lifecycle

```python
class MyPlugin(_PluginBase):
    def __init__(self):
        # Initialize database
        self.db_api = get_plugin_database("my_plugin")
        self._init_models()
    
    def init_plugin(self, config=None):
        # Validate database state
        validation = self.db_api.validate_isolation()
        if not validation["is_valid"]:
            logger.warning(f"Database issues: {validation['issues']}")
    
    def stop_service(self):
        # Plugin shutdown
        pass
    
    def cleanup_on_uninstall(self):
        # Clean up database when uninstalling
        self.db_api.cleanup_on_uninstall()
```

## Troubleshooting

### Common Issues

1. **Table naming errors**: Ensure table names follow `plugin_{plugin_id}_{model_name}` pattern
2. **Migration conflicts**: Each plugin has isolated migrations; conflicts shouldn't occur
3. **Orphaned tables**: Use `PluginDatabaseManager.cleanup_orphans()` to clean up
4. **Database connection issues**: Check main app database configuration

### Debugging

```python
# Check plugin database status
from app.core.plugin_utils import PluginDatabaseManager

status = PluginDatabaseManager.get_system_status()
print(f"System health: {status['health_status']}")

# Validate specific plugin
db_api = get_plugin_database("my_plugin")
validation = db_api.validate_isolation()
if not validation["is_valid"]:
    print(f"Issues: {validation['issues']}")

# Get schema information
schema = db_api.get_schema_info()
print(f"Tables: {list(schema.get('tables', {}).keys())}")
```

### Database Inspection

```python
# List all plugin databases
plugins = PluginDatabaseManager.list_plugins_with_databases()

# Get migration history
db_api = get_plugin_database("my_plugin")
history = db_api.get_migration_history()

# Check current revision
current = db_api.get_current_revision()
```

## Advanced Usage

### Custom Base Class

```python
from app.core.plugin_models import create_plugin_base, PluginModelMixin

# Create custom base with additional functionality
PluginBase = create_plugin_base("my_plugin")

class CustomBase(PluginBase, PluginModelMixin):
    __abstract__ = True
    
    def to_json(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

# Use custom base
class MyModel(CustomBase):
    __tablename__ = "plugin_my_plugin_mymodel"
    
    name = Column(String(100))
```

### Manual Migration Creation

```python
# Create empty migration for manual editing
revision = db_api.create_migration("Custom migration", autogenerate=False)

# Edit the generated migration file manually
# Location: plugins_migrations/{plugin_id}/versions/{revision}_custom_migration.py
```

## Security Considerations

1. **Isolation**: Each plugin's database artifacts are isolated
2. **Naming enforcement**: Prevents plugins from accessing other plugin tables
3. **Migration isolation**: Plugin migrations can't affect main app or other plugins
4. **Cleanup**: Orphaned artifacts are automatically detected and can be cleaned up

## Performance Considerations

1. **Connection pooling**: Uses same connection pool as main application
2. **Metadata isolation**: Each plugin has separate metadata, reducing conflicts
3. **Migration efficiency**: Only relevant tables are included in migrations
4. **Indexing**: Use appropriate indexes on plugin tables for performance