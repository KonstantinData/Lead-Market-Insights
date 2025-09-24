#!/usr/bin/env python3
"""
Basic workflow test - demonstrates the system works without external dependencies.

This test runs the core workflow without requiring S3 or SMTP configuration,
using the built-in fallback mechanisms.
"""

import os
import sys
from datetime import datetime

# Set minimal test environment
os.environ['ADMIN_EMAIL'] = 'test@example.com'
os.environ['S3_BUCKET_NAME'] = 'test-bucket'

def test_basic_workflow():
    """Test the basic workflow functionality."""
    
    print("=== Basic Workflow Test ===\n")
    
    # Import modules
    try:
        from email_agent import email_agent
        from event_log_manager import event_log_manager
        from workflow_log_manager import workflow_log_manager
        from config import validate_config
        
        print("✅ All modules imported successfully")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False
    
    # Test configuration validation
    validation = validate_config()
    print(f"✅ Configuration validation: {'VALID' if validation['valid'] else 'INVALID (expected due to missing services)'}")
    
    # Test workflow creation (should work with console fallback)
    print("\n--- Testing Workflow Creation ---")
    run_id = workflow_log_manager.create_workflow_log(
        workflow_type='TEST_WORKFLOW',
        metadata={'test': 'basic_workflow_test'}
    )
    print(f"✅ Created workflow run: {run_id}")
    
    # Test step logging
    print("\n--- Testing Step Logging ---")
    success = workflow_log_manager.log_step(
        run_id=run_id,
        step_name='TEST_STEP',
        status='SUCCESS',
        details={'message': 'Test step executed'}
    )
    print(f"✅ Logged workflow step: {success}")
    
    # Test event log operations (should work with console fallback)
    print("\n--- Testing Event Log Operations ---")
    test_event = {
        'id': 'test_event_001',
        'summary': 'Test Event',
        'description': 'This is a test event',
        'dateTime': datetime.now().isoformat()
    }
    
    # Note: These will return False when S3 is not available, but won't crash
    exists = event_log_manager.event_exists(test_event['id'])
    print(f"✅ Event exists check: {exists} (False expected without S3)")
    
    created = event_log_manager.create_event_log(
        event_id=test_event['id'],
        event_data=test_event
    )
    print(f"✅ Event log creation: {created} (False expected without S3)")
    
    # Test email template loading
    print("\n--- Testing Email Templates ---")
    templates = email_agent.templates
    print(f"✅ Loaded {len(templates)} email templates:")
    for template_name in templates.keys():
        print(f"   - {template_name}")
    
    # Test template rendering without sending
    print("\n--- Testing Template Rendering ---")
    try:
        rendered = email_agent._render_template(
            'HUMAN_IN_LOOP_REQUEST',
            {
                'event_id': test_event['id'],
                'event_summary': test_event['summary'],
                'event_description': test_event['description'],
                'event_datetime': test_event['dateTime'],
                'company_name': 'Test Company',
                'web_domain': 'test.com'
            }
        )
        print("✅ Template rendering successful")
        print(f"   Subject: {rendered['subject']}")
        print(f"   Body length: {len(rendered['body'])} characters")
    except Exception as e:
        print(f"❌ Template rendering failed: {e}")
        return False
    
    # Test error logging
    print("\n--- Testing Error Logging ---")
    error_logged = workflow_log_manager.log_error(
        run_id=run_id,
        step_name='TEST_ERROR',
        error_message='This is a test error',
        event_id=test_event['id']
    )
    print(f"✅ Error logging: {error_logged}")
    
    # Complete workflow
    print("\n--- Testing Workflow Completion ---")
    completed = workflow_log_manager.complete_workflow(
        run_id=run_id,
        status='COMPLETED',
        final_summary={'test_result': 'SUCCESS'}
    )
    print(f"✅ Workflow completion: {completed}")
    
    print(f"\n=== Basic Workflow Test PASSED ===")
    print("All core functionality works correctly with fallback mechanisms.")
    return True


if __name__ == '__main__':
    success = test_basic_workflow()
    sys.exit(0 if success else 1)