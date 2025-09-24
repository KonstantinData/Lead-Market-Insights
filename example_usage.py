"""
Example usage of the Agentic Intelligence Workflow System components.

This script demonstrates how to use the email agent, event log manager,
and workflow log manager together in a typical workflow scenario.
"""

import uuid
from datetime import datetime
from config_template import create_sample_config
from email_agent import EmailAgent
from event_log_manager import EventLogManager, EventStatus
from workflow_log_manager import WorkflowLogManager


def simulate_calendar_event_processing():
    """
    Simulate processing a Google Calendar event using all components.
    This is a placeholder for the actual calendar integration.
    """
    # Sample calendar event data
    event_data = {
        "event_id": f"calendar_event_{uuid.uuid4().hex[:8]}",
        "event_title": "Weekly Team Meeting",
        "event_date": "2024-09-24",
        "event_time": "14:00 UTC",
        "event_description": "Regular team sync meeting to discuss project progress",
        "organizer": "manager@example.com",
        "attendees": ["alice@example.com", "bob@example.com", "charlie@example.com"],
        "recipient_name": "Alice Johnson",
        "recipient_email": "alice@example.com"
    }
    
    return event_data


def example_workflow():
    """
    Example workflow demonstrating all components working together.
    """
    print("=== Agentic Intelligence Workflow System Example ===\n")
    
    # Load sample configuration
    config = create_sample_config()
    print("1. Loaded sample configuration")
    
    try:
        # Initialize components
        print("2. Initializing components...")
        
        # Initialize workflow logger first
        workflow_logger = WorkflowLogManager.from_config(config)
        print("   - Workflow log manager initialized")
        
        # Initialize other components with workflow logger
        email_agent = EmailAgent.from_config(config, workflow_logger)
        print("   - Email agent initialized")
        
        event_log_manager = EventLogManager.from_config(config, workflow_logger)
        print("   - Event log manager initialized")
        
        print("   All components initialized successfully!\n")
        
        # Start a workflow run
        print("3. Starting workflow run...")
        run_id = workflow_logger.start_workflow("calendar_event_processing")
        print(f"   Started workflow run: {run_id}")
        
        # Simulate calendar event
        print("\n4. Processing calendar event...")
        event_data = simulate_calendar_event_processing()
        event_id = event_data["event_id"]
        print(f"   Event ID: {event_id}")
        print(f"   Event: {event_data['event_title']} on {event_data['event_date']}")
        
        # Check for duplicates
        print("\n5. Checking for duplicate events...")
        if event_log_manager.is_duplicate(event_id):
            print("   WARNING: Duplicate event detected!")
            workflow_logger.log_warning("Duplicate event detected", "event_processor", {"event_id": event_id})
        else:
            print("   No duplicate found, proceeding...")
        
        # Create event log entry
        print("\n6. Creating event log entry...")
        event_entry = event_log_manager.create_event_log(event_id, event_data)
        print(f"   Created event log with status: {event_entry.status.value}")
        
        # Add trigger information
        event_entry.add_trigger("calendar_sync", {
            "source": "google_calendar",
            "sync_time": datetime.now().isoformat()
        })
        print("   Added trigger information")
        
        # Update event status to processing
        event_entry.update_status(EventStatus.PROCESSING)
        event_log_manager.update_event_log(event_entry)
        print("   Updated status to processing")
        
        # Log the event in workflow
        workflow_logger.log_event_processed(event_id)
        
        # Send initial request email
        print("\n7. Sending initial request email...")
        email_success = email_agent.send_request_email(
            to_email=event_data["recipient_email"],
            event_data=event_data,
            workflow_run_id=run_id
        )
        
        if email_success:
            print("   ✓ Initial request email sent successfully")
            event_entry.update_email_status("initial_request", event_data["recipient_email"], True)
            workflow_logger.log_info("Initial request email sent", "email_agent", {"recipient": event_data["recipient_email"]})
        else:
            print("   ✗ Failed to send initial request email")
            event_entry.update_email_status("initial_request", event_data["recipient_email"], False, "Send failed")
            workflow_logger.log_error("email_agent", "Failed to send initial request email", {"recipient": event_data["recipient_email"]})
        
        # Simulate reminder processing
        print("\n8. Simulating reminder workflow...")
        reminder_success = email_agent.send_reminder_email(
            to_email=event_data["recipient_email"],
            event_data=event_data,
            urgent=False
        )
        
        if reminder_success:
            print("   ✓ Reminder email sent successfully")
            event_entry.update_email_status("reminder", event_data["recipient_email"], True)
        else:
            print("   ✗ Failed to send reminder email")
            event_entry.update_email_status("reminder", event_data["recipient_email"], False, "Send failed")
        
        # Update event log
        event_log_manager.update_event_log(event_entry)
        
        # Simulate escalation (if needed)
        print("\n9. Simulating escalation scenario...")
        escalation_success = email_agent.send_escalation_email(
            to_email=config["email"]["admin_email"],
            event_data=event_data,
            workflow_run_id=run_id,
            final=False
        )
        
        if escalation_success:
            print("   ✓ Escalation email sent to admin")
            event_entry.update_status(EventStatus.ESCALATED)
        else:
            print("   ✗ Failed to send escalation email")
            workflow_logger.log_error("email_agent", "Failed to send escalation email")
        
        # Complete the event processing
        print("\n10. Completing event processing...")
        event_entry.update_status(EventStatus.COMPLETED, {"completion_reason": "Successfully processed"})
        event_log_manager.update_event_log(event_entry)
        print("    Event processing completed")
        
        # Complete the workflow
        print("\n11. Completing workflow...")
        workflow_logger.complete_workflow(success=True, metadata={"events_processed": 1})
        print("    Workflow completed successfully")
        
        # Display summary
        print("\n=== Workflow Summary ===")
        print(f"Run ID: {run_id}")
        print(f"Event ID: {event_id}")
        print(f"Event Title: {event_data['event_title']}")
        print(f"Final Status: {event_entry.status.value}")
        print(f"Email Status: {event_entry.email_status}")
        
    except Exception as e:
        print(f"\n❌ Workflow failed with error: {e}")
        
        # Log error to workflow logger
        if 'workflow_logger' in locals():
            workflow_logger.log_error("workflow_orchestrator", str(e))
            workflow_logger.complete_workflow(success=False, metadata={"error": str(e)})
        
        raise


