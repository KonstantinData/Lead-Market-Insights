#!/usr/bin/env python3
"""
Example script demonstrating email functionality with environment configuration.

Before running this script:
1. Copy .env.example to .env
2. Fill in your actual SMTP credentials in .env
3. Optionally install python-dotenv: pip install python-dotenv

Usage:
    python examples/email_example.py
"""
import os
import sys
import logging

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from agents.email_agent import EmailAgent
from reminders.reminder_escalation import ReminderEscalation

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def main():
    """Example demonstrating email functionality."""
    try:
        # Create EmailAgent from environment variables
        print("Creating EmailAgent from environment variables...")
        agent = EmailAgent.from_env()
        print(f"✓ EmailAgent configured with server: {agent.smtp_server}")
        
        # Example 1: Direct email sending
        print("\n--- Example 1: Direct Email ---")
        recipient = "test@example.com"  # Change to a real email for testing
        subject = "Test Email from Agentic Intelligence Research"
        body = "This is a test email sent using environment-configured SMTP settings."
        
        print(f"Would send email to: {recipient}")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        
        # Uncomment the next line to actually send the email
        # success = agent.send_email(recipient, subject, body)
        # print(f"Email sent: {success}")
        
        # Example 2: Using with ReminderEscalation
        print("\n--- Example 2: Reminder/Escalation System ---")
        reminder_system = ReminderEscalation(agent)
        
        reminder_subject = "Reminder: Please complete your task"
        reminder_body = "This is a friendly reminder about a pending task."
        
        print(f"Would send reminder to: {recipient}")
        print(f"Reminder subject: {reminder_subject}")
        
        # Uncomment the next lines to actually send the reminder
        # success = reminder_system.send_reminder(recipient, reminder_subject, reminder_body)
        # print(f"Reminder sent: {success}")
        
        print("\n✓ Examples completed successfully!")
        print("\nTo actually send emails:")
        print("1. Set up your SMTP credentials in .env")
        print("2. Change recipient to a real email address")
        print("3. Uncomment the send_email() calls")
        
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("\nTo fix this:")
        print("1. Copy .env.example to .env")
        print("2. Fill in your SMTP credentials")
        print("3. Run this script again")
        
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        logging.exception("Unexpected error occurred")


if __name__ == "__main__":
    main()