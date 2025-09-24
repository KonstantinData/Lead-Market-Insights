"""
Workflow Log Manager for Agentic Intelligence Research System

This module provides S3-based workflow logging functionality for tracking
workflow runs, errors, step details, tracebacks, and comprehensive execution
monitoring. Each workflow run is logged with complete execution details.
"""

import json
import logging
import os
import traceback
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


class WorkflowStatus(Enum):
    """Workflow execution status."""
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    PAUSED = "paused"


class StepStatus(Enum):
    """Individual step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class WorkflowStep:
    """Individual workflow step data."""
    step_id: str
    step_name: str
    status: StepStatus
    start_time: str
    end_time: str = ""
    duration_seconds: float = 0.0
    event_id: str = ""
    request_id: str = ""
    component: str = ""
    function_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    error_type: str = ""
    traceback: str = ""
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowStep':
        """Create WorkflowStep from dictionary."""
        if 'status' in data:
            data['status'] = StepStatus(data['status'])
        return cls(**data)


@dataclass
class WorkflowRun:
    """Complete workflow run data."""
    run_id: str
    workflow_name: str
    status: WorkflowStatus
    start_time: str = ""
    end_time: str = ""
    duration_seconds: float = 0.0
    triggered_by: str = "system"
    trigger_event: str = ""
    request_id: str = ""
    priority: str = "medium"
    steps: List[WorkflowStep] = field(default_factory=list)
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    error_count: int = 0
    warning_count: int = 0
    logs: List[Dict[str, Any]] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    configuration: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.start_time:
            self.start_time = datetime.utcnow().isoformat() + "Z"
        
        # Initialize environment info if not provided
        if not self.environment:
            self.environment = {
                'python_version': sys.version,
                'platform': sys.platform,
                'hostname': os.getenv('HOSTNAME', 'unknown'),
                'user': os.getenv('USER', 'unknown')
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['status'] = self.status.value
        # Convert steps
        data['steps'] = [step.to_dict() for step in self.steps]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowRun':
        """Create WorkflowRun from dictionary."""
        if 'status' in data:
            data['status'] = WorkflowStatus(data['status'])
        
        # Convert steps
        if 'steps' in data:
            data['steps'] = [WorkflowStep.from_dict(step) for step in data['steps']]
        
        return cls(**data)
    
    def add_step(self, step: WorkflowStep) -> None:
        """Add a step to the workflow run."""
        self.steps.append(step)
        self.total_steps = len(self.steps)
        
        # Update counters
        if step.status == StepStatus.COMPLETED:
            self.completed_steps += 1
        elif step.status == StepStatus.FAILED:
            self.failed_steps += 1
    
    def update_step(self, step_id: str, **kwargs) -> bool:
        """Update an existing step."""
        for step in self.steps:
            if step.step_id == step_id:
                for key, value in kwargs.items():
                    if hasattr(step, key):
                        setattr(step, key, value)
                
                # Update counters
                self._update_counters()
                return True
        return False
    
    def _update_counters(self) -> None:
        """Update step counters."""
        self.completed_steps = sum(1 for step in self.steps if step.status == StepStatus.COMPLETED)
        self.failed_steps = sum(1 for step in self.steps if step.status == StepStatus.FAILED)
        self.total_steps = len(self.steps)
    
    def add_log(self, level: LogLevel, message: str, component: str = "", **kwargs) -> None:
        """Add a log entry to the workflow run."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + "Z",
            'level': level.value,
            'message': message,
            'component': component,
            **kwargs
        }
        self.logs.append(log_entry)
        
        # Update counters
        if level == LogLevel.ERROR or level == LogLevel.CRITICAL:
            self.error_count += 1
        elif level == LogLevel.WARNING:
            self.warning_count += 1
    
    def finish(self, status: WorkflowStatus = None) -> None:
        """Mark workflow as finished."""
        self.end_time = datetime.utcnow().isoformat() + "Z"
        
        if self.start_time:
            start_dt = datetime.fromisoformat(self.start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(self.end_time.replace('Z', '+00:00'))
            self.duration_seconds = (end_dt - start_dt).total_seconds()
        
        if status:
            self.status = status
        elif self.failed_steps > 0:
            self.status = WorkflowStatus.FAILED
        else:
            self.status = WorkflowStatus.COMPLETED


@dataclass
class S3WorkflowConfig:
    """S3 configuration for workflow logging."""
    bucket_name: str
    region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    workflow_logs_prefix: str = "workflow_logs/"
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


class WorkflowLogManager:
    """S3-based workflow log manager for comprehensive execution tracking."""
    
    def __init__(self, s3_config: S3WorkflowConfig):
        self.config = s3_config
        self.logger = logging.getLogger(__name__)
        self._s3_client = None
        self._current_runs = {}  # Track active workflow runs
        
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
    
    def _get_workflow_key(self, run_id: str) -> str:
        """Generate S3 key for workflow run."""
        return f"{self.config.workflow_logs_prefix}{run_id}.json"
    
    def start_workflow_run(
        self, 
        run_id: str, 
        workflow_name: str, 
        triggered_by: str = "system",
        request_id: str = "",
        priority: str = "medium",
        configuration: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> WorkflowRun:
        """
        Start a new workflow run.
        
        Args:
            run_id: Unique run identifier
            workflow_name: Name of the workflow
            triggered_by: Who/what triggered the workflow
            request_id: Associated request ID
            priority: Workflow priority
            configuration: Workflow configuration
            metadata: Additional metadata
            
        Returns:
            WorkflowRun object
        """
        workflow_run = WorkflowRun(
            run_id=run_id,
            workflow_name=workflow_name,
            status=WorkflowStatus.STARTED,
            triggered_by=triggered_by,
            request_id=request_id,
            priority=priority,
            configuration=configuration or {},
            metadata=metadata or {}
        )
        
        # Track in memory
        self._current_runs[run_id] = workflow_run
        
        # Log start
        workflow_run.add_log(
            LogLevel.INFO, 
            f"Workflow '{workflow_name}' started",
            component="workflow_log_manager",
            run_id=run_id
        )
        
        # Save initial state
        self._save_workflow_run(workflow_run)
        
        self.logger.info(f"Workflow run started: {run_id} - {workflow_name}")
        return workflow_run
    
    def _save_workflow_run(self, workflow_run: WorkflowRun) -> bool:
        """Save workflow run to S3."""
        try:
            # Prepare workflow data with metadata
            workflow_dict = workflow_run.to_dict()
            workflow_dict['saved_at'] = datetime.utcnow().isoformat() + "Z"
            
            # Convert to JSON
            workflow_json = json.dumps(workflow_dict, indent=2, ensure_ascii=False)
            
            # Prepare S3 put parameters
            put_kwargs = {
                'Bucket': self.config.bucket_name,
                'Key': self._get_workflow_key(workflow_run.run_id),
                'Body': workflow_json.encode('utf-8'),
                'ContentType': 'application/json',
                'StorageClass': self.config.storage_class,
                'Metadata': {
                    'run-id': workflow_run.run_id,
                    'workflow-name': workflow_run.workflow_name,
                    'status': workflow_run.status.value,
                    'request-id': workflow_run.request_id,
                    'saved-by': 'workflow-log-manager'
                }
            }
            
            # Add encryption if enabled
            if self.config.use_encryption:
                put_kwargs['ServerSideEncryption'] = 'AES256'
            
            # Upload to S3
            self.s3_client.put_object(**put_kwargs)
            
            self.logger.debug(f"Workflow run saved: {workflow_run.run_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save workflow run {workflow_run.run_id}: {e}")
            return False
    
    def get_workflow_run(self, run_id: str) -> Optional[WorkflowRun]:
        """
        Retrieve workflow run from S3 or memory.
        
        Args:
            run_id: Run ID to retrieve
            
        Returns:
            WorkflowRun if found, None otherwise
        """
        # Check memory first
        if run_id in self._current_runs:
            return self._current_runs[run_id]
        
        # Check S3
        try:
            response = self.s3_client.get_object(
                Bucket=self.config.bucket_name,
                Key=self._get_workflow_key(run_id)
            )
            
            content = json.loads(response['Body'].read().decode('utf-8'))
            workflow_run = WorkflowRun.from_dict(content)
            
            self.logger.debug(f"Workflow run retrieved from S3: {run_id}")
            return workflow_run
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                self.logger.warning(f"Workflow run not found: {run_id}")
            else:
                self.logger.error(f"Error retrieving workflow run {run_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving workflow run {run_id}: {e}")
            return None
    
    def log_step_start(
        self, 
        run_id: str, 
        step_id: str, 
        step_name: str,
        component: str = "",
        function_name: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        request_id: str = ""
    ) -> bool:
        """
        Log the start of a workflow step.
        
        Args:
            run_id: Workflow run ID
            step_id: Unique step identifier
            step_name: Human-readable step name
            component: Component executing the step
            function_name: Function name being executed
            parameters: Step parameters
            event_id: Associated event ID
            request_id: Associated request ID
            
        Returns:
            bool: True if logged successfully
        """
        try:
            workflow_run = self.get_workflow_run(run_id)
            if not workflow_run:
                self.logger.error(f"Cannot log step for non-existent workflow: {run_id}")
                return False
            
            step = WorkflowStep(
                step_id=step_id,
                step_name=step_name,
                status=StepStatus.RUNNING,
                start_time=datetime.utcnow().isoformat() + "Z",
                component=component,
                function_name=function_name,
                parameters=parameters or {},
                event_id=event_id,
                request_id=request_id
            )
            
            workflow_run.add_step(step)
            workflow_run.status = WorkflowStatus.RUNNING
            
            # Log step start
            workflow_run.add_log(
                LogLevel.INFO,
                f"Step '{step_name}' started",
                component=component,
                step_id=step_id,
                function_name=function_name
            )
            
            # Update in memory
            self._current_runs[run_id] = workflow_run
            
            # Save to S3
            self._save_workflow_run(workflow_run)
            
            self.logger.debug(f"Step logged: {run_id} - {step_id} - {step_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging step start: {e}")
            return False
    
    def log_step_completion(
        self, 
        run_id: str, 
        step_id: str, 
        status: StepStatus,
        result: Optional[Dict[str, Any]] = None,
        error_message: str = "",
        error_type: str = "",
        traceback_str: str = ""
    ) -> bool:
        """
        Log the completion of a workflow step.
        
        Args:
            run_id: Workflow run ID
            step_id: Step identifier
            status: Final step status
            result: Step execution result
            error_message: Error message if failed
            error_type: Error type if failed
            traceback_str: Full traceback if failed
            
        Returns:
            bool: True if logged successfully
        """
        try:
            workflow_run = self.get_workflow_run(run_id)
            if not workflow_run:
                self.logger.error(f"Cannot update step for non-existent workflow: {run_id}")
                return False
            
            # Find and update the step
            step_found = False
            for step in workflow_run.steps:
                if step.step_id == step_id:
                    step.status = status
                    step.end_time = datetime.utcnow().isoformat() + "Z"
                    step.result = result or {}
                    step.error_message = error_message
                    step.error_type = error_type
                    step.traceback = traceback_str
                    
                    # Calculate duration
                    if step.start_time:
                        start_dt = datetime.fromisoformat(step.start_time.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(step.end_time.replace('Z', '+00:00'))
                        step.duration_seconds = (end_dt - start_dt).total_seconds()
                    
                    step_found = True
                    break
            
            if not step_found:
                self.logger.error(f"Step {step_id} not found in workflow {run_id}")
                return False
            
            # Update counters
            workflow_run._update_counters()
            
            # Log step completion
            if status == StepStatus.COMPLETED:
                workflow_run.add_log(
                    LogLevel.INFO,
                    f"Step '{step_id}' completed successfully",
                    component="workflow_log_manager",
                    step_id=step_id,
                    duration_seconds=step.duration_seconds
                )
            elif status == StepStatus.FAILED:
                workflow_run.add_log(
                    LogLevel.ERROR,
                    f"Step '{step_id}' failed: {error_message}",
                    component="workflow_log_manager",
                    step_id=step_id,
                    error_type=error_type,
                    error_message=error_message,
                    traceback=traceback_str
                )
            
            # Update in memory
            self._current_runs[run_id] = workflow_run
            
            # Save to S3
            self._save_workflow_run(workflow_run)
            
            self.logger.debug(f"Step completion logged: {run_id} - {step_id} - {status.value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging step completion: {e}")
            return False
    
    def log_event(self, run_id: str, level: LogLevel, message: str, **kwargs) -> bool:
        """
        Log an event to the workflow run.
        
        Args:
            run_id: Workflow run ID
            level: Log level
            message: Log message
            **kwargs: Additional log data
            
        Returns:
            bool: True if logged successfully
        """
        try:
            workflow_run = self.get_workflow_run(run_id)
            if not workflow_run:
                self.logger.error(f"Cannot log event for non-existent workflow: {run_id}")
                return False
            
            workflow_run.add_log(level, message, **kwargs)
            
            # Update in memory
            self._current_runs[run_id] = workflow_run
            
            # Save to S3 (optional for frequent logs)
            if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                self._save_workflow_run(workflow_run)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging event: {e}")
            return False
    
    def log_exception(self, run_id: str, exception: Exception, step_id: str = "", component: str = "") -> bool:
        """
        Log an exception with full traceback.
        
        Args:
            run_id: Workflow run ID
            exception: Exception object
            step_id: Associated step ID
            component: Component where exception occurred
            
        Returns:
            bool: True if logged successfully
        """
        try:
            # Get traceback
            traceback_str = traceback.format_exc()
            
            # Log the exception
            return self.log_event(
                run_id=run_id,
                level=LogLevel.ERROR,
                message=f"Exception in {component}: {str(exception)}",
                component=component,
                step_id=step_id,
                exception_type=type(exception).__name__,
                exception_message=str(exception),
                traceback=traceback_str
            )
            
        except Exception as e:
            self.logger.error(f"Error logging exception: {e}")
            return False
    
    def finish_workflow_run(self, run_id: str, status: WorkflowStatus = None) -> bool:
        """
        Mark a workflow run as finished.
        
        Args:
            run_id: Workflow run ID
            status: Final status (if not provided, will be determined automatically)
            
        Returns:
            bool: True if finished successfully
        """
        try:
            workflow_run = self.get_workflow_run(run_id)
            if not workflow_run:
                self.logger.error(f"Cannot finish non-existent workflow: {run_id}")
                return False
            
            workflow_run.finish(status)
            
            # Log completion
            workflow_run.add_log(
                LogLevel.INFO,
                f"Workflow '{workflow_run.workflow_name}' finished with status {workflow_run.status.value}",
                component="workflow_log_manager",
                final_status=workflow_run.status.value,
                duration_seconds=workflow_run.duration_seconds,
                total_steps=workflow_run.total_steps,
                completed_steps=workflow_run.completed_steps,
                failed_steps=workflow_run.failed_steps
            )
            
            # Save final state
            self._save_workflow_run(workflow_run)
            
            # Remove from active runs
            if run_id in self._current_runs:
                del self._current_runs[run_id]
            
            self.logger.info(
                f"Workflow run finished: {run_id} - {workflow_run.status.value} - "
                f"Duration: {workflow_run.duration_seconds:.2f}s - "
                f"Steps: {workflow_run.completed_steps}/{workflow_run.total_steps}"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error finishing workflow run: {e}")
            return False
    
    def list_workflow_runs(self, prefix: str = "", max_keys: int = 100) -> List[str]:
        """
        List workflow run IDs.
        
        Args:
            prefix: Optional prefix filter
            max_keys: Maximum number of runs to return
            
        Returns:
            List of workflow run IDs
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.config.bucket_name,
                Prefix=self.config.workflow_logs_prefix + prefix,
                MaxKeys=max_keys
            )
            
            run_ids = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Extract run ID from key
                    key = obj['Key']
                    if key.endswith('.json'):
                        run_id = key.replace(self.config.workflow_logs_prefix, '').replace('.json', '')
                        run_ids.append(run_id)
            
            self.logger.debug(f"Listed {len(run_ids)} workflow runs")
            return run_ids
            
        except Exception as e:
            self.logger.error(f"Error listing workflow runs: {e}")
            return []
    
    def get_workflow_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of workflow run statistics.
        
        Args:
            run_id: Workflow run ID
            
        Returns:
            Summary dictionary or None
        """
        try:
            workflow_run = self.get_workflow_run(run_id)
            if not workflow_run:
                return None
            
            return {
                'run_id': workflow_run.run_id,
                'workflow_name': workflow_run.workflow_name,
                'status': workflow_run.status.value,
                'duration_seconds': workflow_run.duration_seconds,
                'start_time': workflow_run.start_time,
                'end_time': workflow_run.end_time,
                'total_steps': workflow_run.total_steps,
                'completed_steps': workflow_run.completed_steps,
                'failed_steps': workflow_run.failed_steps,
                'error_count': workflow_run.error_count,
                'warning_count': workflow_run.warning_count,
                'request_id': workflow_run.request_id,
                'triggered_by': workflow_run.triggered_by
            }
            
        except Exception as e:
            self.logger.error(f"Error getting workflow summary: {e}")
            return None


def create_s3_workflow_config_from_env() -> S3WorkflowConfig:
    """Create S3 workflow configuration from environment variables."""
    return S3WorkflowConfig(
        bucket_name=os.getenv('S3_BUCKET_NAME', 'agentic-research-logs'),
        region=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', ''),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', ''),
        aws_session_token=os.getenv('AWS_SESSION_TOKEN', ''),
        workflow_logs_prefix=os.getenv('S3_WORKFLOW_LOGS_PREFIX', 'workflow_logs/'),
        use_encryption=os.getenv('S3_USE_ENCRYPTION', 'true').lower() == 'true',
        storage_class=os.getenv('S3_STORAGE_CLASS', 'STANDARD')
    )


# Example usage and testing
if __name__ == "__main__":
    import time
    
    # Example configuration (use environment variables in production)
    config = S3WorkflowConfig(
        bucket_name="agentic-research-logs",
        region="us-east-1",
        workflow_logs_prefix="workflow_logs/"
    )
    
    # Create workflow log manager
    workflow_logger = WorkflowLogManager(config)
    
    # Start a workflow run
    run_id = f"RUN-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    print(f"Starting workflow run: {run_id}")
    
    workflow_run = workflow_logger.start_workflow_run(
        run_id=run_id,
        workflow_name="email_research_workflow",
        triggered_by="test_script",
        request_id="REQ-2024-001",
        priority="high",
        configuration={"max_retries": 3, "timeout": 300},
        metadata={"test_run": True}
    )
    
    # Log some steps
    print("Logging workflow steps...")
    
    # Step 1: Email sending
    workflow_logger.log_step_start(
        run_id=run_id,
        step_id="email_send",
        step_name="Send Initial Email",
        component="email_agent",
        function_name="send_initial_request",
        parameters={"recipient": "test@example.com", "template": "initial_request"},
        event_id="EVT-001"
    )
    
    time.sleep(1)  # Simulate work
    
    workflow_logger.log_step_completion(
        run_id=run_id,
        step_id="email_send",
        status=StepStatus.COMPLETED,
        result={"email_sent": True, "message_id": "MSG-12345"}
    )
    
    # Step 2: Event logging (with error)
    workflow_logger.log_step_start(
        run_id=run_id,
        step_id="event_log",
        step_name="Log Event to S3",
        component="event_log_manager",
        function_name="log_event"
    )
    
    time.sleep(0.5)
    
    # Simulate an error
    try:
        raise ValueError("Test error for demonstration")
    except Exception as e:
        workflow_logger.log_exception(run_id, e, step_id="event_log", component="event_log_manager")
        workflow_logger.log_step_completion(
            run_id=run_id,
            step_id="event_log",
            status=StepStatus.FAILED,
            error_message=str(e),
            error_type=type(e).__name__,
            traceback_str=traceback.format_exc()
        )
    
    # Log some general events
    workflow_logger.log_event(run_id, LogLevel.INFO, "Processing completed", component="main")
    workflow_logger.log_event(run_id, LogLevel.WARNING, "Performance degraded", component="monitor")
    
    # Finish the workflow
    print("Finishing workflow run...")
    workflow_logger.finish_workflow_run(run_id)
    
    # Get summary
    summary = workflow_logger.get_workflow_summary(run_id)
    if summary:
        print(f"Workflow Summary:")
        print(f"  Status: {summary['status']}")
        print(f"  Duration: {summary['duration_seconds']:.2f}s")
        print(f"  Steps: {summary['completed_steps']}/{summary['total_steps']}")
        print(f"  Errors: {summary['error_count']}")
        print(f"  Warnings: {summary['warning_count']}")
    
    # List workflow runs
    runs = workflow_logger.list_workflow_runs()
    print(f"Total workflow runs: {len(runs)}")