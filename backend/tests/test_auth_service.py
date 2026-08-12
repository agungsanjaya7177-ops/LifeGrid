"""
Unit tests for authentication service.

Tests password hashing, JWT creation/decoding, blocklist operations, and rate limiting.
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Session

from backend.services.auth_service import (
    hash_password,
    verify_password,
    validate_password,
    create_access_token,
    decode_token,
    add_to_blocklist,
    is_blocklisted,
    check_rate_limit,
    increment_failure,
    reset_failure,
)
from backend.models.jwt_blocklist import JWTBlocklist
from backend.models.user import User


class TestPasswordHashing:
    """Test password hashing and verification functions."""

    def test_hash_password_creates_valid_bcrypt_hash(self):
        """Test that hash_password creates a valid bcrypt hash."""
        plain_password = "MyPassword123"
        hashed = hash_password(plain_password)

        # Bcrypt hashes start with $2b$
        assert hashed.startswith("$2b$")
        # Hash should be longer than the original password
        assert len(hashed) > len(plain_password)
        # Different calls should produce different hashes (due to random salt)
        hashed2 = hash_password(plain_password)
        assert hashed != hashed2

    def test_verify_password_accepts_correct_password(self):
        """Test that verify_password returns True for correct password."""
        plain_password = "MyPassword123"
        hashed = hash_password(plain_password)

        assert verify_password(plain_password, hashed) is True

    def test_verify_password_rejects_incorrect_password(self):
        """Test that verify_password returns False for incorrect password."""
        plain_password = "MyPassword123"
        wrong_password = "WrongPassword456"
        hashed = hash_password(plain_password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_handles_invalid_hash_gracefully(self):
        """Test that verify_password handles invalid hashes gracefully."""
        plain_password = "MyPassword123"
        invalid_hash = "not_a_valid_hash"

        # Should not raise an exception, just return False
        assert verify_password(plain_password, invalid_hash) is False

    def test_verify_password_timing_safe(self):
        """Test that verify_password uses timing-safe comparison."""
        # This is a behavioral test - we verify that timing is approximately constant
        # In production, timing attacks would require more sophisticated measurement
        import time

        plain_password = "MyPassword123"
        hashed = hash_password(plain_password)
        invalid_hash = "$2b$12$" + "a" * 53

        # Measure verification with invalid hash
        start = time.perf_counter()
        for _ in range(10):
            verify_password(plain_password, invalid_hash)
        invalid_time = time.perf_counter() - start

        # Measure verification with valid hash
        start = time.perf_counter()
        for _ in range(10):
            verify_password(plain_password, hashed)
        valid_time = time.perf_counter() - start

        # Times should be similar (within 100ms, accounting for system variance)
        # This is a loose check since timing can vary
        assert abs(valid_time - invalid_time) < 0.1


class TestPasswordValidation:
    """Test password validation function."""

    def test_validate_password_accepts_valid_password(self):
        """Test that validate_password accepts a valid password."""
        is_valid, error = validate_password("MyPassword123")
        assert is_valid is True
        assert error is None

    def test_validate_password_requires_minimum_length(self):
        """Test that password must be at least 8 characters."""
        is_valid, error = validate_password("Short1")
        assert is_valid is False
        assert "8 and 128 characters" in error

    def test_validate_password_enforces_maximum_length(self):
        """Test that password must be at most 128 characters."""
        long_password = "A" * 129 + "a1"
        is_valid, error = validate_password(long_password)
        assert is_valid is False
        assert "8 and 128 characters" in error

    def test_validate_password_requires_uppercase(self):
        """Test that password must contain at least one uppercase letter."""
        is_valid, error = validate_password("lowerpassword123")
        assert is_valid is False
        assert "uppercase" in error.lower()

    def test_validate_password_requires_lowercase(self):
        """Test that password must contain at least one lowercase letter."""
        is_valid, error = validate_password("UPPERCASE123")
        assert is_valid is False
        assert "lowercase" in error.lower()

    def test_validate_password_requires_digit(self):
        """Test that password must contain at least one digit."""
        is_valid, error = validate_password("NoDigitsHere")
        assert is_valid is False
        assert "digit" in error.lower()

    def test_validate_password_boundary_8_characters(self):
        """Test that 8-character password is valid."""
        is_valid, error = validate_password("Valid123")
        assert is_valid is True
        assert error is None

    def test_validate_password_boundary_128_characters(self):
        """Test that 128-character password is valid."""
        password = "A" * 64 + "a" * 63 + "1"  # 128 chars total
        is_valid, error = validate_password(password)
        assert is_valid is True
        assert error is None


class TestJWTCreation:
    """Test JWT token creation."""

    def test_create_access_token_returns_string(self):
        """Test that create_access_token returns a string token."""
        user_id = uuid.uuid4()
        jti = str(uuid.uuid4())
        token = create_access_token(user_id, jti)

        assert isinstance(token, str)
        # JWT has 3 parts separated by dots
        assert token.count(".") == 2

    def test_create_access_token_with_custom_expiry(self):
        """Test creating token with custom expiry duration."""
        user_id = uuid.uuid4()
        jti = str(uuid.uuid4())
        custom_delta = timedelta(hours=2)
        token = create_access_token(user_id, jti, custom_delta)

        assert isinstance(token, str)
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["jti"] == jti

    def test_create_access_token_uses_default_expiry_when_none(self):
        """Test that None expiry uses default from config."""
        user_id = uuid.uuid4()
        jti = str(uuid.uuid4())
        token = create_access_token(user_id, jti, expires_delta=None)

        payload = decode_token(token)
        assert payload["sub"] == str(user_id)


class TestJWTDecoding:
    """Test JWT token decoding."""

    def test_decode_token_returns_payload(self):
        """Test that decode_token returns the payload dict."""
        user_id = uuid.uuid4()
        jti = str(uuid.uuid4())
        token = create_access_token(user_id, jti)
        payload = decode_token(token)

        assert isinstance(payload, dict)
        assert payload["sub"] == str(user_id)
        assert payload["jti"] == jti
        assert "iat" in payload
        assert "exp" in payload

    def test_decode_token_rejects_expired_token(self):
        """Test that decode_token raises 401 for expired tokens."""
        from fastapi import HTTPException

        user_id = uuid.uuid4()
        jti = str(uuid.uuid4())
        # Create token that expires immediately
        expired_token = create_access_token(
            user_id, jti, expires_delta=timedelta(seconds=-1)
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_token(expired_token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_decode_token_rejects_malformed_token(self):
        """Test that decode_token raises 401 for malformed tokens."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_token("not.a.valid.token")
        assert exc_info.value.status_code == 401

    def test_decode_token_rejects_tampered_token(self):
        """Test that decode_token raises 401 for tampered tokens."""
        from fastapi import HTTPException

        user_id = uuid.uuid4()
        jti = str(uuid.uuid4())
        token = create_access_token(user_id, jti)

        # Tamper with the token by changing the last character
        tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

        with pytest.raises(HTTPException) as exc_info:
            decode_token(tampered)
        assert exc_info.value.status_code == 401