def example_error_handling():
    """
    Example demonstrating error handling across components.
    """
    print("\n=== Error Handling Example ===\n")
    
    config = create_sample_config()
    
    try:
        # Initialize with invalid S3 bucket to trigger errors
        config["s3"]["bucket"] = "invalid-bucket-that-does-not-exist"
        
        workflow_logger = WorkflowLogManager.from_config(config)
        run_id = workflow_logger.start_workflow("error_demonstration")
        
        # This should fail and be logged
        event_log_manager = EventLogManager.from_config(config, workflow_logger)
        
    except Exception as e:
        print(f"Expected error occurred: {e}")
        print("This demonstrates how errors are caught and logged")


def example_template_usage():
    """
    Example demonstrating email template usage.
    """
    print("\n=== Email Template Usage Example ===\n")
    
    from email_agent import EmailTemplateManager
    
    # Load templates
    template_manager = EmailTemplateManager("email_templates.md")
    print(f"Loaded {len(template_manager.templates)} templates:")
    for template_name in template_manager.list_templates():
        print(f"  - {template_name}")
    
    # Example template formatting
    template = template_manager.get_template("initial_request")
    if template:
        sample_vars = {
            "recipient_name": "John Doe",
            "event_title": "Project Review Meeting",
            "event_date": "2024-09-25",
            "event_time": "10:00 UTC",
            "event_description": "Quarterly project review",
            "organizer": "manager@example.com",
            "attendees": "team@example.com",
            "event_id": "sample_event_123",
            "workflow_run_id": "sample_run_456",
            "timestamp": "2024-09-24 15:30:00 UTC"
        }
        
        subject, body = template.format(**sample_vars)
        print(f"\nSample formatted email:")
        print(f"Subject: {subject}")
        print(f"Body:\n{body[:200]}...")  # Show first 200 characters


if __name__ == "__main__":
    """
    Run all examples.
    """
    try:
        # Run main workflow example
        example_workflow()
        
        # Run error handling example
        example_error_handling()
        
        # Run template example
        example_template_usage()
        
        print("\n🎉 All examples completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()