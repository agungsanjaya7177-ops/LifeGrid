"""
User ORM model for LifeGrid backend.

Defines the User entity with authentication and rate limiting fields.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func

from backend.database import Base


class User(Base):
    """
    User model for authentication and account management.
    
    Attributes:
        id: UUID primary key
        email: User email (unique, required)
        password_hash: Bcrypt hashed password
        failed_attempts: Counter for login rate limiting
        locked_until: Timestamp when login lockout expires
        created_at: Account creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "users"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    email = Column(String(254), nullable=False, unique=True, index=True)
    password_hash = Column(String(128), nullable=False)
    failed_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
