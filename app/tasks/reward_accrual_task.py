"""
Reward accrual task.

Automatic individual reward calculation for deposits.
Runs periodically to process deposits that are due for accrual.
"""

from __future__ import annotations

from datetime import UTC, datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import async_session_maker
from app.services.reward_service import RewardService
from app.services.roi_corridor_service import RoiCorridorService


async def run_individual_reward_accrual() -> None:
    """
    Run individual reward accrual for all due deposits.

    This task:
    1. Checks for 'next' session settings and applies them if needed
    2. Processes all deposits where next_accrual_at <= now
    3. Calculates rewards based on corridor settings
    4. Updates deposit ROI tracking
    5. Sends notifications for completed ROI cycles
    """
    logger.info("Starting individual reward accrual task")

    try:
        async with async_session_maker() as session:
            try:
                corridor_service = RoiCorridorService(session)
                reward_service = RewardService(session)

                # Apply 'next' session settings if any exist
                await corridor_service.apply_next_session_settings()

                # Calculate individual rewards for due deposits
                await reward_service.calculate_individual_rewards()

                logger.info("Individual reward accrual completed successfully")

            except Exception as e:
                logger.error(
                    f"Error in reward accrual: {e}",
                    extra={"error": str(e)},
                )
                await session.rollback()
                raise

    except Exception as e:
        logger.error(
            f"Fatal error in reward accrual task: {e}",
            extra={"error": str(e)},
        )

