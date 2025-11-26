"""
Incoming transfer monitor task.

Scans blockchain for all incoming transfers to system wallet.
Runs frequently (e.g. every minute) to catch deposits without explicit user action.
"""

import asyncio
from decimal import Decimal

import dramatiq
from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.config.settings import settings
from app.services.blockchain_service import get_blockchain_service
from app.services.incoming_deposit_service import IncomingDepositService

@dramatiq.actor(max_retries=3, time_limit=300_000)
def monitor_incoming_transfers() -> None:
    """
    Monitor blockchain for ANY incoming transfer to system wallet.
    """
    logger.info("Starting incoming transfer monitoring...")
    try:
        asyncio.run(_monitor_incoming_async())
        logger.info("Incoming transfer monitoring complete")
    except Exception as e:
        logger.exception(f"Incoming transfer monitoring failed: {e}")

async def _monitor_incoming_async() -> None:
    """Async implementation."""
    
    # Check if maintenance mode is active
    if settings.blockchain_maintenance_mode:
        logger.warning("Blockchain maintenance mode active. Skipping incoming monitor.")
        return

    local_engine = create_async_engine(
        settings.database_url,
        echo=False,
        poolclass=NullPool,
    )
    
    local_session_maker = async_sessionmaker(
        local_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    try:
        async with local_session_maker() as session:
            blockchain = get_blockchain_service()
            service = IncomingDepositService(session)
            
            # Determine scan range
            # We should persist last scanned block to DB to avoid re-scanning.
            # For now, let's scan last N blocks or use a simple state file/redis.
            # A robust solution would be `SystemSetting` table.
            
            from app.repositories.global_settings_repository import GlobalSettingsRepository
            settings_repo = GlobalSettingsRepository(session)
            global_settings = await settings_repo.get_settings()
            
            # Use stored last_scanned_block or fetch current - 100
            current_block = await blockchain.get_block_number()
            
            # If last_scanned_block is 0 or too old (e.g. > 1000 blocks behind), catch up carefully
            # Or just look at recent history for now.
            # Let's add `last_scanned_block` to GlobalSettings in next iteration if needed.
            # For now, let's scan last 100 blocks to be safe, assuming job runs every minute.
            # 1 minute = ~20 blocks on BSC. 100 blocks = ~5 mins overlap.
            
            # NOTE: This overlap means we rely on `process_incoming_transfer` idempotency (tx_hash check).
            
            to_block = current_block
            from_block = current_block - 50 # Scan last 50 blocks
            
            logger.info(f"Scanning blocks {from_block} to {to_block} for incoming USDT...")
            
            # Get transfer events
            # We need a new method in blockchain service or use raw web3 here?
            # Let's add a helper method to BlockchainService if possible, or do it here.
            # Since BlockchainService encapsulates provider failover, we should use it.
            
            # We can use `get_incoming_transfers` if we implement it, 
            # or reuse `search_blockchain_for_deposit` logic but broader.
            
            # Let's implement a broad search in this script using public `web3` property 
            # or add `get_transfers` to service. 
            # Ideally, service should expose `get_usdt_transfers(from_block, to_block)`.
            
            # For now, accessing web3 directly via getter
            w3 = blockchain.get_active_web3()
            contract = blockchain.usdt_contract
            
            # Filter for Transfer events to system wallet
            # topic0 = Transfer
            # topic2 = to address (indexed)
            
            # Transfer(address from, address to, uint256 value)
            # topics = [keccak('Transfer(...)'), pad(from), pad(to)]
            
            transfer_event_signature = w3.keccak(text="Transfer(address,address,uint256)").hex()
            padded_system_wallet = "0x" + settings.system_wallet_address[2:].lower().zfill(64)
            
            logs = await blockchain._run_async_failover(
                lambda w: w.eth.get_logs({
                    "fromBlock": from_block,
                    "toBlock": to_block,
                    "address": blockchain.usdt_contract_address,
                    "topics": [
                        transfer_event_signature,
                        None, # from (any)
                        padded_system_wallet # to (system wallet)
                    ]
                })
            )
            
            logger.info(f"Found {len(logs)} transfer events")
            
            for log in logs:
                try:
                    tx_hash = log["transactionHash"].hex()
                    block_number = log["blockNumber"]
                    
                    # Parse event
                    # Topic 1 is 'from', data is 'value'
                    # topics[0] is signature
                    # topics[1] is from (indexed)
                    # topics[2] is to (indexed)
                    
                    # Extract from address
                    # 0x000...address
                    from_hex = log["topics"][1].hex()
                    from_address = "0x" + from_hex[26:] # Last 40 chars (20 bytes)
                    from_address = w3.to_checksum_address(from_address)
                    
                    # Extract value
                    value_hex = log["data"].hex()
                    value_wei = int(value_hex, 16)
                    amount = Decimal(value_wei) / Decimal(10 ** 18) # USDT 18 decimals
                    
                    # Verify 'to' address just in case
                    to_hex = log["topics"][2].hex()
                    to_addr_extracted = "0x" + to_hex[26:]
                    to_addr_checksum = w3.to_checksum_address(to_addr_extracted)
                    
                    await service.process_incoming_transfer(
                        tx_hash=tx_hash,
                        from_address=from_address,
                        to_address=to_addr_checksum,
                        amount=amount,
                        block_number=block_number
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing log {log}: {e}")

    finally:
        await local_engine.dispose()

