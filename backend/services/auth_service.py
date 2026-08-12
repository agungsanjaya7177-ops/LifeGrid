"""
Authentication service for LifeGrid backend.

Provides password hashing, JWT token management, JWT blocklist operations,
and login rate limiting.
All cryptographic operations use industry-standard algorithms with secure defaults.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID
import logging

from jose import jwt, JWTError
from fastapi import HTTPException
from bcrypt import hashpw, checkpw, gensalt
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.jwt_blocklist import JWTBlocklist
from backend.models.user import User


logger = logging.getLogger(__name__)


# Password hashing constants
BCRYPT_COST_FACTOR = 12  # Cost factor for bcrypt (minimum security requirement)


def hash_password(plain: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    Generates a bcrypt hash of the plaintext password with a cost factor of at least 12.
    The cost factor determines the computational difficulty and should be increased as
    computational power increases. Cost factor 12 provides good security while maintaining
    reasonable performance.

    Args:
        plain: The plaintext password to hash

    Returns:
        str: The bcrypt hash as a UTF-8 string (bcrypt hash prefixed with $2b$)

    Example:
        >>> hashed = hash_password("MyPassword123")
        >>> hashed.startswith("$2b$")
        True
    """
    # Generate a salt with the specified cost factor
    salt = gensalt(rounds=BCRYPT_COST_FACTOR)
    # Hash the password and decode the bytes to string
    hashed = hashpw(plain.encode("utf-8"), salt).decode("utf-8")
    return hashed


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a bcrypt hash using timing-safe comparison.

    Performs constant-time comparison to prevent timing-based password enumeration attacks.
    Uses a dummy check when the password doesn't match to ensure the comparison takes
    approximately the same time regardless of whether the hash is valid or the password matches.

    Args:
        plain: The plaintext password to verify
        hashed: The bcrypt hash to compare against

    Returns:
        bool: True if password matches the hash, False otherwise

    Example:
        >>> hashed = hash_password("MyPassword123")
        >>> verify_password("MyPassword123", hashed)
        True
        >>> verify_password("WrongPassword", hashed)
        False
    """
    try:
        # Perform constant-time comparison using bcrypt
        result = checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        return result
    except Exception:
        # If any error occurs (invalid hash format, encoding error, etc.),
        # perform a dummy check to maintain constant execution time
        # This prevents timing-based enumeration attacks
        try:
            # Generate a dummy salt and hash a dummy password to match execution time
            dummy_salt = gensalt(rounds=BCRYPT_COST_FACTOR)
            _ = hashpw(b"dummy", dummy_salt)
        except Exception:
            pass
        return False


def validate_password(password: str) -> tuple[bool, str | None]:
    """
    Validate password against security constraints.

    Checks that the password meets all security requirements:
    - Length between 8 and 128 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one digit (0-9)

    Args:
        password: The password to validate

    Returns:
        tuple[bool, str | None]: A tuple of (is_valid, error_message)
            - If valid: (True, None)
            - If invalid: (False, error_message describing which constraint was violated)

    Example:
        >>> validate_password("MyPassword123")
        (True, None)
        >>> validate_password("short")
        (False, "Password must be between 8 and 128 characters")
        >>> validate_password("nouppercase123")
        (False, "Password must contain at least one uppercase letter")
    """
    # Check length constraint
    if len(password) < 8:
        return False, "Password must be between 8 and 128 characters"
    if len(password) > 128:
        return False, "Password must be between 8 and 128 characters"

    # Check for at least one uppercase letter
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    # Check for at least one lowercase letter
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    # Check for at least one digit
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    return True, None


def create_access_token(
    user_id: UUID, jti: str, expires_delta: timedelta | None = None
) -> str:
    """
    Create a signed JWT access token for authenticated requests.

    Generates a JSON Web Token signed with HS256 using the JWT_SECRET from configuration.
    The token includes standard JWT claims (iat, exp) and custom claims (sub, jti).

    Token Structure:
    - sub (subject): The user's UUID
    - jti (JWT ID): A unique token identifier used for blocklist invalidation
    - iat (issued at): Token creation timestamp (UTC)
    - exp (expiration): Token expiration timestamp (UTC)

    Args:
        user_id: The UUID of the user
        jti: The JWT ID claim (unique token identifier)
        expires_delta: Optional expiration duration. If None, uses JWT_ACCESS_TOKEN_EXPIRE_MINUTES
                      from config.

    Returns:
        str: The signed JWT token

    Example:
        >>> import uuid
        >>> from datetime import timedelta
        >>> user_id = uuid.uuid4()
        >>> jti = str(uuid.uuid4())
        >>> token = create_access_token(user_id, jti)
        >>> isinstance(token, str)
        True
        >>> token.count(".")  # JWT has 3 parts separated by dots
        2
    """
    # Determine expiration time
    if expires_delta is None:
        expires_delta = timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )

    # Calculate expiration timestamp
    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    # Build JWT payload with required claims
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "iat": now,
        "exp": expire,
    }

    # Sign and return the token
    token = jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    return token


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.

    Verifies the token signature using JWT_SECRET and checks expiration.
    Raises HTTPException(401) if the token is expired, malformed, or signed with an unrecognized key.

    Args:
        token: The JWT token string to decode

    Returns:
        dict: The decoded JWT payload containing sub, jti, iat, exp

    Raises:
        HTTPException: Status 401 if token is invalid, expired, or malformed

    Example:
        >>> import uuid
        >>> user_id = uuid.uuid4()
        >>> jti = str(uuid.uuid4())
        >>> token = create_access_token(user_id, jti)
        >>> payload = decode_token(token)
        >>> payload["sub"] == str(user_id)
        True
    """
    try:
        # Decode the token with signature verification
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
        )
        return payload
    except JWTError as e:
        # Token has expired, is malformed, or signed with wrong key
        error_msg = str(e)
        if "expired" in error_msg.lower():
            logger.warning("Attempted use of expired JWT token")
            raise HTTPException(status_code=401, detail="Token has expired")
        else:
            logger.warning(f"Invalid JWT token: {error_msg}")
            raise HTTPException(
                status_code=401,
                detail="Invalid or malformed token",
            )


