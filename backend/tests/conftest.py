"""
Pytest configuration and fixtures for LifeGrid backend tests.

Provides shared fixtures for database setup, test data, and other test utilities.
"""

import uuid as uuid_module
from datetime import datetime, timezone
from sqlalchemy import create_engine, event, String, TypeDecorator
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import pytest

from backend.database import Base


@pytest.fixture(scope="function")
def db() -> Session:
    """
    Provide a fresh database session for each test.

    Creates an in-memory SQLite database, creates all tables, 
    yields a session, and then cleans up after the test.

    Yields:
        Session: SQLAlchemy database session bound to test database
    """
    # Use in-memory SQLite for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        """Enable foreign key support in SQLite."""
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
        
        # Create a custom gen_random_uuid function for SQLite
        def gen_random_uuid():
            return str(uuid_module.uuid4())
        
        dbapi_conn.create_function("gen_random_uuid", 0, gen_random_uuid)
        
        # Create a now function for SQLite that returns timezone-aware ISO format
        def now():
            return datetime.now(timezone.utc).isoformat()
        
        dbapi_conn.create_function("now", 0, now)

    # Before creating tables, patch the column types
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    
    def compile_uuid(self, type_, **kw):
        """Compile UUID type as VARCHAR for SQLite."""
        return "VARCHAR"
    
    # Replace the UUID compiler for SQLite
    from sqlalchemy.dialects.sqlite import base as sqlite_base
    original_visit_uuid = getattr(sqlite_base.SQLiteTypeCompiler, 'visit_UUID', None)
    sqlite_base.SQLiteTypeCompiler.visit_UUID = compile_uuid

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session factory
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSessionLocal()

    yield session

    # Cleanup
    session.close()
    Base.metadata.drop_all(bind=engine)
    
    # Restore original compiler
    if original_visit_uuid:
        sqlite_base.SQLiteTypeCompiler.visit_UUID = original_visit_uuid
    else:
        if hasattr(sqlite_base.SQLiteTypeCompiler, 'visit_UUID'):
            delattr(sqlite_base.SQLiteTypeCompiler, 'visit_UUID')

