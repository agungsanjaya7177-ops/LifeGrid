"""
Configuration management for LifeGrid backend.

All secrets and configuration are loaded from environment variables.
If any required variable is absent, the application terminates immediately.
"""

import sys
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Required fields - application will not start without these
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int
    ALLOWED_ORIGINS: str

    class Config:
        env_file = ".env"
        case_sensitive = True


def load_settings() -> Settings:
    """
    Load settings from environment variables.

    If any required environment variable is missing or empty, 
    terminate the application with a descriptive error message.

    Returns:
        Settings: The loaded configuration object

    Raises:
        SystemExit: If any required environment variable is absent
    """
    try:
        settings = Settings()
    except Exception as e:
        # Extract the error details from Pydantic's validation error
        error_msg = str(e)
        print(
            f"FATAL: Failed to load required environment variables.\n"
            f"Error details: {error_msg}\n\n"
            f"Required environment variables:\n"
            f"  - DATABASE_URL: PostgreSQL connection string (e.g., "
            f"postgresql://user:password@localhost/lifegrid)\n"
            f"  - JWT_SECRET: Secret key for signing JWTs (minimum 32 bytes)\n"
            f"  - JWT_ACCESS_TOKEN_EXPIRE_MINUTES: Token expiry in minutes (e.g., 30)\n"
            f"  - ALLOWED_ORIGINS: Comma-separated list of allowed CORS origins "
            f"(e.g., http://localhost:5173,https://example.com)\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate that JWT_SECRET has minimum length for security
    if len(settings.JWT_SECRET) < 32:
        print(
            f"FATAL: JWT_SECRET must be at least 32 bytes for security.\n"
            f"Current length: {len(settings.JWT_SECRET)} bytes\n"
            f"Please generate a secure random string of at least 32 bytes.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate that JWT_ACCESS_TOKEN_EXPIRE_MINUTES is in valid range
    if settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES < 1 or settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES > 1440:
        print(
            f"FATAL: JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440.\n"
            f"Current value: {settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES}\n",
            file=sys.stderr,
        )
        sys.exit(1)

    return settings


def get_allowed_origins() -> List[str]:
    """
    Parse the ALLOWED_ORIGINS environment variable into a list.

    Returns:
        List[str]: List of allowed origins (already parsed from settings)
    """
    settings = load_settings()
    return [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]


# Load settings at module import time so we fail fast if env vars are missing
settings = load_settings()
