"""
Task ORM model for LifeGrid backend.

Defines the Task entity for personal task management.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func

from backend.database import Base


class Task(Base):
    """
    Task model for personal task and to-do management.
    
    Attributes:
        id: UUID primary key
        user_id: Foreign key reference to users table
        title: Task title
        description: Optional task description
        priority: Task priority level (high, medium, low)
        deadline: Optional task deadline
        category: Optional task category
        status: Task status (incomplete, completed)
        completed_at: Timestamp when task was completed
        learning_goal_id: Optional reference to learning goal
        created_at: Task creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "tasks"

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
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(10), nullable=False, default="medium")
    deadline = Column(Date, nullable=True)
    category = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="incomplete")
    completed_at = Column(DateTime(timezone=True), nullable=True)
    learning_goal_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("learning_goals.id", ondelete="SET NULL"),
        nullable=True,
    )
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
        Index("idx_task_user_id", "user_id"),
        Index("idx_task_user_deadline", "user_id", "deadline"),
        Index("idx_task_user_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, user_id={self.user_id}, title={self.title})>"