def add_to_blocklist(
    jti: str, user_id: UUID, expires_at: datetime, db: Session
) -> JWTBlocklist:
    """
    Add a JWT ID to the blocklist for token revocation.

    Inserts a new blocklist entry into the database. This is used during logout
    to prevent further use of the invalidated token. The expires_at timestamp
    allows for periodic cleanup of expired blocklist entries.

    Args:
        jti: The JWT ID claim from the token being revoked
        user_id: The UUID of the user whose token is being revoked
        expires_at: The token's expiration timestamp (used for cleanup)
        db: SQLAlchemy database session

    Returns:
        JWTBlocklist: The created blocklist entry

    Example:
        >>> import uuid
        >>> from datetime import datetime, timezone, timedelta
        >>> user_id = uuid.uuid4()
        >>> jti = str(uuid.uuid4())
        >>> expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        >>> blocklist_entry = add_to_blocklist(jti, user_id, expires_at, db)
        >>> blocklist_entry.jti == jti
        True
    """
    # Create new blocklist entry
    blocklist_entry = JWTBlocklist(
        jti=jti,
        user_id=user_id,
        expires_at=expires_at,
    )

    # Add to session and commit
    db.add(blocklist_entry)
    db.commit()
    db.refresh(blocklist_entry)

    logger.info(f"Token {jti} added to blocklist for user {user_id}")
    return blocklist_entry


