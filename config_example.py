"""
Configuration Examples for Agentic Intelligence Research System

This file provides examples of how to configure the system components
for different environments and use cases.
"""

import os
from email_agent import EmailConfig, create_gmail_config, create_outlook_config


# Example 1: Gmail Configuration
def get_gmail_config():
    """Gmail SMTP configuration example"""
    return create_gmail_config(
        email=os.getenv("GMAIL_EMAIL", "your-email@gmail.com"),
        password=os.getenv("GMAIL_APP_PASSWORD", "your-16-char-app-password"),
        sender_name="Agentic Intelligence Research System"
    )


# Example 2: Outlook/Office365 Configuration
def get_outlook_config():
    """Outlook SMTP configuration example"""
    return create_outlook_config(
        email=os.getenv("OUTLOOK_EMAIL", "your-email@outlook.com"),
        password=os.getenv("OUTLOOK_PASSWORD", "your-password"),
        sender_name="Agentic Intelligence Research System"
    )


# Example 3: Custom SMTP Configuration
def get_custom_smtp_config():
    """Custom SMTP server configuration example"""
    return EmailConfig(
        smtp_server=os.getenv("SMTP_SERVER", "mail.yourcompany.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        username=os.getenv("SMTP_USERNAME", "noreply@yourcompany.com"),
        password=os.getenv("SMTP_PASSWORD", "secure-password"),
        use_tls=True,
        sender_name=os.getenv("SENDER_NAME", "Your Company Notification System"),
        sender_email=os.getenv("SENDER_EMAIL", "noreply@yourcompany.com")
    )


# Example 4: Development Configuration (Console logging only)
def get_development_config():
    """Development configuration with console logging"""
    return EmailConfig(
        smtp_server="localhost",
        smtp_port=1025,  # MailHog or similar local SMTP server
        username="dev@localhost",
        password="password",
        use_tls=False,
        sender_name="Development System"
    )


# AWS S3 Configuration Examples
def get_aws_config():
    """AWS S3 configuration for production"""
    return {
        'bucket_name': os.getenv("S3_BUCKET_NAME", "agentic-intelligence-prod"),
        'aws_access_key_id': os.getenv("AWS_ACCESS_KEY_ID"),
        'aws_secret_access_key': os.getenv("AWS_SECRET_ACCESS_KEY"),
        'aws_region': os.getenv("AWS_REGION", "us-east-1")
    }


def get_aws_config_with_iam():
    """AWS S3 configuration using IAM roles (recommended for EC2/Lambda)"""
    return {
        'bucket_name': os.getenv("S3_BUCKET_NAME", "agentic-intelligence-prod"),
        'aws_region': os.getenv("AWS_REGION", "us-east-1")
        # No credentials needed when using IAM roles
    }


# Environment-specific configurations
def get_config_for_environment(env: str = None):
    """Get configuration based on environment"""
    
    if env is None:
        env = os.getenv("ENVIRONMENT", "development")
    
    configs = {
        "development": {
            "email": get_development_config(),
            "s3": {
                'bucket_name': "agentic-intelligence-dev",
                'aws_region': "us-east-1"
            }
        },
        "staging": {
            "email": get_gmail_config(),  # Use Gmail for staging
            "s3": {
                'bucket_name': "agentic-intelligence-staging",
                'aws_region': "us-east-1"
            }
        },
        "production": {
            "email": get_custom_smtp_config(),  # Use company SMTP for production
            "s3": get_aws_config_with_iam()  # Use IAM roles in production
        }
    }
    
    return configs.get(env, configs["development"])


# Template customization example
def get_custom_template_variables():
    """Example of custom template variables for your organization"""
    return {
        'company_name': 'Your Company Name',
        'support_email': 'support@yourcompany.com',
        'company_url': 'https://www.yourcompany.com',
        'it_department': 'IT Support',
        'hr_department': 'Human Resources',
        'default_meeting_duration': '30 minutes',
        'default_location': 'Main Conference Room',
        'business_hours': '9:00 AM - 5:00 PM EST',
        'time_zone': 'Eastern Time',
        'escalation_timeline': '24 hours'
    }


# Example usage patterns
if __name__ == "__main__":
    
    # Example 1: Get configuration for current environment
    current_env = os.getenv("ENVIRONMENT", "development")
    config = get_config_for_environment(current_env)
    print(f"Configuration for {current_env} environment:")
    print(f"Email SMTP Server: {config['email'].smtp_server}")
    print(f"S3 Bucket: {config['s3']['bucket_name']}")
    
    # Example 2: Test email configuration
    email_config = get_gmail_config()
    print(f"\nEmail configuration:")
    print(f"Server: {email_config.smtp_server}:{email_config.smtp_port}")
    print(f"Username: {email_config.username}")
    print(f"Sender: {email_config.sender_name} <{email_config.sender_email}>")
    
    # Example 3: Custom template variables
    custom_vars = get_custom_template_variables()
    print(f"\nCustom template variables available:")
    for key, value in custom_vars.items():
        print(f"  {{{key}}}: {value}")