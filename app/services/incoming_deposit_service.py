"""
Incoming deposit service.

Handles processing of incoming transfers detected on blockchain.
"""

from decimal import Decimal
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.deposit import Deposit
from app.models.enums import TransactionStatus
from app.services.deposit_service import DepositService
from app.services.notification_service import NotificationService
from app.config.settings import settings
from bot.utils.formatters import escape_md

class IncomingDepositService:
    """
    Service for processing incoming blockchain transfers.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize service.

        Args:
            session: Database session
        """
        self.session = session
        self.deposit_service = DepositService(session)
        self.notification_service = NotificationService(session)

    async def process_incoming_transfer(
        self,
        tx_hash: str,
        from_address: str,
        to_address: str,
        amount: Decimal,
        block_number: int,
    ) -> None:
        """
        Process an incoming transfer event.

        Args:
            tx_hash: Transaction hash
            from_address: Sender address
            to_address: Recipient address (should be system wallet)
            amount: Amount in USDT
            block_number: Block number
        """
        logger.info(f"📥 Processing incoming transfer: {amount} USDT from {from_address} (TX: {tx_hash})")

        # 1. Idempotency Check
        existing_deposit = await self.session.execute(
            select(Deposit).where(Deposit.tx_hash == tx_hash)
        )
        if existing_deposit.scalars().first():
            logger.info(f"⏩ Deposit {tx_hash} already processed. Skipping.")
            return

        # 2. Verify Recipient
        # Note: This check should ideally happen before calling this service, 
        # but good to have as a safeguard.
        if to_address.lower() != settings.system_wallet_address.lower():
            logger.warning(f"⚠️ Transfer recipient mismatch: {to_address} != {settings.system_wallet_address}")
            # Allow processing if it's a valid deposit to a known hot wallet?
            # For now strict check against configured system wallet.
            return

        # 3. User Identification
        user_result = await self.session.execute(
            select(User).where(User.wallet_address.ilike(from_address))
        )
        user = user_result.scalars().first()

        if user:
            logger.info(f"✅ Identified user {user.id} for wallet {from_address}")
            
            # Determine Level based on amount
            # We need to reverse lookup amount -> level from validation logic
            from app.services.deposit_validation_service import DEPOSIT_LEVELS
            # Invert mapping: amount -> level
            amount_to_level = {v: k for k, v in DEPOSIT_LEVELS.items()}
            
            level = amount_to_level.get(amount)
            
            if not level:
                logger.warning(f"⚠️ Amount {amount} does not match any level. Defaulting to Level 1 logic or Manual Review.")
                # Decision: Create deposit with level 1 but maybe mark for review?
                # For now, try to find closest valid level or just use 1?
                # Strict mode: Only exact amounts allowed?
                # Let's assume Level 1 for unknown amounts to capture the funds in system.
                level = 1

            try:
                # Create and Confirm Deposit
                # Use create_deposit from service which handles locks and logic
                deposit = await self.deposit_service.create_deposit(
                    user_id=user.id,
                    level=level,
                    amount=amount,
                    tx_hash=tx_hash
                )
                
                # Manually update block number and wallet address if not set by create
                deposit.block_number = block_number
                deposit.wallet_address = from_address
                await self.session.commit()

                # Confirm
                await self.deposit_service.confirm_deposit(deposit.id, block_number)
                
                # Notify User
                await self.notification_service.notify_user(
                    user.id,
                    f"✅ **Депозит успешно зачислен!**\n\n"
                    f"Сумма: `{amount} USDT`\n"
                    f"Уровень: {level}\n"
                    f"Hash: `{tx_hash}`"
                )
                
                # Notify Admin
                username = escape_md(user.username) if user.username else "без юзернейма"
                await self.notification_service.notify_admins(
                    f"💰 **Новый автоматический депозит**\n"
                    f"User: {user.id} (@{username})\n"
                    f"Amount: {amount} USDT\n"
                    f"TX: `{tx_hash}`"
                )
                
            except Exception as e:
                logger.error(f"❌ Failed to process deposit for user {user.id}: {e}")
                await self.notification_service.notify_admins(
                    f"❌ **Ошибка обработки депозита**\n"
                    f"User: {user.id}\n"
                    f"TX: `{tx_hash}`\n"
                    f"Error: {str(e)}"
                )
        
        else:
            # User NOT found
            logger.warning(f"⚠️ Unidentified deposit from {from_address}")
            
            # Notify Admins about unidentified funds
            await self.notification_service.notify_admins(
                f"⚠️ **НЕОПОЗНАННЫЙ ДЕПОЗИТ**\n\n"
                f"Сумма: `{amount} USDT`\n"
                f"От: `{from_address}`\n"
                f"TX: `{tx_hash}`\n\n"
                f"Кошелек не привязан ни к одному пользователю!\n"
                f"Требуется ручная проверка."
            )
            # Optional: Create a "OrphanedDeposit" record? 
            # For now logging and alerting is sufficient.

