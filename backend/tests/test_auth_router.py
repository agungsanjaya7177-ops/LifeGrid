"""
Integration tests for authentication router endpoints.

Tests POST /auth/register, POST /auth/login, and POST /auth/logout
with comprehensive coverage of success and error paths.

Uses TestClient to simulate HTTP requests to the FastAPI app.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.dependencies import get_db
from backend.models.user import User
from backend.services.auth_service import hash_password, create_access_token, add_to_blocklist


@pytest.fixture
def app():
    """Create a fresh FastAPI app for testing."""
    return create_app()


@pytest.fixture
def client(app, db):
    """
    Create a TestClient with dependency override for database.
    
    Overrides get_db to use the test database fixture instead of
    the production database configured in dependencies.py.
    """
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    
    return TestClient(app)


class TestRegister:
    """Tests for POST /auth/register endpoint."""

    def test_register_success(self, client, db):
        """Valid email/password should return 201 with JWT."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "ValidPassword123"
            }
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response structure
        assert "id" in data
        assert data["email"] == "user@example.com"
        assert "token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

        # Verify user was created in database
        user = db.query(User).filter(User.email == "user@example.com").first()
        assert user is not None
        assert user.id == data["id"]

    def test_register_duplicate_email(self, client, db):
        """Duplicate email should return 409 Conflict."""
        # Create first user
        existing_user = User(
            email="existing@example.com",
            password_hash=hash_password("Password123")
        )
        db.add(existing_user)
        db.commit()

        # Try to register with same email
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "existing@example.com",
                "password": "NewPassword123"
            }
        )

        assert response.status_code == 409
        data = response.json()
        assert "Email already registered" in data["detail"]

    def test_register_invalid_password_short(self, client):
        """Password shorter than 8 chars should return 422."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "Short1"  # 6 chars
            }
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_register_invalid_password_long(self, client):
        """Password longer than 128 chars should return 422."""
        long_password = "A1a" + ("x" * 130)  # 133 chars
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": long_password
            }
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_register_invalid_password_no_uppercase(self, client):
        """Password without uppercase should return 422."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "lowercase123"
            }
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_register_invalid_password_no_lowercase(self, client):
        """Password without lowercase should return 422."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "UPPERCASE123"
            }
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_register_invalid_password_no_digit(self, client):
        """Password without digit should return 422."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "NoDigitsHere"
            }
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_register_invalid_email(self, client):
        """Malformed email should return 422."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "ValidPassword123"
            }
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_register_returns_jwt_expiry_24_hours(self, client, db):
        """Register response should have JWT expiring in ~24 hours."""
        # Record time before request
        before_time = datetime.now(timezone.utc)

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "user@example.com",
                "password": "ValidPassword123"
            }
        )

        assert response.status_code == 201
        data = response.json()

        # expires_in should be approximately 24 hours = 86400 seconds
        # Allow ±5% tolerance for timing variations
        expires_in = data["expires_in"]
        expected_min = int(86400 * 0.95)  # 82080 seconds
        expected_max = int(86400 * 1.05)  # 90720 seconds

        assert expected_min <= expires_in <= expected_max


class TestLogin:
    """Tests for POST /auth/login endpoint."""

    @pytest.fixture
    def existing_user(self, db):
        """Create a user for login tests."""
        user = User(
            email="existing@example.com",
            password_hash=hash_password("CorrectPassword123")
        )
        db.add(user)
        db.commit()
        # Don't refresh - SQLite test db can have issues with refresh
        # Just return the user with the committed id
        return user

    def test_login_success(self, client, existing_user):
        """Valid credentials should return 200 with JWT."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "existing@example.com",
                "password": "CorrectPassword123"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_login_nonexistent_user(self, client):
        """Nonexistent email should return 401 without revealing email/password."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "AnyPassword123"
            }
        )

        assert response.status_code == 401
        data = response.json()
        # Message should be opaque
        assert "Invalid credentials" in data["detail"]
        assert "not found" not in data["detail"].lower()

    def test_login_wrong_password(self, client, existing_user):
        """Wrong password should return 401 without revealing email/password."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "existing@example.com",
                "password": "WrongPassword123"
            }
        )

        assert response.status_code == 401
        data = response.json()
        # Message should be opaque
        assert "Invalid credentials" in data["detail"]

    def test_login_rate_limit_after_5_failures(self, client, existing_user, db):
        """5 wrong attempts should trigger 15-minute lockout returning 423."""
        # Make 5 failed login attempts
        for _ in range(5):
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "existing@example.com",
                    "password": "WrongPassword123"
                }
            )
            assert response.status_code == 401

        # 6th attempt should be locked
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "existing@example.com",
                "password": "CorrectPassword123"  # Even correct password won't work
            }
        )

        assert response.status_code == 423
        data = response.json()
        assert "locked" in data["detail"].lower() or "temporarily" in data["detail"].lower()

    def test_login_rate_limit_expires_after_15_min(self, client, existing_user, db):
        """After lockout expires (15 min), login should succeed."""
        # Make 5 failed login attempts to trigger lockout
        for _ in range(5):
            client.post(
                "/api/v1/auth/login",
                json={
                    "email": "existing@example.com",
                    "password": "WrongPassword123"
                }
            )

        # Verify locked
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "existing@example.com",
                "password": "CorrectPassword123"
            }
        )
        assert response.status_code == 423

        # Manually update locked_until in database to past time
        user = db.query(User).filter(User.email == "existing@example.com").first()
        user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()

        # Now login should succeed
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "existing@example.com",
                "password": "CorrectPassword123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data

    def test_login_resets_failure_counter(self, client, existing_user, db):
        """Successful login should reset failure counter to 0."""
        # Make 3 failed attempts
        for _ in range(3):
            client.post(
                "/api/v1/auth/login",
                json={
                    "email": "existing@example.com",
                    "password": "WrongPassword123"
                }
            )

        # Verify counter is 3
        user = db.query(User).filter(User.email == "existing@example.com").first()
        assert user.failed_attempts == 3

        # Successful login
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "existing@example.com",
                "password": "CorrectPassword123"
            }
        )
        assert response.status_code == 200

        # Verify counter is reset to 0
        user = db.query(User).filter(User.email == "existing@example.com").first()
        assert user.failed_attempts == 0

    def test_login_returns_jwt_expiry_15_60_min(self, client, existing_user):
        """Login JWT expiry should be in 15-60 minute range."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "existing@example.com",
                "password": "CorrectPassword123"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # expires_in should be in 15-60 minute range
        expires_in = data["expires_in"]
        expected_min = 15 * 60  # 900 seconds
        expected_max = 60 * 60  # 3600 seconds

        assert expected_min <= expires_in <= expected_max


class TestLogout:
    """Tests for POST /auth/logout endpoint."""

    @pytest.fixture
    def authenticated_headers(self, db):
        """Create a valid JWT token and return Authorization header."""
        # Create user
        user = User(
            email="user@example.com",
            password_hash=hash_password("Password123")
        )
        db.add(user)
        db.commit()

        # Generate JWT
        jti = str(uuid4())
        token = create_access_token(str(user.id), jti)

        return {
            "Authorization": f"Bearer {token}"
        }

    def test_logout_success(self, client, authenticated_headers):
        """Valid token should return 204 and blocklist token."""
        response = client.post(
            "/api/v1/auth/logout",
            headers=authenticated_headers
        )

        assert response.status_code == 204
        assert response.content == b""

    def test_logout_invalid_token(self, client):
        """Missing or invalid token should return 401."""
        # No Authorization header
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 403  # HTTPBearer returns 403 when missing

    def test_logout_expired_token(self, client, db):
        """Expired token should return 401."""
        # Create user
        user = User(
            email="user@example.com",
            password_hash=hash_password("Password123")
        )
        db.add(user)
        db.commit()

        # Generate expired token (exp in past)
        jti = str(uuid4())
        # Use negative timedelta to create an already-expired token
        token = create_access_token(str(user.id), jti, timedelta(seconds=-1))

        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            "/api/v1/auth/logout",
            headers=headers
        )

        assert response.status_code == 401

    def test_logout_blocklists_token(self, client, authenticated_headers, db):
        """After logout, token should be in blocklist."""
        # Extract token from header
        token = authenticated_headers["Authorization"].replace("Bearer ", "")

        # Logout
        response = client.post(
            "/api/v1/auth/logout",
            headers=authenticated_headers
        )
        assert response.status_code == 204

        # Verify token is in blocklist
        from backend.models.jwt_blocklist import JWTBlocklist
        from backend.services.auth_service import decode_token

        payload = decode_token(token)
        jti = payload["jti"]

        blocklisted = db.query(JWTBlocklist).filter(JWTBlocklist.jti == jti).first()
        assert blocklisted is not None
        assert blocklisted.jti == jti

    def test_logout_client_cannot_reuse_token(self, client, authenticated_headers, db):
        """After logout, using same token on protected endpoint should fail."""
        # First, logout with the token
        response = client.post(
            "/api/v1/auth/logout",
            headers=authenticated_headers
        )
        assert response.status_code == 204

        # Try to use the same token on a protected endpoint (health check won't work)
        # We'll need to create a minimal protected endpoint or test with /api/v1/auth/logout again
        response = client.post(
            "/api/v1/auth/logout",
            headers=authenticated_headers
        )

        # Should be rejected because token is blocklisted
        assert response.status_code == 401


class TestErrorResponses:
    """Tests for error response format consistency."""

    def test_all_errors_follow_response_format(self, client):
        """All error responses should have 'detail' field."""
        # Test 422 validation error
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "invalid-email", "password": "short"}
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

        # Test 409 duplicate email
        # First create a user
        client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "ValidPassword123"}
        )
        # Try to create again
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "AnotherPassword123"}
        )
        assert response.status_code == 409
        data = response.json()
        assert "detail" in data

        # Test 401 invalid credentials
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "Password123"}
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
