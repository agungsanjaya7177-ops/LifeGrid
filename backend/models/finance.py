"""
Finance ORM models for LifeGrid backend.

Defines Transaction and MonthlyBudget entities for financial management.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func

from backend.database import Base


class Transaction(Base):
    """
    Transaction model for income and expense tracking.
    
    Attributes:
        id: UUID primary key
        user_id: Foreign key reference to users table
        amount: Transaction amount (must be > 0)
        type: Transaction type (income or expense)
        category: Transaction category
        transaction_date: Date of transaction
        description: Optional transaction description
        created_at: Transaction creation timestamp
    """

    __tablename__ = "transactions"

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
    amount = Column(Numeric(16, 2), nullable=False)
    type = Column(String(10), nullable=False)  # income or expense
    category = Column(String(100), nullable=False)
    transaction_date = Column(Date, nullable=False)
    description = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transaction_amount_positive"),
        Index("idx_transaction_user_id", "user_id"),
        Index("idx_transaction_user_date", "user_id", "transaction_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, user_id={self.user_id}, "
            f"type={self.type}, amount={self.amount})>"
        )


class MonthlyBudget(Base):
    """
    MonthlyBudget model for monthly budget management.
    
    Attributes:
        id: UUID primary key
        user_id: Foreign key reference to users table
        amount: Budget amount in integer IDR (must be > 0)
        budget_year: Budget year
        budget_month: Budget month (1-12)
        created_at: Budget creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "monthly_budgets"

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
    amount = Column(Numeric(14, 0), nullable=False)
    budget_year = Column(Integer, nullable=False)
    budget_month = Column(Integer, nullable=False)
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
        CheckConstraint("amount > 0", name="ck_monthly_budget_amount_positive"),
        CheckConstraint(
            "budget_month >= 1 AND budget_month <= 12",
            name="ck_monthly_budget_month_range",
        ),
        UniqueConstraint(
            "user_id",
            "budget_year",
            "budget_month",
            name="uq_monthly_budget_user_month",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<MonthlyBudget(id={self.id}, user_id={self.user_id}, "
            f"year={self.budget_year}, month={self.budget_month})>"
        )
