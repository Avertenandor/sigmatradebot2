"""
Blockchain service.

Full Web3.py implementation for BSC blockchain operations
(USDT transfers, monitoring) with Dual-Core engine (QuickNode + NodeReal).
"""

import asyncio
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, TypeVar

# Suppress eth_utils network warnings about invalid ChainId
warnings.filterwarnings(
    "ignore",
    message=".*does not have a valid ChainId.*",
    category=UserWarning,
    module="eth_utils.network",
)
warnings.filterwarnings(
    "ignore",
    message=".*does not have a valid ChainId.*",
    category=UserWarning,
)

from eth_account import Account
from eth_utils import is_address, to_checksum_address
from loguru import logger
from web3 import Web3
from web3.middleware import geth_poa_middleware

from app.config.settings import Settings
from app.repositories.global_settings_repository import GlobalSettingsRepository
from app.config.database import async_session_maker

# USDT contract ABI (ERC-20 standard functions)
USDT_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
]

# USDT decimals (BEP-20 USDT uses 18 decimals)
USDT_DECIMALS = 18

# Gas settings for BSC
# 0.1 Gwei = 100_000_000 Wei (1 Gwei = 10^9 Wei)
# User requirement: Max 0.1 Gwei, try lower if possible
MIN_GAS_PRICE_GWEI = Decimal("0.01")
MAX_GAS_PRICE_GWEI = Decimal("0.1")
MIN_GAS_PRICE_WEI = int(MIN_GAS_PRICE_GWEI * 10**9)
MAX_GAS_PRICE_WEI = int(MAX_GAS_PRICE_GWEI * 10**9)

T = TypeVar("T")

