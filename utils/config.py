"""
Configuration module for loading environment variables.
Supports both .env files for local development and direct environment variables for CI/CD.
"""
import os
from typing import Optional


def load_dotenv_if_available():
    """
    Load .env file if python-dotenv is available and .env file exists.
    This allows for optional dotenv usage without making it a hard dependency.
    """
    try:
        from dotenv import load_dotenv
        env_path = ".env"
        if os.path.exists(env_path):
            load_dotenv(env_path)
            return True
    except ImportError:
        # python-dotenv not installed, continue with environment variables only
        pass
    return False


class SMTPConfig:
    """
    SMTP configuration loaded from environment variables.
    """
    
    def __init__(self):
        # Try to load .env file if available
        load_dotenv_if_available()
        
        # Load SMTP configuration from environment variables
        self.host = os.environ.get("SMTP_HOST")
        self.port = self._get_int_env("SMTP_PORT", 587)
        self.user = os.environ.get("SMTP_USER")
        self.password = os.environ.get("SMTP_PASS")
        self.secure = self._get_bool_env("SMTP_SECURE", True)
        self.mail_from = os.environ.get("MAIL_FROM")
        
        # Validate required configuration
        self._validate()
    
    def _get_int_env(self, key: str, default: int) -> int:
        """Get integer environment variable with default."""
        try:
            value = os.environ.get(key)
            return int(value) if value else default
        except ValueError:
            return default
    
    def _get_bool_env(self, key: str, default: bool) -> bool:
        """Get boolean environment variable with default."""
        value = os.environ.get(key, "").lower()
        if value in ("true", "1", "yes", "on"):
            return True
        elif value in ("false", "0", "no", "off"):
            return False
        return default
    
    def _validate(self):
        """Validate that required SMTP configuration is present."""
        required_fields = ["host", "user", "password", "mail_from"]
        missing_fields = []
        
        for field in required_fields:
            if not getattr(self, field):
                env_var = {
                    "host": "SMTP_HOST",
                    "user": "SMTP_USER", 
                    "password": "SMTP_PASS",
                    "mail_from": "MAIL_FROM"
                }[field]
                missing_fields.append(env_var)
        
        if missing_fields:
            raise ValueError(
                f"Missing required SMTP environment variables: {', '.join(missing_fields)}\n"
                f"Please set these environment variables or create a .env file with the required values.\n"
                f"See .env.example for the expected format."
            )
    
    def get_smtp_config(self) -> dict:
        """Get SMTP configuration as a dictionary."""
        return {
            "smtp_server": self.host,
            "smtp_port": self.port,
            "username": self.user,
            "password": self.password,
            "sender_email": self.mail_from,
            "secure": self.secure
        }


def get_smtp_config() -> SMTPConfig:
    """
    Get SMTP configuration from environment variables.
    
    Returns:
        SMTPConfig: Configured SMTP settings
        
    Raises:
        ValueError: If required environment variables are missing
    """
    return SMTPConfig()