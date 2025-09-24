"""
Workflow Log Manager - S3-based workflow logging system for tracking workflow runs and errors.

This module provides comprehensive workflow logging functionality with S3 storage,
error tracking, and traceback collection for the agentic intelligence workflow system.
"""

import json
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum
import logging
import uuid
import traceback
import sys


class WorkflowStatus(Enum):
    """Workflow run status enumeration."""
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class WorkflowLogEntry:
    """Represents a single workflow log entry."""
    
    def __init__(self, run_id: str, workflow_name: Optional[str] = None):
        self.run_id = run_id
        self.workflow_name = workflow_name or "unknown"
        self.status = WorkflowStatus.STARTED
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.completed_at = None
        self.duration_seconds = None
        self.events = []  # List of processed event IDs
        self.log_entries = []  # List of log messages
        self.errors = []  # List of error entries
        self.metadata = {}
        self.component_stats = {}  # Statistics per component
    
    def add_log(self, level: LogLevel, message: str, component: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """Add a log entry."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.value,
            "message": message,
            "component": component,
            "context": context or {}
        }
        self.log_entries.append(log_entry)
    
    def add_error(self, component: str, error: str, context: Optional[Dict[str, Any]] = None, 
                  exception: Optional[Exception] = None):
        """Add an error entry with optional traceback."""
        error_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "error": error,
            "context": context or {},
            "traceback": None
        }
        
        # Capture traceback if exception provided
        if exception:
            error_entry["traceback"] = traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        elif sys.exc_info()[0] is not None:
            # Capture current exception if available
            error_entry["traceback"] = traceback.format_exc()
        
        self.errors.append(error_entry)
        
        # Update component stats
        if component not in self.component_stats:
            self.component_stats[component] = {"errors": 0, "last_error": None}
        
        self.component_stats[component]["errors"] += 1
        self.component_stats[component]["last_error"] = error_entry["timestamp"]
    
    def add_event(self, event_id: str):
        """Add a processed event ID."""
        if event_id not in self.events:
            self.events.append(event_id)
    
    def update_status(self, status: WorkflowStatus, metadata: Optional[Dict[str, Any]] = None):
        """Update workflow status."""
        self.status = status
        
        if status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED]:
            self.completed_at = datetime.now(timezone.utc).isoformat()
            
            # Calculate duration
            if self.started_at:
                try:
                    start_time = datetime.fromisoformat(self.started_at.replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(self.completed_at.replace('Z', '+00:00'))
                    self.duration_seconds = (end_time - start_time).total_seconds()
                except Exception:
                    self.duration_seconds = None
        
        if metadata:
            self.metadata.update(metadata)
    
    def get_error_count(self) -> int:
        """Get total error count."""
        return len(self.errors)
    
    def get_component_error_count(self, component: str) -> int:
        """Get error count for a specific component."""
        return self.component_stats.get(component, {}).get("errors", 0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert workflow log entry to dictionary."""
        return {
            "run_id": self.run_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "events": self.events,
            "log_entries": self.log_entries,
            "errors": self.errors,
            "metadata": self.metadata,
            "component_stats": self.component_stats,
            "summary": {
                "total_events": len(self.events),
                "total_logs": len(self.log_entries),
                "total_errors": len(self.errors),
                "components_with_errors": len([c for c, stats in self.component_stats.items() if stats.get("errors", 0) > 0])
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowLogEntry':
        """Create WorkflowLogEntry from dictionary."""
        entry = cls(data["run_id"], data.get("workflow_name"))
        entry.status = WorkflowStatus(data["status"])
        entry.started_at = data.get("started_at", entry.started_at)
        entry.completed_at = data.get("completed_at")
        entry.duration_seconds = data.get("duration_seconds")
        entry.events = data.get("events", [])
        entry.log_entries = data.get("log_entries", [])
        entry.errors = data.get("errors", [])
        entry.metadata = data.get("metadata", {})
        entry.component_stats = data.get("component_stats", {})
        return entry


class WorkflowLogManager:
    """Manages workflow logs in S3 storage with comprehensive error tracking."""
    
    def __init__(self,
                 s3_bucket: str,
                 s3_prefix: str = "workflow_logs/",
                 aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None,
                 aws_region: str = "us-east-1"):
        """
        Initialize the workflow log manager.
        
        Args:
            s3_bucket: S3 bucket name for storing workflow logs
            s3_prefix: S3 key prefix for workflow logs (default: "workflow_logs/")
            aws_access_key_id: AWS access key ID (optional, uses default credential chain)
            aws_secret_access_key: AWS secret access key (optional, uses default credential chain)
            aws_region: AWS region (default: "us-east-1")
        """
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix.rstrip('/') + '/'
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Initialize S3 client
        try:
            session_kwargs = {"region_name": aws_region}
            if aws_access_key_id and aws_secret_access_key:
                session_kwargs.update({
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key
                })
            
            self.s3_client = boto3.client('s3', **session_kwargs)
            
            # Test connection
            self._test_connection()
            
        except Exception as e:
            error_msg = f"Failed to initialize S3 client for workflow logs: {e}"
            self.logger.error(error_msg)
            raise
        
        # Current workflow log entry
        self.current_workflow: Optional[WorkflowLogEntry] = None
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'WorkflowLogManager':
        """Create WorkflowLogManager from configuration dictionary."""
        s3_config = config.get('s3', {})
        return cls(
            s3_bucket=s3_config.get('bucket'),
            s3_prefix=s3_config.get('workflow_prefix', 'workflow_logs/'),
            aws_access_key_id=s3_config.get('aws_access_key_id'),
            aws_secret_access_key=s3_config.get('aws_secret_access_key'),
            aws_region=s3_config.get('aws_region', 'us-east-1')
        )
    
    def _test_connection(self):
        """Test S3 connection and bucket access."""
        try:
            self.s3_client.head_bucket(Bucket=self.s3_bucket)
            self.logger.info(f"S3 connection test successful for workflow logs bucket: {self.s3_bucket}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise ValueError(f"S3 bucket '{self.s3_bucket}' does not exist")
            elif error_code == '403':
                raise ValueError(f"Access denied to S3 bucket '{self.s3_bucket}'")
            else:
                raise
    
    def _get_s3_key(self, run_id: str) -> str:
        """Generate S3 key for workflow log."""
        return f"{self.s3_prefix}{run_id}.json"
    
    def start_workflow(self, workflow_name: str, run_id: Optional[str] = None) -> str:
        """
        Start a new workflow run.
        
        Args:
            workflow_name: Name of the workflow
            run_id: Optional custom run ID (will generate UUID if not provided)
            
        Returns:
            str: The workflow run ID
        """
        try:
            if not run_id:
                run_id = str(uuid.uuid4())
            
            self.current_workflow = WorkflowLogEntry(run_id, workflow_name)
            self.current_workflow.add_log(LogLevel.INFO, f"Started workflow: {workflow_name}", "workflow_manager")
            
            # Save initial state
            self._save_workflow_log(self.current_workflow)
            
            self.logger.info(f"Started workflow run: {run_id} ({workflow_name})")
            return run_id
            
        except Exception as e:
            error_msg = f"Failed to start workflow {workflow_name}: {e}"
            self.logger.error(error_msg)
            if self.current_workflow:
                self.current_workflow.add_error("workflow_manager", error_msg, exception=e)
            raise
    
    def log_info(self, message: str, component: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """Log an info message."""
        if self.current_workflow:
            self.current_workflow.add_log(LogLevel.INFO, message, component, context)
            self._save_workflow_log(self.current_workflow)
    
    def log_warning(self, message: str, component: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """Log a warning message."""
        if self.current_workflow:
            self.current_workflow.add_log(LogLevel.WARNING, message, component, context)
            self._save_workflow_log(self.current_workflow)
    
    def log_error(self, component: str, error: str, context: Optional[Dict[str, Any]] = None, 
                  exception: Optional[Exception] = None):
        """
        Log an error from any component.
        
        Args:
            component: Name of the component that generated the error
            error: Error message
            context: Additional context information
            exception: Optional exception object for traceback capture
        """
        try:
            if self.current_workflow:
                self.current_workflow.add_error(component, error, context, exception)
                self._save_workflow_log(self.current_workflow)
            
            self.logger.error(f"[{component}] {error}")
            
        except Exception as e:
            self.logger.error(f"Failed to log error from {component}: {e}")
    
    def log_event_processed(self, event_id: str):
        """Log that an event has been processed."""
        if self.current_workflow:
            self.current_workflow.add_event(event_id)
            self.current_workflow.add_log(LogLevel.INFO, f"Processed event: {event_id}", "workflow_manager")
            self._save_workflow_log(self.current_workflow)
    
    def complete_workflow(self, success: bool = True, metadata: Optional[Dict[str, Any]] = None):
        """
        Complete the current workflow run.
        
        Args:
            success: Whether the workflow completed successfully
            metadata: Additional metadata to include
        """
        try:
            if not self.current_workflow:
                self.logger.warning("No active workflow to complete")
                return
            
            status = WorkflowStatus.COMPLETED if success else WorkflowStatus.FAILED
            self.current_workflow.update_status(status, metadata)
            
            completion_msg = f"Workflow {'completed successfully' if success else 'failed'}"
            self.current_workflow.add_log(LogLevel.INFO, completion_msg, "workflow_manager")
            
            # Save final state
            self._save_workflow_log(self.current_workflow)
            
            self.logger.info(f"Workflow {self.current_workflow.run_id} {completion_msg}")
            
            # Clear current workflow
            self.current_workflow = None
            
        except Exception as e:
            error_msg = f"Failed to complete workflow: {e}"
            self.logger.error(error_msg)
            if self.current_workflow:
                self.current_workflow.add_error("workflow_manager", error_msg, exception=e)
                self._save_workflow_log(self.current_workflow)
    
    def cancel_workflow(self, reason: str = "Cancelled"):
        """Cancel the current workflow run."""
        try:
            if not self.current_workflow:
                self.logger.warning("No active workflow to cancel")
                return
            
            self.current_workflow.update_status(WorkflowStatus.CANCELLED, {"reason": reason})
            self.current_workflow.add_log(LogLevel.WARNING, f"Workflow cancelled: {reason}", "workflow_manager")
            
            self._save_workflow_log(self.current_workflow)
            
            self.logger.info(f"Workflow {self.current_workflow.run_id} cancelled: {reason}")
            self.current_workflow = None
            
        except Exception as e:
            error_msg = f"Failed to cancel workflow: {e}"
            self.logger.error(error_msg)
            if self.current_workflow:
                self.current_workflow.add_error("workflow_manager", error_msg, exception=e)
    
    def get_workflow_log(self, run_id: str) -> Optional[WorkflowLogEntry]:
        """
        Retrieve a workflow log by run ID.
        
        Args:
            run_id: Workflow run ID
            
        Returns:
            WorkflowLogEntry or None if not found
        """
        try:
            s3_key = self._get_s3_key(run_id)
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            return WorkflowLogEntry.from_dict(data)
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            else:
                self.logger.error(f"Failed to retrieve workflow log {run_id}: {e}")
                return None
        except Exception as e:
            self.logger.error(f"Failed to retrieve workflow log {run_id}: {e}")
            return None
    
    def _save_workflow_log(self, entry: WorkflowLogEntry):
        """Save workflow log entry to S3."""
        try:
            s3_key = self._get_s3_key(entry.run_id)
            data = json.dumps(entry.to_dict(), indent=2)
            
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=data,
                ContentType='application/json'
            )
            
        except Exception as e:
            self.logger.error(f"Failed to save workflow log {entry.run_id}: {e}")
            # Don't raise here to avoid recursive errors
    
    def list_recent_workflows(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recent workflow runs with summary information.
        
        Args:
            limit: Maximum number of workflows to return
            
        Returns:
            List of workflow summaries
        """
        workflows = []
        
        try:
            # List objects sorted by last modified (most recent first)
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix)
            
            objects = []
            for page in pages:
                if 'Contents' in page:
                    objects.extend(page['Contents'])
            
            # Sort by last modified (newest first)
            objects.sort(key=lambda x: x['LastModified'], reverse=True)
            
            # Get details for the most recent workflows
            for obj in objects[:limit]:
                key = obj['Key']
                if key.endswith('.json'):
                    try:
                        response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=key)
                        data = json.loads(response['Body'].read().decode('utf-8'))
                        
                        summary = {
                            "run_id": data.get("run_id"),
                            "workflow_name": data.get("workflow_name"),
                            "status": data.get("status"),
                            "started_at": data.get("started_at"),
                            "completed_at": data.get("completed_at"),
                            "duration_seconds": data.get("duration_seconds"),
                            "summary": data.get("summary", {})
                        }
                        workflows.append(summary)
                        
                    except Exception as e:
                        self.logger.warning(f"Failed to process workflow summary for {key}: {e}")
                        continue
            
            return workflows
            
        except Exception as e:
            self.logger.error(f"Failed to list recent workflows: {e}")
            return []
    
    def get_error_statistics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get error statistics for the last N days.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with error statistics
        """
        stats = {
            "total_workflows": 0,
            "failed_workflows": 0,
            "total_errors": 0,
            "errors_by_component": {},
            "most_common_errors": [],
            "period_days": days
        }
        
        try:
            cutoff_date = datetime.now(timezone.utc).timestamp() - (days * 24 * 3600)
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix)
            
            error_messages = []
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        if obj['LastModified'].timestamp() >= cutoff_date:
                            key = obj['Key']
                            if key.endswith('.json'):
                                try:
                                    response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=key)
                                    data = json.loads(response['Body'].read().decode('utf-8'))
                                    
                                    stats["total_workflows"] += 1
                                    
                                    if data.get("status") == "failed":
                                        stats["failed_workflows"] += 1
                                    
                                    errors = data.get("errors", [])
                                    stats["total_errors"] += len(errors)
                                    
                                    for error in errors:
                                        component = error.get("component", "unknown")
                                        if component not in stats["errors_by_component"]:
                                            stats["errors_by_component"][component] = 0
                                        stats["errors_by_component"][component] += 1
                                        
                                        error_messages.append(error.get("error", ""))
                                        
                                except Exception as e:
                                    self.logger.warning(f"Failed to process statistics for {key}: {e}")
                                    continue
            
            # Count most common error messages
            from collections import Counter
            error_counts = Counter(error_messages)
            stats["most_common_errors"] = error_counts.most_common(10)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get error statistics: {e}")
            return stats


# Configuration validation
def validate_workflow_log_config(config: Dict[str, Any]) -> List[str]:
    """Validate workflow log configuration and return list of errors."""
    errors = []
    s3_config = config.get('s3', {})
    
    if not s3_config.get('bucket'):
        errors.append("Missing required S3 configuration: bucket")
    
    return errors