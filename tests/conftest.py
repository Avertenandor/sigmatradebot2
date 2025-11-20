"""
Pytest configuration and shared fixtures.

Этот файл содержит общие фикстуры и конфигурацию для всех тестов.
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Callable, Generator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, delete, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models import (
    Admin,
    Deposit,
    SupportTicket,
    Transaction,
    User,
    WalletChangeRequest,
)
from app.models.enums import WalletChangeStatus
from app.repositories import (
    AdminRepository,
    AppealRepository,
    BlacklistRepository,
    DepositRepository,
    ReferralEarningRepository,
    ReferralRepository,
    SupportTicketRepository,
    TransactionRepository,
    UserRepository,
)
from app.services import (
    AdminService,
    BlacklistService,
    DepositService,
    NotificationService,
    ReferralService,
    RewardService,
    SupportService,
    TransactionService,
    UserService,
    WithdrawalService,
)
# Helper function for hashing passwords in tests
def hash_password(password: str) -> str:
    """Hash password for tests (simple bcrypt-like hash)."""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

# ==================== PYTEST CONFIGURATION ====================


def pytest_configure(config: Any) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
    config.addinivalue_line("markers", "critical: marks tests as critical")
    config.addinivalue_line(
        "markers", "blockchain: marks tests that interact with blockchain"
    )
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "e2e: marks end-to-end tests")
    config.addinivalue_line("markers", "security: marks security tests")
    config.addinivalue_line("markers", "performance: marks performance tests")


# ==================== EVENT LOOP ====================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== DATABASE FIXTURES ====================

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/sigmatradebot_test",
)

SYNC_TEST_DATABASE_URL = TEST_DATABASE_URL.replace("+asyncpg", "")


@pytest_asyncio.fixture(scope="session")
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create async engine for tests."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    async_engine: AsyncEngine,  # pylint: disable=redefined-outer-name
) -> AsyncGenerator[AsyncSession, None]:
    """
    Create database session for tests.

    Args:
        async_engine: Async database engine

    Yields:
        AsyncSession: Database session
    """
    async_session = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="session")
def sync_engine() -> Generator[Any, None, None]:
    """Create sync engine for synchronous tests."""
    engine = create_engine(SYNC_TEST_DATABASE_URL, echo=False)
    yield engine
    engine.dispose()


@pytest.fixture
def sync_db_session(
    sync_engine: Any,  # pylint: disable=redefined-outer-name
) -> Generator[Session, None, None]:
    """
    Create sync database session for tests.

    Args:
        sync_engine: Sync database engine

    Yields:
        Session: Sync database session
    """
    session_local = sessionmaker(bind=sync_engine)
    session = session_local()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ==================== MODEL FIXTURES ====================


@pytest.fixture
def test_user_data() -> dict[str, Any]:
    """Basic user data for testing."""
    return {
        "telegram_id": 123456789,
        "username": "testuser",
        "wallet_address": "0x" + "1" * 40,
        "financial_password": hash_password("test123"),
        "balance": Decimal("0"),
        "total_earned": Decimal("0"),
        "pending_earnings": Decimal("0"),
    }


@pytest_asyncio.fixture
async def test_user(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_user_data: dict[str, Any],
) -> User:
    """Create test user."""
    user = User(**test_user_data)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> Admin:
    """Create test admin."""
    admin = Admin(
        telegram_id=987654321,
        username="testadmin",
        role="super_admin",
        master_key=hash_password("admin123"),
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest_asyncio.fixture
async def test_users_batch(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> list[User]:
    """Create batch of test users."""
    users = []
    for i in range(10):
        user = User(
            telegram_id=100000000 + i,
            username=f"testuser{i}",
            wallet_address="0x" + str(i) * 40,
            financial_password=hash_password(f"test{i}"),
        )
        db_session.add(user)
        users.append(user)

    await db_session.commit()
    for user in users:
        await db_session.refresh(user)
    return users


@pytest_asyncio.fixture
async def test_deposit(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_user: User,  # pylint: disable=redefined-outer-name
) -> Deposit:
    """Create test deposit."""
    deposit = Deposit(
        user_id=test_user.id,
        level=3,
        amount=Decimal("100"),
        status="confirmed",
        roi_cap_amount=Decimal("500"),  # 500% cap
        roi_paid_amount=Decimal("0"),
        tx_hash="0x" + "a" * 64,
    )
    db_session.add(deposit)
    await db_session.commit()
    await db_session.refresh(deposit)
    return deposit


@pytest_asyncio.fixture
async def test_transaction(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_user: User,  # pylint: disable=redefined-outer-name
) -> Transaction:
    """Create test transaction."""
    transaction = Transaction(
        user_id=test_user.id,
        type="deposit",
        amount=Decimal("100"),
        balance_before=Decimal("0"),
        balance_after=Decimal("100"),
        status="confirmed",
        description="Test deposit",
        tx_hash="0x" + "b" * 64,
    )
    db_session.add(transaction)
    await db_session.commit()
    await db_session.refresh(transaction)
    return transaction


@pytest_asyncio.fixture
async def test_referral_chain(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> tuple[User, User, User, User]:
    """
    Create referral chain: referrer -> level1 -> level2 -> level3.

    Returns:
        tuple: (referrer, level1, level2, level3)
    """
    # Create referrer
    referrer = User(
        telegram_id=200000000,
        username="referrer",
        wallet_address="0x" + "r" * 40,
        financial_password=hash_password("ref123"),
    )
    db_session.add(referrer)
    await db_session.commit()
    await db_session.refresh(referrer)

    # Create level 1
    level1 = User(
        telegram_id=200000001,
        username="level1",
        wallet_address="0x" + "1" * 40,
        financial_password=hash_password("l1_123"),
        referrer_id=referrer.id,
    )
    db_session.add(level1)
    await db_session.commit()
    await db_session.refresh(level1)

    # Create level 2
    level2 = User(
        telegram_id=200000002,
        username="level2",
        wallet_address="0x" + "2" * 40,
        financial_password=hash_password("l2_123"),
        referrer_id=level1.id,
    )
    db_session.add(level2)
    await db_session.commit()
    await db_session.refresh(level2)

    # Create level 3
    level3 = User(
        telegram_id=200000003,
        username="level3",
        wallet_address="0x" + "3" * 40,
        financial_password=hash_password("l3_123"),
        referrer_id=level2.id,
    )
    db_session.add(level3)
    await db_session.commit()
    await db_session.refresh(level3)

    return referrer, level1, level2, level3


@pytest_asyncio.fixture
async def test_support_ticket(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_user: User,  # pylint: disable=redefined-outer-name
) -> SupportTicket:
    """Create test support ticket."""
    ticket = SupportTicket(
        user_id=test_user.id,
        category="payments",
        priority="medium",
        status="open",
        subject="Test ticket",
    )
    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)
    return ticket


@pytest_asyncio.fixture
async def test_wallet_change_request(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
    test_admin: Admin,  # pylint: disable=redefined-outer-name
) -> WalletChangeRequest:
    """Create wallet change request used in admin tests."""
    request = WalletChangeRequest(
        type="system_deposit",
        new_address="0x" + "9" * 40,
        secret_ref="vault:system/deposit",
        initiated_by_admin_id=test_admin.id,
        status=WalletChangeStatus.PENDING.value,
        reason="Planned wallet rotation",
    )
    db_session.add(request)
    await db_session.commit()
    await db_session.refresh(request)
    return request


# ==================== REPOSITORY FIXTURES ====================


@pytest.fixture
def user_repository(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> UserRepository:
    """User repository instance."""
    return UserRepository(db_session)


@pytest.fixture
def deposit_repository(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> DepositRepository:
    """Deposit repository instance."""
    return DepositRepository(db_session)


@pytest.fixture
def transaction_repository(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> TransactionRepository:
    """Transaction repository instance."""
    return TransactionRepository(db_session)


@pytest.fixture
def referral_repository(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> ReferralRepository:
    """Referral repository instance."""
    return ReferralRepository(db_session)


@pytest.fixture
def referral_earning_repository(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> ReferralEarningRepository:
    """Referral earning repository instance."""
    return ReferralEarningRepository(db_session)


@pytest.fixture
def admin_repository(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> AdminRepository:
    """Admin repository instance."""
    return AdminRepository(db_session)


@pytest.fixture
def support_ticket_repository(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> SupportTicketRepository:
    """Support ticket repository instance."""
    return SupportTicketRepository(db_session)


@pytest.fixture
def blacklist_repository(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> BlacklistRepository:
    """Blacklist repository instance."""
    return BlacklistRepository(db_session)


@pytest.fixture
def appeal_repository(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> AppealRepository:
    """Appeal repository instance."""
    return AppealRepository(db_session)


# ==================== SERVICE FIXTURES ====================


@pytest.fixture
def user_service(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> UserService:
    """User service instance."""
    return UserService(db_session)


@pytest.fixture
def deposit_service(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> DepositService:
    """Deposit service instance."""
    return DepositService(db_session)


@pytest.fixture
def withdrawal_service(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> WithdrawalService:
    """Withdrawal service instance."""
    return WithdrawalService(db_session)


@pytest.fixture
def referral_service(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> ReferralService:
    """Referral service instance."""
    return ReferralService(db_session)


@pytest.fixture
def reward_service(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> RewardService:
    """Reward service instance."""
    return RewardService(db_session)


@pytest.fixture
def notification_service(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> NotificationService:
    """Notification service instance."""
    return NotificationService(db_session)


@pytest.fixture
def transaction_service(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> TransactionService:
    """Transaction service instance."""
    return TransactionService(db_session)


@pytest.fixture
def support_service(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> SupportService:
    """Support service instance."""
    return SupportService(db_session)


@pytest.fixture
def admin_service(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> AdminService:
    """Admin service instance."""
    return AdminService(db_session)


@pytest.fixture
def blacklist_service(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> BlacklistService:
    """Blacklist service instance."""
    return BlacklistService(db_session)


# ==================== HELPER FIXTURES ====================


@pytest.fixture
def create_user_helper(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> Callable[..., Any]:
    """Helper function to create users dynamically."""

    async def _create_user(
        telegram_id: int | None = None,
        username: str | None = None,
        wallet_address: str | None = None,
        balance: Decimal = Decimal("0"),
        referrer_id: int | None = None,
        **kwargs: Any,
    ) -> User:
        if telegram_id is None:
            base_id = 100000000
            timestamp = int(datetime.now(UTC).timestamp())
            telegram_id = base_id + timestamp
        if username is None:
            username = f"user_{telegram_id}"
        if wallet_address is None:
            wallet_address = "0x" + str(telegram_id) * 8

        user = User(
            telegram_id=telegram_id,
            username=username,
            wallet_address=wallet_address,
            financial_password=hash_password("test123"),
            balance=balance,
            referrer_id=referrer_id,
            **kwargs,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
def create_deposit_helper(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> Callable[..., Any]:
    """Helper function to create deposits dynamically."""

    async def _create_deposit(
        user: User,
        level: int = 1,
        amount: Decimal = Decimal("10"),
        status: str = "confirmed",
        **kwargs: Any,
    ) -> Deposit:
        deposit = Deposit(
            user_id=user.id,
            level=level,
            amount=amount,
            status=status,
            roi_cap_amount=amount * 5,  # 500% cap
            roi_paid_amount=Decimal("0"),
            **kwargs,
        )
        db_session.add(deposit)
        await db_session.commit()
        await db_session.refresh(deposit)
        return deposit

    return _create_deposit


@pytest.fixture
def create_transaction_helper(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> Callable[..., Any]:
    """Helper function to create transactions dynamically."""

    async def _create_transaction(
        user: User,
        transaction_type: str = "deposit",
        amount: Decimal = Decimal("10"),
        status: str = "confirmed",
        **kwargs: Any,
    ) -> Transaction:
        transaction = Transaction(
            user_id=user.id,
            type=transaction_type,
            amount=amount,
            balance_before=user.balance,
            balance_after=user.balance + amount,
            status=status,
            **kwargs,
        )
        db_session.add(transaction)
        await db_session.commit()
        await db_session.refresh(transaction)
        return transaction

    return _create_transaction


# ==================== CLEANUP FIXTURES ====================


@pytest_asyncio.fixture
async def cleanup_test_data(
    db_session: AsyncSession,  # pylint: disable=redefined-outer-name
) -> AsyncGenerator[None, None]:
    """Cleanup test data after test execution."""
    yield

    # Clean up all test data with telegram_id > 100000000
    # Delete in correct order (respecting foreign keys)

    # Get test user IDs
    result = await db_session.execute(
        select(User.id).where(User.telegram_id > 100000000)
    )
    test_user_ids = [row[0] for row in result.fetchall()]

    if test_user_ids:
        # Delete transactions
        await db_session.execute(
            delete(Transaction).where(Transaction.user_id.in_(test_user_ids))
        )
        # Delete deposits
        await db_session.execute(
            delete(Deposit).where(Deposit.user_id.in_(test_user_ids))
        )
        # Delete users
        await db_session.execute(
            delete(User).where(User.telegram_id > 100000000)
        )
        await db_session.commit()


# ==================== MOCK FIXTURES ====================


class MockBlockchainService:
    """Mock blockchain service for testing."""

    async def send_payment(self, _to_address: str, _amount: Decimal) -> str:
        """Mock send payment."""
        return "0x" + "mock_tx_hash" + "0" * 40

    async def get_deposit_events(
        self, _from_block: int | None = None
    ) -> list[Any]:
        """Mock get deposit events."""
        return []

    async def verify_transaction(self, _tx_hash: str) -> dict[str, Any]:
        """Mock verify transaction."""
        return {
            "status": "confirmed",
            "block_number": 123456,
            "from": "0x" + "a" * 40,
            "to": "0x" + "b" * 40,
            "value": "100000000000000000000",  # 100 USDT
        }


class MockNotificationService:
    """Mock notification service for testing."""

    async def send_notification(self, _user_id: int, _message: str) -> bool:
        """Mock send notification."""
        return True

    async def send_admin_notification(self, _message: str) -> bool:
        """Mock send admin notification."""
        return True


@pytest.fixture
def mock_blockchain_service() -> MockBlockchainService:
    """
    Mock blockchain service.

    Mock blockchain service for testing without real blockchain calls.
    """
    return MockBlockchainService()


@pytest.fixture
def mock_notification_service() -> MockNotificationService:
    """
    Mock notification service.

    Mock notification service for testing without real Telegram calls.
    """
    return MockNotificationService()


# ==================== CONSTANTS ====================

# Deposit levels configuration
DEPOSIT_LEVELS = {
    1: {"amount": Decimal("10"), "roi_percent": Decimal("2")},
    2: {"amount": Decimal("50"), "roi_percent": Decimal("2")},
    3: {"amount": Decimal("100"), "roi_percent": Decimal("2")},
    4: {"amount": Decimal("150"), "roi_percent": Decimal("2")},
    5: {"amount": Decimal("300"), "roi_percent": Decimal("2")},
}

# Referral commission percentages
REFERRAL_COMMISSIONS = {
    1: Decimal("0.03"),  # 3% for level 1
    2: Decimal("0.02"),  # 2% for level 2
    3: Decimal("0.05"),  # 5% for level 3
}

# ROI cap multiplier (500%)
ROI_CAP_MULTIPLIER = Decimal("5")
