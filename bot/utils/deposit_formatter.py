"""
Deposit formatter utilities.

Formats deposit information with corridor and ROI details for users.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.deposit import Deposit
from app.models.deposit_reward import DepositReward


async def format_deposit_with_corridor(
    deposit: Deposit,
    corridor_config: dict,
    recent_rewards: list[DepositReward],
) -> str:
    """
    Format deposit information with corridor details and history.

    Args:
        deposit: Deposit object
        corridor_config: Corridor configuration dict
        recent_rewards: List of recent rewards

    Returns:
        Formatted text for user display
    """
    # ROI progress
    roi_paid = deposit.roi_paid_amount or Decimal("0")
    roi_cap = deposit.roi_cap_amount or Decimal("0")
    roi_progress_pct = (
        (roi_paid / roi_cap * 100) if roi_cap > 0 else Decimal("0")
    )

    # Corridor info
    mode = corridor_config["mode"]
    if mode == "custom":
        corridor_text = (
            f"📊 **Коридор дневного ROI:** "
            f"{corridor_config['roi_min']}% - {corridor_config['roi_max']}%"
        )
    else:
        corridor_text = (
            f"📊 **Фиксированный ROI:** {corridor_config['roi_fixed']}%"
        )

    # Current rate (from last reward)
    current_rate_text = ""
    if recent_rewards:
        last_reward = recent_rewards[0]
        if last_reward.actual_rate:
            current_rate_text = (
                f"📈 **Ваш текущий процент:** {last_reward.actual_rate}%\n"
            )

    # History
    history_text = ""
    if recent_rewards:
        history_text = "\n\n📜 **История начислений (последние 5):**\n"
        for reward in recent_rewards[:5]:
            date_str = reward.created_at.strftime("%d.%m.%Y")
            rate_str = (
                f"{reward.actual_rate}%"
                if reward.actual_rate
                else f"{reward.reward_rate}%"
            )
            history_text += (
                f"• {date_str}: +{reward.reward_amount:.2f} USDT ({rate_str})\n"
            )

    text = (
        f"💰 **Депозит #{deposit.id}**\n\n"
        f"💵 **Сумма депозита:** {deposit.amount:.2f} USDT\n"
        f"🎯 **Уровень:** {deposit.level}\n\n"
        f"{corridor_text}\n"
        f"{current_rate_text}\n"
        f"💸 **Всего заработано:** {roi_paid:.2f} USDT\n"
        f"📊 **ROI прогресс:** {roi_progress_pct:.2f}% / 500%\n"
        f"🎯 **Лимит ROI:** {roi_cap:.2f} USDT"
        f"{history_text}"
    )

    return text

