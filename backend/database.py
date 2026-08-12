"""
SQLAlchemy database configuration and session management for LifeGrid backend.

Exports:
    - engine: SQLAlchemy Engine connected to the PostgreSQL database
    - SessionLocal: SQLAlchemy sessionmaker factory for creating database sessions
    - Base: SQLAlchemy declarative base for ORM model definitions
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import settings

# Create the SQLAlchemy engine using the DATABASE_URL from environment
engine = create_engine(
    settings.DATABASE_URL,
    # echo=True enables logging of all SQL statements (disable in production)
    echo=False,
)

# Create a session factory for creating new database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Declarative base for all ORM model definitions
Base = declarative_base()
