from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Notes: Number of days to look ahead when polling calendar events
    cal_lookahead_days: int = Field(
        14, description="Days to look ahead for polling events"
    )
    # Notes: Number of days to look back when polling calendar events
    cal_lookback_days: int = Field(
        1, description="Days to look back for polling events"
    )

    # Notes: AWS/S3 Configuration
    aws_access_key_id: Optional[str] = Field(
        None, description="AWS Access Key ID"
    )
    aws_secret_access_key: Optional[str] = Field(
        None, description="AWS Secret Access Key"
    )
    aws_default_region: Optional[str] = Field(
        None, description="AWS Region"
    )
    s3_bucket: Optional[str] = Field(
        None, description="S3 bucket name for logs or artifacts"
    )

    # Notes: Comma-separated list of trigger words (for event/meeting
    # detection)
    trigger_words: Optional[str] = Field(
        None, description="Comma-separated list of trigger words"
    )

    # Notes: Add further configuration options as needed (e.g., email
    # recipients, logging levels, etc.)
    # Example:
    # email_recipient: Optional[str] = Field(
    #     None, description="Notification email recipient"
    # )
    # log_level: Optional[str] = Field("INFO", description="Logging level")

    class Config:
        # Notes: Load environment variables from .env file and support
        # UTF-8 encoding
        env_file = ".env"
        env_file_encoding = "utf-8"


# Notes: Singleton instance for importing settings in other modules
settings = Settings()
