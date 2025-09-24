"""
Workflow Log Manager for Agentic Intelligence Research System

This module manages workflow logs stored in S3 in the format workflow_log/{run_id}.json.
Handles creating, appending to, and managing workflow execution logs including
steps, errors, details, and comprehensive error handling for each workflow run.
"""

import json
import boto3
import traceback
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
import logging
from botocore.exceptions import ClientError, NoCredentialsError


class WorkflowStatus(Enum):
    """Workflow run status enumeration"""
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class StepStatus(Enum):
    """Individual step status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


@dataclass
class WorkflowStep:
    """Individual workflow step"""
    step_id: str
    step_name: str
    status: StepStatus
    start_timestamp: datetime
    end_timestamp: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = {
            'step_id': self.step_id,
            'step_name': self.step_name,
            'status': self.status.value,
            'start_timestamp': self.start_timestamp.isoformat(),
            'details': self.details,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries
        }
        
        if self.end_timestamp:
            data['end_timestamp'] = self.end_timestamp.isoformat()
        if self.duration_seconds is not None:
            data['duration_seconds'] = self.duration_seconds
        if self.error_message:
            data['error_message'] = self.error_message
        if self.error_traceback:
            data['error_traceback'] = self.error_traceback
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowStep':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['status'] = StepStatus(data_copy['status'])
        data_copy['start_timestamp'] = datetime.fromisoformat(data_copy['start_timestamp'])
        
        if data_copy.get('end_timestamp'):
            data_copy['end_timestamp'] = datetime.fromisoformat(data_copy['end_timestamp'])
        
        return cls(**data_copy)
    
    def complete(self, details: Dict[str, Any] = None) -> None:
        """Mark step as completed"""
        self.status = StepStatus.COMPLETED
        self.end_timestamp = datetime.now(timezone.utc)
        if self.start_timestamp:
            self.duration_seconds = (self.end_timestamp - self.start_timestamp).total_seconds()
        if details:
            self.details.update(details)
    
    def fail(self, error: Exception, details: Dict[str, Any] = None) -> None:
        """Mark step as failed"""
        self.status = StepStatus.FAILED
        self.end_timestamp = datetime.now(timezone.utc)
        if self.start_timestamp:
            self.duration_seconds = (self.end_timestamp - self.start_timestamp).total_seconds()
        
        self.error_message = str(error)
        self.error_traceback = traceback.format_exc()
        
        if details:
            self.details.update(details)


@dataclass
class WorkflowRun:
    """Complete workflow run log"""
    run_id: str
    workflow_name: str
    workflow_version: Optional[str]
    status: WorkflowStatus
    start_timestamp: datetime
    end_timestamp: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    steps: List[WorkflowStep] = field(default_factory=list)
    error_summary: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    event_ids: List[str] = field(default_factory=list)
    triggered_by: Optional[str] = None
    environment: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = {
            'run_id': self.run_id,
            'workflow_name': self.workflow_name,
            'workflow_version': self.workflow_version,
            'status': self.status.value,
            'start_timestamp': self.start_timestamp.isoformat(),
            'steps': [step.to_dict() for step in self.steps],
            'metadata': self.metadata,
            'event_ids': self.event_ids,
            'triggered_by': self.triggered_by,
            'environment': self.environment
        }
        
        if self.end_timestamp:
            data['end_timestamp'] = self.end_timestamp.isoformat()
        if self.duration_seconds is not None:
            data['duration_seconds'] = self.duration_seconds
        if self.error_summary:
            data['error_summary'] = self.error_summary
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowRun':
        """Create from dictionary"""
        data_copy = data.copy()
        data_copy['status'] = WorkflowStatus(data_copy['status'])
        data_copy['start_timestamp'] = datetime.fromisoformat(data_copy['start_timestamp'])
        
        if data_copy.get('end_timestamp'):
            data_copy['end_timestamp'] = datetime.fromisoformat(data_copy['end_timestamp'])
        
        data_copy['steps'] = [
            WorkflowStep.from_dict(step_data) for step_data in data_copy.get('steps', [])
        ]
        
        return cls(**data_copy)
    
    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """Get step by ID"""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def get_failed_steps(self) -> List[WorkflowStep]:
        """Get all failed steps"""
        return [step for step in self.steps if step.status == StepStatus.FAILED]
    
    def get_current_step(self) -> Optional[WorkflowStep]:
        """Get currently running step"""
        for step in self.steps:
            if step.status == StepStatus.RUNNING:
                return step
        return None


class WorkflowLogManager:
    """Manages workflow logs in S3 storage"""
    
    def __init__(self, 
                 bucket_name: str,
                 aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None,
                 aws_region: str = "us-east-1",
                 workflow_prefix: str = "workflow_log/",
                 auto_save: bool = True):
        """
        Initialize WorkflowLogManager
        
        Args:
            bucket_name: S3 bucket name
            aws_access_key_id: AWS access key (optional, can use IAM roles)
            aws_secret_access_key: AWS secret key (optional, can use IAM roles)
            aws_region: AWS region
            workflow_prefix: S3 prefix for workflow logs
            auto_save: Whether to automatically save after each operation
        """
        self.bucket_name = bucket_name
        self.workflow_prefix = workflow_prefix.rstrip('/') + '/'
        self.auto_save = auto_save
        self._current_runs: Dict[str, WorkflowRun] = {}
        
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
    
    def _get_workflow_key(self, run_id: str) -> str:
        """Get S3 key for workflow log"""
        return f"{self.workflow_prefix}{run_id}.json"
    
    def _save_workflow_run(self, workflow_run: WorkflowRun) -> None:
        """Save workflow run to S3"""
        try:
            key = self._get_workflow_key(workflow_run.run_id)
            data = json.dumps(workflow_run.to_dict(), indent=2)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType='application/json'
            )
            
        except Exception as e:
            self.logger.error(f"Failed to save workflow run {workflow_run.run_id}: {e}")
            raise
    
    def start_workflow_run(self, 
                          workflow_name: str,
                          run_id: Optional[str] = None,
                          workflow_version: Optional[str] = None,
                          triggered_by: Optional[str] = None,
                          environment: Optional[str] = None,
                          metadata: Dict[str, Any] = None,
                          event_ids: List[str] = None) -> str:
        """Start a new workflow run"""
        try:
            if run_id is None:
                run_id = f"{workflow_name}-{uuid.uuid4().hex[:8]}-{int(datetime.now().timestamp())}"
            
            workflow_run = WorkflowRun(
                run_id=run_id,
                workflow_name=workflow_name,
                workflow_version=workflow_version,
                status=WorkflowStatus.STARTED,
                start_timestamp=datetime.now(timezone.utc),
                triggered_by=triggered_by,
                environment=environment,
                metadata=metadata or {},
                event_ids=event_ids or []
            )
            
            self._current_runs[run_id] = workflow_run
            
            if self.auto_save:
                self._save_workflow_run(workflow_run)
            
            self.logger.info(f"Started workflow run: {run_id}")
            return run_id
            
        except Exception as e:
            self.logger.error(f"Failed to start workflow run: {e}")
            raise
    
    def start_step(self, 
                   run_id: str, 
                   step_name: str,
                   step_id: Optional[str] = None,
                   details: Dict[str, Any] = None,
                   max_retries: int = 0) -> str:
        """Start a new workflow step"""
        try:
            if step_id is None:
                step_id = f"{step_name.lower().replace(' ', '_')}_{len(self._current_runs.get(run_id, WorkflowRun('', '', '', WorkflowStatus.STARTED, datetime.now())).steps) + 1}"
            
            workflow_run = self._current_runs.get(run_id)
            if not workflow_run:
                # Try to load from S3
                workflow_run = self.get_workflow_run(run_id)
                if not workflow_run:
                    raise ValueError(f"Workflow run not found: {run_id}")
                self._current_runs[run_id] = workflow_run
            
            step = WorkflowStep(
                step_id=step_id,
                step_name=step_name,
                status=StepStatus.RUNNING,
                start_timestamp=datetime.now(timezone.utc),
                details=details or {},
                max_retries=max_retries
            )
            
            workflow_run.steps.append(step)
            workflow_run.status = WorkflowStatus.RUNNING
            
            if self.auto_save:
                self._save_workflow_run(workflow_run)
            
            self.logger.info(f"Started step {step_id} in workflow {run_id}")
            return step_id
            
        except Exception as e:
            self.logger.error(f"Failed to start step in workflow {run_id}: {e}")
            # Try to log this error to the workflow
            self.log_error(run_id, "start_step", e)
            raise
    
    def complete_step(self, 
                     run_id: str, 
                     step_id: str, 
                     details: Dict[str, Any] = None) -> bool:
        """Complete a workflow step"""
        try:
            workflow_run = self._current_runs.get(run_id)
            if not workflow_run:
                workflow_run = self.get_workflow_run(run_id)
                if not workflow_run:
                    self.logger.error(f"Workflow run not found: {run_id}")
                    return False
                self._current_runs[run_id] = workflow_run
            
            step = workflow_run.get_step(step_id)
            if not step:
                self.logger.error(f"Step not found: {step_id} in workflow {run_id}")
                return False
            
            step.complete(details)
            
            if self.auto_save:
                self._save_workflow_run(workflow_run)
            
            self.logger.info(f"Completed step {step_id} in workflow {run_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to complete step {step_id} in workflow {run_id}: {e}")
            self.log_error(run_id, "complete_step", e, step_id)
            return False
    
    def fail_step(self, 
                  run_id: str, 
                  step_id: str, 
                  error: Exception, 
                  details: Dict[str, Any] = None) -> bool:
        """Fail a workflow step"""
        try:
            workflow_run = self._current_runs.get(run_id)
            if not workflow_run:
                workflow_run = self.get_workflow_run(run_id)
                if not workflow_run:
                    self.logger.error(f"Workflow run not found: {run_id}")
                    return False
                self._current_runs[run_id] = workflow_run
            
            step = workflow_run.get_step(step_id)
            if not step:
                self.logger.error(f"Step not found: {step_id} in workflow {run_id}")
                return False
            
            step.fail(error, details)
            
            if self.auto_save:
                self._save_workflow_run(workflow_run)
            
            self.logger.error(f"Failed step {step_id} in workflow {run_id}: {error}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to record step failure {step_id} in workflow {run_id}: {e}")
            return False
    
    def complete_workflow(self, run_id: str, metadata: Dict[str, Any] = None) -> bool:
        """Complete a workflow run"""
        try:
            workflow_run = self._current_runs.get(run_id)
            if not workflow_run:
                workflow_run = self.get_workflow_run(run_id)
                if not workflow_run:
                    self.logger.error(f"Workflow run not found: {run_id}")
                    return False
                self._current_runs[run_id] = workflow_run
            
            workflow_run.status = WorkflowStatus.COMPLETED
            workflow_run.end_timestamp = datetime.now(timezone.utc)
            workflow_run.duration_seconds = (
                workflow_run.end_timestamp - workflow_run.start_timestamp
            ).total_seconds()
            
            if metadata:
                workflow_run.metadata.update(metadata)
            
            self._save_workflow_run(workflow_run)
            
            # Remove from current runs to free memory
            if run_id in self._current_runs:
                del self._current_runs[run_id]
            
            self.logger.info(f"Completed workflow run: {run_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to complete workflow {run_id}: {e}")
            return False
    
    def fail_workflow(self, run_id: str, error: Exception, metadata: Dict[str, Any] = None) -> bool:
        """Fail a workflow run"""
        try:
            workflow_run = self._current_runs.get(run_id)
            if not workflow_run:
                workflow_run = self.get_workflow_run(run_id)
                if not workflow_run:
                    self.logger.error(f"Workflow run not found: {run_id}")
                    return False
                self._current_runs[run_id] = workflow_run
            
            workflow_run.status = WorkflowStatus.FAILED
            workflow_run.end_timestamp = datetime.now(timezone.utc)
            workflow_run.duration_seconds = (
                workflow_run.end_timestamp - workflow_run.start_timestamp
            ).total_seconds()
            workflow_run.error_summary = str(error)
            
            if metadata:
                workflow_run.metadata.update(metadata)
            
            self._save_workflow_run(workflow_run)
            
            # Remove from current runs to free memory
            if run_id in self._current_runs:
                del self._current_runs[run_id]
            
            self.logger.error(f"Failed workflow run {run_id}: {error}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to record workflow failure {run_id}: {e}")
            return False
    
    def log_error(self, 
                  run_id: str, 
                  step: str, 
                  error: Exception, 
                  event_id: Optional[str] = None,
                  timestamp: Optional[datetime] = None) -> bool:
        """Log error in workflow run"""
        try:
            workflow_run = self._current_runs.get(run_id)
            if not workflow_run:
                workflow_run = self.get_workflow_run(run_id)
                if not workflow_run:
                    # Create a minimal workflow run for error logging
                    workflow_run = WorkflowRun(
                        run_id=run_id,
                        workflow_name="unknown",
                        workflow_version=None,
                        status=WorkflowStatus.FAILED,
                        start_timestamp=timestamp or datetime.now(timezone.utc)
                    )
                    self._current_runs[run_id] = workflow_run
            
            # Create error step if needed
            error_step_id = f"error_{len(workflow_run.steps) + 1}"
            error_step = WorkflowStep(
                step_id=error_step_id,
                step_name=f"Error in {step}",
                status=StepStatus.FAILED,
                start_timestamp=timestamp or datetime.now(timezone.utc),
                details={
                    'original_step': step,
                    'event_id': event_id,
                    'error_type': type(error).__name__
                }
            )
            error_step.fail(error)
            
            workflow_run.steps.append(error_step)
            
            if self.auto_save:
                self._save_workflow_run(workflow_run)
            
            self.logger.error(f"Logged error in workflow {run_id}, step {step}: {error}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to log error in workflow {run_id}: {e}")
            return False
    
    def get_workflow_run(self, run_id: str) -> Optional[WorkflowRun]:
        """Retrieve workflow run from S3"""
        try:
            # Check current runs first
            if run_id in self._current_runs:
                return self._current_runs[run_id]
            
            key = self._get_workflow_key(run_id)
            
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            data = json.loads(response['Body'].read().decode('utf-8'))
            
            return WorkflowRun.from_dict(data)
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                self.logger.warning(f"Workflow run not found: {run_id}")
                return None
            else:
                self.logger.error(f"Failed to get workflow run {run_id}: {e}")
                raise
        except Exception as e:
            self.logger.error(f"Failed to get workflow run {run_id}: {e}")
            raise
    
    def list_workflow_runs(self, 
                          workflow_name: Optional[str] = None,
                          status: Optional[WorkflowStatus] = None,
                          limit: int = None) -> List[str]:
        """List workflow run IDs"""
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=self.workflow_prefix
            )
            
            run_ids = []
            count = 0
            
            for page in page_iterator:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    if limit and count >= limit:
                        break
                    
                    key = obj['Key']
                    if key.endswith('.json'):
                        run_id = key.replace(self.workflow_prefix, '').replace('.json', '')
                        
                        # Apply filters if specified
                        if workflow_name or status:
                            workflow_run = self.get_workflow_run(run_id)
                            if not workflow_run:
                                continue
                            
                            if workflow_name and workflow_run.workflow_name != workflow_name:
                                continue
                            if status and workflow_run.status != status:
                                continue
                        
                        run_ids.append(run_id)
                        count += 1
                
                if limit and count >= limit:
                    break
            
            return run_ids
            
        except Exception as e:
            self.logger.error(f"Failed to list workflow runs: {e}")
            return []
    
    def get_workflow_stats(self, workflow_name: Optional[str] = None) -> Dict[str, Any]:
        """Get workflow execution statistics"""
        try:
            runs = self.list_workflow_runs(workflow_name=workflow_name)
            
            stats = {
                'total_runs': len(runs),
                'completed': 0,
                'failed': 0,
                'running': 0,
                'average_duration': 0,
                'success_rate': 0
            }
            
            total_duration = 0
            duration_count = 0
            
            for run_id in runs:
                workflow_run = self.get_workflow_run(run_id)
                if not workflow_run:
                    continue
                
                if workflow_run.status == WorkflowStatus.COMPLETED:
                    stats['completed'] += 1
                elif workflow_run.status == WorkflowStatus.FAILED:
                    stats['failed'] += 1
                elif workflow_run.status in [WorkflowStatus.RUNNING, WorkflowStatus.STARTED]:
                    stats['running'] += 1
                
                if workflow_run.duration_seconds:
                    total_duration += workflow_run.duration_seconds
                    duration_count += 1
            
            if duration_count > 0:
                stats['average_duration'] = total_duration / duration_count
            
            if stats['total_runs'] > 0:
                stats['success_rate'] = (stats['completed'] / stats['total_runs']) * 100
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get workflow stats: {e}")
            return {}


if __name__ == "__main__":
    # Example usage
    import os
    import time
    
    # Example configuration (would typically be loaded from environment)
    bucket_name = os.getenv("S3_WORKFLOW_BUCKET", "agentic-intelligence-workflows")
    
    try:
        # Create workflow log manager
        manager = WorkflowLogManager(bucket_name=bucket_name)
        
        # Start a workflow run
        run_id = manager.start_workflow_run(
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            triggered_by="test_script",
            environment="development",
            metadata={"test": True}
        )
        
        print(f"✓ Started workflow run: {run_id}")
        
        # Add some steps
        step1_id = manager.start_step(run_id, "Initialize System")
        time.sleep(0.1)  # Simulate work
        manager.complete_step(run_id, step1_id, {"initialized": True})
        
        step2_id = manager.start_step(run_id, "Process Data")
        time.sleep(0.1)  # Simulate work
        manager.complete_step(run_id, step2_id, {"records_processed": 100})
        
        # Complete workflow
        manager.complete_workflow(run_id, {"total_records": 100})
        
        print(f"✓ Completed workflow run: {run_id}")
        
        # Get stats
        stats = manager.get_workflow_stats("test_workflow")
        print(f"Workflow stats: {stats}")
        
    except Exception as e:
        print(f"✗ Workflow log manager test failed: {e}")