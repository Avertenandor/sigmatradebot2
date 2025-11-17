"""
Database configuration.

Provides async SQLAlchemy engine and session factory.
"""

from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import settings

# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=5,  # Reduced from 20 to prevent connection exhaustion
    max_overflow=10,  # Reduced from 40
    pool_pre_ping=True,
    pool_recycle=300,  # Recycle connections every 5 minutes (was 3600)
    pool_timeout=30,  # Wait max 30 seconds for connection
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get async database session.

    Yields:
        AsyncSession: Database session
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database (create tables if needed)."""

    async with engine.begin():
        # For production, use Alembic migrations instead
        # await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized")


async def close_db() -> None:
    """Close database connection."""
    await engine.dispose()
    logger.info("Database connection closed")
