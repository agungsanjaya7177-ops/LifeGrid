"""
Pydantic schemas for authentication endpoints.

Defines request and response models for user registration, login, token responses,
and error handling with field-level validation.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    """
    Request schema for user registration.

    Includes validation for email format and password strength requirements.

    Attributes:
        email: User email address (must be valid RFC 5321 format)
        password: User password (8-128 chars, ≥1 uppercase, ≥1 lowercase, ≥1 digit)

    Example:
        {
            "email": "user@example.com",
            "password": "MySecurePassword123"
        }
    """

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """
        Validate password meets security requirements.

        Ensures password:
        - Is between 8 and 128 characters
        - Contains at least one uppercase letter
        - Contains at least one lowercase letter
        - Contains at least one digit

        Args:
            v: The password string to validate

        Returns:
            str: The validated password

        Raises:
            ValueError: If password fails any strength check
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    """
    Request schema for user login.

    Includes email validation but no server-side password validation,
    as password strength is only enforced during registration.

    Attributes:
        email: User email address (must be valid RFC 5321 format)
        password: User password (no field validator; validated during authentication)

    Example:
        {
            "email": "user@example.com",
            "password": "MySecurePassword123"
        }
    """

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """
    Response schema for successful token creation.

    Returned by login and register endpoints to provide the client with
    a JWT token for use in Authorization headers.

    Attributes:
        token: The JWT bearer token string
        token_type: The token type (always "bearer" for standard JWT usage)
        expires_in: Token expiration time in seconds from now

    Example:
        {
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "expires_in": 3600
        }
    """

    token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """
    Response schema for user data.

    Represents a user's basic account information without exposing
    sensitive fields like password hashes.

    Attributes:
        id: User UUID
        email: User email address
        created_at: Account creation timestamp

    Example:
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "user@example.com",
            "created_at": "2024-01-15T10:30:00+00:00"
        }
    """

    id: UUID
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    """
    Response schema for successful user registration.

    Combines user information with a JWT token, allowing immediate
    authenticated access after account creation without requiring a second login.

    Attributes:
        id: User UUID
        email: User email address
        token: JWT bearer token for authenticated requests
        token_type: The token type (always "bearer")
        expires_in: Token expiration time in seconds from now

    Example:
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "user@example.com",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "expires_in": 86400
        }
    """

    id: UUID
    email: str
    token: str
    token_type: str = "bearer"
    expires_in: int


class ErrorResponse(BaseModel):
    """
    Response schema for error responses.

    Provides structured error information including detail message and optional
    error code. For validation errors, includes field-level error details.

    Attributes:
        detail: Human-readable error message
        code: Optional error code for programmatic handling
        fields: Optional dict of field-level validation errors (key: field name, value: error message)

    Example (general error):
        {
            "detail": "Email already registered",
            "code": "EMAIL_EXISTS"
        }

    Example (validation error):
        {
            "detail": "Validation failed",
            "code": "VALIDATION_ERROR",
            "fields": {
                "password": "Password must contain at least one uppercase letter",
                "email": "Invalid email format"
            }
        }
    """

    detail: str
    code: str | None = None
    fields: dict[str, str] | None = None
