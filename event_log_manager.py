"""
Event Log Manager for Agentic Intelligence Research System

This module manages event logs stored in S3 in the format events/{event_id}.json.
Handles reading, writing, and managing event status, trigger information, timestamps,
email status, and cleanup after event completion.
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
import logging
from botocore.exceptions import ClientError, NoCredentialsError


class EventStatus(Enum):
    """Event status enumeration"""
    CREATED = "created"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    ESCALATED = "escalated"


class EmailStatus(Enum):
    """Email status enumeration"""
    NOT_SENT = "not_sent"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    REPLIED = "replied"


@dataclass
class TriggerInfo:
    """Information about event triggers"""
    trigger_type: str  # "manual", "scheduled", "calendar", "email", etc.
    trigger_source: str  # source identifier
    trigger_time: datetime
    trigger_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['trigger_time'] = self.trigger_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TriggerInfo':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['trigger_time'] = datetime.fromisoformat(data_copy['trigger_time'])
        return cls(**data_copy)


@dataclass
class EmailLog:
    """Email activity log entry"""
    email_id: str
    email_type: str  # "request", "reminder", "escalation"
    recipient_email: str
    recipient_name: Optional[str]
    subject: str
    status: EmailStatus
    sent_timestamp: Optional[datetime] = None
    delivered_timestamp: Optional[datetime] = None
    error_message: Optional[str] = None
    template_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        if self.sent_timestamp:
            data['sent_timestamp'] = self.sent_timestamp.isoformat()
        if self.delivered_timestamp:
            data['delivered_timestamp'] = self.delivered_timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmailLog':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['status'] = EmailStatus(data_copy['status'])
        if data_copy.get('sent_timestamp'):
            data_copy['sent_timestamp'] = datetime.fromisoformat(data_copy['sent_timestamp'])
        if data_copy.get('delivered_timestamp'):
            data_copy['delivered_timestamp'] = datetime.fromisoformat(data_copy['delivered_timestamp'])
        return cls(**data_copy)


@dataclass
class EventLog:
    """Complete event log structure"""
    event_id: str
    event_title: str
    event_type: str
    status: EventStatus
    created_timestamp: datetime
    updated_timestamp: datetime
    trigger_info: TriggerInfo
    event_data: Dict[str, Any] = field(default_factory=dict)
    email_logs: List[EmailLog] = field(default_factory=list)
    completion_timestamp: Optional[datetime] = None
    error_logs: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = {
            'event_id': self.event_id,
            'event_title': self.event_title,
            'event_type': self.event_type,
            'status': self.status.value,
            'created_timestamp': self.created_timestamp.isoformat(),
            'updated_timestamp': self.updated_timestamp.isoformat(),
            'trigger_info': self.trigger_info.to_dict(),
            'event_data': self.event_data,
            'email_logs': [email_log.to_dict() for email_log in self.email_logs],
            'error_logs': self.error_logs,
            'metadata': self.metadata
        }
        
        if self.completion_timestamp:
            data['completion_timestamp'] = self.completion_timestamp.isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EventLog':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['status'] = EventStatus(data_copy['status'])
        data_copy['created_timestamp'] = datetime.fromisoformat(data_copy['created_timestamp'])
        data_copy['updated_timestamp'] = datetime.fromisoformat(data_copy['updated_timestamp'])
        data_copy['trigger_info'] = TriggerInfo.from_dict(data_copy['trigger_info'])
        
        if data_copy.get('completion_timestamp'):
            data_copy['completion_timestamp'] = datetime.fromisoformat(data_copy['completion_timestamp'])
        
        data_copy['email_logs'] = [
            EmailLog.from_dict(email_data) for email_data in data_copy.get('email_logs', [])
        ]
        
        return cls(**data_copy)


class EventLogManager:
    """Manages event logs in S3 storage"""
    
    def __init__(self, 
                 bucket_name: str,
                 aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None,
                 aws_region: str = "us-east-1",
                 events_prefix: str = "events/",
                 workflow_logger=None):
        """
        Initialize EventLogManager
        
        Args:
            bucket_name: S3 bucket name
            aws_access_key_id: AWS access key (optional, can use IAM roles)
            aws_secret_access_key: AWS secret key (optional, can use IAM roles)
            aws_region: AWS region
            events_prefix: S3 prefix for event logs
            workflow_logger: Optional workflow logger for error reporting
        """
        self.bucket_name = bucket_name
        self.events_prefix = events_prefix.rstrip('/') + '/'
        self.workflow_logger = workflow_logger
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Initialize S3 client
        try:
            session_kwargs = {'region_name': aws_region}
            if aws_access_key_id and aws_secret_access_key:
                session_kwargs.update({
                    'aws_access_key_id': aws_access_key_id,
                    'aws_secret_access_key': aws_secret_access_key
                })
            
            session = boto3.Session(**session_kwargs)
            self.s3_client = session.client('s3')
            
            # Test connection
            self._test_s3_connection()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize S3 client: {e}")
            self._log_workflow_error("s3_init", e)
            raise
    
    def _test_s3_connection(self) -> bool:
        """Test S3 connection and permissions"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            self.logger.info(f"S3 connection successful to bucket: {self.bucket_name}")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                self.logger.error(f"S3 bucket not found: {self.bucket_name}")
            elif error_code == '403':
                self.logger.error(f"Access denied to S3 bucket: {self.bucket_name}")
            else:
                self.logger.error(f"S3 connection error: {e}")
            raise
        except NoCredentialsError:
            self.logger.error("AWS credentials not found")
            raise
    
    def _log_workflow_error(self, step: str, error: Exception, event_id: str = None) -> None:
        """Log error to workflow logger if available"""
        if self.workflow_logger:
            try:
                self.workflow_logger.log_error(
                    step=step,
                    error=error,
                    event_id=event_id,
                    timestamp=datetime.now(timezone.utc)
                )
            except Exception as log_error:
                self.logger.error(f"Failed to log workflow error: {log_error}")
    
    def _get_event_key(self, event_id: str) -> str:
        """Get S3 key for event log"""
        return f"{self.events_prefix}{event_id}.json"
    
    def create_event_log(self, 
                        event_id: str,
                        event_title: str,
                        event_type: str,
                        trigger_info: TriggerInfo,
                        event_data: Dict[str, Any] = None,
                        metadata: Dict[str, Any] = None) -> EventLog:
        """Create new event log"""
        try:
            now = datetime.now(timezone.utc)
            
            event_log = EventLog(
                event_id=event_id,
                event_title=event_title,
                event_type=event_type,
                status=EventStatus.CREATED,
                created_timestamp=now,
                updated_timestamp=now,
                trigger_info=trigger_info,
                event_data=event_data or {},
                metadata=metadata or {}
            )
            
            # Save to S3
            self._save_event_log(event_log)
            
            self.logger.info(f"Created event log: {event_id}")
            return event_log
            
        except Exception as e:
            self.logger.error(f"Failed to create event log {event_id}: {e}")
            self._log_workflow_error("create_event_log", e, event_id)
            raise
    
    def get_event_log(self, event_id: str) -> Optional[EventLog]:
        """Retrieve event log from S3"""
        try:
            key = self._get_event_key(event_id)
            
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            
            return EventLog.from_dict(data)
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                self.logger.warning(f"Event log not found: {event_id}")
                return None
            else:
                self.logger.error(f"Failed to get event log {event_id}: {e}")
                self._log_workflow_error("get_event_log", e, event_id)
                raise
        except Exception as e:
            self.logger.error(f"Failed to get event log {event_id}: {e}")
            self._log_workflow_error("get_event_log", e, event_id)
            raise
    
    def _save_event_log(self, event_log: EventLog) -> None:
        """Save event log to S3"""
        try:
            key = self._get_event_key(event_log.event_id)
            data = json.dumps(event_log.to_dict(), indent=2)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType='application/json'
            )
            
        except Exception as e:
            self.logger.error(f"Failed to save event log {event_log.event_id}: {e}")
            self._log_workflow_error("save_event_log", e, event_log.event_id)
            raise
    
    def update_event_status(self, event_id: str, status: EventStatus) -> bool:
        """Update event status"""
        try:
            event_log = self.get_event_log(event_id)
            if not event_log:
                self.logger.error(f"Event not found for status update: {event_id}")
                return False
            
            event_log.status = status
            event_log.updated_timestamp = datetime.now(timezone.utc)
            
            if status in [EventStatus.COMPLETED, EventStatus.CANCELLED, EventStatus.FAILED]:
                event_log.completion_timestamp = event_log.updated_timestamp
            
            self._save_event_log(event_log)
            
            self.logger.info(f"Updated event {event_id} status to {status.value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update event status {event_id}: {e}")
            self._log_workflow_error("update_event_status", e, event_id)
            return False
    
    def add_email_log(self, event_id: str, email_log: EmailLog) -> bool:
        """Add email log entry to event"""
        try:
            event_log = self.get_event_log(event_id)
            if not event_log:
                self.logger.error(f"Event not found for email log: {event_id}")
                return False
            
            # Update existing email log or add new one
            existing_index = None
            for i, existing_email in enumerate(event_log.email_logs):
                if existing_email.email_id == email_log.email_id:
                    existing_index = i
                    break
            
            if existing_index is not None:
                event_log.email_logs[existing_index] = email_log
            else:
                event_log.email_logs.append(email_log)
            
            event_log.updated_timestamp = datetime.now(timezone.utc)
            
            self._save_event_log(event_log)
            
            self.logger.info(f"Added email log to event {event_id}: {email_log.email_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add email log to event {event_id}: {e}")
            self._log_workflow_error("add_email_log", e, event_id)
            return False
    
    def update_email_status(self, event_id: str, email_id: str, status: EmailStatus, 
                           error_message: str = None) -> bool:
        """Update email status in event log"""
        try:
            event_log = self.get_event_log(event_id)
            if not event_log:
                self.logger.error(f"Event not found for email status update: {event_id}")
                return False
            
            # Find and update email log
            for email_log in event_log.email_logs:
                if email_log.email_id == email_id:
                    email_log.status = status
                    if error_message:
                        email_log.error_message = error_message
                    if status == EmailStatus.DELIVERED:
                        email_log.delivered_timestamp = datetime.now(timezone.utc)
                    break
            else:
                self.logger.error(f"Email log not found: {email_id} in event {event_id}")
                return False
            
            event_log.updated_timestamp = datetime.now(timezone.utc)
            self._save_event_log(event_log)
            
            self.logger.info(f"Updated email {email_id} status to {status.value} in event {event_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update email status {event_id}/{email_id}: {e}")
            self._log_workflow_error("update_email_status", e, event_id)
            return False
    
    def add_error_log(self, event_id: str, step: str, error: Exception, 
                     additional_data: Dict[str, Any] = None) -> bool:
        """Add error log entry to event"""
        try:
            event_log = self.get_event_log(event_id)
            if not event_log:
                self.logger.error(f"Event not found for error log: {event_id}")
                return False
            
            error_entry = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'step': step,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'additional_data': additional_data or {}
            }
            
            event_log.error_logs.append(error_entry)
            event_log.updated_timestamp = datetime.now(timezone.utc)
            
            self._save_event_log(event_log)
            
            self.logger.info(f"Added error log to event {event_id}: {step}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add error log to event {event_id}: {e}")
            self._log_workflow_error("add_error_log", e, event_id)
            return False
    
    def list_events(self, status_filter: Optional[EventStatus] = None, 
                   limit: int = None) -> List[str]:
        """List event IDs, optionally filtered by status"""
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=self.events_prefix
            )
            
            event_ids = []
            count = 0
            
            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    if limit and count >= limit:
                        break
                    
                    key = obj['Key']
                    if key.endswith('.json'):
                        event_id = key.replace(self.events_prefix, '').replace('.json', '')
                        
                        # Apply status filter if specified
                        if status_filter:
                            event_log = self.get_event_log(event_id)
                            if event_log and event_log.status == status_filter:
                                event_ids.append(event_id)
                                count += 1
                        else:
                            event_ids.append(event_id)
                            count += 1
                
                if limit and count >= limit:
                    break
            
            return event_ids
            
        except Exception as e:
            self.logger.error(f"Failed to list events: {e}")
            self._log_workflow_error("list_events", e)
            return []
    
    def delete_event_log(self, event_id: str) -> bool:
        """Delete event log from S3"""
        try:
            key = self._get_event_key(event_id)
            
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            
            self.logger.info(f"Deleted event log: {event_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete event log {event_id}: {e}")
            self._log_workflow_error("delete_event_log", e, event_id)
            return False
    
    def cleanup_completed_events(self, older_than_days: int = 30) -> int:
        """Delete completed events older than specified days"""
        try:
            cutoff_date = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - datetime.timedelta(days=older_than_days)
            
            completed_events = self.list_events(status_filter=EventStatus.COMPLETED)
            deleted_count = 0
            
            for event_id in completed_events:
                event_log = self.get_event_log(event_id)
                if (event_log and 
                    event_log.completion_timestamp and 
                    event_log.completion_timestamp < cutoff_date):
                    
                    if self.delete_event_log(event_id):
                        deleted_count += 1
            
            self.logger.info(f"Cleaned up {deleted_count} completed events")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup completed events: {e}")
            self._log_workflow_error("cleanup_completed_events", e)
            return 0


if __name__ == "__main__":
    # Example usage
    import os
    
    # Example configuration (would typically be loaded from environment)
    bucket_name = os.getenv("S3_EVENTLOG_BUCKET", "agentic-intelligence-events")
    
    try:
        # Create event log manager
        manager = EventLogManager(bucket_name=bucket_name)
        
        # Create sample trigger info
        trigger_info = TriggerInfo(
            trigger_type="manual",
            trigger_source="test_script",
            trigger_time=datetime.now(timezone.utc),
            trigger_data={"test": True}
        )
        
        # Create sample event log
        event_log = manager.create_event_log(
            event_id="test-event-001",
            event_title="Test Calendar Event",
            event_type="calendar_meeting",
            trigger_info=trigger_info,
            event_data={"meeting_url": "https://example.com/meeting"}
        )
        
        print(f"✓ Created event log: {event_log.event_id}")
        
        # List events
        events = manager.list_events(limit=10)
        print(f"Found {len(events)} events")
        
    except Exception as e:
        print(f"✗ Event log manager test failed: {e}")