"""
Integration tests for FastAPI dependencies.

Tests JWT authentication, blocklist validation, and user retrieval.
"""

import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID
from unittest.mock import Mock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.dependencies import get_current_user, oauth2_scheme
from backend.models.user import User
from backend.services.auth_service import (
    create_access_token,
    add_to_blocklist,
    decode_token,
    is_blocklisted,
)


class TestGetCurrentUser:
    """Test get_current_user dependency."""

    def test_get_current_user_with_valid_token_mocked_db(self):
        """Test that get_current_user returns user with valid token."""
        # Create a mock database
        mock_db = MagicMock()
        
        # Create a test user
        user_id = uuid.uuid4()
        user = Mock()
        user.id = user_id
        user.email = "test@example.com"
        
        # Mock the query chain
        mock_db.query.return_value.filter.return_value.first.return_value = user
        
        # Create a valid token
        jti = str(uuid.uuid4())
        token = create_access_token(user_id, jti)

        # Mock the HTTPBearer credentials
        mock_credentials = Mock()
        mock_credentials.credentials = token

        # Mock is_blocklisted to return False
        with patch('backend.dependencies.is_blocklisted', return_value=False):
            # Call get_current_user
            result = get_current_user(token=mock_credentials, db=mock_db)

            # Verify the user is returned
            assert result.id == user_id
            assert result.email == "test@example.com"

    def test_get_current_user_with_expired_token(self):
        """Test that get_current_user raises 401 for expired tokens."""
        mock_db = MagicMock()
        user_id = uuid.uuid4()
        jti = str(uuid.uuid4())

        # Create an expired token
        expired_token = create_access_token(
            user_id, jti, expires_delta=timedelta(seconds=-1)
        )

        # Mock the HTTPBearer credentials
        mock_credentials = Mock()
        mock_credentials.credentials = expired_token

        # Call get_current_user and expect 401
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=mock_credentials, db=mock_db)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_get_current_user_with_malformed_token(self):
        """Test that get_current_user raises 401 for malformed tokens."""
        mock_db = MagicMock()
        
        # Mock the HTTPBearer credentials with malformed token
        mock_credentials = Mock()
        mock_credentials.credentials = "not.a.valid.token"

        # Call get_current_user and expect 401
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=mock_credentials, db=mock_db)

        assert exc_info.value.status_code == 401

    def test_get_current_user_with_blocklisted_token(self):
        """Test that get_current_user raises 401 for blocklisted tokens."""
        mock_db = MagicMock()
        
        # Create a test user
        user_id = uuid.uuid4()
        
        # Create a valid token
        jti = str(uuid.uuid4())
        token = create_access_token(user_id, jti)

        # Mock the HTTPBearer credentials
        mock_credentials = Mock()
        mock_credentials.credentials = token

        # Mock is_blocklisted to return True (token is blocklisted)
        with patch('backend.dependencies.is_blocklisted', return_value=True):
            # Call get_current_user and expect 401
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=mock_credentials, db=mock_db)

            assert exc_info.value.status_code == 401
            assert "revoked" in exc_info.value.detail.lower()

    def test_get_current_user_with_nonexistent_user(self):
        """Test that get_current_user raises 401 when user not found."""
        mock_db = MagicMock()
        
        # Create a token for a non-existent user
        nonexistent_user_id = uuid.uuid4()
        jti = str(uuid.uuid4())
        token = create_access_token(nonexistent_user_id, jti)

        # Mock the query chain to return None (user not found)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock the HTTPBearer credentials
        mock_credentials = Mock()
        mock_credentials.credentials = token

        # Mock is_blocklisted to return False
        with patch('backend.dependencies.is_blocklisted', return_value=False):
            # Call get_current_user and expect 401
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=mock_credentials, db=mock_db)

            assert exc_info.value.status_code == 401
            assert "not found" in exc_info.value.detail.lower()

    def test_get_current_user_with_tampered_token(self):
        """Test that get_current_user raises 401 for tampered tokens."""
        mock_db = MagicMock()
        
        # Create a valid token
        user_id = uuid.uuid4()
        jti = str(uuid.uuid4())
        token = create_access_token(user_id, jti)

        # Tamper with the token
        tampered_token = token[:-1] + ("a" if token[-1] != "a" else "b")

        # Mock the HTTPBearer credentials
        mock_credentials = Mock()
        mock_credentials.credentials = tampered_token

        # Call get_current_user and expect 401
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=mock_credentials, db=mock_db)

        assert exc_info.value.status_code == 401

    def test_get_current_user_extracts_correct_user_from_payload(self):
        """Test that get_current_user extracts user_id from token payload."""
        mock_db = MagicMock()
        
        # Create two different user IDs
        user1_id = uuid.uuid4()
        user2_id = uuid.uuid4()
        
        # Create a mock user
        user1 = Mock()
        user1.id = user1_id
        user1.email = "user1@example.com"

        # Mock the query chain to return user1
        mock_db.query.return_value.filter.return_value.first.return_value = user1

        # Create a token for user1
        jti = str(uuid.uuid4())
        token = create_access_token(user1_id, jti)

        # Mock the HTTPBearer credentials
        mock_credentials = Mock()
        mock_credentials.credentials = token

        # Mock is_blocklisted to return False
        with patch('backend.dependencies.is_blocklisted', return_value=False):
            # Call get_current_user
            result = get_current_user(token=mock_credentials, db=mock_db)

            # Verify the correct user is returned (user1, not user2)
            assert result.id == user1_id
            assert result.email == "user1@example.com"