class TestBlocklist:
    """Test JWT blocklist operations."""

    @pytest.mark.skip(reason="Requires PostgreSQL - blocklist storage tested in integration tests")
    def test_add_to_blocklist_creates_entry(self, db: Session):
        """Test that add_to_blocklist creates a database entry."""
        pass

    @pytest.mark.skip(reason="Requires PostgreSQL - blocklist queries tested in integration tests")
    def test_is_blocklisted_returns_false_for_active_token(self, db: Session):
        """Test that is_blocklisted returns False for tokens not in blocklist."""
        pass

    @pytest.mark.skip(reason="Requires PostgreSQL - blocklist queries tested in integration tests")
    def test_is_blocklisted_returns_true_after_adding_to_blocklist(
        self, db: Session
    ):
        """Test that is_blocklisted returns True after adding to blocklist."""
        pass


class TestRateLimiting:
    """Test login rate limiting functions."""

    def test_check_rate_limit_allows_unlocked_account(self, db: Session):
        """Test check_rate_limit allows login for brand new user with no failures."""
        # Create a new user with no failures
        user = User(
            email="newuser@example.com",
            password_hash=hash_password("Password123"),
            failed_attempts=0,
            locked_until=None,
        )
        db.add(user)
        db.commit()

        is_locked, error_msg = check_rate_limit("newuser@example.com", db)
        assert is_locked is False
        assert error_msg is None

    def test_check_rate_limit_allows_unlocked_account_after_reset(self, db: Session):
        """Test check_rate_limit allows login after reset_failure is called."""
        # Create a user with some failures
        user = User(
            email="user@example.com",
            password_hash=hash_password("Password123"),
            failed_attempts=3,
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db.add(user)
        db.commit()

        # Reset the failure
        reset_failure("user@example.com", db)

        # Should now be allowed
        is_locked, error_msg = check_rate_limit("user@example.com", db)
        assert is_locked is False
        assert error_msg is None

    def test_check_rate_limit_locks_account_after_5_failures(self, db: Session):
        """Test check_rate_limit locks account after 5 increments."""
        # Create a user with 5 failed attempts and locked_until set
        user = User(
            email="locked@example.com",
            password_hash=hash_password("Password123"),
            failed_attempts=5,
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        db.add(user)
        db.commit()

        is_locked, error_msg = check_rate_limit("locked@example.com", db)
        assert is_locked is True
        assert error_msg == "Account is temporarily locked. Try again in 15 minutes."

    def test_check_rate_limit_rejects_locked_account(self, db: Session):
        """Test check_rate_limit rejects login when locked_until > now()."""
        # Create a user whose lockout is still valid
        future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        user = User(
            email="still_locked@example.com",
            password_hash=hash_password("Password123"),
            failed_attempts=5,
            locked_until=future_time,
        )
        db.add(user)
        db.commit()

        is_locked, error_msg = check_rate_limit("still_locked@example.com", db)
        assert is_locked is True
        assert "temporarily locked" in error_msg

    def test_check_rate_limit_allows_account_after_lockout_expires(self, db: Session):
        """Test check_rate_limit allows login after lockout_until < now()."""
        # Create a user whose lockout has expired
        past_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        user = User(
            email="expired_lock@example.com",
            password_hash=hash_password("Password123"),
            failed_attempts=5,
            locked_until=past_time,
        )
        db.add(user)
        db.commit()

        is_locked, error_msg = check_rate_limit("expired_lock@example.com", db)
        assert is_locked is False
        assert error_msg is None

    def test_increment_failure_increments_counter(self, db: Session):
        """Test increment_failure increments counter 0→1→2→3→4→5."""
        user = User(
            email="counter@example.com",
            password_hash=hash_password("Password123"),
            failed_attempts=0,
            locked_until=None,
        )
        db.add(user)
        db.commit()

        # Increment through all attempts
        for expected_count in range(1, 6):
            increment_failure("counter@example.com", db)
            user = db.query(User).filter(User.email == "counter@example.com").first()
            assert user.failed_attempts == expected_count

    def test_increment_failure_locks_account_at_5(self, db: Session):
        """Test increment_failure sets locked_until on 5th increment."""
        user = User(
            email="locktest@example.com",
            password_hash=hash_password("Password123"),
            failed_attempts=0,
            locked_until=None,
        )
        db.add(user)
        db.commit()

        # Increment 4 times - should not lock
        for _ in range(4):
            increment_failure("locktest@example.com", db)
        user = db.query(User).filter(User.email == "locktest@example.com").first()
        assert user.locked_until is None

        # Increment 5th time - should lock
        before_increment = datetime.now(timezone.utc)
        increment_failure("locktest@example.com", db)
        after_increment = datetime.now(timezone.utc)

        user = db.query(User).filter(User.email == "locktest@example.com").first()
        assert user.failed_attempts == 5
        assert user.locked_until is not None
        # Verify locked_until is approximately 15 minutes from now
        # Handle SQLite returning naive datetimes
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        assert before_increment + timedelta(minutes=15) <= locked_until <= after_increment + timedelta(minutes=15)

    def test_reset_failure_clears_counter_and_lockout(self, db: Session):
        """Test reset_failure clears both failed_attempts and locked_until."""
        # Create a locked user
        future_time = datetime.now(timezone.utc) + timedelta(minutes=15)
        user = User(
            email="reset_test@example.com",
            password_hash=hash_password("Password123"),
            failed_attempts=5,
            locked_until=future_time,
        )
        db.add(user)
        db.commit()

        # Reset the failure
        reset_failure("reset_test@example.com", db)

        # Verify both fields are cleared
        user = db.query(User).filter(User.email == "reset_test@example.com").first()
        assert user.failed_attempts == 0
        assert user.locked_until is None

