"""
Authentication router for LifeGrid API.

Implements user registration, login, and logout endpoints with secure JWT handling,
password validation, rate limiting, and server-side token invalidation.

Endpoints:
    - POST /auth/register: Register a new user account
    - POST /auth/login: Authenticate user and receive JWT
    - POST /auth/logout: Invalidate JWT server-side (blocklist)
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status

from backend.database import SessionLocal
from backend.dependencies import get_db, get_current_user, oauth2_scheme
from backend.models.user import User
from backend.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    RegisterResponse,
)
from backend.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    check_rate_limit,
    increment_failure,
    reset_failure,
    add_to_blocklist,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", status_code=201, response_model=RegisterResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user account.

    Validates registration request, checks for duplicate email, hashes password,
    creates user record, and returns JWT token for immediate authenticated access.

    Request body validation (via Pydantic):
    - email: Valid RFC 5321 format (via EmailStr)
    - password: 8-128 chars with ≥1 uppercase, ≥1 lowercase, ≥1 digit

    Args:
        request: RegisterRequest with email and password
        db: Database session

    Returns:
        RegisterResponse: User ID, email, JWT token, token type, expiry in seconds

    Raises:
        HTTPException: 409 if email already registered
        HTTPException: 422 if validation fails (handled by Pydantic)
        HTTPException: 500 if database error during user creation
    """
    try:
        # Check if email already exists in database
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            logger.warning(f"Registration attempted with existing email: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        # Hash password using bcrypt (cost factor ≥ 12)
        password_hash = hash_password(request.password)

        # Create new user record
        new_user = User(
            email=request.email,
            password_hash=password_hash,
        )

        db.add(new_user)
        db.commit()
        # SQLite test DB can have issues with refresh, just query the user back
        new_user = db.query(User).filter(User.email == request.email).first()

        # Generate JWT token with 24-hour expiry (per Requirement 1.6)
        jti = str(uuid4())
        token = create_access_token(
            user_id=str(new_user.id),
            jti=jti,
        )

        # Decode token to get expires_in
        payload = decode_token(token)
        expires_in = payload["exp"] - int(datetime.now(timezone.utc).timestamp())

        logger.info(f"User registered successfully: {new_user.email}")

        return RegisterResponse(
            id=new_user.id,
            email=new_user.email,
            token=token,
            token_type="bearer",
            expires_in=expires_in,
        )

    except HTTPException:
        # Re-raise HTTP exceptions (409, 422)
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user account: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account",
        )


@router.post("/login", status_code=200, response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user and return JWT token.

    Validates credentials with rate limiting (5 failures = 15-minute lockout),
    timing-safe password verification, and opaque error messages.

    Args:
        request: LoginRequest with email and password
        db: Database session

    Returns:
        TokenResponse: JWT token, token type, expiry in seconds (15-60 minutes)

    Raises:
        HTTPException: 423 if account locked (rate limit exceeded)
        HTTPException: 401 if credentials invalid (opaque message)
        HTTPException: 500 if database error
    """
    try:
        # Check rate limit first (before querying user to avoid timing attacks)
        is_locked, lock_message = check_rate_limit(request.email, db)
        if is_locked:
            logger.warning(f"Login attempt on locked account: {request.email}")
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=lock_message or "Account temporarily locked",
            )

        # Query user by email
        user = db.query(User).filter(User.email == request.email).first()

        # Verify password with timing-safe check even if user not found
        password_valid = verify_password(request.password, user.password_hash if user else None)

        if not user or not password_valid:
            # Increment failure counter
            increment_failure(request.email, db)
            logger.warning(f"Failed login attempt: {request.email}")
            # Return opaque error message (don't reveal email/password distinction)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        # Password is valid, reset failure counter
        reset_failure(request.email, db)

        # Generate JWT token with expiry from config (15-60 minutes)
        jti = str(uuid4())
        token = create_access_token(
            user_id=str(user.id),
            jti=jti,
        )

        # Decode token to get expires_in
        payload = decode_token(token)
        expires_in = payload["exp"] - int(datetime.now(timezone.utc).timestamp())

        logger.info(f"User logged in successfully: {user.email}")

        return TokenResponse(
            token=token,
            token_type="bearer",
            expires_in=expires_in,
        )

    except HTTPException:
        # Re-raise HTTP exceptions (401, 423, 500)
        raise
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error",
        )


@router.post("/logout", status_code=204)
def logout(
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """
    Invalidate JWT token server-side (add to blocklist).

    Extracts token expiry and JWT ID, adds token to blocklist table to prevent reuse.
    If blocklist operation fails, still returns 204 so frontend can proceed with logout
    (frontend responsibility to clear token from storage per Requirement 3.4).

    Args:
        current_user: Authenticated user (validates JWT via dependency)
        token: HTTPBearer credential with JWT token
        db: Database session

    Returns:
        No content (204 response)

    Raises:
        HTTPException: 401 if token invalid/expired (from get_current_user dependency)
    """
    try:
        # Extract raw token string from HTTPBearer credentials
        token_string = token.credentials

        # Decode token to extract jti and expiry
        payload = decode_token(token_string)
        jti = payload.get("jti")
        exp_timestamp = payload.get("exp")

        if not jti or not exp_timestamp:
            logger.warning(f"Invalid token structure during logout: {current_user.email}")
            # Return 204 anyway - frontend will handle client-side logout
            return

        # Convert Unix timestamp to datetime
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

        # Add token to blocklist (prevents reuse)
        add_to_blocklist(
            jti=jti,
            user_id=str(current_user.id),
            expires_at=expires_at,
            db=db,
        )

        logger.info(f"User logged out successfully: {current_user.email}")

        # Return 204 No Content (no response body)
        return

    except HTTPException:
        # Re-raise HTTP exceptions (401 from get_current_user)
        raise
    except Exception as e:
        # Log error but still return 204 per Requirement 3.4
        # Frontend handles client-side logout regardless of blocklist success
        logger.error(f"Error during logout blocklist operation: {str(e)}")
        return
