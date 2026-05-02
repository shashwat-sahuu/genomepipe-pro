"""Database connection and session management"""
import logging
from typing import Optional, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, pool, Pool, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.models.database import Base

logger = logging.getLogger(__name__)
settings = get_settings()


class DatabaseManager:
    """Manages database connections and sessions"""

    _engine = None
    _session_local = None

    @classmethod
    def init_db(cls):
        """Initialize database engine and session factory"""
        try:
            cls._engine = create_engine(
                settings.DATABASE_URL,
                poolclass=pool.QueuePool,
                pool_size=20,
                max_overflow=40,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=settings.DB_ECHO,
                connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
            )

            # Add event listeners for connection pool
            @event.listens_for(Pool, "connect")
            def receive_connect(dbapi_conn, connection_record):
                """Configure connection on creation"""
                if "sqlite" not in settings.DATABASE_URL:
                    # Enable query logging for PostgreSQL
                    cursor = dbapi_conn.cursor()
                    cursor.execute("SET statement_timeout = '30s'")
                    cursor.close()

            cls._session_local = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=cls._engine
            )

            logger.info("Database engine initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    @classmethod
    def create_tables(cls):
        """Create all database tables"""
        if cls._engine is None:
            cls.init_db()

        try:
            Base.metadata.create_all(bind=cls._engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    @classmethod
    def get_session(cls) -> Session:
        """Get a new database session"""
        if cls._session_local is None:
            cls.init_db()

        return cls._session_local()

    @classmethod
    @contextmanager
    def get_session_context(cls) -> Generator[Session, None, None]:
        """Context manager for database sessions"""
        session = cls.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    @classmethod
    def close(cls):
        """Close all connections"""
        if cls._engine:
            cls._engine.dispose()
            logger.info("Database connections closed")

    @classmethod
    def health_check(cls) -> bool:
        """Check database connectivity"""
        try:
            session = cls.get_session()
            session.execute(text("SELECT 1"))
            session.close()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# FastAPI dependency for getting session
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: get database session"""
    db = DatabaseManager.get_session()
    try:
        yield db
    finally:
        db.close()


# Initialize database on module load
try:
    DatabaseManager.init_db()
except Exception as e:
    logger.error(f"Failed to initialize database on module load: {e}")
