"""
Initialize deposit level versions.

R17-1, R17-2: Creates initial deposit level versions for levels 1-5.

Run this script after migration to populate initial versions.
"""

import asyncio
from decimal import Decimal
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config.settings import settings
from app.models.deposit_level_version import DepositLevelVersion
from app.repositories.deposit_level_version_repository import (
    DepositLevelVersionRepository,
)
from loguru import logger


# Default deposit conditions (can be adjusted)
DEFAULT_CONDITIONS = {
    1: {
        "amount": Decimal("10.00"),
        "roi_percent": Decimal("2.00"),  # 2% daily
        "roi_cap_percent": 500,  # 500% cap
    },
    2: {
        "amount": Decimal("50.00"),
        "roi_percent": Decimal("2.50"),  # 2.5% daily
        "roi_cap_percent": 500,
    },
    3: {
        "amount": Decimal("100.00"),
        "roi_percent": Decimal("3.00"),  # 3% daily
        "roi_cap_percent": 500,
    },
    4: {
        "amount": Decimal("500.00"),
        "roi_percent": Decimal("3.50"),  # 3.5% daily
        "roi_cap_percent": 500,
    },
    5: {
        "amount": Decimal("1000.00"),
        "roi_percent": Decimal("4.00"),  # 4% daily
        "roi_cap_percent": 500,
    },
}


async def init_deposit_versions(session: AsyncSession) -> None:
    """
    Initialize deposit level versions.

    Args:
        session: Database session
    """
    version_repo = DepositLevelVersionRepository(session)

    for level in range(1, 6):
        # Check if version already exists
        existing = await version_repo.get_current_version(level)
        if existing:
            logger.info(
                f"Level {level} version already exists (version {existing.version}), skipping"
            )
            continue

        # Get default conditions
        conditions = DEFAULT_CONDITIONS[level]

        # Create initial version
        version = await version_repo.create(
            level_number=level,
            amount=conditions["amount"],
            roi_percent=conditions["roi_percent"],
            roi_cap_percent=conditions["roi_cap_percent"],
            version=1,
            effective_from=datetime.now(UTC),
            is_active=True,
            created_by_admin_id=None,  # System initialization
        )

        logger.info(
            f"Created initial version for level {level}: "
            f"amount={conditions['amount']}, "
            f"roi={conditions['roi_percent']}%, "
            f"cap={conditions['roi_cap_percent']}%"
        )

    await session.commit()
    logger.info("Deposit level versions initialized successfully")


async def main() -> None:
    """Main entry point."""
    try:
        engine = create_async_engine(settings.database_url, echo=False)
        async_session_maker = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session_maker() as session:
            await init_deposit_versions(session)

        await engine.dispose()
        logger.info("Initialization completed")

    except Exception as e:
        logger.error(f"Failed to initialize deposit versions: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())

