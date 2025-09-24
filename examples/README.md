# Examples

This directory contains example scripts demonstrating how to use the Agentic Intelligence Research components.

## Email Examples

### `email_example.py`

Demonstrates how to use the EmailAgent with environment-based configuration:

- Direct email sending
- Integration with ReminderEscalation system
- Proper error handling for missing configuration

**Prerequisites:**
1. Set up SMTP credentials in `.env` (copy from `.env.example`)
2. Optionally install `python-dotenv` for automatic .env file loading

**Usage:**
```bash
cd /path/to/Agentic-Intelligence-Research
python examples/email_example.py
```

The script includes safety features - it shows what would be sent without actually sending emails unless you uncomment the specific send lines.