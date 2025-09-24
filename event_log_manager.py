"""
Event Log Manager - S3-based event logging system for tracking calendar event processing.

This module provides event logging functionality with S3 storage, duplicate detection,
status tracking, and automatic cleanup for the agentic intelligence workflow system.
"""

import json
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timezone
from enum import Enum
import logging
import uuid


class EventStatus(Enum):
    """Event processing status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class EventLogEntry:
    """Represents a single event log entry."""
    
    def __init__(self, event_id: str, status: EventStatus = EventStatus.PENDING):
        self.event_id = event_id
        self.status = status
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at
        self.triggers = []
        self.email_status = {}
        self.metadata = {}
        self.error_count = 0
        self.last_error = None
    
    def update_status(self, new_status: EventStatus, metadata: Optional[Dict[str, Any]] = None):
        """Update the event status and timestamp."""
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if metadata:
            self.metadata.update(metadata)
    
    def add_trigger(self, trigger_type: str, trigger_data: Dict[str, Any]):
        """Add a trigger event to the log."""
        trigger_entry = {
            "type": trigger_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": trigger_data
        }
        self.triggers.append(trigger_entry)
    
    def update_email_status(self, email_type: str, recipient: str, success: bool, details: Optional[str] = None):
        """Update email sending status."""
        if email_type not in self.email_status:
            self.email_status[email_type] = {}
        
        self.email_status[email_type][recipient] = {
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details
        }
    
    def log_error(self, error: str, context: Optional[Dict[str, Any]] = None):
        """Log an error for this event."""
        self.error_count += 1
        self.last_error = {
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context or {}
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the event log entry to a dictionary."""
        return {
            "event_id": self.event_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "triggers": self.triggers,
            "email_status": self.email_status,
            "metadata": self.metadata,
            "error_count": self.error_count,
            "last_error": self.last_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EventLogEntry':
        """Create an EventLogEntry from a dictionary."""
        entry = cls(data["event_id"], EventStatus(data["status"]))
        entry.created_at = data.get("created_at", entry.created_at)
        entry.updated_at = data.get("updated_at", entry.updated_at)
        entry.triggers = data.get("triggers", [])
        entry.email_status = data.get("email_status", {})
        entry.metadata = data.get("metadata", {})
        entry.error_count = data.get("error_count", 0)
        entry.last_error = data.get("last_error")
        return entry


class EventLogManager:
    """Manages event logs in S3 storage with duplicate detection and status tracking."""
    
    def __init__(self, 
                 s3_bucket: str,
                 s3_prefix: str = "events/",
                 aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None,
                 aws_region: str = "us-east-1",
                 workflow_logger: Optional[Any] = None):
        """
        Initialize the event log manager.
        
        Args:
            s3_bucket: S3 bucket name for storing event logs
            s3_prefix: S3 key prefix for event logs (default: "events/")
            aws_access_key_id: AWS access key ID (optional, uses default credential chain)
            aws_secret_access_key: AWS secret access key (optional, uses default credential chain)
            aws_region: AWS region (default: "us-east-1")
            workflow_logger: Workflow logger for error reporting
        """
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix.rstrip('/') + '/'
        self.workflow_logger = workflow_logger
        
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
            error_msg = f"Failed to initialize S3 client: {e}"
            self.logger.error(error_msg)
            self._log_to_workflow(error_msg, {"action": "initialize_s3"})
            raise
        
        # Cache for duplicate detection
        self._event_cache: Set[str] = set()
        self._cache_loaded = False
    
    @classmethod
    def from_config(cls, config: Dict[str, Any], workflow_logger: Optional[Any] = None) -> 'EventLogManager':
        """Create EventLogManager from configuration dictionary."""
        s3_config = config.get('s3', {})
        return cls(
            s3_bucket=s3_config.get('bucket'),
            s3_prefix=s3_config.get('event_prefix', 'events/'),
            aws_access_key_id=s3_config.get('aws_access_key_id'),
            aws_secret_access_key=s3_config.get('aws_secret_access_key'),
            aws_region=s3_config.get('aws_region', 'us-east-1'),
            workflow_logger=workflow_logger
        )
    
    def _test_connection(self):
        """Test S3 connection and bucket access."""
        try:
            self.s3_client.head_bucket(Bucket=self.s3_bucket)
            self.logger.info(f"S3 connection test successful for bucket: {self.s3_bucket}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise ValueError(f"S3 bucket '{self.s3_bucket}' does not exist")
            elif error_code == '403':
                raise ValueError(f"Access denied to S3 bucket '{self.s3_bucket}'")
            else:
                raise
    
    def _log_to_workflow(self, error: str, context: Dict[str, Any]):
        """Log error to workflow logger if available."""
        if self.workflow_logger:
            try:
                self.workflow_logger.log_error(
                    component="event_log_manager",
                    error=error,
                    context=context
                )
            except Exception as e:
                self.logger.error(f"Failed to log to workflow logger: {e}")
    
    def _get_s3_key(self, event_id: str) -> str:
        """Generate S3 key for event log."""
        return f"{self.s3_prefix}{event_id}.json"
    
    def _load_event_cache(self):
        """Load existing event IDs into cache for duplicate detection."""
        if self._cache_loaded:
            return
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        if key.endswith('.json'):
                            # Extract event ID from key
                            event_id = key[len(self.s3_prefix):-5]  # Remove prefix and .json
                            self._event_cache.add(event_id)
            
            self._cache_loaded = True
            self.logger.info(f"Loaded {len(self._event_cache)} existing event IDs into cache")
            
        except Exception as e:
            error_msg = f"Failed to load event cache: {e}"
            self.logger.error(error_msg)
            self._log_to_workflow(error_msg, {"action": "load_event_cache"})
    
    def is_duplicate(self, event_id: str) -> bool:
        """Check if an event ID already exists (duplicate detection)."""
        try:
            self._load_event_cache()
            return event_id in self._event_cache
        except Exception as e:
            error_msg = f"Failed to check for duplicate event {event_id}: {e}"
            self.logger.error(error_msg)
            self._log_to_workflow(error_msg, {"event_id": event_id, "action": "duplicate_check"})
            return False
    
    def create_event_log(self, event_id: str, initial_data: Optional[Dict[str, Any]] = None) -> EventLogEntry:
        """
        Create a new event log entry.
        
        Args:
            event_id: Unique identifier for the event
            initial_data: Initial metadata for the event
            
        Returns:
            EventLogEntry: The created event log entry
            
        Raises:
            ValueError: If event_id already exists (duplicate)
        """
        try:
            # Check for duplicates
            if self.is_duplicate(event_id):
                raise ValueError(f"Event ID '{event_id}' already exists")
            
            # Create new event log entry
            entry = EventLogEntry(event_id)
            if initial_data:
                entry.metadata.update(initial_data)
            
            # Save to S3
            self._save_event_log(entry)
            
            # Add to cache
            self._event_cache.add(event_id)
            
            self.logger.info(f"Created event log for event ID: {event_id}")
            return entry
            
        except Exception as e:
            error_msg = f"Failed to create event log for {event_id}: {e}"
            self.logger.error(error_msg)
            self._log_to_workflow(error_msg, {"event_id": event_id, "action": "create_event_log"})
            raise
    
    def get_event_log(self, event_id: str) -> Optional[EventLogEntry]:
        """
        Retrieve an event log entry by ID.
        
        Args:
            event_id: Event ID to retrieve
            
        Returns:
            EventLogEntry or None if not found
        """
        try:
            s3_key = self._get_s3_key(event_id)
            response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            return EventLogEntry.from_dict(data)
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            else:
                error_msg = f"Failed to retrieve event log for {event_id}: {e}"
                self.logger.error(error_msg)
                self._log_to_workflow(error_msg, {"event_id": event_id, "action": "get_event_log"})
                return None
        except Exception as e:
            error_msg = f"Failed to retrieve event log for {event_id}: {e}"
            self.logger.error(error_msg)
            self._log_to_workflow(error_msg, {"event_id": event_id, "action": "get_event_log"})
            return None
    
    def update_event_log(self, entry: EventLogEntry) -> bool:
        """
        Update an existing event log entry.
        
        Args:
            entry: EventLogEntry to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            entry.updated_at = datetime.now(timezone.utc).isoformat()
            self._save_event_log(entry)
            self.logger.info(f"Updated event log for event ID: {entry.event_id}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to update event log for {entry.event_id}: {e}"
            self.logger.error(error_msg)
            self._log_to_workflow(error_msg, {"event_id": entry.event_id, "action": "update_event_log"})
            return False
    
    def _save_event_log(self, entry: EventLogEntry):
        """Save event log entry to S3."""
        s3_key = self._get_s3_key(entry.event_id)
        data = json.dumps(entry.to_dict(), indent=2)
        
        self.s3_client.put_object(
            Bucket=self.s3_bucket,
            Key=s3_key,
            Body=data,
            ContentType='application/json'
        )
    
    def delete_event_log(self, event_id: str) -> bool:
        """
        Delete an event log entry (typically after completion).
        
        Args:
            event_id: Event ID to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            s3_key = self._get_s3_key(event_id)
            self.s3_client.delete_object(Bucket=self.s3_bucket, Key=s3_key)
            
            # Remove from cache
            self._event_cache.discard(event_id)
            
            self.logger.info(f"Deleted event log for event ID: {event_id}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to delete event log for {event_id}: {e}"
            self.logger.error(error_msg)
            self._log_to_workflow(error_msg, {"event_id": event_id, "action": "delete_event_log"})
            return False
    
    def list_events_by_status(self, status: EventStatus) -> List[str]:
        """
        List all event IDs with a specific status.
        
        Args:
            status: EventStatus to filter by
            
        Returns:
            List of event IDs
        """
        matching_events = []
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        if key.endswith('.json'):
                            try:
                                # Get object and check status
                                response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=key)
                                data = json.loads(response['Body'].read().decode('utf-8'))
                                
                                if data.get('status') == status.value:
                                    matching_events.append(data.get('event_id'))
                                    
                            except Exception as e:
                                self.logger.warning(f"Failed to check status for {key}: {e}")
                                continue
            
            return matching_events
            
        except Exception as e:
            error_msg = f"Failed to list events by status {status}: {e}"
            self.logger.error(error_msg)
            self._log_to_workflow(error_msg, {"status": status.value, "action": "list_events_by_status"})
            return []
    
    def cleanup_completed_events(self, older_than_days: int = 7) -> int:
        """
        Clean up completed events older than specified days.
        
        Args:
            older_than_days: Delete completed events older than this many days
            
        Returns:
            Number of events deleted
        """
        deleted_count = 0
        cutoff_date = datetime.now(timezone.utc).timestamp() - (older_than_days * 24 * 3600)
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.s3_bucket, Prefix=self.s3_prefix)
            
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        if key.endswith('.json'):
                            try:
                                # Check if old enough and completed
                                if obj['LastModified'].timestamp() < cutoff_date:
                                    response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=key)
                                    data = json.loads(response['Body'].read().decode('utf-8'))
                                    
                                    if data.get('status') == EventStatus.COMPLETED.value:
                                        self.s3_client.delete_object(Bucket=self.s3_bucket, Key=key)
                                        event_id = data.get('event_id')
                                        self._event_cache.discard(event_id)
                                        deleted_count += 1
                                        self.logger.info(f"Cleaned up completed event: {event_id}")
                                        
                            except Exception as e:
                                self.logger.warning(f"Failed to process cleanup for {key}: {e}")
                                continue
            
            self.logger.info(f"Cleanup completed: deleted {deleted_count} events")
            return deleted_count
            
        except Exception as e:
            error_msg = f"Failed to cleanup completed events: {e}"
            self.logger.error(error_msg)
            self._log_to_workflow(error_msg, {"action": "cleanup_completed_events"})
            return deleted_count


# Configuration validation
def validate_event_log_config(config: Dict[str, Any]) -> List[str]:
    """Validate event log configuration and return list of errors."""
    errors = []
    s3_config = config.get('s3', {})
    
    if not s3_config.get('bucket'):
        errors.append("Missing required S3 configuration: bucket")
    
    return errors