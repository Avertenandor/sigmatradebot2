"""
Daily rewards task.

Processes daily reward sessions for all confirmed deposits.
Runs once per day to calculate and distribute rewards.
"""

import asyncio
from datetime import datetime, timedelta

import dramatiq
from loguru import logger

from app.config.database import async_session_maker
from app.services.reward_service import RewardService


@dramatiq.actor(max_retries=3, time_limit=600_000)  # 10 min timeout
def process_daily_rewards(session_id: int | None = None) -> dict:
    """
    Process daily rewards for active session.

    Calculates rewards for all eligible deposits based on reward session
    configuration. Respects ROI cap (500% for level 1) and earnings_blocked
    flag.

    Args:
        session_id: Specific session ID to process (optional)

    Returns:
        Dict with success, rewards_calculated, total_amount
    """
    logger.info(
        f"Starting daily rewards processing"
        f"{f' for session {session_id}' if session_id else ''}..."
    )

    try:
        # Run async code
        result = asyncio.run(
            _process_daily_rewards_async(session_id)
        )

        if result["success"]:
            logger.info(
                f"Daily rewards processing complete: "
                f"{result['rewards_calculated']} rewards calculated, "
                f"total: {result['total_amount']} USDT"
            )
        else:
            logger.error(
                f"Daily rewards processing failed: {result.get('error')}"
            )

        return result

    except Exception as e:
        logger.exception(f"Daily rewards processing failed: {e}")
        return {
            "success": False,
            "rewards_calculated": 0,
            "total_amount": 0,
            "error": str(e),
        }


async def _process_daily_rewards_async(
    session_id: int | None,
) -> dict:
    """Async implementation of daily rewards processing."""
    async with async_session_maker() as session:
        reward_service = RewardService(session)

        # If session_id provided, process that session
        if session_id:
            success, calculated, total, error = (
                await reward_service.calculate_rewards_for_session(
                    session_id
                )
            )

            return {
                "success": success,
                "rewards_calculated": calculated,
                "total_amount": float(total),
                "error": error,
            }

        # Otherwise, process all active sessions
        active_sessions = await reward_service.get_active_sessions()

        if not active_sessions:
            logger.info("No active reward sessions found")
            return {
                "success": True,
                "rewards_calculated": 0,
                "total_amount": 0,
            }

        total_calculated = 0
        total_amount_sum = 0.0

        for session_obj in active_sessions:
            success, calculated, total, error = (
                await reward_service.calculate_rewards_for_session(
                    session_obj.id
                )
            )

            if success:
                total_calculated += calculated
                total_amount_sum += float(total)
            else:
                logger.error(
                    f"Failed to process session {session_obj.id}: {error}"
                )

        return {
            "success": True,
            "rewards_calculated": total_calculated,
            "total_amount": total_amount_sum,
        }
