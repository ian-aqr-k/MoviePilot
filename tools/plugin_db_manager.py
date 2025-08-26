#!/usr/bin/env python3
"""
Plugin Database Management CLI

A command-line tool for managing the plugin database system.
"""

import sys
import argparse
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.plugin_utils import PluginDatabaseManager, get_plugin_database
from app.log import logger


def cmd_list_plugins(args):
    """List all plugins with databases."""
    plugins = PluginDatabaseManager.list_plugins_with_databases()
    
    if not plugins:
        print("No plugins with databases found.")
        return
    
    print(f"Found {len(plugins)} plugins with databases:")
    for plugin_id in plugins:
        print(f"  - {plugin_id}")


def cmd_plugin_info(args):
    """Show information about a specific plugin."""
    plugin_id = args.plugin_id
    db_api = get_plugin_database(plugin_id)
    
    print(f"Plugin: {plugin_id}")
    print("-" * 50)
    
    # Schema info
    schema_info = db_api.get_schema_info()
    tables = schema_info.get("tables", {})
    
    if tables:
        print(f"Tables ({len(tables)}):")
        for table_name, table_info in tables.items():
            print(f"  - {table_name}")
            print(f"    Columns: {', '.join(table_info['columns'])}")
            if table_info['primary_key']:
                print(f"    Primary Key: {', '.join(table_info['primary_key'])}")
    else:
        print("No tables found.")
    
    # Current revision
    current_revision = db_api.get_current_revision()
    if current_revision:
        print(f"\nCurrent Revision: {current_revision}")
    else:
        print("\nNo migration revisions found.")
    
    # Migration history
    history = db_api.get_migration_history()
    if history:
        print(f"\nMigration History ({len(history)} entries):")
        for rev in history[-5:]:  # Show last 5
            print(f"  - {rev['revision']}: {rev['doc'] or 'No description'}")
    
    # Validation
    validation = db_api.validate_isolation()
    print(f"\nDatabase Isolation: {'✓ Valid' if validation['is_valid'] else '✗ Issues found'}")
    if validation['issues']:
        for issue in validation['issues']:
            print(f"  - {issue}")


def cmd_system_status(args):
    """Show overall system status."""
    status = PluginDatabaseManager.get_system_status()
    
    print("Plugin Database System Status")
    print("=" * 40)
    
    print(f"Health Status: {status['health_status']}")
    print(f"Active Plugins: {len(status['active_plugins'])}")
    print(f"Plugins with Migrations: {len(status['plugins_with_migrations'])}")
    print(f"Plugin Version Tables: {status['total_plugin_version_tables']}")
    
    orphaned = status['orphaned_artifacts']
    if any(orphaned.values()):
        print("\nOrphaned Artifacts Found:")
        if orphaned['version_tables']:
            print(f"  - Version Tables: {orphaned['version_tables']}")
        if orphaned['plugin_tables']:
            print(f"  - Plugin Tables: {orphaned['plugin_tables']}")
        if orphaned['migration_configs']:
            print(f"  - Migration Configs: {orphaned['migration_configs']}")
    else:
        print("\n✓ No orphaned artifacts found.")
    
    validation = status['validation']
    if validation['plugins_with_issues']:
        print(f"\n⚠️  {validation['plugins_with_issues']} plugins have validation issues")
        print(f"Total Issues: {validation['total_issues']}")
    else:
        print("\n✓ All plugins pass validation.")


def cmd_detect_orphans(args):
    """Detect orphaned database artifacts."""
    summary = PluginDatabaseManager.get_orphan_summary()
    
    print("Orphaned Artifacts Detection")
    print("=" * 40)
    
    orphaned_version_tables = summary['orphaned_version_tables']
    orphaned_plugin_tables = summary['orphaned_plugin_tables']
    orphaned_migration_configs = summary['orphaned_migration_configs']
    
    if not any([orphaned_version_tables, orphaned_plugin_tables, orphaned_migration_configs]):
        print("✓ No orphaned artifacts found.")
        return
    
    if orphaned_version_tables:
        print(f"\nOrphaned Version Tables ({len(orphaned_version_tables)}):")
        for table in orphaned_version_tables:
            print(f"  - {table}")
    
    if orphaned_plugin_tables:
        print(f"\nOrphaned Plugin Tables:")
        for plugin_id, tables in orphaned_plugin_tables.items():
            print(f"  Plugin '{plugin_id}' ({len(tables)} tables):")
            for table in tables:
                print(f"    - {table}")
    
    if orphaned_migration_configs:
        print(f"\nOrphaned Migration Configs ({len(orphaned_migration_configs)}):")
        for plugin_id in orphaned_migration_configs:
            print(f"  - {plugin_id}")
    
    print(f"\nUse 'cleanup-orphans --confirm' to remove these artifacts.")