class BlockchainService:
    """
    Blockchain service for BSC/USDT operations.

    Full Web3.py implementation with:
    - Dual-Core Engine (QuickNode + NodeReal)
    - Automatic Failover
    - Smart Gas Management
    - USDT contract interaction
    - Transaction sending
    - Balance checking
    - Event monitoring
    """

    def __init__(
        self,
        settings: Settings,
        session_factory: Any | None = None,
    ) -> None:
        """
        Initialize blockchain service.

        Args:
            settings: Application settings
            session_factory: Async session factory for DB access (optional)
        """
        self.settings = settings
        self.session_factory = session_factory
        
        self.usdt_contract_address = to_checksum_address(settings.usdt_contract_address)
        self.wallet_private_key = settings.wallet_private_key
        self.system_wallet_address = settings.system_wallet_address

        # Initialize RPC rate limiter
        from app.services.blockchain.rpc_rate_limiter import RPCRateLimiter
        self.rpc_limiter = RPCRateLimiter(max_concurrent=10, max_rps=25)

        # Thread pool executor
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="web3"
        )

        # Providers storage
        self.providers: dict[str, Web3] = {}
        self.active_provider_name = "quicknode"
        self.is_auto_switch_enabled = True
        self._last_settings_update = 0.0
        self._settings_cache_ttl = 30.0  # Check DB every 30 seconds

        # Initialize Providers
        self._init_providers()

        # Initialize Wallet
        self._init_wallet()

        logger.success(
            f"BlockchainService initialized successfully\n"
            f"  Active Provider: {self.active_provider_name}\n"
            f"  Providers: {list(self.providers.keys())}\n"
            f"  USDT Contract: {self.usdt_contract_address}\n"
            f"  Wallet: {self.wallet_address if self.wallet_address else 'Not configured'}"
        )

    def get_optimal_gas_price(self, w3: Web3) -> int:
        """
        Calculate optimal gas price with Smart Gas strategy.
        
        Logic:
        1. Get current RPC gas price.
        2. Clamp between MIN (0.1 Gwei) and MAX (5.0 Gwei).
        
        Args:
            w3: Web3 instance
            
        Returns:
            Gas price in Wei
        """
        try:
            rpc_gas = w3.eth.gas_price
            
            # Clamp logic
            final_gas = max(MIN_GAS_PRICE_WEI, min(MAX_GAS_PRICE_WEI, rpc_gas))
            
            # Log if capped
            if rpc_gas > MAX_GAS_PRICE_WEI:
                logger.warning(
                    f"Gas price capped! RPC: {rpc_gas/1e9:.2f} Gwei, "
                    f"Used: {final_gas/1e9:.2f} Gwei"
                )
            
            return int(final_gas)
        except Exception as e:
            logger.warning(f"Failed to get gas price, using MIN: {e}")
            return int(MIN_GAS_PRICE_WEI)

    def _init_providers(self) -> None:
        """Initialize Web3 providers based on settings."""
        # RPC timeout in seconds
        rpc_timeout = 30
        
        # 1. QuickNode
        qn_url = self.settings.rpc_quicknode_http or self.settings.rpc_url
        if qn_url:
            try:
                w3_qn = Web3(Web3.HTTPProvider(
                    qn_url,
                    request_kwargs={'timeout': rpc_timeout}
                ))
                w3_qn.middleware_onion.inject(geth_poa_middleware, layer=0)
                if w3_qn.is_connected():
                    self.providers["quicknode"] = w3_qn
                    logger.info("✅ QuickNode provider connected (timeout=30s)")
                else:
                    logger.warning("❌ QuickNode provider failed to connect")
            except Exception as e:
                logger.error(f"Failed to init QuickNode: {e}")

        # 2. NodeReal
        nr_url = self.settings.rpc_nodereal_http
        if nr_url:
            try:
                w3_nr = Web3(Web3.HTTPProvider(
                    nr_url,
                    request_kwargs={'timeout': rpc_timeout}
                ))
                w3_nr.middleware_onion.inject(geth_poa_middleware, layer=0)
                if w3_nr.is_connected():
                    self.providers["nodereal"] = w3_nr
                    logger.info("✅ NodeReal provider connected (timeout=30s)")
                else:
                    logger.warning("❌ NodeReal provider failed to connect")
            except Exception as e:
                logger.error(f"Failed to init NodeReal: {e}")

        if not self.providers:
            logger.error("🔥 NO BLOCKCHAIN PROVIDERS AVAILABLE! Service will fail.")

    def _init_wallet(self) -> None:
        """Initialize wallet account."""
        if self.wallet_private_key:
            try:
                self.wallet_account = Account.from_key(self.wallet_private_key)
                self.wallet_address = to_checksum_address(self.wallet_account.address)
            except Exception as e:
                logger.error(f"Failed to init wallet: {e}")
                self.wallet_account = None
                self.wallet_address = None
        else:
            self.wallet_account = None
            self.wallet_address = None

    async def _update_settings_from_db(self) -> None:
        """Update active provider and auto-switch settings from DB."""
        if not self.session_factory:
            return

        now = time.time()
        if now - self._last_settings_update < self._settings_cache_ttl:
            return

        try:
            async with self.session_factory() as session:
                repo = GlobalSettingsRepository(session)
                settings = await repo.get_settings()
                self.active_provider_name = settings.active_rpc_provider
                self.is_auto_switch_enabled = settings.is_auto_switch_enabled
                self._last_settings_update = now
        except Exception as e:
            logger.warning(f"Failed to update blockchain settings from DB: {e}")

    def get_active_web3(self) -> Web3:
        """Get the currently active Web3 instance."""
        provider = self.providers.get(self.active_provider_name)
        if not provider:
            # Fallback to any available
            if self.providers:
                fallback_name = next(iter(self.providers))
                logger.warning(f"Active provider '{self.active_provider_name}' not found, falling back to '{fallback_name}'")
                return self.providers[fallback_name]
            raise ConnectionError("No blockchain providers available")
        return provider

    @property
    def web3(self) -> Web3:
        """Backward compatibility property."""
        return self.get_active_web3()
    
    @property
    def usdt_contract(self):
        """Get USDT contract on active provider."""
        w3 = self.get_active_web3()
        return w3.eth.contract(address=self.usdt_contract_address, abi=USDT_ABI)

    async def _execute_with_failover(self, func: Callable[[Web3], Any]) -> Any:
        """
        Execute a function with automatic failover to the backup provider.
        """
        await self._update_settings_from_db()
        
        current_name = self.active_provider_name
        providers_list = list(self.providers.keys())
        
        # Try current provider first
        try:
            w3 = self.get_active_web3()
            return func(w3)
        except Exception as e:
            if not self.is_auto_switch_enabled:
                raise e
                
            logger.warning(f"Provider '{current_name}' failed: {e}. Attempting failover...")
            
            # Find backup provider
            backup_name = None
            for name in providers_list:
                if name != current_name:
                    backup_name = name
                    break
            
            if not backup_name:
                logger.error("No backup provider available.")
                raise e
                
            logger.info(f"Switching to backup provider: {backup_name}")
            try:
                self.active_provider_name = backup_name 
                w3_backup = self.providers[backup_name]
                result = func(w3_backup)
                
                # If successful, persist the switch asynchronously
                if self.session_factory:
                    asyncio.create_task(self._persist_provider_switch(backup_name))
                
                return result
            except Exception as e2:
                logger.error(f"Backup provider '{backup_name}' also failed: {e2}")
                raise e2

    async def _persist_provider_switch(self, new_provider: str):
        """Persist the provider switch to DB."""
        if not self.session_factory:
            return
        try:
            async with self.session_factory() as session:
                repo = GlobalSettingsRepository(session)
                await repo.update_settings(active_rpc_provider=new_provider)
                await session.commit()
            logger.success(f"Persisted active provider switch to: {new_provider}")
        except Exception as e:
            logger.error(f"Failed to persist provider switch: {e}")

    async def force_refresh_settings(self):
        """Force update settings from DB."""
        self._last_settings_update = 0
        await self._update_settings_from_db()

    def get_rpc_stats(self) -> dict[str, Any]:
        return self.rpc_limiter.get_stats()

    def close(self) -> None:
        if hasattr(self, '_executor') and self._executor:
            self._executor.shutdown(wait=True)

    async def get_block_number(self) -> int:
        loop = asyncio.get_event_loop()
        async with self.rpc_limiter:
            return await loop.run_in_executor(
                self._executor,
                lambda: asyncio.run(self._execute_with_failover(
                    lambda w3: w3.eth.block_number
                ))
            )

    async def _run_async_failover(self, sync_func: Callable[[Web3], Any]) -> Any:
        """
        Runs a synchronous Web3 function in the thread pool, 
        with failover logic handled in the main async loop.
        """
        await self._update_settings_from_db()
        loop = asyncio.get_event_loop()
        
        current_name = self.active_provider_name
        
        # Try primary
        try:
            # Check primary provider exists logic handled by get_active_web3 inside executor or here
            # Actually better to get w3 instance here
            if current_name not in self.providers and self.providers:
                 current_name = next(iter(self.providers))
            
            if current_name not in self.providers:
                 raise ConnectionError("No providers available")

            w3 = self.providers[current_name]
            
            async with self.rpc_limiter:
                return await loop.run_in_executor(
                    self._executor,
                    lambda: sync_func(w3)
                )
        except Exception as e:
            if not self.is_auto_switch_enabled:
                raise e
            
            logger.warning(f"Primary provider '{current_name}' failed: {e}. Trying failover...")
            
            # Find backup
            backup_name = next((n for n in self.providers if n != current_name), None)
            if not backup_name:
                raise e
                
            # Try backup
            try:
                logger.info(f"Switching to backup: {backup_name}")
                w3_backup = self.providers[backup_name]
                
                async with self.rpc_limiter:
                    result = await loop.run_in_executor(
                        self._executor,
                        lambda: sync_func(w3_backup)
                    )
                
                # If success, switch permanent
                self.active_provider_name = backup_name
                if self.session_factory:
                    asyncio.create_task(self._persist_provider_switch(backup_name))
                
                return result
            except Exception as e2:
                logger.error(f"Backup provider failed: {e2}")
                raise e 

    async def send_payment(self, to_address: str, amount: float) -> dict[str, Any]:
        try:
            if not self.wallet_account:
                return {"success": False, "error": "Wallet not configured"}

            if not await self.validate_wallet_address(to_address):
                return {"success": False, "error": f"Invalid address: {to_address}"}

            to_address = to_checksum_address(to_address)
            amount_wei = int(amount * (10 ** USDT_DECIMALS))

            def _send_tx(w3: Web3):
                contract = w3.eth.contract(address=self.usdt_contract_address, abi=USDT_ABI)
                func = contract.functions.transfer(to_address, amount_wei)
                
                # Use Smart Gas
                gas_price = self.get_optimal_gas_price(w3)
                
                try:
                    gas_est = func.estimate_gas({"from": self.wallet_address})
                except Exception:
                    gas_est = 100000  # Fallback for USDT transfer
                
                # Use pending block for better concurrency
                nonce = w3.eth.get_transaction_count(self.wallet_address, 'pending')
                
                txn = func.build_transaction({
                    "from": self.wallet_address,
                    "gas": int(gas_est * 1.2),
                    "gasPrice": gas_price,
                    "nonce": nonce,
                    "chainId": w3.eth.chain_id,
                })
                
                logger.info(
                    f"Sending USDT tx: to={to_address}, amount={amount}, "
                    f"gas_price={gas_price} wei ({gas_price / 10**9} Gwei), "
                    f"gas_limit={int(gas_est * 1.2)}"
                )
                
                signed = self.wallet_account.sign_transaction(txn)
                tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
                return tx_hash.hex()

            tx_hash_str = await self._run_async_failover(_send_tx)
            
            logger.info(f"USDT payment sent: {amount} to {to_address}, hash: {tx_hash_str}")
            return {"success": True, "tx_hash": tx_hash_str, "error": None}

        except Exception as e:
            logger.error(f"Failed to send payment: {e}")
            return {"success": False, "error": str(e)}

    async def send_native_token(self, to_address: str, amount: float) -> dict[str, Any]:
        """
        Send native token (BNB) to address.
        """
        try:
            if not self.wallet_account:
                return {"success": False, "error": "Wallet not configured"}

            if not await self.validate_wallet_address(to_address):
                return {"success": False, "error": f"Invalid address: {to_address}"}

            to_address = to_checksum_address(to_address)
            amount_wei = Web3.to_wei(amount, 'ether')

            def _send_native(w3: Web3):
                # Use Smart Gas
                gas_price = self.get_optimal_gas_price(w3)
                gas_limit = 21000  # Standard native transfer gas
                
                # Use pending block for better concurrency
                nonce = w3.eth.get_transaction_count(self.wallet_address, 'pending')

                txn = {
                    "to": to_address,
                    "value": amount_wei,
                    "gas": gas_limit,
                    "gasPrice": gas_price,
                    "nonce": nonce,
                    "chainId": w3.eth.chain_id,
                }
                
                logger.info(
                    f"Sending BNB tx: to={to_address}, amount={amount}, "
                    f"gas_price={gas_price} wei ({gas_price / 10**9} Gwei)"
                )

                signed = self.wallet_account.sign_transaction(txn)
                tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
                return tx_hash.hex()

            tx_hash_str = await self._run_async_failover(_send_native)
            
            logger.info(f"BNB payment sent: {amount} to {to_address}, hash: {tx_hash_str}")
            return {"success": True, "tx_hash": tx_hash_str, "error": None}

        except Exception as e:
            logger.error(f"Failed to send BNB: {e}")
            return {"success": False, "error": str(e)}

    async def get_native_balance(self, address: str) -> Decimal | None:
        """Get Native Token (BNB) balance."""
        try:
            address = to_checksum_address(address)
            def _get_bal(w3: Web3):
                return w3.eth.get_balance(address)
            
            wei = await self._run_async_failover(_get_bal)
            return Decimal(wei) / Decimal(10 ** 18)
        except Exception as e:
            logger.error(f"Get BNB balance failed: {e}")
            return None

    async def check_transaction_status(self, tx_hash: str) -> dict[str, Any]:
        try:
            def _check(w3: Web3):
                try:
                    receipt = w3.eth.get_transaction_receipt(tx_hash)
                    current = w3.eth.block_number
                    return receipt, current
                except Exception:
                    return None, None

            receipt, current_block = await self._run_async_failover(_check)
            
            if not receipt:
                return {"status": "pending", "confirmations": 0}
                
            confirmations = max(0, current_block - receipt.blockNumber)
            status = "confirmed" if receipt.status == 1 else "failed"
            
            return {
                "status": status,
                "confirmations": confirmations,
                "block_number": receipt.blockNumber
            }
        except Exception:
            return {"status": "unknown", "confirmations": 0}

    async def get_transaction_details(self, tx_hash: str) -> dict[str, Any] | None:
        try:
            # Just execute directly via failover helper, encapsulating logic
            return await self._run_async_failover(lambda w3: self._fetch_tx_details_sync(w3, tx_hash))
        except Exception:
            return None

    def _fetch_tx_details_sync(self, w3: Web3, tx_hash: str):
        try:
            tx = w3.eth.get_transaction(tx_hash)
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
            except Exception:
                receipt = None
            
            # Parse logic...
            contract = w3.eth.contract(address=self.usdt_contract_address, abi=USDT_ABI)
            
            from_address = to_checksum_address(tx["from"])
            to_address = to_checksum_address(tx["to"]) if tx["to"] else None
            value = Decimal(0)
            
            if to_address and to_address.lower() == self.usdt_contract_address.lower():
                 try:
                    decoded = contract.decode_function_input(tx["input"])
                    if decoded[0].fn_name == "transfer":
                        amount_wei = decoded[1]["_value"]
                        value = Decimal(amount_wei) / Decimal(10 ** USDT_DECIMALS)
                        to_address = to_checksum_address(decoded[1]["_to"])
                 except Exception:
                     pass
                     
            return {
                "from_address": from_address,
                "to_address": to_address,
                "value": value,
                "status": "confirmed" if receipt and receipt.status == 1 else "pending",
            }
        except Exception:
            return None

    async def validate_wallet_address(self, address: str) -> bool:
        try:
            return is_address(address)
        except Exception:
            return False
            
    async def get_usdt_balance(self, address: str) -> Decimal | None:
        try:
            address = to_checksum_address(address)
            def _get_bal(w3: Web3):
                contract = w3.eth.contract(address=self.usdt_contract_address, abi=USDT_ABI)
                return contract.functions.balanceOf(address).call()
            
            wei = await self._run_async_failover(_get_bal)
            return Decimal(wei) / Decimal(10 ** USDT_DECIMALS)
        except Exception as e:
            logger.error(f"Get balance failed: {e}")
            return None

    async def estimate_gas_fee(self, to_address: str, amount: Decimal) -> Decimal | None:
         try:
            to_address = to_checksum_address(to_address)
            amount_wei = int(amount * (10 ** USDT_DECIMALS))
            
            def _est_gas(w3: Web3):
                contract = w3.eth.contract(address=self.usdt_contract_address, abi=USDT_ABI)
                func = contract.functions.transfer(to_address, amount_wei)
                func_gas = func.estimate_gas({"from": self.wallet_address})
                price = self.get_optimal_gas_price(w3)
                return func_gas * price

            total_wei = await self._run_async_failover(_est_gas)
            return Decimal(total_wei) / Decimal(10 ** 18)
         except Exception:
             return None

    async def get_providers_status(self) -> dict[str, Any]:
        """Get status of all providers."""
        status = {}
        for name, w3 in self.providers.items():
            try:
                loop = asyncio.get_event_loop()
                # Run ping in executor
                bn = await loop.run_in_executor(
                    self._executor, lambda: w3.eth.block_number
                )
                status[name] = {"connected": True, "block": bn, "active": name == self.active_provider_name}
            except Exception as e:
                status[name] = {"connected": False, "error": str(e), "active": name == self.active_provider_name}
        return status

# Singleton initialization
_blockchain_service: BlockchainService | None = None

def get_blockchain_service() -> BlockchainService:
    global _blockchain_service
    if _blockchain_service is None:
         raise RuntimeError("BlockchainService not initialized")
    return _blockchain_service

def init_blockchain_service(settings: Settings, session_factory: Any = None) -> None:
    global _blockchain_service
    _blockchain_service = BlockchainService(settings, session_factory)
