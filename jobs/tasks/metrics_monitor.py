"""
Metrics Monitor Task (R14-1).

Monitors financial metrics and detects anomalies.
Runs every 5 minutes.
"""

import asyncio

import dramatiq
from aiogram import Bot
from loguru import logger

from app.config.database import async_session_maker
from app.config.settings import settings
from typing import Any

from app.services.metrics_monitor_service import MetricsMonitorService
from app.services.notification_service import NotificationService


@dramatiq.actor(max_retries=3, time_limit=120_000)  # 2 min timeout
def monitor_metrics() -> None:
    """
    Monitor financial metrics and detect anomalies (R14-1).
    """
    logger.debug("Starting metrics monitoring...")

    try:
        asyncio.run(_monitor_metrics_async())

    except Exception as e:
        logger.exception(f"Metrics monitoring failed: {e}")


async def _monitor_metrics_async() -> dict:
    """Async implementation of metrics monitoring."""
    async with async_session_maker() as session:
        metrics_service = MetricsMonitorService(session)

        # Collect current metrics
        current_metrics = await metrics_service.collect_current_metrics()

        # Detect anomalies
        anomalies = await metrics_service.detect_anomalies(current_metrics)

        if anomalies:
            logger.warning(
                f"Detected {len(anomalies)} anomalies",
                extra={"anomalies": anomalies},
            )

            # Send alerts for each anomaly
            await _send_anomaly_alerts(anomalies, current_metrics)

            # Take protective actions for critical anomalies
            critical_anomalies = [
                a
                for a in anomalies
                if a.get("severity") == "critical"
            ]
            if critical_anomalies:
                await _take_protective_actions(critical_anomalies)

        return {
            "success": True,
            "metrics": current_metrics,
            "anomalies_detected": len(anomalies),
            "anomalies": anomalies,
        }


# Переводы типов аномалий
ANOMALY_TRANSLATIONS = {
    "withdrawal_pending_spike": {
        "title": "📤 Скачок ожидающих выводов",
        "description": "Много заявок на вывод ожидают обработки",
        "recommendations": [
            "Проверить очередь выводов вручную",
            "При необходимости приостановить авто-одобрение",
        ],
    },
    "withdrawal_amount_spike": {
        "title": "💸 Крупный вывод средств",
        "description": "Сумма вывода значительно выше среднего",
        "recommendations": [
            "Проверить легитимность вывода",
            "Убедиться что пользователь реальный",
        ],
    },
    "deposit_spike": {
        "title": "📥 Скачок депозитов",
        "description": "Необычно много депозитов за короткое время",
        "recommendations": [
            "Проверить источники депозитов",
            "Мониторить на предмет мошенничества",
        ],
    },
    "level5_deposit_spike": {
        "title": "💎 Скачок депозитов Level 5",
        "description": "Много крупных депозитов (Level 5)",
        "recommendations": [
            "Проверить новых крупных инвесторов",
            "Верифицировать источники средств",
        ],
    },
    "rejection_rate_spike": {
        "title": "❌ Рост отказов по выводам",
        "description": "Много выводов отклонено",
        "recommendations": [
            "Проверить причины отказов",
            "Связаться с пользователями",
        ],
    },
}

SEVERITY_TRANSLATIONS = {
    "low": "🟢 Низкая",
    "medium": "🟡 Средняя",
    "high": "🟠 Высокая",
    "critical": "🔴 КРИТИЧЕСКАЯ",
}


async def _send_anomaly_alerts(
    anomalies: list[dict[str, Any]], metrics: dict[str, Any]
) -> None:
    """Send anomaly alerts to admins in Russian (R14-1)."""
    try:
        async with async_session_maker() as session:
            bot = Bot(token=settings.telegram_bot_token)
            notification_service = NotificationService(session)

            admin_ids = settings.get_admin_ids()

            for anomaly in anomalies:
                anomaly_type = anomaly.get("type", "unknown")
                current = anomaly.get("current", 0)
                expected = anomaly.get("expected_mean", 0)
                severity = anomaly.get("severity", "medium")

                # Get translation
                translation = ANOMALY_TRANSLATIONS.get(anomaly_type, {})
                title = translation.get("title", f"⚠️ {anomaly_type}")
                description = translation.get(
                    "description", "Обнаружена аномалия"
                )
                recommendations = translation.get("recommendations", [])

                severity_text = SEVERITY_TRANSLATIONS.get(
                    severity, f"⚪ {severity}"
                )

                # Calculate deviation
                if expected > 0:
                    deviation_pct = (current - expected) / expected * 100
                    comparison = (
                        f"в *{current/expected:.1f}x* раз больше"
                        if current > expected
                        else f"в *{expected/current:.1f}x* раз меньше"
                    )
                else:
                    deviation_pct = 0
                    comparison = "—"

                # Format current value nicely
                if isinstance(current, float):
                    current_str = f"{current:.2f} USDT"
                else:
                    current_str = str(current)

                if isinstance(expected, float):
                    expected_str = f"{expected:.2f} USDT"
                else:
                    expected_str = str(expected)

                # Build message
                message = f"""
🚨 *ВНИМАНИЕ: {title}*
{'━' * 28}

📋 *{description}*

{'─' * 28}
📊 *Статистика:*
├ Сейчас: *{current_str}*
├ Обычно: *{expected_str}*
├ Отклонение: *{deviation_pct:+.0f}%* ({comparison})
└ Важность: {severity_text}

{'─' * 28}
💡 *Рекомендации:*
"""
                for i, rec in enumerate(recommendations, 1):
                    message += f"{i}. {rec}\n"

                message += f"""
{'─' * 28}
🕐 _{metrics.get('timestamp', 'N/A')[:19]}_
                """.strip()

                for admin_id in admin_ids:
                    await notification_service.send_notification(
                        bot,
                        admin_id,
                        message,
                        critical=(severity == "critical"),
                    )

            await bot.session.close()

    except Exception as e:
        logger.error(f"Error sending anomaly alerts: {e}")


async def _take_protective_actions(
    anomalies: list[dict[str, Any]]
) -> None:
    """
    Take automatic protective actions for critical anomalies (R14-1).

    Args:
        anomalies: List of critical anomalies
    """
    logger.warning(
        f"Taking protective actions for {len(anomalies)} critical anomalies"
    )

    # In production, would implement:
    # - Temporary pause of auto-approvals for withdrawals >$1000
    # - Require two super_admin for large withdrawals
    # - Enhanced fraud detection

    for anomaly in anomalies:
        anomaly_type = anomaly.get("type", "unknown")
        logger.info(
            f"Protective action triggered for: {anomaly_type}",
            extra={"anomaly": anomaly},
        )