def cmd_cleanup_orphans(args):
    """Clean up orphaned database artifacts."""
    confirm = args.confirm
    
    if not confirm:
        print("Performing dry run (use --confirm to actually clean up)...")
    
    results = PluginDatabaseManager.cleanup_orphans(confirm=confirm)
    
    if confirm:
        print("Cleanup Results:")
        print("=" * 40)
        
        if results['success']:
            print("✓ Cleanup completed successfully.")
        else:
            print("⚠️  Cleanup completed with errors:")
            for error in results['errors']:
                print(f"  - {error}")
    else:
        summary = results['would_cleanup']
        print("\nWould clean up the following:")
        
        if summary['orphaned_version_tables']:
            print(f"  - {len(summary['orphaned_version_tables'])} version tables")
        
        if summary['orphaned_plugin_tables']:
            table_count = sum(len(tables) for tables in summary['orphaned_plugin_tables'].values())
            print(f"  - {table_count} plugin tables from {len(summary['orphaned_plugin_tables'])} plugins")
        
        if summary['orphaned_migration_configs']:
            print(f"  - {len(summary['orphaned_migration_configs'])} migration configs")


def cmd_validate_plugin(args):
    """Validate a specific plugin's database isolation."""
    plugin_id = args.plugin_id
    db_api = get_plugin_database(plugin_id)
    
    validation = db_api.validate_isolation()
    
    print(f"Validation Results for Plugin: {plugin_id}")
    print("=" * 50)
    
    if validation['is_valid']:
        print("✓ Plugin database isolation is valid.")
    else:
        print("✗ Plugin database isolation has issues:")
        for issue in validation['issues']:
            print(f"  - {issue}")


def cmd_create_migration(args):
    """Create a migration for a plugin."""
    plugin_id = args.plugin_id
    message = args.message
    autogenerate = not args.no_autogenerate
    
    db_api = get_plugin_database(plugin_id)
    
    print(f"Creating migration for plugin: {plugin_id}")
    print(f"Message: {message}")
    print(f"Autogenerate: {autogenerate}")
    
    revision_id = db_api.create_migration(message, autogenerate)
    
    if revision_id:
        print(f"✓ Created migration with revision ID: {revision_id}")
    else:
        print("✗ Failed to create migration.")


def cmd_upgrade_plugin(args):
    """Upgrade a plugin's database."""
    plugin_id = args.plugin_id
    revision = args.revision or "head"
    
    db_api = get_plugin_database(plugin_id)
    
    print(f"Upgrading plugin '{plugin_id}' to revision: {revision}")
    
    try:
        db_api.upgrade_database(revision)
        print("✓ Database upgrade completed successfully.")
    except Exception as e:
        print(f"✗ Database upgrade failed: {e}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Plugin Database Management CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List plugins command
    subparsers.add_parser('list', help='List all plugins with databases')
    
    # Plugin info command
    info_parser = subparsers.add_parser('info', help='Show information about a plugin')
    info_parser.add_argument('plugin_id', help='Plugin ID')
    
    # System status command
    subparsers.add_parser('status', help='Show overall system status')
    
    # Detect orphans command
    subparsers.add_parser('detect-orphans', help='Detect orphaned database artifacts')
    
    # Cleanup orphans command
    cleanup_parser = subparsers.add_parser('cleanup-orphans', help='Clean up orphaned database artifacts')
    cleanup_parser.add_argument('--confirm', action='store_true', help='Actually perform cleanup (default is dry run)')
    
    # Validate plugin command
    validate_parser = subparsers.add_parser('validate', help='Validate a plugin\'s database isolation')
    validate_parser.add_argument('plugin_id', help='Plugin ID')
    
    # Create migration command
    migration_parser = subparsers.add_parser('create-migration', help='Create a migration for a plugin')
    migration_parser.add_argument('plugin_id', help='Plugin ID')
    migration_parser.add_argument('message', help='Migration message')
    migration_parser.add_argument('--no-autogenerate', action='store_true', help='Disable autogeneration')
    
    # Upgrade plugin command
    upgrade_parser = subparsers.add_parser('upgrade', help='Upgrade a plugin\'s database')
    upgrade_parser.add_argument('plugin_id', help='Plugin ID')
    upgrade_parser.add_argument('--revision', help='Target revision (default: head)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Command mapping
    commands = {
        'list': cmd_list_plugins,
        'info': cmd_plugin_info,
        'status': cmd_system_status,
        'detect-orphans': cmd_detect_orphans,
        'cleanup-orphans': cmd_cleanup_orphans,
        'validate': cmd_validate_plugin,
        'create-migration': cmd_create_migration,
        'upgrade': cmd_upgrade_plugin,
    }
    
    if args.command in commands:
        try:
            commands[args.command](args)
        except Exception as e:
            print(f"Error: {e}")
            if args.command in ['info', 'validate', 'create-migration', 'upgrade']:
                print("Make sure the plugin exists and has database models.")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()