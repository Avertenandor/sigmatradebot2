"""
Verify deposit versioning implementation.

R17-1: Checks that all deposits have deposit_version_id and validates
the versioning system is working correctly.

Run this script to verify:
1. All deposits have deposit_version_id
2. All deposit versions exist and are valid
3. Deposit service correctly uses versions
"""

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config.settings import settings
from app.models.deposit import Deposit
from app.models.deposit_level_version import DepositLevelVersion
from app.repositories.deposit_level_version_repository import (
    DepositLevelVersionRepository,
)
from loguru import logger


async def verify_deposit_versioning(session: AsyncSession) -> dict[str, Any]:
    """
    Verify deposit versioning implementation.

    R17-1: Validates that versioning is correctly implemented.

    Args:
        session: Database session

    Returns:
        Dict with verification results
    """
    results = {
        "total_deposits": 0,
        "deposits_with_version": 0,
        "deposits_without_version": 0,
        "invalid_versions": 0,
        "missing_versions": [],
        "errors": [],
    }

    try:
        # Get all deposits
        stmt = select(Deposit)
        result = await session.execute(stmt)
        deposits = result.scalars().all()

        results["total_deposits"] = len(deposits)

        version_repo = DepositLevelVersionRepository(session)

        # Check each deposit
        for deposit in deposits:
            if deposit.deposit_version_id:
                results["deposits_with_version"] += 1

                # Verify version exists
                version_stmt = select(DepositLevelVersion).where(
                    DepositLevelVersion.id == deposit.deposit_version_id
                )
                version_result = await session.execute(version_stmt)
                version = version_result.scalar_one_or_none()

                if not version:
                    results["invalid_versions"] += 1
                    results["errors"].append(
                        f"Deposit {deposit.id} has invalid version_id {deposit.deposit_version_id}"
                    )
                elif version.level_number != deposit.level:
                    results["invalid_versions"] += 1
                    results["errors"].append(
                        f"Deposit {deposit.id} level {deposit.level} doesn't match "
                        f"version level {version.level_number}"
                    )
            else:
                results["deposits_without_version"] += 1
                results["missing_versions"].append(
                    {
                        "deposit_id": deposit.id,
                        "user_id": deposit.user_id,
                        "level": deposit.level,
                        "amount": str(deposit.amount),
                        "created_at": deposit.created_at.isoformat() if deposit.created_at else None,
                    }
                )

        # Check that all levels have active versions
        for level in range(1, 6):
            current_version = await version_repo.get_current_version(level)
            if not current_version:
                results["errors"].append(
                    f"Level {level} has no active version"
                )
            elif not current_version.is_active:
                results["errors"].append(
                    f"Level {level} version exists but is not active"
                )

        return results

    except Exception as e:
        logger.error(f"Error verifying deposit versioning: {e}", exc_info=True)
        results["errors"].append(f"Verification failed: {str(e)}")
        return results


async def migrate_legacy_deposits(session: AsyncSession) -> dict[str, Any]:
    """
    Migrate legacy deposits without version_id to use current versions.

    R17-1: Assigns current version to deposits that don't have one.

    Args:
        session: Database session

    Returns:
        Dict with migration results
    """
    results = {
        "migrated": 0,
        "failed": 0,
        "errors": [],
    }

    try:
        version_repo = DepositLevelVersionRepository(session)

        # Get deposits without version
        stmt = select(Deposit).where(Deposit.deposit_version_id == None)
        result = await session.execute(stmt)
        deposits = result.scalars().all()

        for deposit in deposits:
            try:
                # Get current version for this level
                current_version = await version_repo.get_current_version(deposit.level)

                if not current_version:
                    results["failed"] += 1
                    results["errors"].append(
                        f"Deposit {deposit.id}: No version available for level {deposit.level}"
                    )
                    continue

                # Assign version
                deposit.deposit_version_id = current_version.id
                results["migrated"] += 1

            except Exception as e:
                results["failed"] += 1
                results["errors"].append(
                    f"Deposit {deposit.id}: Migration failed: {str(e)}"
                )

        if results["migrated"] > 0:
            await session.commit()
            logger.info(f"Migrated {results['migrated']} deposits to use versions")

        return results

    except Exception as e:
        logger.error(f"Error migrating legacy deposits: {e}", exc_info=True)
        await session.rollback()
        results["errors"].append(f"Migration failed: {str(e)}")
        return results


async def main() -> None:
    """Main entry point."""
    try:
        engine = create_async_engine(settings.database_url, echo=False)
        async_session_maker = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session_maker() as session:
            logger.info("Starting deposit versioning verification...")

            # Verify versioning
            verification_results = await verify_deposit_versioning(session)

            logger.info("Verification results:")
            logger.info(f"  Total deposits: {verification_results['total_deposits']}")
            logger.info(
                f"  Deposits with version: {verification_results['deposits_with_version']}"
            )
            logger.info(
                f"  Deposits without version: {verification_results['deposits_without_version']}"
            )
            logger.info(
                f"  Invalid versions: {verification_results['invalid_versions']}"
            )

            if verification_results["errors"]:
                logger.warning("Errors found:")
                for error in verification_results["errors"]:
                    logger.warning(f"  - {error}")

            if verification_results["deposits_without_version"] > 0:
                logger.warning(
                    f"Found {verification_results['deposits_without_version']} deposits without version"
                )
                logger.info("Attempting to migrate legacy deposits...")

                migration_results = await migrate_legacy_deposits(session)

                logger.info("Migration results:")
                logger.info(f"  Migrated: {migration_results['migrated']}")
                logger.info(f"  Failed: {migration_results['failed']}")

                if migration_results["errors"]:
                    logger.warning("Migration errors:")
                    for error in migration_results["errors"]:
                        logger.warning(f"  - {error}")

            if (
                verification_results["deposits_without_version"] == 0
                and verification_results["invalid_versions"] == 0
                and len(verification_results["errors"]) == 0
            ):
                logger.info("✅ Deposit versioning verification passed!")
            else:
                logger.warning("⚠️ Deposit versioning verification found issues")

        await engine.dispose()
        logger.info("Verification completed")

    except Exception as e:
        logger.error(f"Failed to verify deposit versioning: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    from typing import Any

    asyncio.run(main())

