"""
JWT Blocklist ORM model for LifeGrid backend.

Defines the JWTBlocklist entity for token revocation management.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func

from backend.database import Base


class JWTBlocklist(Base):
    """
    JWT Blocklist model for token revocation and logout functionality.
    
    Attributes:
        id: UUID primary key
        jti: JWT ID claim (unique)
        user_id: Foreign key reference to users table
        expires_at: Token expiration timestamp (for cleanup)
        created_at: Blocklist entry creation timestamp
    """

    __tablename__ = "jwt_blocklist"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    jti = Column(String(36), nullable=False, unique=True, index=True)
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_jwt_blocklist_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<JWTBlocklist(id={self.id}, user_id={self.user_id})>"
