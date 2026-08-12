"""
Fitness ORM model for LifeGrid backend.

Defines the WorkoutSession entity for fitness and workout tracking.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func

from backend.database import Base


class WorkoutSession(Base):
    """
    WorkoutSession model for tracking fitness and workout sessions.
    
    Attributes:
        id: UUID primary key
        user_id: Foreign key reference to users table
        workout_type: Type of workout
        duration_minutes: Workout duration in minutes (1-1440)
        session_date: Date of workout session
        notes: Optional workout notes
        created_at: Session creation timestamp
    """

    __tablename__ = "workout_sessions"

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
    workout_type = Column(String(100), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    session_date = Column(Date, nullable=False)
    notes = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "duration_minutes >= 1 AND duration_minutes <= 1440",
            name="ck_workout_session_duration_range",
        ),
        Index("idx_workout_session_user_id", "user_id"),
        Index("idx_workout_session_user_date", "user_id", "session_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<WorkoutSession(id={self.id}, user_id={self.user_id}, "
            f"type={self.workout_type}, duration={self.duration_minutes} min)>"
        )
