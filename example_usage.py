#!/usr/bin/env python3
"""
Example usage of the Agentic Intelligence Research System components

This script demonstrates how the four core components work together:
- EmailTemplateManager for template rendering
- EmailAgent for email sending
- EventLogManager for event tracking
- WorkflowLogManager for workflow execution logging

Note: This is a demonstration script. In production, AWS credentials and SMTP 
configuration would be properly configured.
"""

import os
import uuid
from datetime import datetime, timezone
from email_agent import EmailAgent, EmailConfig, create_gmail_config
from event_log_manager import EventLogManager, TriggerInfo, EmailLog, EventStatus, EmailStatus
from workflow_log_manager import WorkflowLogManager, WorkflowStatus


def simulate_calendar_event_workflow():
    """
    Simulate a complete calendar event workflow with email notifications
    """
    
    print("🚀 Starting Calendar Event Workflow Simulation")
    print("=" * 50)
    
    # Configuration (in production, these would come from environment variables)
    smtp_config = EmailConfig(
        smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        username=os.getenv("SMTP_USERNAME", "demo@example.com"),
        password=os.getenv("SMTP_PASSWORD", "demo_password"),
        use_tls=True,
        sender_name="Agentic Intelligence Research System"
    )
    
    s3_bucket = os.getenv("S3_BUCKET", "agentic-intelligence-demo")
    
    # Initialize components
    try:
        # Note: These will fail without proper AWS credentials, but the demo will continue
        workflow_logger = WorkflowLogManager(bucket_name=s3_bucket)
        event_logger = EventLogManager(bucket_name=s3_bucket, workflow_logger=workflow_logger)
        email_agent = EmailAgent(smtp_config, workflow_logger=workflow_logger)
        
        print("✓ All components initialized successfully")
        
    except Exception as e:
        print(f"⚠️  Component initialization failed (expected without AWS/SMTP config): {e}")
        
        # Create mock loggers for demonstration
        class MockLogger:
            def log_error(self, step, error, event_id=None, timestamp=None):
                print(f"Mock Log Error - Step: {step}, Error: {error}, Event: {event_id}")
        
        mock_logger = MockLogger()
        email_agent = EmailAgent(smtp_config, workflow_logger=mock_logger)
        print("✓ Created mock components for demonstration")
    
    # Start workflow
    run_id = f"calendar-workflow-{uuid.uuid4().hex[:8]}"
    
    try:
        if 'workflow_logger' in locals():
            workflow_logger.start_workflow_run(
                workflow_name="calendar_event_processing",
                run_id=run_id,
                workflow_version="1.0.0",
                triggered_by="calendar_api",
                environment="demo",
                metadata={"demo": True}
            )
            print(f"✓ Started workflow run: {run_id}")
    except:
        print(f"✓ Mock workflow run started: {run_id}")
    
    # Simulate event creation
    event_id = f"event-{uuid.uuid4().hex[:8]}"
    
    try:
        if 'event_logger' in locals():
            trigger_info = TriggerInfo(
                trigger_type="calendar",
                trigger_source="google_calendar",
                trigger_time=datetime.now(timezone.utc),
                trigger_data={"calendar_id": "primary", "demo": True}
            )
            
            event_log = event_logger.create_event_log(
                event_id=event_id,
                event_title="Team Strategy Meeting",
                event_type="meeting",
                trigger_info=trigger_info,
                event_data={
                    "datetime": "2024-01-15T10:00:00Z",
                    "duration": "1 hour",
                    "location": "Conference Room A",
                    "attendees": ["john.doe@company.com", "jane.smith@company.com"]
                }
            )
            print(f"✓ Created event log: {event_id}")
    except:
        print(f"✓ Mock event created: {event_id}")
    
    # Step 1: Send initial request emails
    step1_id = None
    try:
        if 'workflow_logger' in locals():
            step1_id = workflow_logger.start_step(run_id, "Send Initial Request Emails")
    except:
        step1_id = "mock-step-1"
        print("✓ Mock step started: Send Initial Request Emails")
    
    # Demonstrate email template rendering
    template_variables = {
        'recipient_name': 'John Doe',
        'event_title': 'Team Strategy Meeting',
        'event_datetime': 'January 15, 2024 at 10:00 AM',
        'event_duration': '1 hour',
        'event_location': 'Conference Room A',
        'event_description': 'Quarterly strategy review and planning session',
        'sender_name': 'Meeting Coordinator'
    }
    
    # Create email message from template
    message = email_agent.create_message_from_template(
        template_name="initial_request_template",
        to_email="john.doe@company.com",
        template_variables=template_variables,
        to_name="John Doe"
    )
    
    if message:
        print("✓ Email message created from template")
        print(f"  Subject: {message.subject}")
        print(f"  Body preview: {message.body[:100]}...")
        
        # In production, this would actually send the email
        # result = email_agent.send_email(message, event_id)
        
        # Simulate email log entry
        email_log = EmailLog(
            email_id=f"email-{uuid.uuid4().hex[:8]}",
            email_type="request",
            recipient_email="john.doe@company.com",
            recipient_name="John Doe",
            subject=message.subject,
            status=EmailStatus.SENT,
            sent_timestamp=datetime.now(timezone.utc),
            template_name="initial_request_template"
        )
        
        try:
            if 'event_logger' in locals():
                event_logger.add_email_log(event_id, email_log)
                print("✓ Email log added to event")
        except:
            print("✓ Mock email log recorded")
    
    # Complete step 1
    try:
        if 'workflow_logger' in locals() and step1_id:
            workflow_logger.complete_step(run_id, step1_id, {"emails_sent": 2})
    except:
        print("✓ Mock step completed: Send Initial Request Emails")
    
    # Step 2: Check for responses (simulated)
    step2_id = None
    try:
        if 'workflow_logger' in locals():
            step2_id = workflow_logger.start_step(run_id, "Check Email Responses")
    except:
        step2_id = "mock-step-2"
        print("✓ Mock step started: Check Email Responses")
    
    # Simulate no response, trigger reminder
    print("⏰ No response received, triggering reminder workflow...")
    
    # Create reminder email
    reminder_variables = template_variables.copy()
    reminder_variables.update({
        'time_until_event': '2 days',
        'response_deadline': 'January 13, 2024'
    })
    
    reminder_message = email_agent.create_message_from_template(
        template_name="first_reminder_template",
        to_email="john.doe@company.com",
        template_variables=reminder_variables,
        to_name="John Doe"
    )
    
    if reminder_message:
        print("✓ Reminder email created from template")
        print(f"  Subject: {reminder_message.subject}")
        
        # Simulate reminder email log
        reminder_email_log = EmailLog(
            email_id=f"email-{uuid.uuid4().hex[:8]}",
            email_type="reminder",
            recipient_email="john.doe@company.com",
            recipient_name="John Doe",
            subject=reminder_message.subject,
            status=EmailStatus.SENT,
            sent_timestamp=datetime.now(timezone.utc),
            template_name="first_reminder_template"
        )
        
        try:
            if 'event_logger' in locals():
                event_logger.add_email_log(event_id, reminder_email_log)
                print("✓ Reminder email log added")
        except:
            print("✓ Mock reminder email log recorded")
    
    # Complete step 2
    try:
        if 'workflow_logger' in locals() and step2_id:
            workflow_logger.complete_step(run_id, step2_id, {"reminders_sent": 1})
    except:
        print("✓ Mock step completed: Check Email Responses")
    
    # Step 3: Simulate escalation
    step3_id = None
    try:
        if 'workflow_logger' in locals():
            step3_id = workflow_logger.start_step(run_id, "Handle Escalation")
    except:
        step3_id = "mock-step-3"
        print("✓ Mock step started: Handle Escalation")
    
    # Update event status to escalated
    try:
        if 'event_logger' in locals():
            event_logger.update_event_status(event_id, EventStatus.ESCALATED)
            print("✓ Event status updated to ESCALATED")
    except:
        print("✓ Mock event status updated to ESCALATED")
    
    # Create escalation email
    escalation_variables = template_variables.copy()
    escalation_variables.update({
        'manager_name': 'Sarah Johnson',
        'escalation_reason': 'Critical planning meeting requires all team members',
        'business_justification': 'Q1 strategy planning',
        'original_invite_date': 'January 10, 2024',
        'reminder_count': '2',
        'last_reminder_date': 'January 12, 2024'
    })
    
    escalation_message = email_agent.create_message_from_template(
        template_name="manager_escalation_template",
        to_email="sarah.johnson@company.com",
        template_variables=escalation_variables,
        to_name="Sarah Johnson"
    )
    
    if escalation_message:
        print("✓ Escalation email created from template")
        print(f"  Subject: {escalation_message.subject}")
    
    # Complete step 3
    try:
        if 'workflow_logger' in locals() and step3_id:
            workflow_logger.complete_step(run_id, step3_id, {"escalations_sent": 1})
    except:
        print("✓ Mock step completed: Handle Escalation")
    
    # Complete workflow
    try:
        if 'workflow_logger' in locals():
            workflow_logger.complete_workflow(run_id, {"total_emails": 4, "escalated": True})
            print("✓ Workflow completed successfully")
    except:
        print("✓ Mock workflow completed")
    
    # Demonstrate template listing
    print("\n📧 Available Email Templates:")
    templates = email_agent.template_manager.list_templates()
    for i, template in enumerate(templates, 1):
        print(f"  {i}. {template}")
    
    # Show template variables
    print("\n🔧 Template Variables Available:")
    variables = email_agent.template_manager.get_template_variables()
    for i, var in enumerate(variables[:10], 1):  # Show first 10
        print(f"  {i}. {{{var}}}")
    if len(variables) > 10:
        print(f"  ... and {len(variables) - 10} more")
    
    print(f"\n✅ Workflow simulation completed successfully!")
    print(f"   Run ID: {run_id}")
    print(f"   Event ID: {event_id}")
    
    return run_id, event_id


