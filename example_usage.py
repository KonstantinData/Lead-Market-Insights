#!/usr/bin/env python3
"""
Example usage of the Google Calendar Event Processing System components.

This script demonstrates how to use the Block 1 components for basic event processing.
"""

import os
import time
from datetime import datetime, timedelta

from email_agent import email_agent
from event_log_manager import event_log_manager
from workflow_log_manager import workflow_log_manager
from config import validate_config, get_config


def main():
    """Demonstrate the basic workflow of the event processing system."""
    
    print("=== Google Calendar Event Processing System - Example Usage ===\n")
    
    # Step 1: Validate configuration
    print("1. Validating configuration...")
    validation = validate_config()
    
    if not validation['valid']:
        print("❌ Configuration validation failed:")
        for error in validation['errors']:
            print(f"   - {error}")
        print("\nPlease fix configuration errors before proceeding.")
        return
    
    if validation['warnings']:
        print("⚠️  Configuration warnings:")
        for warning in validation['warnings']:
            print(f"   - {warning}")
    
    print("✅ Configuration validation passed\n")
    
    # Step 2: Create a workflow run
    print("2. Creating workflow run...")
    run_id = workflow_log_manager.create_workflow_log(
        workflow_type='EXAMPLE_PROCESSING',
        metadata={
            'description': 'Example usage demonstration',
            'user': 'example_user',
            'environment': os.getenv('ENVIRONMENT', 'development')
        }
    )
    print(f"✅ Created workflow run: {run_id}\n")
    
    # Step 3: Simulate event processing
    print("3. Processing example events...")
    
    # Example events that might come from Google Calendar
    example_events = [
        {
            'id': 'example_event_001',
            'summary': 'Meeting with ACME Corporation',
            'description': 'Discuss Q1 contract renewal. Contact: john@acme.com, Website: https://acme.com',
            'dateTime': (datetime.now() + timedelta(days=1)).isoformat(),
            'organizer': {'email': 'user@example.com'}
        },
        {
            'id': 'example_event_002', 
            'summary': 'Follow-up call with TechCorp',
            'description': 'Review project status. Domain: techcorp.io',
            'dateTime': (datetime.now() + timedelta(days=2)).isoformat(),
            'organizer': {'email': 'manager@example.com'}
        },
        {
            'id': 'example_event_003',
            'summary': 'URGENT: System maintenance window',
            'description': 'Critical maintenance for production systems',
            'dateTime': (datetime.now() + timedelta(hours=2)).isoformat(),
            'organizer': {'email': 'admin@example.com'}
        }
    ]
    
    processed_events = 0
    successful_events = 0
    
    for event in example_events:
        print(f"   Processing event: {event['id']}")
        
        # Log workflow step
        workflow_log_manager.log_step(
            run_id=run_id,
            step_name='CHECK_DUPLICATE',
            status='SUCCESS',
            event_id=event['id'],
            details={'action': 'Checking if event already exists'}
        )
        
        # Step 3a: Check for duplicates
        if event_log_manager.event_exists(event['id']):
            print(f"     ⚠️  Event {event['id']} already exists, skipping")
            workflow_log_manager.log_step(
                run_id=run_id,
                step_name='PROCESS_EVENT',
                status='SKIPPED',
                event_id=event['id'],
                details={'reason': 'Event already exists'}
            )
            continue
        
        # Step 3b: Create event log
        workflow_log_manager.log_step(
            run_id=run_id,
            step_name='CREATE_EVENT_LOG',
            status='SUCCESS',
            event_id=event['id']
        )
        
        success = event_log_manager.create_event_log(
            event_id=event['id'],
            event_data=event,
            trigger_info={
                'detected_triggers': [],
                'trigger_type': 'example',
                'processing_reason': 'Example demonstration'
            }
        )
        
        if not success:
            print(f"     ❌ Failed to create event log for {event['id']}")
            workflow_log_manager.log_error(
                run_id=run_id,
                step_name='CREATE_EVENT_LOG',
                error_message='Failed to create event log',
                event_id=event['id']
            )
            continue
        
        processed_events += 1
        
        # Step 3c: Extract company/domain info (simulated)
        extracted_info = extract_company_info(event)
        
        if extracted_info['needs_validation']:
            # Step 3d: Send human-in-loop request
            print(f"     📧 Sending validation request for {event['id']}")
            
            workflow_log_manager.log_step(
                run_id=run_id,
                step_name='SEND_VALIDATION_REQUEST',
                status='SUCCESS',
                event_id=event['id'],
                details=extracted_info
            )
            
            # Only send email if admin email is configured
            config = get_config()
            if config['email']['admin_email']:
                email_success = email_agent.send_human_in_loop_request(
                    event_data=event,
                    company_name=extracted_info.get('company_name'),
                    web_domain=extracted_info.get('web_domain')
                )
                
                # Log email result
                event_log_manager.add_email_record(
                    event_id=event['id'],
                    email_type='HUMAN_IN_LOOP_REQUEST',
                    recipient=config['email']['admin_email'],
                    success=email_success,
                    template_name='HUMAN_IN_LOOP_REQUEST'
                )
                
                if email_success:
                    print(f"     ✅ Validation email sent successfully")
                else:
                    print(f"     ❌ Failed to send validation email")
            else:
                print(f"     ⚠️  Admin email not configured, skipping email")
        
        # Step 3e: Update event log with extracted info
        event_log_manager.update_event_log(
            event_id=event['id'],
            updates={
                'company_name': extracted_info.get('company_name'),
                'web_domain': extracted_info.get('web_domain'),
                'validation_status': 'PENDING' if extracted_info['needs_validation'] else 'CONFIRMED',
                'status': 'PROCESSING'
            },
            action='COMPANY_EXTRACTION'
        )
        
        # Log successful processing
        workflow_log_manager.log_event_processed(
            run_id=run_id,
            event_id=event['id'],
            status='SUCCESS',
            processing_details={
                'company_extracted': bool(extracted_info.get('company_name')),
                'domain_extracted': bool(extracted_info.get('web_domain')),
                'validation_needed': extracted_info['needs_validation']
            }
        )
        
        successful_events += 1
        print(f"     ✅ Event {event['id']} processed successfully")
        
        # Small delay to simulate processing time
        time.sleep(0.5)
    
    print(f"\n   Processed {processed_events} events, {successful_events} successful\n")
    
    # Step 4: Update performance metrics
    print("4. Updating performance metrics...")
    workflow_log_manager.update_performance_metrics(run_id, {
        'total_events': len(example_events),
        'successful_events': successful_events,
        'failed_events': processed_events - successful_events,
        'emails_sent': successful_events  # Simplified for example
    })
    print("✅ Performance metrics updated\n")
    
    # Step 5: Complete workflow
    print("5. Completing workflow...")
    workflow_log_manager.complete_workflow(
        run_id=run_id,
        status='COMPLETED',
        final_summary={
            'description': 'Example workflow completed successfully',
            'events_processed': processed_events,
            'events_successful': successful_events,
            'validation_requests_sent': successful_events
        }
    )
    print(f"✅ Workflow {run_id} completed\n")
    
    # Step 6: Display summary
    print("6. Summary:")
    print(f"   - Workflow Run ID: {run_id}")
    print(f"   - Events Processed: {processed_events}/{len(example_events)}")
    print(f"   - Successful Events: {successful_events}")
    print(f"   - Event Logs Created: {processed_events}")
    print(f"   - Validation Requests: {successful_events}")
    
    # Show event log status
    print("\n   Event Log Status:")
    for event in example_events[:processed_events]:
        log_data = event_log_manager.get_event_log(event['id'])
        if log_data:
            status = log_data.get('status', 'UNKNOWN')
            company = log_data.get('company_name', 'Not extracted')
            domain = log_data.get('web_domain', 'Not extracted')
            print(f"   - {event['id']}: {status} | Company: {company} | Domain: {domain}")
    
    print("\n=== Example completed successfully! ===")


def extract_company_info(event):
    """
    Simulate company/domain extraction from event data.
    In a real implementation, this would use NLP/regex to extract information.
    """
    summary = event.get('summary', '')
    description = event.get('description', '')
    combined_text = f"{summary} {description}".lower()
    
    # Simple extraction simulation
    extracted = {
        'company_name': None,
        'web_domain': None,
        'needs_validation': False
    }
    
    # Look for company names
    if 'acme' in combined_text:
        extracted['company_name'] = 'ACME Corporation'
        extracted['web_domain'] = 'acme.com'
    elif 'techcorp' in combined_text:
        extracted['company_name'] = 'TechCorp'
        extracted['web_domain'] = 'techcorp.io'
    
    # Look for domains in description
    import re
    domain_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    domain_matches = re.findall(domain_pattern, description)
    if domain_matches and not extracted['web_domain']:
        extracted['web_domain'] = domain_matches[0]
    
    # Determine if validation is needed
    extracted['needs_validation'] = bool(extracted['company_name'] or extracted['web_domain'])
    
    return extracted


if __name__ == '__main__':
    main()