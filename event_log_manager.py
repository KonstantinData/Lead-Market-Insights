"""
Event Log Manager for Agentic Intelligence Research System

This module provides S3-based logging functionality for events with status tracking,
trigger management, timestamps, and email status monitoring. Includes duplicate
checking and comprehensive error handling.
"""

import json
import logging
import os
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class EventStatus(Enum):
    """Event status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


class TriggerType(Enum):
    """Event trigger types."""
    MANUAL = "manual"
    AUTOMATED = "automated"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    EMAIL_RESPONSE = "email_response"
    TIMEOUT = "timeout"
    ESCALATION = "escalation"


class EmailStatus(Enum):
    """Email status enumeration."""
    NOT_SENT = "not_sent"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"


@dataclass
class EventData:
    """Event data structure for logging."""
    event_id: str
    request_id: str
    status: EventStatus
    trigger: TriggerType
    timestamp: str
    email_status: EmailStatus
    recipient_email: str = ""
    recipient_name: str = ""
    company: str = ""
    request_details: str = ""
    priority: str = "medium"
    deadline: str = ""
    escalation_level: int = 0
    retry_count: int = 0
    last_email_sent: str = ""
    response_received: str = ""
    created_by: str = "system"
    updated_by: str = "system"
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        
        # Ensure timestamp is ISO format
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert enums to their values
        data['status'] = self.status.value
        data['trigger'] = self.trigger.value
        data['email_status'] = self.email_status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EventData':
        """Create EventData from dictionary."""
        # Convert enum values back to enums
        if 'status' in data:
            data['status'] = EventStatus(data['status'])
        if 'trigger' in data:
            data['trigger'] = TriggerType(data['trigger'])
        if 'email_status' in data:
            data['email_status'] = EmailStatus(data['email_status'])
        
        return cls(**data)
    
    def generate_hash(self) -> str:
        """Generate hash for duplicate detection."""
        # Create hash based on key fields that define uniqueness
        hash_data = f"{self.request_id}:{self.recipient_email}:{self.trigger.value}:{self.timestamp[:10]}"
        return hashlib.sha256(hash_data.encode()).hexdigest()[:16]


@dataclass
class S3Config:
    """S3 configuration for event logging."""
    bucket_name: str
    region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    events_prefix: str = "events/"
    use_encryption: bool = True
    storage_class: str = "STANDARD"
    
    def __post_init__(self):
        # Use environment variables if not provided
        if not self.aws_access_key_id:
            self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID', '')
        if not self.aws_secret_access_key:
            self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY', '')
        if not self.aws_session_token:
            self.aws_session_token = os.getenv('AWS_SESSION_TOKEN', '')


class EventLogManager:
    """S3-based event log manager with duplicate checking and comprehensive tracking."""
    
    def __init__(self, s3_config: S3Config, workflow_logger=None):
        self.config = s3_config
        self.workflow_logger = workflow_logger
        self.logger = logging.getLogger(__name__)
        self._s3_client = None
        self._duplicate_cache = {}  # Simple in-memory cache for recent duplicates
        
        # Configure logging if not already configured
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
    
    @property
    def s3_client(self):
        """Lazy initialization of S3 client."""
        if self._s3_client is None:
            try:
                session_kwargs = {'region_name': self.config.region}
                
                if self.config.aws_access_key_id and self.config.aws_secret_access_key:
                    session_kwargs.update({
                        'aws_access_key_id': self.config.aws_access_key_id,
                        'aws_secret_access_key': self.config.aws_secret_access_key
                    })
                    
                    if self.config.aws_session_token:
                        session_kwargs['aws_session_token'] = self.config.aws_session_token
                
                session = boto3.Session(**session_kwargs)
                self._s3_client = session.client('s3')
                
                # Test connection
                self._s3_client.head_bucket(Bucket=self.config.bucket_name)
                self.logger.info(f"S3 connection established to bucket: {self.config.bucket_name}")
                
            except NoCredentialsError:
                self.logger.error("AWS credentials not found")
                raise
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    self.logger.error(f"S3 bucket not found: {self.config.bucket_name}")
                else:
                    self.logger.error(f"S3 connection failed: {e}")
                raise
            except Exception as e:
                self.logger.error(f"Failed to initialize S3 client: {e}")
                raise
        
        return self._s3_client
    
    def _log_workflow_event(self, event_type: str, details: Dict[str, Any], error: bool = False) -> None:
        """Log events to workflow logger if available."""
        if self.workflow_logger:
            try:
                log_entry = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'component': 'event_log_manager',
                    'event_type': event_type,
                    'details': details,
                    'error': error
                }
                self.workflow_logger.log_event(log_entry)
            except Exception as e:
                self.logger.error(f"Failed to log workflow event: {e}")
    
    def _get_event_key(self, event_id: str) -> str:
        """Generate S3 key for event."""
        return f"{self.config.events_prefix}{event_id}.json"
    
    def _check_duplicate(self, event_data: EventData) -> bool:
        """Check if event is a duplicate based on hash."""
        event_hash = event_data.generate_hash()
        
        # Check in-memory cache first
        if event_hash in self._duplicate_cache:
            self.logger.warning(f"Duplicate event detected (cached): {event_data.event_id}")
            return True
        
        # Check S3 for existing events with same hash
        try:
            # List recent events to check for duplicates
            prefix = self.config.events_prefix
            response = self.s3_client.list_objects_v2(
                Bucket=self.config.bucket_name,
                Prefix=prefix,
                MaxKeys=100  # Check last 100 events
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    try:
                        # Get object content
                        obj_response = self.s3_client.get_object(
                            Bucket=self.config.bucket_name,
                            Key=obj['Key']
                        )
                        content = json.loads(obj_response['Body'].read().decode('utf-8'))
                        
                        # Check if this event has the same hash
                        if 'hash' in content and content['hash'] == event_hash:
                            self.logger.warning(f"Duplicate event detected (S3): {event_data.event_id}")
                            # Cache the duplicate
                            self._duplicate_cache[event_hash] = True
                            return True
                            
                    except Exception as e:
                        self.logger.debug(f"Error checking duplicate in {obj['Key']}: {e}")
                        continue
            
            # Add to cache as not duplicate
            self._duplicate_cache[event_hash] = False
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking duplicates: {e}")
            return False
    
    def log_event(self, event_data: EventData, allow_duplicates: bool = False) -> bool:
        """
        Log event to S3.
        
        Args:
            event_data: Event data to log
            allow_duplicates: Whether to allow duplicate events
            
        Returns:
            bool: True if logged successfully, False otherwise
        """
        start_time = datetime.utcnow()
        
        try:
            # Check for duplicates unless explicitly allowed
            if not allow_duplicates and self._check_duplicate(event_data):
                self._log_workflow_event('duplicate_event_blocked', {
                    'event_id': event_data.event_id,
                    'request_id': event_data.request_id,
                    'hash': event_data.generate_hash()
                })
                return False
            
            # Prepare event data with metadata
            event_dict = event_data.to_dict()
            event_dict['hash'] = event_data.generate_hash()
            event_dict['logged_at'] = datetime.utcnow().isoformat() + "Z"
            
            # Convert to JSON
            event_json = json.dumps(event_dict, indent=2, ensure_ascii=False)
            
            # Prepare S3 put parameters
            put_kwargs = {
                'Bucket': self.config.bucket_name,
                'Key': self._get_event_key(event_data.event_id),
                'Body': event_json.encode('utf-8'),
                'ContentType': 'application/json',
                'StorageClass': self.config.storage_class,
                'Metadata': {
                    'event-id': event_data.event_id,
                    'request-id': event_data.request_id,
                    'status': event_data.status.value,
                    'trigger': event_data.trigger.value,
                    'logged-by': 'event-log-manager'
                }
            }
            
            # Add encryption if enabled
            if self.config.use_encryption:
                put_kwargs['ServerSideEncryption'] = 'AES256'
            
            # Upload to S3
            self.s3_client.put_object(**put_kwargs)
            
            # Log success
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.logger.info(
                f"Event logged successfully - ID: {event_data.event_id}, "
                f"Request: {event_data.request_id}, "
                f"Status: {event_data.status.value}, "
                f"Duration: {duration:.2f}s"
            )
            
            self._log_workflow_event('event_logged', {
                'event_id': event_data.event_id,
                'request_id': event_data.request_id,
                'status': event_data.status.value,
                'trigger': event_data.trigger.value,
                'email_status': event_data.email_status.value,
                'duration_seconds': duration
            })
            
            return True
            
        except Exception as e:
            # Log error
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Failed to log event - ID: {event_data.event_id}, " \
                       f"Request: {event_data.request_id}, " \
                       f"Error: {str(e)}"
            
            self.logger.error(error_msg)
            
            self._log_workflow_event('event_log_failed', {
                'event_id': event_data.event_id,
                'request_id': event_data.request_id,
                'error': str(e),
                'duration_seconds': duration
            }, error=True)
            
            return False
    
    def get_event(self, event_id: str) -> Optional[EventData]:
        """
        Retrieve event from S3.
        
        Args:
            event_id: Event ID to retrieve
            
        Returns:
            EventData if found, None otherwise
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.config.bucket_name,
                Key=self._get_event_key(event_id)
            )
            
            content = json.loads(response['Body'].read().decode('utf-8'))
            event_data = EventData.from_dict(content)
            
            self.logger.debug(f"Event retrieved successfully: {event_id}")
            return event_data
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                self.logger.warning(f"Event not found: {event_id}")
            else:
                self.logger.error(f"Error retrieving event {event_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving event {event_id}: {e}")
            return None
    
    def update_event_status(self, event_id: str, status: EventStatus, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update event status and metadata.
        
        Args:
            event_id: Event ID to update
            status: New status
            metadata: Additional metadata to merge
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            # Get existing event
            event_data = self.get_event(event_id)
            if not event_data:
                self.logger.error(f"Cannot update non-existent event: {event_id}")
                return False
            
            # Update status and metadata
            event_data.status = status
            event_data.updated_by = "event_log_manager"
            
            if metadata:
                event_data.metadata.update(metadata)
            
            # Log updated event
            return self.log_event(event_data, allow_duplicates=True)
            
        except Exception as e:
            self.logger.error(f"Error updating event {event_id}: {e}")
            return False
    
    def update_email_status(self, event_id: str, email_status: EmailStatus, timestamp: Optional[str] = None) -> bool:
        """
        Update email status for an event.
        
        Args:
            event_id: Event ID to update
            email_status: New email status
            timestamp: Timestamp of email status change
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            # Get existing event
            event_data = self.get_event(event_id)
            if not event_data:
                self.logger.error(f"Cannot update email status for non-existent event: {event_id}")
                return False
            
            # Update email status
            event_data.email_status = email_status
            event_data.updated_by = "event_log_manager"
            
            if timestamp:
                if email_status == EmailStatus.SENT:
                    event_data.last_email_sent = timestamp
                elif email_status == EmailStatus.REPLIED:
                    event_data.response_received = timestamp
            
            # Add to metadata
            status_update = {
                'email_status_updated': datetime.utcnow().isoformat() + "Z",
                'previous_email_status': event_data.email_status.value if hasattr(event_data, 'email_status') else 'unknown'
            }
            
            if not event_data.metadata:
                event_data.metadata = {}
            event_data.metadata.update(status_update)
            
            # Log updated event
            return self.log_event(event_data, allow_duplicates=True)
            
        except Exception as e:
            self.logger.error(f"Error updating email status for event {event_id}: {e}")
            return False
    
    def list_events(self, prefix: str = "", max_keys: int = 100) -> List[str]:
        """
        List event IDs with optional prefix filtering.
        
        Args:
            prefix: Prefix to filter event IDs
            max_keys: Maximum number of keys to return
            
        Returns:
            List of event IDs
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.config.bucket_name,
                Prefix=self.config.events_prefix + prefix,
                MaxKeys=max_keys
            )
            
            event_ids = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Extract event ID from key
                    key = obj['Key']
                    if key.endswith('.json'):
                        event_id = key.replace(self.config.events_prefix, '').replace('.json', '')
                        event_ids.append(event_id)
            
            self.logger.debug(f"Listed {len(event_ids)} events with prefix '{prefix}'")
            return event_ids
            
        except Exception as e:
            self.logger.error(f"Error listing events: {e}")
            return []
    
    def delete_event(self, event_id: str) -> bool:
        """
        Delete event from S3.
        
        Args:
            event_id: Event ID to delete
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.config.bucket_name,
                Key=self._get_event_key(event_id)
            )
            
            self.logger.info(f"Event deleted successfully: {event_id}")
            
            self._log_workflow_event('event_deleted', {
                'event_id': event_id
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting event {event_id}: {e}")
            
            self._log_workflow_event('event_delete_failed', {
                'event_id': event_id,
                'error': str(e)
            }, error=True)
            
            return False
    
    def get_events_by_request_id(self, request_id: str) -> List[EventData]:
        """
        Get all events for a specific request ID.
        
        Args:
            request_id: Request ID to search for
            
        Returns:
            List of EventData objects
        """
        events = []
        try:
            # List all events
            event_ids = self.list_events(max_keys=1000)
            
            # Filter by request_id
            for event_id in event_ids:
                event_data = self.get_event(event_id)
                if event_data and event_data.request_id == request_id:
                    events.append(event_data)
            
            self.logger.debug(f"Found {len(events)} events for request {request_id}")
            return events
            
        except Exception as e:
            self.logger.error(f"Error getting events for request {request_id}: {e}")
            return []
    
    def cleanup_old_events(self, days_old: int = 30) -> int:
        """
        Delete events older than specified days.
        
        Args:
            days_old: Number of days to keep events
            
        Returns:
            Number of events deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            deleted_count = 0
            
            # List all events
            response = self.s3_client.list_objects_v2(
                Bucket=self.config.bucket_name,
                Prefix=self.config.events_prefix
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Check last modified date
                    if obj['LastModified'].replace(tzinfo=timezone.utc) < cutoff_date.replace(tzinfo=timezone.utc):
                        # Delete old event
                        self.s3_client.delete_object(
                            Bucket=self.config.bucket_name,
                            Key=obj['Key']
                        )
                        deleted_count += 1
            
            self.logger.info(f"Cleanup completed: {deleted_count} old events deleted")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            return 0


def create_s3_config_from_env() -> S3Config:
    """Create S3 configuration from environment variables."""
    return S3Config(
        bucket_name=os.getenv('S3_BUCKET_NAME', 'agentic-research-logs'),
        region=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', ''),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', ''),
        aws_session_token=os.getenv('AWS_SESSION_TOKEN', ''),
        events_prefix=os.getenv('S3_EVENTS_PREFIX', 'events/'),
        use_encryption=os.getenv('S3_USE_ENCRYPTION', 'true').lower() == 'true',
        storage_class=os.getenv('S3_STORAGE_CLASS', 'STANDARD')
    )


