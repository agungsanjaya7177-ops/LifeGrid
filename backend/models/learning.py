"""
Learning ORM model for LifeGrid backend.

Defines the LearningGoal entity for learning and skill development tracking.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func

from backend.database import Base


class LearningGoal(Base):
    """
    LearningGoal model for tracking learning and skill development goals.
    
    Attributes:
        id: UUID primary key
        user_id: Foreign key reference to users table
        title: Goal title
        progress_pct: Progress percentage (0-100)
        target_date: Target completion date
        created_at: Goal creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "learning_goals"

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
    title = Column(String(200), nullable=False)
    progress_pct = Column(Integer, nullable=False, default=0)
    target_date = Column(Date, nullable=False)
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

    __table_args__ = (
        CheckConstraint(
            "progress_pct >= 0 AND progress_pct <= 100",
            name="ck_learning_goal_progress_range",
        ),
        Index("idx_learning_goal_user_id", "user_id"),
        Index("idx_learning_goal_user_progress", "user_id", "progress_pct"),
    )

    def __repr__(self) -> str:
        return (
            f"<LearningGoal(id={self.id}, user_id={self.user_id}, "
            f"title={self.title}, progress={self.progress_pct}%)>"
        )
