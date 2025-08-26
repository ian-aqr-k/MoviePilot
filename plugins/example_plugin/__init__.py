"""
Example Plugin with Database Models

This is an example plugin demonstrating how to use the plugin database
management system. It shows best practices for creating isolated database
models and managing migrations.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, func

from app.plugins import _PluginBase
from app.core.plugin_utils import get_plugin_database
from app.log import logger


class ExamplePlugin(_PluginBase):
    """
    Example plugin demonstrating database model usage.
    
    This plugin creates isolated database tables and demonstrates:
    - Model creation with proper naming conventions
    - Database operations using plugin-specific models
    - Migration management
    - Cleanup on uninstall
    """
    
    plugin_name = "示例数据库插件"
    plugin_desc = "演示如何使用插件数据库管理系统的示例插件"
    plugin_icon = "database"
    plugin_version = "1.0.0"
    plugin_author = "MoviePilot Team"
    plugin_order = 99
    
    def __init__(self):
        super().__init__()
        
        # Get plugin database API
        self.db_api = get_plugin_database("example_plugin")
        
        # Initialize models
        self._init_models()
        
        # Set up database on first run
        self._setup_database()
    
    def _init_models(self):
        """Initialize database models."""
        
        # Get plugin base class
        Base = self.db_api.Base
        
        # Define models following naming convention
        class PluginExampleTask(Base):
            """Example task model."""
            __tablename__ = "plugin_example_plugin_task"
            
            id = Column(Integer, primary_key=True)
            name = Column(String(100), nullable=False, index=True)
            description = Column(Text)
            status = Column(String(20), default="pending", index=True)
            created_at = Column(DateTime, default=func.now())
            updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
            completed = Column(Boolean, default=False)
        
        class PluginExampleLog(Base):
            """Example log model."""
            __tablename__ = "plugin_example_plugin_log"
            
            id = Column(Integer, primary_key=True)
            task_id = Column(Integer, index=True)
            level = Column(String(10), default="info", index=True)
            message = Column(Text, nullable=False)
            timestamp = Column(DateTime, default=func.now(), index=True)
        
        # Store model references
        self.Task = PluginExampleTask
        self.Log = PluginExampleLog
        
        logger.info("Example plugin models initialized")
    
    def _setup_database(self):
        """Set up database tables and migrations."""
        try:
            # Create tables if they don't exist
            self.db_api.create_tables()
            
            # Check if we need to create initial migration
            history = self.db_api.get_migration_history()
            if not history:
                # Create initial migration
                revision = self.db_api.create_migration(
                    "Initial example plugin database schema",
                    autogenerate=True
                )
                if revision:
                    logger.info(f"Created initial migration for example plugin: {revision}")
                else:
                    logger.warning("Could not create initial migration for example plugin")
            
            logger.info("Example plugin database setup completed")
            
        except Exception as e:
            logger.error(f"Failed to set up example plugin database: {e}")
    
    def init_plugin(self, config: dict = None):
        """Initialize plugin with configuration."""
        self.info = config or {}
        
        # Validate database isolation
        validation = self.db_api.validate_isolation()
        if validation["is_valid"]:
            logger.info("Example plugin database isolation validated successfully")
        else:
            logger.warning(f"Example plugin database isolation issues: {validation['issues']}")
    
    def get_state(self) -> bool:
        """Get plugin state."""
        return self.get_config("enabled", True)
    
    def stop_service(self):
        """Stop plugin service."""
        pass
    
    def create_task(self, name: str, description: str = None) -> Optional[int]:
        """
        Create a new task.
        
        Args:
            name: Task name
            description: Task description
            
        Returns:
            Task ID if created successfully, None otherwise
        """
        try:
            from app.db import ScopedSession
            
            with ScopedSession() as db:
                task = self.Task(
                    name=name,
                    description=description,
                    status="pending"
                )
                db.add(task)
                db.commit()
                db.refresh(task)
                
                self.log_message(task.id, "info", f"Created task: {name}")
                logger.info(f"Created task {task.id}: {name}")
                return task.id
                
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return None
    
    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        Get task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task dictionary or None if not found
        """
        try:
            from app.db import ScopedSession
            
            with ScopedSession() as db:
                task = db.query(self.Task).filter(self.Task.id == task_id).first()
                if task:
                    return {
                        "id": task.id,
                        "name": task.name,
                        "description": task.description,
                        "status": task.status,
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                        "completed": task.completed
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            return None
    
    def list_tasks(self) -> List[Dict[str, Any]]:
        """
        List all tasks.
        
        Returns:
            List of task dictionaries
        """
        try:
            from app.db import ScopedSession
            
            with ScopedSession() as db:
                tasks = db.query(self.Task).order_by(self.Task.created_at.desc()).all()
                return [
                    {
                        "id": task.id,
                        "name": task.name,
                        "description": task.description,
                        "status": task.status,
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                        "completed": task.completed
                    }
                    for task in tasks
                ]
                
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return []
    
    def update_task_status(self, task_id: int, status: str) -> bool:
        """
        Update task status.
        
        Args:
            task_id: Task ID
            status: New status
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            from app.db import ScopedSession
            
            with ScopedSession() as db:
                task = db.query(self.Task).filter(self.Task.id == task_id).first()
                if task:
                    old_status = task.status
                    task.status = status
                    task.completed = (status == "completed")
                    task.updated_at = datetime.now()
                    db.commit()
                    
                    self.log_message(
                        task_id, "info", 
                        f"Status changed from {old_status} to {status}"
                    )
                    logger.info(f"Updated task {task_id} status to {status}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Failed to update task {task_id} status: {e}")
            return False
    
    def log_message(self, task_id: int, level: str, message: str):
        """
        Log a message for a task.
        
        Args:
            task_id: Task ID
            level: Log level (info, warning, error)
            message: Log message
        """
        try:
            from app.db import ScopedSession
            
            with ScopedSession() as db:
                log_entry = self.Log(
                    task_id=task_id,
                    level=level,
                    message=message
                )
                db.add(log_entry)
                db.commit()
                
        except Exception as e:
            logger.error(f"Failed to log message for task {task_id}: {e}")
    
    def get_task_logs(self, task_id: int) -> List[Dict[str, Any]]:
        """
        Get logs for a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            List of log entry dictionaries
        """
        try:
            from app.db import ScopedSession
            
            with ScopedSession() as db:
                logs = (db.query(self.Log)
                       .filter(self.Log.task_id == task_id)
                       .order_by(self.Log.timestamp.desc())
                       .all())
                
                return [
                    {
                        "id": log.id,
                        "task_id": log.task_id,
                        "level": log.level,
                        "message": log.message,
                        "timestamp": log.timestamp.isoformat() if log.timestamp else None
                    }
                    for log in logs
                ]
                
        except Exception as e:
            logger.error(f"Failed to get logs for task {task_id}: {e}")
            return []
    
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get database information for this plugin.
        
        Returns:
            Dictionary with database information
        """
        try:
            return {
                "schema_info": self.db_api.get_schema_info(),
                "current_revision": self.db_api.get_current_revision(),
                "migration_history": self.db_api.get_migration_history(),
                "validation": self.db_api.validate_isolation()
            }
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {"error": str(e)}
    
    def cleanup_database(self):
        """
        Clean up database when plugin is uninstalled.
        This method should be called during plugin removal.
        """
        try:
            self.db_api.cleanup_on_uninstall()
            logger.info("Example plugin database cleanup completed")
        except Exception as e:
            logger.error(f"Failed to cleanup example plugin database: {e}")
    
    def get_dashboard(self, key: str = None, **kwargs) -> Optional[tuple]:
        """
        Get dashboard information.
        
        Returns:
            Tuple of (dashboard_data, dashboard_config, dashboard_elements)
        """
        try:
            tasks = self.list_tasks()
            completed_tasks = len([t for t in tasks if t["completed"]])
            pending_tasks = len([t for t in tasks if not t["completed"]])
            
            dashboard_data = {
                "total_tasks": len(tasks),
                "completed_tasks": completed_tasks,
                "pending_tasks": pending_tasks,
                "recent_tasks": tasks[:5]  # Show 5 most recent tasks
            }
            
            dashboard_config = {
                "title": "数据库示例插件",
                "subtitle": f"总任务数: {len(tasks)}, 已完成: {completed_tasks}, 待处理: {pending_tasks}"
            }
            
            # Simple dashboard elements showing task statistics
            dashboard_elements = [
                {
                    "type": "card",
                    "title": "任务统计",
                    "content": {
                        "total": len(tasks),
                        "completed": completed_tasks,
                        "pending": pending_tasks
                    }
                }
            ]
            
            return dashboard_data, dashboard_config, dashboard_elements
            
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            return None