# Example usage and testing
if __name__ == "__main__":
    from datetime import timedelta
    
    # Example configuration (use environment variables in production)
    config = S3Config(
        bucket_name="agentic-research-logs",
        region="us-east-1",
        events_prefix="events/"
    )
    
    # Create event log manager
    event_manager = EventLogManager(config)
    
    # Example event data
    event_data = EventData(
        event_id="EVT-2024-001",
        request_id="REQ-2024-001",
        status=EventStatus.PENDING,
        trigger=TriggerType.MANUAL,
        timestamp=datetime.utcnow().isoformat() + "Z",
        email_status=EmailStatus.NOT_SENT,
        recipient_email="john.doe@example.com",
        recipient_name="John Doe",
        company="Example Corp",
        request_details="AI model evaluation research request",
        priority="high",
        deadline=(datetime.utcnow() + timedelta(days=7)).isoformat() + "Z",
        created_by="research_system"
    )
    
    # Log event
    print("Logging event...")
    success = event_manager.log_event(event_data)
    print(f"Event logged: {success}")
    
    # Retrieve event
    print("Retrieving event...")
    retrieved_event = event_manager.get_event("EVT-2024-001")
    if retrieved_event:
        print(f"Retrieved event: {retrieved_event.event_id} - Status: {retrieved_event.status.value}")
    
    # Update status
    print("Updating event status...")
    success = event_manager.update_event_status("EVT-2024-001", EventStatus.IN_PROGRESS)
    print(f"Status updated: {success}")
    
    # Update email status
    print("Updating email status...")
    success = event_manager.update_email_status("EVT-2024-001", EmailStatus.SENT, datetime.utcnow().isoformat() + "Z")
    print(f"Email status updated: {success}")
    
    # List events
    print("Listing events...")
    event_ids = event_manager.list_events()
    print(f"Found {len(event_ids)} events: {event_ids}")
    
    # Get events by request ID
    print("Getting events by request ID...")
    request_events = event_manager.get_events_by_request_id("REQ-2024-001")
    print(f"Found {len(request_events)} events for request REQ-2024-001")