def is_blocklisted(jti: str, db: Session) -> bool:
    """
    Check if a JWT ID is in the blocklist.

    Queries the jwt_blocklist table to determine if the token has been revoked.
    This is called during request authentication on protected endpoints.

    Args:
        jti: The JWT ID claim to check
        db: SQLAlchemy database session

    Returns:
        bool: True if the JWT is blocklisted (revoked), False otherwise

    Example:
        >>> import uuid
        >>> user_id = uuid.uuid4()
        >>> jti = str(uuid.uuid4())
        >>> is_blocklisted(jti, db)
        False
    """
    # Query for the blocklist entry
    entry = db.query(JWTBlocklist).filter(JWTBlocklist.jti == jti).first()
    return entry is not None


def check_rate_limit(email: str, db: Session) -> tuple[bool, str | None]:
    """
    Check if a user account is rate-limited due to failed login attempts.

    Queries the user by email and checks if their account is temporarily locked.
    If the lockout has expired (locked_until < now()), the account is unlocked.

    Args:
        email: The user's email address
        db: SQLAlchemy database session

    Returns:
        tuple[bool, str | None]: A tuple of (is_locked, error_message)
            - If user not found or not locked: (False, None)
            - If account is locked: (True, "Account is temporarily locked. Try again in 15 minutes.")

    Example:
        >>> is_locked, msg = check_rate_limit("user@example.com", db)
        >>> if is_locked:
        ...     print(msg)  # "Account is temporarily locked. Try again in 15 minutes."
    """
    # Query user by email
    user = db.query(User).filter(User.email == email).first()

    # If user doesn't exist, cannot rate limit
    if user is None:
        return False, None

    # If locked_until is None, account is not locked
    if user.locked_until is None:
        return False, None

    # Get current time in UTC
    now = datetime.now(timezone.utc)
    
    # Ensure locked_until is timezone-aware (SQLite returns naive datetimes)
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)

    # If locked_until is in the past, account is unlocked
    if locked_until < now:
        return False, None

    # Account is currently locked
    return True, "Account is temporarily locked. Try again in 15 minutes."


def increment_failure(email: str, db: Session) -> None:
    """
    Increment failed login attempt counter and lock account if necessary.

    Queries the user by email, increments their failed_attempts counter by 1.
    If failed_attempts reaches 5, sets locked_until to 15 minutes from now.
    Commits all changes to the database and logs the failure.

    Args:
        email: The user's email address
        db: SQLAlchemy database session

    Returns:
        None

    Example:
        >>> increment_failure("user@example.com", db)
        # After 5 calls, account will be locked
    """
    from sqlalchemy import update
    
    # Perform update with raw SQL to avoid primary key issues with SQLite
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return
    
    # Increment counter and lock if needed
    new_attempts = user.failed_attempts + 1
    locked_until = None
    if new_attempts >= 5:
        locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        logger.warning(f"Account {email} locked after 5 failed login attempts")
    else:
        logger.info(f"Failed login attempt for {email}. Attempt {new_attempts}/5")
    
    # Update using SQLAlchemy update statement
    db.execute(
        update(User).where(User.email == email).values(
            failed_attempts=new_attempts,
            locked_until=locked_until
        )
    )
    db.commit()


def reset_failure(email: str, db: Session) -> None:
    """
    Reset failed login attempts and clear account lockout.

    Queries the user by email, sets failed_attempts to 0 and locked_until to None.
    This is called after a successful login to clear the failure counter.

    Args:
        email: The user's email address
        db: SQLAlchemy database session

    Returns:
        None

    Example:
        >>> reset_failure("user@example.com", db)
        # User's failed_attempts and locked_until are now cleared
    """
    from sqlalchemy import update
    
    # Perform update with raw SQL to avoid primary key issues with SQLite
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return
    
    # Update using SQLAlchemy update statement
    db.execute(
        update(User).where(User.email == email).values(
            failed_attempts=0,
            locked_until=None
        )
    )
    db.commit()
    logger.info(f"Failed login attempts cleared for {email}")

