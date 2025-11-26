#!/usr/bin/env python3
"""
Manual recovery script for missing deposits.
Usage: python3 scripts/manual_recover_deposits.py
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy import select

from app.config.settings import settings
from app.services.blockchain_service import init_blockchain_service, get_blockchain_service
from app.services.deposit_service import DepositService
from app.models.user import User
from app.models.deposit import Deposit
from app.models.enums import TransactionStatus

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")

# Transactions to recover
RECOVERY_TXS = [
    "0x96696780516b6fbbeaa16338478292eabaa7abefbd16f864d16698fcfa9e20d3",
    "0x0883f6030aed1d379a225725036dadf8ea52ba6d0a8b5fc05d3f3fe7cecdce4d"
]

async def recover_deposits():
    logger.info("🚀 Starting manual deposit recovery...")

    # Initialize Database
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        poolclass=NullPool,
    )
    
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Initialize Blockchain Service
    init_blockchain_service(settings, session_maker)
    blockchain = get_blockchain_service()

    try:
        async with session_maker() as session:
            deposit_service = DepositService(session)

            for tx_hash in RECOVERY_TXS:
                logger.info(f"🔍 Processing TX: {tx_hash}")

                # 1. Get Transaction Details from Blockchain
                tx_details = await blockchain.get_transaction_details(tx_hash)
                
                if not tx_details:
                    logger.error(f"❌ Transaction not found or failed to fetch: {tx_hash}")
                    continue

                logger.info(f"   Details: {tx_details}")

                if tx_details['status'] != 'confirmed':
                    logger.warning(f"⚠️ Transaction is not confirmed: {tx_details['status']}")
                    continue

                # Verify recipient is system wallet
                # Note: to_address from details is the USDT recipient
                if tx_details['to_address'].lower() != settings.system_wallet_address.lower():
                    logger.error(f"❌ Recipient mismatch! Expected {settings.system_wallet_address}, got {tx_details['to_address']}")
                    continue

                from_address = tx_details['from_address']
                amount = tx_details['value']

                # 2. Find User by Wallet
                # Note: Currently wallet_address is just a string in User model. 
                # Users might have entered it in different cases, so we should check case-insensitive.
                
                result = await session.execute(
                    select(User).where(User.wallet_address.ilike(from_address))
                )
                user = result.scalars().first()

                if not user:
                    logger.error(f"❌ No user found with wallet: {from_address}")
                    continue

                logger.info(f"✅ Found User: {user.id} ({user.username or user.telegram_id})")

                # 3. Check for existing deposit with this hash
                result = await session.execute(
                    select(Deposit).where(Deposit.tx_hash == tx_hash)
                )
                existing_deposit = result.scalars().first()

                if existing_deposit:
                    if existing_deposit.status == TransactionStatus.CONFIRMED.value:
                        logger.info(f"⚠️ Deposit {existing_deposit.id} already confirmed. Skipping.")
                        continue
                    
                    logger.info(f"🔄 Found pending/failed deposit {existing_deposit.id}. Confirming...")
                    await deposit_service.confirm_deposit(existing_deposit.id, 0) # Block number 0 for manual
                    logger.success(f"✅ Deposit {existing_deposit.id} confirmed!")
                
                else:
                    logger.info(f"➕ Creating NEW deposit for {amount} USDT...")
                    
                    # Determine level based on amount
                    level = 1
                    from app.services.deposit_validation_service import DEPOSIT_LEVELS
                    # Invert mapping to find level by amount
                    amount_to_level = {v: k for k, v in DEPOSIT_LEVELS.items()}
                    
                    # Simple check for exact match, else default to 1 or logic?
                    # For recovery, let's assume standard levels.
                    # If amount doesn't match standard level, we might have an issue logic-wise, 
                    # but for recovery we credit what they sent.
                    # However, create_deposit expects a valid level.
                    
                    if amount in amount_to_level:
                        level = amount_to_level[amount]
                    else:
                        logger.warning(f"⚠️ Amount {amount} does not match standard levels. Defaulting to Level 1.")
                        # Logic decision: Do we want to force level 1? Or reject?
                        # Let's try to find closest level or just use 1.
                        level = 1

                    try:
                        # We bypass redis lock here by not passing redis_client (using DB lock fallback which works for single script)
                        # Wait, create_deposit raises error if lock fails.
                        # Since this script is single threaded, DB lock should succeed.
                        
                        # NOTE: create_deposit checks min amount and level constraints.
                        # If amount is weird, it might raise ValueError.
                        
                        deposit = await deposit_service.create_deposit(
                            user_id=user.id,
                            level=level,
                            amount=amount,
                            tx_hash=tx_hash
                        )
                        
                        # Automatically confirm it
                        await deposit_service.confirm_deposit(deposit.id, 0)
                        logger.success(f"✅ New deposit {deposit.id} created and confirmed!")

                    except Exception as e:
                        logger.error(f"❌ Failed to create/confirm deposit: {e}")

    except Exception as e:
        logger.exception(f"Script error: {e}")
    finally:
        blockchain.close()
        await engine.dispose()
        logger.info("🏁 Recovery script finished.")

if __name__ == "__main__":
    asyncio.run(recover_deposits())

