"""
Event Log Manager - S3 Event Log Management

This module handles reading and writing event logs to S3 storage.
Event logs are stored as JSON files in the format: events/{event_id}.json
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class EventLogManager:
    """Manages event logs in S3 storage."""
    
    def __init__(self, bucket_name: str = None, aws_region: str = None,
                 aws_access_key_id: str = None, aws_secret_access_key: str = None):
        """
        Initialize EventLogManager with S3 configuration.
        
        Args:
            bucket_name: S3 bucket name for storing event logs
            aws_region: AWS region for S3 bucket
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
        """
        self.bucket_name = bucket_name or os.getenv('S3_BUCKET_NAME')
        self.aws_region = aws_region or os.getenv('AWS_REGION', 'us-east-1')
        
        # Initialize S3 client
        session = boto3.Session(
            aws_access_key_id=aws_access_key_id or os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=aws_secret_access_key or os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=self.aws_region
        )
        
        try:
            # Only attempt S3 connection if bucket name is provided
            if self.bucket_name:
                self.s3_client = session.client('s3')
                # Test connection
                self.s3_client.head_bucket(Bucket=self.bucket_name)
            else:
                print("Warning: S3_BUCKET_NAME not configured, S3 operations will be disabled")
                self.s3_client = None
        except (NoCredentialsError, ClientError, TypeError) as e:
            print(f"Warning: S3 connection failed: {e}")
            self.s3_client = None
    
    def _get_event_key(self, event_id: str) -> str:
        """Generate S3 key for event log file."""
        return f"events/{event_id}.json"
    
    def _ensure_valid_event_id(self, event_id: str) -> str:
        """Ensure event ID is valid for use as S3 key."""
        if not event_id:
            raise ValueError("Event ID cannot be empty")
        
        # Remove or replace invalid characters for S3 keys
        valid_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./"
        sanitized_id = ''.join(c if c in valid_chars else '_' for c in event_id)
        
        return sanitized_id
    
    def event_exists(self, event_id: str) -> bool:
        """
        Check if event log exists in S3.
        
        Args:
            event_id: Google Calendar event ID
            
        Returns:
            bool: True if event log exists, False otherwise
        """
        if not self.s3_client:
            return False
        
        try:
            sanitized_id = self._ensure_valid_event_id(event_id)
            key = self._get_event_key(sanitized_id)
            
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                raise e
    
    def create_event_log(self, event_id: str, event_data: Dict[str, Any], 
                        trigger_info: Dict[str, Any] = None) -> bool:
        """
        Create new event log in S3.
        
        Args:
            event_id: Google Calendar event ID
            event_data: Event data from Google Calendar
            trigger_info: Information about what triggered the event processing
            
        Returns:
            bool: True if log created successfully, False otherwise
        """
        if not self.s3_client:
            print("S3 client not available, cannot create event log")
            return False
        
        try:
            sanitized_id = self._ensure_valid_event_id(event_id)
            key = self._get_event_key(sanitized_id)
            
            # Create event log structure
            log_data = {
                'event_id': event_id,
                'original_event_id': event_id,  # Keep original for reference
                'created_timestamp': datetime.utcnow().isoformat(),
                'updated_timestamp': datetime.utcnow().isoformat(),
                'status': 'CREATED',
                'event_data': event_data,
                'trigger_info': trigger_info or {},
                'processing_history': [{
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'CREATED',
                    'details': 'Event log created'
                }],
                'email_history': [],
                'error_history': [],
                'company_name': None,
                'web_domain': None,
                'validation_status': 'PENDING',
                'reminder_sent': False,
                'escalation_sent': False,
                'completed': False
            }
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(log_data, indent=2, ensure_ascii=False),
                ContentType='application/json',
                ServerSideEncryption='AES256'
            )
            
            return True
            
        except Exception as e:
            print(f"Failed to create event log for {event_id}: {str(e)}")
            return False
    
    def get_event_log(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve event log from S3.
        
        Args:
            event_id: Google Calendar event ID
            
        Returns:
            Dict or None: Event log data if found, None otherwise
        """
        if not self.s3_client:
            return None
        
        try:
            sanitized_id = self._ensure_valid_event_id(event_id)
            key = self._get_event_key(sanitized_id)
            
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            log_data = json.loads(response['Body'].read().decode('utf-8'))
            
            return log_data
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            else:
                print(f"Failed to get event log for {event_id}: {str(e)}")
                return None
        except Exception as e:
            print(f"Failed to get event log for {event_id}: {str(e)}")
            return None
    
    def update_event_log(self, event_id: str, updates: Dict[str, Any], 
                        action: str = 'UPDATED') -> bool:
        """
        Update existing event log in S3.
        
        Args:
            event_id: Google Calendar event ID
            updates: Dictionary of fields to update
            action: Description of the action being performed
            
        Returns:
            bool: True if log updated successfully, False otherwise
        """
        if not self.s3_client:
            return False
        
        try:
            # Get existing log
            log_data = self.get_event_log(event_id)
            if not log_data:
                print(f"Event log not found for {event_id}")
                return False
            
            # Update fields
            for key, value in updates.items():
                log_data[key] = value
            
            # Update metadata
            log_data['updated_timestamp'] = datetime.utcnow().isoformat()
            
            # Add to processing history
            log_data['processing_history'].append({
                'timestamp': datetime.utcnow().isoformat(),
                'action': action,
                'details': f"Updated fields: {', '.join(updates.keys())}"
            })
            
            # Save updated log
            sanitized_id = self._ensure_valid_event_id(event_id)
            key = self._get_event_key(sanitized_id)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(log_data, indent=2, ensure_ascii=False),
                ContentType='application/json',
                ServerSideEncryption='AES256'
            )
            
            return True
            
        except Exception as e:
            print(f"Failed to update event log for {event_id}: {str(e)}")
            return False
    
    def add_email_record(self, event_id: str, email_type: str, recipient: str, 
                        success: bool, template_name: str = None, 
                        error_message: str = None) -> bool:
        """
        Add email sending record to event log.
        
        Args:
            event_id: Google Calendar event ID
            email_type: Type of email sent (e.g., 'REMINDER', 'ESCALATION')
            recipient: Email recipient address
            success: Whether email was sent successfully
            template_name: Name of email template used
            error_message: Error message if sending failed
            
        Returns:
            bool: True if record added successfully, False otherwise
        """
        email_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'email_type': email_type,
            'recipient': recipient,
            'success': success,
            'template_name': template_name,
            'error_message': error_message
        }
        
        # Get current log to append email record
        log_data = self.get_event_log(event_id)
        if not log_data:
            return False
        
        log_data['email_history'].append(email_record)
        
        # Update specific email flags
        if email_type == 'REMINDER' and success:
            log_data['reminder_sent'] = True
        elif email_type == 'ESCALATION' and success:
            log_data['escalation_sent'] = True
        
        return self.update_event_log(event_id, {
            'email_history': log_data['email_history'],
            'reminder_sent': log_data.get('reminder_sent', False),
            'escalation_sent': log_data.get('escalation_sent', False)
        }, f'EMAIL_{email_type}')
    
    def add_error_record(self, event_id: str, error_step: str, error_message: str, 
                        error_traceback: str = None) -> bool:
        """
        Add error record to event log.
        
        Args:
            event_id: Google Calendar event ID
            error_step: Step where error occurred
            error_message: Error message
            error_traceback: Full error traceback
            
        Returns:
            bool: True if record added successfully, False otherwise
        """
        error_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'error_step': error_step,
            'error_message': error_message,
            'error_traceback': error_traceback
        }
        
        # Get current log to append error record
        log_data = self.get_event_log(event_id)
        if not log_data:
            return False
        
        log_data['error_history'].append(error_record)
        
        return self.update_event_log(event_id, {
            'error_history': log_data['error_history'],
            'status': 'ERROR'
        }, 'ERROR_LOGGED')
    
    def mark_event_completed(self, event_id: str) -> bool:
        """
        Mark event as completed and optionally schedule for deletion.
        
        Args:
            event_id: Google Calendar event ID
            
        Returns:
            bool: True if marked successfully, False otherwise
        """
        return self.update_event_log(event_id, {
            'status': 'COMPLETED',
            'completed': True,
            'completion_timestamp': datetime.utcnow().isoformat()
        }, 'COMPLETED')
    
    def delete_event_log(self, event_id: str) -> bool:
        """
        Delete event log from S3.
        
        Args:
            event_id: Google Calendar event ID
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if not self.s3_client:
            return False
        
        try:
            sanitized_id = self._ensure_valid_event_id(event_id)
            key = self._get_event_key(sanitized_id)
            
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
            
        except Exception as e:
            print(f"Failed to delete event log for {event_id}: {str(e)}")
            return False
    
    def list_event_logs(self, status_filter: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List event logs with optional status filtering.
        
        Args:
            status_filter: Optional status to filter by
            limit: Maximum number of logs to return
            
        Returns:
            List of event log summaries
        """
        if not self.s3_client:
            return []
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='events/',
                MaxKeys=limit
            )
            
            logs = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Extract event ID from key
                    key = obj['Key']
                    if key.endswith('.json'):
                        event_id = key.replace('events/', '').replace('.json', '')
                        
                        # Get basic info about the log
                        log_info = {
                            'event_id': event_id,
                            'key': key,
                            'last_modified': obj['LastModified'].isoformat(),
                            'size': obj['Size']
                        }
                        
                        # If status filter is specified, load the log to check status
                        if status_filter:
                            log_data = self.get_event_log(event_id)
                            if log_data and log_data.get('status') == status_filter:
                                log_info.update({
                                    'status': log_data.get('status'),
                                    'created_timestamp': log_data.get('created_timestamp'),
                                    'updated_timestamp': log_data.get('updated_timestamp')
                                })
                                logs.append(log_info)
                        else:
                            logs.append(log_info)
            
            return logs
            
        except Exception as e:
            print(f"Failed to list event logs: {str(e)}")
            return []


# Global event log manager instance
event_log_manager = EventLogManager()