"""
Configuration template for the Agentic Intelligence Workflow System.

This module provides configuration templates and validation for all components.
Copy this file to create your own configuration and fill in the required values.
"""

import os
from typing import Dict, Any, List
from email_agent import validate_email_config
from event_log_manager import validate_event_log_config
from workflow_log_manager import validate_workflow_log_config


# Template configuration - replace with actual values
CONFIG_TEMPLATE: Dict[str, Any] = {
    # S3 Configuration for event and workflow logging
    "s3": {
        "bucket": "your-agentic-intelligence-bucket",
        "event_prefix": "events/",
        "workflow_prefix": "workflow_logs/",
        "aws_access_key_id": None,  # Optional - uses default credential chain if None
        "aws_secret_access_key": None,  # Optional - uses default credential chain if None
        "aws_region": "us-east-1"
    },
    
    # SMTP Configuration for email sending
    "smtp": {
        "server": "smtp.example.com",
        "port": 587,
        "username": "your-email@example.com",
        "password": "your-app-password",
        "from_email": "agentic-intelligence@example.com"
    },
    
    # Workflow Configuration
    "workflow": {
        "default_timeout_seconds": 3600,  # 1 hour
        "max_retries": 3,
        "retry_delay_seconds": 300,  # 5 minutes
        "cleanup_completed_events_days": 7
    },
    
    # Email Configuration
    "email": {
        "template_file": "email_templates.md",
        "admin_email": "admin@example.com",
        "default_reply_to": "noreply@example.com"
    },
    
    # Logging Configuration
    "logging": {
        "level": "INFO",
        "enable_console": True,
        "log_file": None  # Optional log file path
    }
}


def load_config_from_env() -> Dict[str, Any]:
    """
    Load configuration from environment variables.
    
    Environment variables:
    - AGENTIC_S3_BUCKET: S3 bucket name
    - AGENTIC_AWS_ACCESS_KEY_ID: AWS access key ID
    - AGENTIC_AWS_SECRET_ACCESS_KEY: AWS secret access key
    - AGENTIC_AWS_REGION: AWS region
    - AGENTIC_SMTP_SERVER: SMTP server hostname
    - AGENTIC_SMTP_PORT: SMTP server port
    - AGENTIC_SMTP_USERNAME: SMTP username
    - AGENTIC_SMTP_PASSWORD: SMTP password
    - AGENTIC_FROM_EMAIL: From email address
    - AGENTIC_ADMIN_EMAIL: Admin email address
    
    Returns:
        Configuration dictionary
    """
    config = {
        "s3": {
            "bucket": os.getenv("AGENTIC_S3_BUCKET"),
            "event_prefix": os.getenv("AGENTIC_S3_EVENT_PREFIX", "events/"),
            "workflow_prefix": os.getenv("AGENTIC_S3_WORKFLOW_PREFIX", "workflow_logs/"),
            "aws_access_key_id": os.getenv("AGENTIC_AWS_ACCESS_KEY_ID"),
            "aws_secret_access_key": os.getenv("AGENTIC_AWS_SECRET_ACCESS_KEY"),
            "aws_region": os.getenv("AGENTIC_AWS_REGION", "us-east-1")
        },
        "smtp": {
            "server": os.getenv("AGENTIC_SMTP_SERVER"),
            "port": int(os.getenv("AGENTIC_SMTP_PORT", "587")),
            "username": os.getenv("AGENTIC_SMTP_USERNAME"),
            "password": os.getenv("AGENTIC_SMTP_PASSWORD"),
            "from_email": os.getenv("AGENTIC_FROM_EMAIL")
        },
        "workflow": {
            "default_timeout_seconds": int(os.getenv("AGENTIC_WORKFLOW_TIMEOUT", "3600")),
            "max_retries": int(os.getenv("AGENTIC_MAX_RETRIES", "3")),
            "retry_delay_seconds": int(os.getenv("AGENTIC_RETRY_DELAY", "300")),
            "cleanup_completed_events_days": int(os.getenv("AGENTIC_CLEANUP_DAYS", "7"))
        },
        "email": {
            "template_file": os.getenv("AGENTIC_EMAIL_TEMPLATE_FILE", "email_templates.md"),
            "admin_email": os.getenv("AGENTIC_ADMIN_EMAIL"),
            "default_reply_to": os.getenv("AGENTIC_REPLY_TO_EMAIL")
        },
        "logging": {
            "level": os.getenv("AGENTIC_LOG_LEVEL", "INFO"),
            "enable_console": os.getenv("AGENTIC_ENABLE_CONSOLE_LOG", "true").lower() == "true",
            "log_file": os.getenv("AGENTIC_LOG_FILE")
        }
    }
    
    return config


def validate_config(config: Dict[str, Any]) -> List[str]:
    """
    Validate the complete configuration.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        List of validation error messages
    """
    errors = []
    
    # Validate each component's configuration
    errors.extend(validate_email_config(config))
    errors.extend(validate_event_log_config(config))
    errors.extend(validate_workflow_log_config(config))
    
    # Additional general validation
    email_config = config.get('email', {})
    if not email_config.get('admin_email'):
        errors.append("Missing required email configuration: admin_email")
    
    return errors


def create_sample_config() -> Dict[str, Any]:
    """Create a sample configuration for testing purposes."""
    return {
        "s3": {
            "bucket": "test-agentic-intelligence-bucket",
            "event_prefix": "events/",
            "workflow_prefix": "workflow_logs/",
            "aws_access_key_id": None,
            "aws_secret_access_key": None,
            "aws_region": "us-east-1"
        },
        "smtp": {
            "server": "localhost",
            "port": 1025,  # MailHog or similar test server
            "username": "test@example.com",
            "password": "test_password",
            "from_email": "agentic-test@example.com"
        },
        "workflow": {
            "default_timeout_seconds": 300,  # 5 minutes for testing
            "max_retries": 2,
            "retry_delay_seconds": 30,  # 30 seconds for testing
            "cleanup_completed_events_days": 1
        },
        "email": {
            "template_file": "email_templates.md",
            "admin_email": "admin@example.com",
            "default_reply_to": "noreply@example.com"
        },
        "logging": {
            "level": "DEBUG",
            "enable_console": True,
            "log_file": None
        }
    }


# Example usage and component initialization
if __name__ == "__main__":
    """
    Example of how to use the configuration system.
    """
    # Load configuration from environment or use template
    try:
        config = load_config_from_env()
        
        # Validate configuration
        errors = validate_config(config)
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            print("\nPlease fix configuration errors before running the system.")
        else:
            print("Configuration is valid!")
            
            # Example of component initialization
            from email_agent import EmailAgent
            from event_log_manager import EventLogManager
            from workflow_log_manager import WorkflowLogManager
            
            print("\nInitializing components...")
            
            # Initialize workflow logger first
            workflow_logger = WorkflowLogManager.from_config(config)
            
            # Initialize other components with workflow logger
            email_agent = EmailAgent.from_config(config, workflow_logger)
            event_log_manager = EventLogManager.from_config(config, workflow_logger)
            
            print("All components initialized successfully!")
            
    except Exception as e:
        print(f"Failed to initialize configuration: {e}")
        print("\nUsing sample configuration for demonstration...")
        
        # Use sample config for demonstration
        sample_config = create_sample_config()
        print(f"Sample configuration: {sample_config}")