"""
Unit tests for authentication schemas.

Tests Pydantic model validation for auth requests and responses.
"""

import uuid
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from backend.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    RegisterResponse,
    ErrorResponse,
)


class TestRegisterRequest:
    """Test RegisterRequest schema validation."""

    def test_register_request_accepts_valid_data(self):
        """Test that RegisterRequest accepts valid email and password."""
        data = {
            "email": "user@example.com",
            "password": "ValidPassword123",
        }
        request = RegisterRequest(**data)
        assert request.email == "user@example.com"
        assert request.password == "ValidPassword123"

    def test_register_request_rejects_invalid_email(self):
        """Test that RegisterRequest rejects invalid email format."""
        data = {
            "email": "not-an-email",
            "password": "ValidPassword123",
        }
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**data)
        errors = exc_info.value.errors()
        assert any("email" in str(error).lower() for error in errors)

    def test_register_request_rejects_short_password(self):
        """Test that RegisterRequest rejects password shorter than 8 characters."""
        data = {
            "email": "user@example.com",
            "password": "Short12",
        }
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**data)
        errors = exc_info.value.errors()
        assert any("password" in str(error).lower() for error in errors)

    def test_register_request_rejects_long_password(self):
        """Test that RegisterRequest rejects password longer than 128 characters."""
        data = {
            "email": "user@example.com",
            "password": "A" * 129 + "a1",
        }
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**data)
        errors = exc_info.value.errors()
        assert any("password" in str(error).lower() for error in errors)

    def test_register_request_rejects_password_missing_uppercase(self):
        """Test that RegisterRequest rejects password without uppercase letter."""
        data = {
            "email": "user@example.com",
            "password": "nouppercasepassword1",
        }
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**data)
        errors = exc_info.value.errors()
        assert any("password" in str(error).lower() for error in errors)

    def test_register_request_rejects_password_missing_lowercase(self):
        """Test that RegisterRequest rejects password without lowercase letter."""
        data = {
            "email": "user@example.com",
            "password": "NOLOWERCASEPASSWORD1",
        }
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**data)
        errors = exc_info.value.errors()
        assert any("password" in str(error).lower() for error in errors)

    def test_register_request_rejects_password_missing_digit(self):
        """Test that RegisterRequest rejects password without digit."""
        data = {
            "email": "user@example.com",
            "password": "NoDigitPassword",
        }
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(**data)
        errors = exc_info.value.errors()
        assert any("password" in str(error).lower() for error in errors)


class TestLoginRequest:
    """Test LoginRequest schema validation."""

    def test_login_request_accepts_valid_data(self):
        """Test that LoginRequest accepts valid email and password."""
        data = {
            "email": "user@example.com",
            "password": "MyPassword123",
        }
        request = LoginRequest(**data)
        assert request.email == "user@example.com"
        assert request.password == "MyPassword123"

    def test_login_request_accepts_any_password_format(self):
        """Test that LoginRequest accepts any password (no validation on login)."""
        data = {
            "email": "user@example.com",
            "password": "weak",
        }
        request = LoginRequest(**data)
        assert request.password == "weak"

    def test_login_request_rejects_invalid_email(self):
        """Test that LoginRequest rejects invalid email format."""
        data = {
            "email": "not-an-email",
            "password": "MyPassword123",
        }
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(**data)
        errors = exc_info.value.errors()
        assert any("email" in str(error).lower() for error in errors)


class TestTokenResponse:
    """Test TokenResponse schema."""

    def test_token_response_with_all_fields(self):
        """Test that TokenResponse validates with all fields."""
        data = {
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "expires_in": 3600,
        }
        response = TokenResponse(**data)
        assert response.token == data["token"]
        assert response.token_type == "bearer"
        assert response.expires_in == 3600

    def test_token_response_defaults_token_type(self):
        """Test that TokenResponse defaults token_type to 'bearer'."""
        data = {
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "expires_in": 3600,
        }
        response = TokenResponse(**data)
        assert response.token_type == "bearer"

    def test_token_response_requires_token(self):
        """Test that TokenResponse requires token field."""
        data = {
            "expires_in": 3600,
        }
        with pytest.raises(ValidationError):
            TokenResponse(**data)


class TestUserResponse:
    """Test UserResponse schema."""

    def test_user_response_with_valid_data(self):
        """Test that UserResponse validates with valid user data."""
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        data = {
            "id": user_id,
            "email": "user@example.com",
            "created_at": now,
        }
        response = UserResponse(**data)
        assert response.id == user_id
        assert response.email == "user@example.com"
        assert response.created_at == now


class TestRegisterResponse:
    """Test RegisterResponse schema."""

    def test_register_response_with_all_fields(self):
        """Test that RegisterResponse validates with all fields."""
        user_id = uuid.uuid4()
        data = {
            "id": user_id,
            "email": "user@example.com",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "expires_in": 86400,
        }
        response = RegisterResponse(**data)
        assert response.id == user_id
        assert response.email == "user@example.com"
        assert response.token == data["token"]
        assert response.token_type == "bearer"
        assert response.expires_in == 86400

    def test_register_response_defaults_token_type(self):
        """Test that RegisterResponse defaults token_type to 'bearer'."""
        user_id = uuid.uuid4()
        data = {
            "id": user_id,
            "email": "user@example.com",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "expires_in": 86400,
        }
        response = RegisterResponse(**data)
        assert response.token_type == "bearer"


class TestErrorResponse:
    """Test ErrorResponse schema."""

    def test_error_response_with_detail_only(self):
        """Test that ErrorResponse works with detail field only."""
        data = {
            "detail": "An error occurred",
        }
        response = ErrorResponse(**data)
        assert response.detail == "An error occurred"
        assert response.code is None
        assert response.fields is None

    def test_error_response_with_code(self):
        """Test that ErrorResponse includes optional code."""
        data = {
            "detail": "Email already exists",
            "code": "EMAIL_EXISTS",
        }
        response = ErrorResponse(**data)
        assert response.detail == "Email already exists"
        assert response.code == "EMAIL_EXISTS"

    def test_error_response_with_fields(self):
        """Test that ErrorResponse includes optional validation fields."""
        data = {
            "detail": "Validation failed",
            "code": "VALIDATION_ERROR",
            "fields": {
                "email": "Invalid email format",
                "password": "Password too short",
            },
        }
        response = ErrorResponse(**data)
        assert response.detail == "Validation failed"
        assert response.code == "VALIDATION_ERROR"
        assert response.fields == data["fields"]
