"""
Workflow Log Manager - S3 Workflow Log Management

This module handles workflow logging to S3 storage.
Workflow logs are stored as JSON files in the format: workflow_log/{run_id}.json
"""

import json
import os
import uuid
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class WorkflowLogManager:
    """Manages workflow logs in S3 storage."""
    
    def __init__(self, bucket_name: str = None, aws_region: str = None,
                 aws_access_key_id: str = None, aws_secret_access_key: str = None):
        """
        Initialize WorkflowLogManager with S3 configuration.
        
        Args:
            bucket_name: S3 bucket name for storing workflow logs
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
    
    def _get_workflow_key(self, run_id: str) -> str:
        """Generate S3 key for workflow log file."""
        return f"workflow_log/{run_id}.json"
    
    def generate_run_id(self) -> str:
        """Generate a unique run ID for a workflow execution."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4()).split('-')[0]
        return f"{timestamp}_{unique_id}"
    
    def create_workflow_log(self, run_id: str = None, workflow_type: str = 'GENERAL',
                           metadata: Dict[str, Any] = None) -> str:
        """
        Create new workflow log in S3.
        
        Args:
            run_id: Unique run identifier (generated if not provided)
            workflow_type: Type of workflow being executed
            metadata: Additional metadata for the workflow
            
        Returns:
            str: The run_id of the created workflow log
        """
        if not run_id:
            run_id = self.generate_run_id()
        
        if not self.s3_client:
            print("S3 client not available, logging to console only")
            print(f"WORKFLOW LOG CREATED: {run_id}")
            return run_id
        
        try:
            key = self._get_workflow_key(run_id)
            
            # Create workflow log structure
            log_data = {
                'run_id': run_id,
                'workflow_type': workflow_type,
                'start_timestamp': datetime.utcnow().isoformat(),
                'end_timestamp': None,
                'status': 'RUNNING',
                'metadata': metadata or {},
                'steps': [],
                'errors': [],
                'events_processed': [],
                'performance_metrics': {
                    'total_events': 0,
                    'successful_events': 0,
                    'failed_events': 0,
                    'emails_sent': 0,
                    'duration_seconds': None
                },
                'system_info': {
                    'created_by': 'calendar_event_processor',
                    'version': '1.0.0',
                    'environment': os.getenv('ENVIRONMENT', 'development')
                }
            }
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(log_data, indent=2, ensure_ascii=False),
                ContentType='application/json',
                ServerSideEncryption='AES256'
            )
            
            return run_id
            
        except Exception as e:
            print(f"Failed to create workflow log for {run_id}: {str(e)}")
            return run_id  # Return run_id even if S3 fails, for console logging
    
    def log_step(self, run_id: str, step_name: str, status: str = 'SUCCESS',
                 details: Dict[str, Any] = None, event_id: str = None,
                 duration_ms: int = None) -> bool:
        """
        Log a workflow step.
        
        Args:
            run_id: Workflow run identifier
            step_name: Name of the step being logged
            status: Step status (SUCCESS, ERROR, WARNING, SKIPPED)
            details: Additional details about the step
            event_id: Associated event ID if applicable
            duration_ms: Step execution duration in milliseconds
            
        Returns:
            bool: True if logged successfully, False otherwise
        """
        step_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'step_name': step_name,
            'status': status,
            'details': details or {},
            'event_id': event_id,
            'duration_ms': duration_ms
        }
        
        if not self.s3_client:
            # Console logging fallback
            print(f"WORKFLOW STEP [{run_id}]: {step_name} - {status}")
            if details:
                print(f"  Details: {json.dumps(details, indent=2)}")
            return True
        
        return self._append_to_workflow_log(run_id, {'steps': [step_data]})
    
    def log_error(self, run_id: str, step_name: str, error_message: str,
                  event_id: str = None, exception: Exception = None) -> bool:
        """
        Log an error in the workflow.
        
        Args:
            run_id: Workflow run identifier
            step_name: Name of the step where error occurred
            error_message: Error message
            event_id: Associated event ID if applicable
            exception: The exception object for traceback
            
        Returns:
            bool: True if logged successfully, False otherwise
        """
        error_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'step_name': step_name,
            'error_message': error_message,
            'event_id': event_id,
            'traceback': None
        }
        
        # Get traceback if exception provided
        if exception:
            error_data['traceback'] = traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        
        if not self.s3_client:
            # Console logging fallback
            print(f"WORKFLOW ERROR [{run_id}]: {step_name} - {error_message}")
            if error_data['traceback']:
                print(f"  Traceback: {''.join(error_data['traceback'])}")
            return True
        
        # Also log as a step with ERROR status
        self.log_step(run_id, step_name, 'ERROR', {'error_message': error_message}, event_id)
        
        return self._append_to_workflow_log(run_id, {'errors': [error_data]})
    
    def log_event_processed(self, run_id: str, event_id: str, status: str,
                           processing_details: Dict[str, Any] = None) -> bool:
        """
        Log an event processing result.
        
        Args:
            run_id: Workflow run identifier
            event_id: Google Calendar event ID
            status: Processing status (SUCCESS, ERROR, SKIPPED)
            processing_details: Details about the processing
            
        Returns:
            bool: True if logged successfully, False otherwise
        """
        event_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_id': event_id,
            'status': status,
            'details': processing_details or {}
        }
        
        if not self.s3_client:
            # Console logging fallback
            print(f"EVENT PROCESSED [{run_id}]: {event_id} - {status}")
            return True
        
        return self._append_to_workflow_log(run_id, {'events_processed': [event_data]})
    
    def update_performance_metrics(self, run_id: str, metrics: Dict[str, Any]) -> bool:
        """
        Update performance metrics for the workflow.
        
        Args:
            run_id: Workflow run identifier
            metrics: Dictionary of metrics to update
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        if not self.s3_client:
            print(f"PERFORMANCE METRICS [{run_id}]: {json.dumps(metrics, indent=2)}")
            return True
        
        # Get current log to update metrics
        log_data = self.get_workflow_log(run_id)
        if not log_data:
            return False
        
        # Update performance metrics
        current_metrics = log_data.get('performance_metrics', {})
        current_metrics.update(metrics)
        
        return self._update_workflow_log(run_id, {'performance_metrics': current_metrics})
    
    def complete_workflow(self, run_id: str, status: str = 'COMPLETED',
                         final_summary: Dict[str, Any] = None) -> bool:
        """
        Mark workflow as completed and finalize the log.
        
        Args:
            run_id: Workflow run identifier
            status: Final workflow status (COMPLETED, FAILED, CANCELLED)
            final_summary: Summary information about the workflow execution
            
        Returns:
            bool: True if completed successfully, False otherwise
        """
        completion_data = {
            'end_timestamp': datetime.utcnow().isoformat(),
            'status': status,
            'final_summary': final_summary or {}
        }
        
        # Calculate duration if we have start time
        if self.s3_client:
            log_data = self.get_workflow_log(run_id)
            if log_data and log_data.get('start_timestamp'):
                start_time = datetime.fromisoformat(log_data['start_timestamp'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(completion_data['end_timestamp'].replace('Z', '+00:00'))
                duration = (end_time - start_time).total_seconds()
                
                # Update performance metrics with duration
                metrics = log_data.get('performance_metrics', {})
                metrics['duration_seconds'] = duration
                completion_data['performance_metrics'] = metrics
        
        if not self.s3_client:
            print(f"WORKFLOW COMPLETED [{run_id}]: {status}")
            if final_summary:
                print(f"  Summary: {json.dumps(final_summary, indent=2)}")
            return True
        
        return self._update_workflow_log(run_id, completion_data)
    
    def get_workflow_log(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve workflow log from S3.
        
        Args:
            run_id: Workflow run identifier
            
        Returns:
            Dict or None: Workflow log data if found, None otherwise
        """
        if not self.s3_client:
            return None
        
        try:
            key = self._get_workflow_key(run_id)
            
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            log_data = json.loads(response['Body'].read().decode('utf-8'))
            
            return log_data
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            else:
                print(f"Failed to get workflow log for {run_id}: {str(e)}")
                return None
        except Exception as e:
            print(f"Failed to get workflow log for {run_id}: {str(e)}")
            return None
    
    def _append_to_workflow_log(self, run_id: str, data: Dict[str, List]) -> bool:
        """Append data to existing workflow log."""
        try:
            # Get existing log
            log_data = self.get_workflow_log(run_id)
            if not log_data:
                return False
            
            # Append new data to appropriate lists
            for key, values in data.items():
                if key in log_data and isinstance(log_data[key], list):
                    log_data[key].extend(values)
                else:
                    log_data[key] = values
            
            # Update timestamp
            log_data['last_updated'] = datetime.utcnow().isoformat()
            
            # Save updated log
            key = self._get_workflow_key(run_id)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(log_data, indent=2, ensure_ascii=False),
                ContentType='application/json',
                ServerSideEncryption='AES256'
            )
            
            return True
            
        except Exception as e:
            print(f"Failed to append to workflow log for {run_id}: {str(e)}")
            return False
    
    def _update_workflow_log(self, run_id: str, updates: Dict[str, Any]) -> bool:
        """Update fields in existing workflow log."""
        try:
            # Get existing log
            log_data = self.get_workflow_log(run_id)
            if not log_data:
                return False
            
            # Update fields
            for key, value in updates.items():
                log_data[key] = value
            
            # Update timestamp
            log_data['last_updated'] = datetime.utcnow().isoformat()
            
            # Save updated log
            key = self._get_workflow_key(run_id)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(log_data, indent=2, ensure_ascii=False),
                ContentType='application/json',
                ServerSideEncryption='AES256'
            )
            
            return True
            
        except Exception as e:
            print(f"Failed to update workflow log for {run_id}: {str(e)}")
            return False
    
    def list_workflow_logs(self, status_filter: str = None, limit: int = 100,
                          workflow_type: str = None) -> List[Dict[str, Any]]:
        """
        List workflow logs with optional filtering.
        
        Args:
            status_filter: Optional status to filter by
            limit: Maximum number of logs to return
            workflow_type: Optional workflow type to filter by
            
        Returns:
            List of workflow log summaries
        """
        if not self.s3_client:
            return []
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='workflow_log/',
                MaxKeys=limit
            )
            
            logs = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Extract run ID from key
                    key = obj['Key']
                    if key.endswith('.json'):
                        run_id = key.replace('workflow_log/', '').replace('.json', '')
                        
                        # Get basic info about the log
                        log_info = {
                            'run_id': run_id,
                            'key': key,
                            'last_modified': obj['LastModified'].isoformat(),
                            'size': obj['Size']
                        }
                        
                        # If filters are specified, load the log to check
                        if status_filter or workflow_type:
                            log_data = self.get_workflow_log(run_id)
                            if log_data:
                                matches_status = not status_filter or log_data.get('status') == status_filter
                                matches_type = not workflow_type or log_data.get('workflow_type') == workflow_type
                                
                                if matches_status and matches_type:
                                    log_info.update({
                                        'status': log_data.get('status'),
                                        'workflow_type': log_data.get('workflow_type'),
                                        'start_timestamp': log_data.get('start_timestamp'),
                                        'end_timestamp': log_data.get('end_timestamp')
                                    })
                                    logs.append(log_info)
                        else:
                            logs.append(log_info)
            
            return logs
            
        except Exception as e:
            print(f"Failed to list workflow logs: {str(e)}")
            return []
    
    def delete_workflow_log(self, run_id: str) -> bool:
        """
        Delete workflow log from S3.
        
        Args:
            run_id: Workflow run identifier
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if not self.s3_client:
            return False
        
        try:
            key = self._get_workflow_key(run_id)
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
            
        except Exception as e:
            print(f"Failed to delete workflow log for {run_id}: {str(e)}")
            return False


# Global workflow log manager instance
workflow_log_manager = WorkflowLogManager()