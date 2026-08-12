"""Tests for configuration management."""

import os
import sys
import pytest


def test_config_requires_all_env_vars(monkeypatch):
    """
    Test that the application terminates with a descriptive error 
    if any required environment variable is missing.
    
    Validates: Requirement 20.1
    """
    # Clear all required environment variables
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    # Try to import config - should fail
    with pytest.raises(SystemExit) as exc_info:
        # Remove the cached settings module so it gets reloaded
        if "backend.config" in sys.modules:
            del sys.modules["backend.config"]
        from backend import config  # noqa: F401
    
    assert exc_info.value.code == 1


def test_config_loads_with_all_env_vars(monkeypatch):
    """
    Test that configuration loads successfully when all environment 
    variables are provided.
    
    Validates: Requirement 20.1
    """
    # Set all required environment variables
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/lifegrid")
    monkeypatch.setenv("JWT_SECRET", "this-is-a-secret-key-that-is-at-least-32-bytes-long-ok")
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")

    # Remove the cached settings module so it gets reloaded
    if "backend.config" in sys.modules:
        del sys.modules["backend.config"]
    
    from backend.config import settings
    
    assert settings.DATABASE_URL == "postgresql://test:test@localhost/lifegrid"
    assert settings.JWT_SECRET == "this-is-a-secret-key-that-is-at-least-32-bytes-long-ok"
    assert settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert settings.ALLOWED_ORIGINS == "http://localhost:5173"


def test_config_jwt_secret_minimum_length(monkeypatch, capsys):
    """
    Test that JWT_SECRET must be at least 32 bytes for security.
    
    Validates: Requirement 20.1
    """
    # Set environment variables with a short JWT_SECRET
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/lifegrid")
    monkeypatch.setenv("JWT_SECRET", "short")  # Less than 32 bytes
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")

    # Remove the cached settings module so it gets reloaded
    if "backend.config" in sys.modules:
        del sys.modules["backend.config"]
    
    with pytest.raises(SystemExit) as exc_info:
        from backend.config import settings  # noqa: F401, E501, F841
    
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "JWT_SECRET must be at least 32 bytes" in captured.err
