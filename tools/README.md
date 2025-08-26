# Plugin Database Management CLI

A command-line tool for managing the MoviePilot plugin database system.

## Usage

```bash
cd /path/to/MoviePilot
python tools/plugin_db_manager.py <command> [options]
```

## Available Commands

### System Status

```bash
# Show overall system status
python tools/plugin_db_manager.py status
```

Example output:
```
Plugin Database System Status
========================================
Health Status: healthy
Active Plugins: 3
Plugins with Migrations: 2
Plugin Version Tables: 2

✓ No orphaned artifacts found.
✓ All plugins pass validation.
```

### Plugin Management

```bash
# List all plugins with databases
python tools/plugin_db_manager.py list

# Show detailed information about a plugin
python tools/plugin_db_manager.py info my_plugin

# Validate a plugin's database isolation
python tools/plugin_db_manager.py validate my_plugin
```

### Migration Management

```bash
# Create a new migration for a plugin
python tools/plugin_db_manager.py create-migration my_plugin "Add new column"

# Create a manual migration (without autogeneration)
python tools/plugin_db_manager.py create-migration my_plugin "Custom migration" --no-autogenerate

# Upgrade plugin database to latest
python tools/plugin_db_manager.py upgrade my_plugin

# Upgrade to specific revision
python tools/plugin_db_manager.py upgrade my_plugin --revision abc123
```

### Orphan Management

```bash
# Detect orphaned database artifacts
python tools/plugin_db_manager.py detect-orphans

# Clean up orphans (dry run)
python tools/plugin_db_manager.py cleanup-orphans

# Actually clean up orphans
python tools/plugin_db_manager.py cleanup-orphans --confirm
```

## Command Details

### `status`
Shows overall health status of the plugin database system including:
- Health status (healthy/issues_detected)
- Number of active plugins
- Number of plugins with migrations
- Number of plugin version tables
- Orphaned artifacts summary
- Validation results

### `list`
Lists all plugins that have database configurations registered.

### `info <plugin_id>`
Shows detailed information about a specific plugin:
- Database tables and their structure
- Current migration revision
- Migration history (last 5 entries)
- Database isolation validation results

### `validate <plugin_id>`
Validates that a plugin's database artifacts are properly isolated:
- Table naming conventions
- Migration isolation
- Version table integrity

### `detect-orphans`
Scans for orphaned database artifacts:
- Version tables from deleted plugins
- Plugin tables from deleted plugins
- Migration configurations from deleted plugins

### `cleanup-orphans [--confirm]`
Cleans up orphaned database artifacts. Without `--confirm`, performs a dry run showing what would be cleaned up.

### `create-migration <plugin_id> <message> [--no-autogenerate]`
Creates a new migration for a plugin:
- By default, autogenerates migration content based on model changes
- Use `--no-autogenerate` to create an empty migration for manual editing

### `upgrade <plugin_id> [--revision]`
Upgrades a plugin's database:
- Without `--revision`, upgrades to the latest version
- With `--revision`, upgrades to a specific revision

## Examples

### Basic Plugin Setup
```bash
# Check system status
python tools/plugin_db_manager.py status

# Create initial migration for a new plugin
python tools/plugin_db_manager.py create-migration my_plugin "Initial schema"

# Upgrade to apply the migration
python tools/plugin_db_manager.py upgrade my_plugin
```

### Maintenance Tasks
```bash
# Check for orphaned artifacts
python tools/plugin_db_manager.py detect-orphans

# Clean up if any found
python tools/plugin_db_manager.py cleanup-orphans --confirm

# Validate all plugins are properly isolated
python tools/plugin_db_manager.py status
```

### Plugin Development Workflow
```bash
# 1. Make changes to plugin models
# 2. Create migration
python tools/plugin_db_manager.py create-migration my_plugin "Add user preferences table"

# 3. Apply migration
python tools/plugin_db_manager.py upgrade my_plugin

# 4. Validate everything is correct
python tools/plugin_db_manager.py info my_plugin
```

## Error Handling

The CLI tool provides clear error messages and suggestions:

- If a plugin doesn't exist, it will suggest checking the plugin name
- If migrations fail, it will show the specific error
- If validation fails, it will list the specific issues found

## Integration with Plugin Development

Plugin developers can use this tool to:

1. **Monitor database health**: Regular `status` checks ensure the system is healthy
2. **Manage migrations**: Create and apply database schema changes
3. **Debug issues**: Use `info` and `validate` to troubleshoot problems
4. **Clean up**: Remove orphaned artifacts after plugin uninstallation

## Automation

The CLI tool can be used in scripts for automated maintenance:

```bash
#!/bin/bash
# Daily maintenance script

echo "Checking plugin database system health..."
python tools/plugin_db_manager.py status

echo "Detecting orphaned artifacts..."
if python tools/plugin_db_manager.py detect-orphans | grep -q "No orphaned artifacts"; then
    echo "No cleanup needed."
else
    echo "Cleaning up orphaned artifacts..."
    python tools/plugin_db_manager.py cleanup-orphans --confirm
fi
```