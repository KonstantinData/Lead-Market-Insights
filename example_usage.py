#!/usr/bin/env python3
"""
Example Usage - Agentic Intelligence Research System Block 1

This script demonstrates how to use all four components together:
1. Email Agent for sending research requests
2. Event Log Manager for tracking events
3. Workflow Log Manager for workflow execution logging
4. Email Templates for consistent messaging

Note: This example uses mock configurations. In production, configure:
- SMTP settings for email sending
- AWS S3 credentials for logging
"""

import os
import sys
from datetime import datetime, timedelta

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_agent import (
    EmailAgent, EmailConfig, EmailRecipient, EmailContext, 
    EmailType, EmailPriority, create_email_config_from_env
)
from event_log_manager import (
    EventLogManager, S3Config, EventData, EventStatus, 
    TriggerType, EmailStatus, create_s3_config_from_env
)
from workflow_log_manager import (
    WorkflowLogManager, S3WorkflowConfig, WorkflowStatus, 
    StepStatus, LogLevel, create_s3_workflow_config_from_env
)


def example_complete_workflow():
    """
    Example of a complete research request workflow using all components.
    """
    print("=" * 80)
    print("Agentic Intelligence Research System - Complete Workflow Example")
    print("=" * 80)
    
    # 1. CONFIGURATION SETUP
    print("\n1. Setting up configurations...")
    
    # Email configuration (use environment variables in production)
    email_config = EmailConfig(
        smtp_server=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
        smtp_port=int(os.getenv('SMTP_PORT', '587')),
        username=os.getenv('SMTP_USERNAME', 'research@example.com'),
        password=os.getenv('SMTP_PASSWORD', 'your_password'),
        from_email=os.getenv('SMTP_FROM_EMAIL', 'research@example.com'),
        from_name='Agentic Intelligence Research Team'
    )
    
    # S3 configuration for event logging
    s3_config = S3Config(
        bucket_name=os.getenv('S3_BUCKET_NAME', 'agentic-research-logs'),
        region=os.getenv('AWS_REGION', 'us-east-1'),
        events_prefix='events/'
    )
    
    # S3 configuration for workflow logging
    workflow_config = S3WorkflowConfig(
        bucket_name=os.getenv('S3_BUCKET_NAME', 'agentic-research-logs'),
        region=os.getenv('AWS_REGION', 'us-east-1'),
        workflow_logs_prefix='workflow_logs/'
    )
    
    print("✓ Configurations loaded")
    
    # 2. COMPONENT INITIALIZATION
    print("\n2. Initializing components...")
    
    # Initialize workflow logger first (used by other components)
    workflow_logger = WorkflowLogManager(workflow_config)
    
    # Initialize event manager and email agent with workflow logging
    event_manager = EventLogManager(s3_config, workflow_logger=workflow_logger)
    email_agent = EmailAgent(email_config, workflow_logger=workflow_logger)
    
    print("✓ All components initialized")
    
    # 3. START WORKFLOW RUN
    print("\n3. Starting workflow run...")
    
    run_id = f"RESEARCH-WORKFLOW-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    request_id = "REQ-2024-001"
    
    workflow_run = workflow_logger.start_workflow_run(
        run_id=run_id,
        workflow_name="research_request_workflow",
        triggered_by="example_script",
        request_id=request_id,
        priority="high",
        configuration={
            "max_retries": 3,
            "reminder_intervals": [3, 7, 14],  # days
            "escalation_levels": 3
        },
        metadata={
            "example_run": True,
            "recipient_type": "external_expert"
        }
    )
    
    print(f"✓ Workflow started: {run_id}")
    
    # 4. CREATE RESEARCH REQUEST EVENT
    print("\n4. Creating research request event...")
    
    event_id = f"EVT-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    
    event_data = EventData(
        event_id=event_id,
        request_id=request_id,
        status=EventStatus.PENDING,
        trigger=TriggerType.MANUAL,
        timestamp=datetime.utcnow().isoformat() + "Z",
        email_status=EmailStatus.NOT_SENT,
        recipient_email="dr.expert@university.edu",
        recipient_name="Dr. Jane Expert",
        company="Research University",
        request_details="We need your expertise in evaluating our new AI model for natural language processing. Your insights on model architecture and performance metrics would be invaluable for our research.",
        priority="high",
        deadline=(datetime.utcnow() + timedelta(days=14)).isoformat() + "Z",
        created_by="research_coordinator"
    )
    
    # Note: In production, this would log to S3
    try:
        success = event_manager.log_event(event_data)
        if success:
            print(f"✓ Event logged: {event_id}")
        else:
            print(f"⚠ Event logging simulated (S3 not configured): {event_id}")
    except:
        print(f"⚠ Event logging simulated (S3 not configured): {event_id}")
    
    # 5. SEND INITIAL RESEARCH REQUEST EMAIL
    print("\n5. Sending initial research request...")
    
    # Log workflow step start
    workflow_logger.log_step_start(
        run_id=run_id,
        step_id="send_initial_request",
        step_name="Send Initial Research Request",
        component="email_agent",
        function_name="send_initial_request",
        parameters={
            "recipient": event_data.recipient_email,
            "request_id": request_id,
            "event_id": event_id
        },
        event_id=event_id,
        request_id=request_id
    )
    
    # Create email context
    recipient = EmailRecipient(
        name=event_data.recipient_name,
        email=event_data.recipient_email,
        company=event_data.company
    )
    
    email_context = EmailContext(
        request_id=request_id,
        event_id=event_id,
        recipient=recipient,
        request_details=event_data.request_details,
        deadline=event_data.deadline,
        priority=EmailPriority.HIGH
    )
    
    # Note: In production, this would send actual email
    try:
        success = email_agent.send_initial_request(email_context)
        step_status = StepStatus.COMPLETED if success else StepStatus.FAILED
        result = {"email_sent": success, "simulation": True}
        error_msg = "" if success else "SMTP not configured"
    except Exception as e:
        step_status = StepStatus.FAILED
        result = {"email_sent": False, "simulation": True}
        error_msg = f"Email sending simulated: {str(e)}"
    
    # Log step completion
    workflow_logger.log_step_completion(
        run_id=run_id,
        step_id="send_initial_request",
        status=step_status,
        result=result,
        error_message=error_msg
    )
    
    print("✓ Initial request email processed (simulated if SMTP not configured)")
    
    # 6. UPDATE EVENT STATUS
    print("\n6. Updating event status...")
    
    try:
        event_manager.update_email_status(
            event_id, 
            EmailStatus.SENT, 
            datetime.utcnow().isoformat() + "Z"
        )
        print("✓ Event email status updated")
    except:
        print("⚠ Event status update simulated (S3 not configured)")
    
    # 7. SIMULATE REMINDER WORKFLOW (after no response)
    print("\n7. Simulating reminder workflow...")
    
    # First reminder
    workflow_logger.log_step_start(
        run_id=run_id,
        step_id="send_first_reminder",
        step_name="Send First Reminder",
        component="email_agent",
        function_name="send_reminder",
        parameters={"reminder_level": 1},
        event_id=event_id,
        request_id=request_id
    )
    
    # Update context for reminder
    email_context.original_date = "2024-01-01"
    email_context.days_overdue = 3
    
    try:
        success = email_agent.send_reminder(email_context, reminder_level=1)
        workflow_logger.log_step_completion(
            run_id=run_id,
            step_id="send_first_reminder",
            status=StepStatus.COMPLETED if success else StepStatus.FAILED,
            result={"reminder_sent": success, "level": 1}
        )
        print("✓ First reminder processed")
    except Exception as e:
        workflow_logger.log_step_completion(
            run_id=run_id,
            step_id="send_first_reminder",
            status=StepStatus.FAILED,
            error_message=f"Reminder simulated: {str(e)}"
        )
        print("⚠ First reminder simulated")
    
    # 8. LOG GENERAL WORKFLOW EVENTS
    print("\n8. Logging workflow events...")
    
    workflow_logger.log_event(
        run_id, 
        LogLevel.INFO, 
        "Research request workflow executing normally",
        component="workflow_controller",
        progress="50%"
    )
    
    workflow_logger.log_event(
        run_id,
        LogLevel.WARNING,
        "No response received within expected timeframe",
        component="response_monitor",
        days_elapsed=3
    )
    
    print("✓ Workflow events logged")
    
    # 9. FINISH WORKFLOW
    print("\n9. Finishing workflow...")
    
    workflow_logger.finish_workflow_run(run_id, WorkflowStatus.COMPLETED)
    
    # Get workflow summary
    summary = workflow_logger.get_workflow_summary(run_id)
    if summary:
        print(f"✓ Workflow completed successfully:")
        print(f"  - Duration: {summary.get('duration_seconds', 0):.2f} seconds")
        print(f"  - Steps: {summary.get('completed_steps', 0)}/{summary.get('total_steps', 0)}")
        print(f"  - Status: {summary.get('status', 'unknown')}")
    else:
        print("✓ Workflow completed (summary not available without S3)")
    
    print("\n" + "=" * 80)
    print("WORKFLOW EXAMPLE COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print()
    print("In production environment:")
    print("1. Configure SMTP settings for actual email sending")
    print("2. Configure AWS S3 credentials for persistent logging")
    print("3. Set up monitoring and alerting for failed workflows")
    print("4. Implement response parsing and human-in-the-loop integration")
    print("5. Add polling logic for checking email responses")
    print()


def example_template_customization():
    """
    Example of how to customize email templates.
    """
    print("\n" + "=" * 60)
    print("Email Template Customization Example")
    print("=" * 60)
    
    from email_agent import EmailTemplateManager
    
    # Load and examine templates
    template_manager = EmailTemplateManager("email_templates.md")
    
    # Example context
    recipient = EmailRecipient(
        name="Dr. Research Expert",
        email="expert@university.edu",
        company="Top Research University"
    )
    
    context = EmailContext(
        request_id="REQ-CUSTOM-001",
        event_id="EVT-CUSTOM-001",
        recipient=recipient,
        request_details="Custom research request with specific requirements for AI model validation.",
        deadline="2024-03-01",
        priority=EmailPriority.CRITICAL,
        escalation_level=2,
        contact_person="Dr. Project Lead",
        contact_phone="+1-555-RESEARCH"
    )
    
    # Show different email types
    email_types = [
        EmailType.INITIAL_REQUEST,
        EmailType.ESCALATION,
        EmailType.SUCCESS_THANK_YOU
    ]
    
    for email_type in email_types:
        subject, body = template_manager.render_template(email_type, context)
        print(f"\n{email_type.value.upper()} EMAIL:")
        print(f"Subject: {subject}")
        print(f"Body Preview: {body[:200]}...")
        print("-" * 40)
    
    print("\n✓ Template customization examples shown")


if __name__ == "__main__":
    # Run the complete workflow example
    example_complete_workflow()
    
    # Show template customization
    example_template_customization()
    
    print("\n🎉 All examples completed successfully!")
    print("\nNext steps for production deployment:")
    print("- Set environment variables for SMTP and AWS configuration")
    print("- Implement polling logic for email response detection")
    print("- Add human-in-the-loop integration for manual review")
    print("- Set up monitoring and alerting for workflow failures")
    print("- Implement data extraction and analysis workflows")