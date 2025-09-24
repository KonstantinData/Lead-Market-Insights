"""
Configuration settings for the Google Calendar Event Processing System
"""

import os
from typing import Dict, Any

# Email Configuration
EMAIL_CONFIG = {
    'smtp_server': os.getenv('SMTP_SERVER', 'localhost'),
    'smtp_port': int(os.getenv('SMTP_PORT', '587')),
    'smtp_username': os.getenv('SMTP_USERNAME'),
    'smtp_password': os.getenv('SMTP_PASSWORD'),
    'from_email': os.getenv('FROM_EMAIL'),
    'admin_email': os.getenv('ADMIN_EMAIL'),
}

# S3/AWS Configuration
AWS_CONFIG = {
    'bucket_name': os.getenv('S3_BUCKET_NAME'),
    'region': os.getenv('AWS_REGION', 'us-east-1'),
    'access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
    'secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
}

# Google Calendar Configuration (for future implementation)
GOOGLE_CALENDAR_CONFIG = {
    'credentials_file': os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json'),
    'token_file': os.getenv('GOOGLE_TOKEN_FILE', 'token.json'),
    'calendar_id': os.getenv('GOOGLE_CALENDAR_ID', 'primary'),
}

# Trigger Configuration (for future implementation)
TRIGGER_CONFIG = {
    'hard_triggers': [
        'URGENT',
        'EMERGENCY', 
        'CRITICAL',
        'IMMEDIATE'
    ],
    'soft_triggers': [
        'follow-up',
        'reminder',
        'check',
        'review'
    ],
    'enable_hard_triggers': True,
    'enable_soft_triggers': True,
}

# Workflow Configuration
WORKFLOW_CONFIG = {
    'reminder_delay_hours': int(os.getenv('REMINDER_DELAY_HOURS', '24')),
    'escalation_delay_hours': int(os.getenv('ESCALATION_DELAY_HOURS', '48')),
    'enable_reminders': os.getenv('ENABLE_REMINDERS', 'true').lower() == 'true',
    'enable_escalations': os.getenv('ENABLE_ESCALATIONS', 'true').lower() == 'true',
    'auto_delete_completed_events': os.getenv('AUTO_DELETE_COMPLETED', 'false').lower() == 'true',
}

# Logging Configuration
LOGGING_CONFIG = {
    'log_level': os.getenv('LOG_LEVEL', 'INFO'),
    'console_logging': os.getenv('CONSOLE_LOGGING', 'true').lower() == 'true',
    'file_logging': os.getenv('FILE_LOGGING', 'false').lower() == 'true',
    'log_file_path': os.getenv('LOG_FILE_PATH', 'logs/application.log'),
}

# System Configuration
SYSTEM_CONFIG = {
    'environment': os.getenv('ENVIRONMENT', 'development'),
    'version': '1.0.0',
    'timezone': os.getenv('TIMEZONE', 'UTC'),
    'max_events_per_run': int(os.getenv('MAX_EVENTS_PER_RUN', '100')),
}


def get_config() -> Dict[str, Any]:
    """Get complete configuration dictionary."""
    return {
        'email': EMAIL_CONFIG,
        'aws': AWS_CONFIG,
        'google_calendar': GOOGLE_CALENDAR_CONFIG,
        'triggers': TRIGGER_CONFIG,
        'workflow': WORKFLOW_CONFIG,
        'logging': LOGGING_CONFIG,
        'system': SYSTEM_CONFIG,
    }


def validate_config() -> Dict[str, Any]:
    """Validate configuration and return validation results."""
    validation_results = {
        'valid': True,
        'errors': [],
        'warnings': []
    }
    
    # Check required email settings
    if not EMAIL_CONFIG['admin_email']:
        validation_results['errors'].append('ADMIN_EMAIL environment variable is required')
        validation_results['valid'] = False
    
    if not EMAIL_CONFIG['smtp_username']:
        validation_results['warnings'].append('SMTP_USERNAME not set - email sending may fail')
    
    # Check required AWS settings
    if not AWS_CONFIG['bucket_name']:
        validation_results['errors'].append('S3_BUCKET_NAME environment variable is required')
        validation_results['valid'] = False
    
    if not AWS_CONFIG['access_key_id'] or not AWS_CONFIG['secret_access_key']:
        validation_results['warnings'].append('AWS credentials not set - S3 operations may fail')
    
    # Check Google Calendar settings (for future use)
    if not os.path.exists(GOOGLE_CALENDAR_CONFIG['credentials_file']):
        validation_results['warnings'].append(f"Google credentials file not found: {GOOGLE_CALENDAR_CONFIG['credentials_file']}")
    
    return validation_results


if __name__ == '__main__':
    # Print configuration validation when run directly
    config = get_config()
    validation = validate_config()
    
    print("Configuration Validation:")
    print(f"Valid: {validation['valid']}")
    
    if validation['errors']:
        print("\nErrors:")
        for error in validation['errors']:
            print(f"  - {error}")
    
    if validation['warnings']:
        print("\nWarnings:")
        for warning in validation['warnings']:
            print(f"  - {warning}")
    
    print("\nCurrent Configuration:")
    import json
    # Mask sensitive values
    masked_config = config.copy()
    for section in masked_config.values():
        if isinstance(section, dict):
            for key, value in section.items():
                if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token']):
                    if value:
                        section[key] = '***REDACTED***'
    
    print(json.dumps(masked_config, indent=2))