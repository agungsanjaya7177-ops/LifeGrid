"""
Security ORM model for LifeGrid backend.

Defines the SecurityChecklistItem entity for security best practices tracking.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func

from backend.database import Base


class SecurityChecklistItem(Base):
    """
    SecurityChecklistItem model for tracking security best practices checklist.
    
    Attributes:
        id: UUID primary key
        user_id: Foreign key reference to users table
        item_order: Order of checklist item (1-5)
        item_label: Label for checklist item
        is_checked: Whether item is completed
        updated_at: Last update timestamp
    """

    __tablename__ = "security_checklist_items"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_order = Column(Integer, nullable=False)
    item_label = Column(String(200), nullable=False)
    is_checked = Column(Boolean, nullable=False, default=False)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "item_order",
            name="uq_security_checklist_user_order",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SecurityChecklistItem(id={self.id}, user_id={self.user_id}, "
            f"order={self.item_order}, checked={self.is_checked})>"
        )