def demonstrate_error_handling():
    """Demonstrate error handling capabilities"""
    
    print("\n🔧 Demonstrating Error Handling")
    print("=" * 30)
    
    try:
        # This will fail and demonstrate error logging
        from workflow_log_manager import WorkflowLogManager
        
        # Try to create with invalid bucket (will fail gracefully)
        try:
            workflow_logger = WorkflowLogManager(bucket_name="invalid-bucket-name-demo")
        except Exception as e:
            print(f"✓ Error handling working: {type(e).__name__}")
        
        # Demonstrate step error handling
        from workflow_log_manager import WorkflowStep, StepStatus
        
        step = WorkflowStep(
            step_id="demo-error-step",
            step_name="Demonstration Error Step",
            status=StepStatus.RUNNING,
            start_timestamp=datetime.now(timezone.utc)
        )
        
        # Simulate step failure
        demo_error = ValueError("This is a demonstration error")
        step.fail(demo_error, {"context": "error_demo"})
        
        print("✓ Step error handling demonstrated")
        print(f"  Error message: {step.error_message}")
        print(f"  Has traceback: {step.error_traceback is not None}")
        
    except Exception as e:
        print(f"✓ Error handling demonstration completed: {e}")


def main():
    """Main demonstration function"""
    
    print("🎯 Agentic Intelligence Research System - Block 1 Demonstration")
    print("=" * 70)
    print()
    
    # Run the main workflow simulation
    run_id, event_id = simulate_calendar_event_workflow()
    
    # Demonstrate error handling
    demonstrate_error_handling()
    
    print("\n" + "=" * 70)
    print("🎉 Demonstration completed successfully!")
    print()
    print("📝 Summary of implemented components:")
    print("   • email_templates.md - 6 customizable email templates")
    print("   • email_agent.py - SMTP email sending with template support")
    print("   • event_log_manager.py - S3-based event logging and tracking")
    print("   • workflow_log_manager.py - S3-based workflow execution logging")
    print("")
    print("🚀 Ready for integration with:")
    print("   • Google Calendar API polling")
    print("   • Advanced trigger systems")
    print("   • Complex agent workflows")
    print("   • Production AWS/SMTP configuration")


if __name__ == "__main__":
    main()