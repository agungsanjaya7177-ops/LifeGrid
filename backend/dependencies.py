"""
Shared FastAPI dependencies for LifeGrid backend.

This module provides reusable dependency functions used across all routers,
such as database session injection and user authentication.

Exports:
    - get_db: FastAPI dependency that yields a SQLAlchemy session
    - oauth2_scheme: HTTPBearer instance for Bearer token extraction
    - get_current_user: FastAPI dependency for user authentication
"""

from typing import Generator

from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

from backend.database import SessionLocal
from backend.models.user import User
from backend.services.auth_service import decode_token, is_blocklisted


# HTTPBearer instance for extracting Bearer tokens from Authorization header
oauth2_scheme = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session for the request lifetime.

    The session is automatically closed after the request completes, regardless
    of success or failure. This dependency is declared in route handlers as:

        def some_route(db: Session = Depends(get_db)):
            ...

    Yields:
        Session: A SQLAlchemy database session bound to the application's engine

    Example:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency that validates JWT tokens and returns authenticated user.

    Extracts the Bearer token from the Authorization header, validates the JWT signature
    and expiry, checks if the token is blocklisted (revoked), and returns the authenticated
    user object. All failures result in 401 Unauthorized responses.

    The dependency is used in route handlers as:

        def protected_route(current_user: User = Depends(get_current_user)):
            ...

    Token Validation Flow:
    1. Extract token from Authorization header via HTTPBearer
    2. Call decode_token(token) to validate JWT signature and expiry
    3. Extract user_id from payload["sub"]
    4. Check if token is blocklisted (revoked)
    5. Query User by user_id
    6. Return the User object

    Args:
        token: HTTPBearer credential containing the JWT token
        db: SQLAlchemy database session

    Returns:
        User: The authenticated user object

    Raises:
        HTTPException: Status 401 Unauthorized if:
            - Token is missing or malformed
            - Token signature is invalid
            - Token has expired
            - Token is blocklisted (revoked)
            - User not found in database

    Example:
        @router.get("/profile")
        def get_profile(current_user: User = Depends(get_current_user)):
            return {"email": current_user.email}
    """
    # Extract token string from HTTPBearer credentials
    token_string = token.credentials

    # Decode and validate JWT token
    # This will raise HTTPException(401) if token is invalid or expired
    payload = decode_token(token_string)

    # Extract user_id from the "sub" (subject) claim
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=401,
            detail="Invalid token: missing user identifier",
        )

    # Extract jti (JWT ID) from the payload
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(
            status_code=401,
            detail="Invalid token: missing JWT ID",
        )

    # Check if token is blocklisted (revoked)
    if is_blocklisted(jti, db):
        raise HTTPException(
            status_code=401,
            detail="Token has been revoked",
        )

    # Query the user by user_id
    user = db.query(User).filter(User.id == user_id_str).first()

    # Verify user exists
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    return user
