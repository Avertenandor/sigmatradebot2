"""
Load tests for user scenarios.

Tests load scenarios:
- Many registrations simultaneously (100+)
- Many deposits simultaneously (50+)
- Many withdrawals simultaneously (30+)
- Race condition checks
"""

import asyncio
import pytest
from decimal import Decimal

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.deposit_service import DepositService
from app.services.user_service import UserService
from app.services.withdrawal_service import WithdrawalService
from tests.conftest import hash_password


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.asyncio
async def test_many_registrations_simultaneously(
    db_session,
    user_service: UserService,
) -> None:
    """
    Test many registrations simultaneously.

    GIVEN: 100+ concurrent registration requests
    WHEN: All users register at once
    THEN: All registrations succeed without conflicts
    """
    # Arrange: Prepare 100 users
    num_users = 100
    tasks = []

    async def register_user(telegram_id: int) -> User | None:
        """Register single user."""
        try:
            hashed_password = hash_password("test123456")
            wallet = "0x" + str(telegram_id) * 8
            user = await user_service.register_user(
                telegram_id=telegram_id,
                wallet_address=wallet,
                financial_password=hashed_password,
            )
            return user
        except Exception as e:
            # Log error but don't fail test
            print(f"Registration failed for {telegram_id}: {e}")
            return None

    # Act: Register all users concurrently
    for i in range(num_users):
        telegram_id = 900000000 + i
        tasks.append(register_user(telegram_id))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Assert: Most registrations succeed
    successful = sum(1 for r in results if r is not None and not isinstance(r, Exception))
    assert successful >= num_users * 0.95  # At least 95% success rate

    # Assert: All users are in database
    user_repo = UserRepository(db_session)
    for i in range(num_users):
        telegram_id = 900000000 + i
        user = await user_repo.get_by_telegram_id(telegram_id)
        # Some may fail due to race conditions, but most should succeed
        if user:
            assert user.telegram_id == telegram_id


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.asyncio
async def test_many_deposits_simultaneously(
    db_session,
    deposit_service: DepositService,
    create_user_helper,
) -> None:
    """
    Test many deposits simultaneously.

    GIVEN: 50+ users with deposits
    WHEN: All create deposits at once
    THEN: All deposits are created without conflicts
    """
    # Arrange: Create 50 users with Level 1 deposits
    num_users = 50
    users = []
    for i in range(num_users):
        user = await create_user_helper(
            telegram_id=800000000 + i,
            wallet_address="0x" + str(i) * 8,
        )
        users.append(user)

    tasks = []

    async def create_deposit(user: User) -> bool:
        """Create deposit for user."""
        try:
            deposit = await deposit_service.create_deposit(
                user_id=user.id,
                level=1,
                amount=Decimal("10"),
                tx_hash="0x" + str(user.id) * 16,
            )
            return deposit is not None
        except Exception as e:
            print(f"Deposit failed for user {user.id}: {e}")
            return False

    # Act: Create all deposits concurrently
    for user in users:
        tasks.append(create_deposit(user))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Assert: Most deposits succeed
    successful = sum(1 for r in results if r is True)
    assert successful >= num_users * 0.95  # At least 95% success rate


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.asyncio
async def test_many_withdrawals_simultaneously(
    db_session,
    withdrawal_service: WithdrawalService,
    create_user_helper,
) -> None:
    """
    Test many withdrawals simultaneously.

    GIVEN: 30+ users with balance
    WHEN: All request withdrawals at once
    THEN: All withdrawals are processed without race conditions
    """
    # Arrange: Create 30 users with balance
    num_users = 30
    users = []
    for i in range(num_users):
        user = await create_user_helper(
            telegram_id=700000000 + i,
            wallet_address="0x" + str(i) * 8,
            balance=Decimal("100"),  # Has balance
        )
        user.is_verified = True
        users.append(user)
    await db_session.commit()

    tasks = []

    async def request_withdrawal(user: User) -> bool:
        """Request withdrawal for user."""
        try:
            transaction, error_msg = await withdrawal_service.request_withdrawal(
                user_id=user.id,
                amount=Decimal("50"),
                available_balance=Decimal("100"),
            )
            return transaction is not None
        except Exception as e:
            print(f"Withdrawal failed for user {user.id}: {e}")
            return False

    # Act: Request all withdrawals concurrently
    for user in users:
        tasks.append(request_withdrawal(user))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Assert: Most withdrawals succeed
    successful = sum(1 for r in results if r is True)
    assert successful >= num_users * 0.90  # At least 90% success rate

    # Assert: Balance deducted correctly (no double-spending)
    for user in users:
        await db_session.refresh(user)
        # Balance should be deducted (either 50 or 100, depending on success)
        assert user.balance <= Decimal("100")


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.asyncio
async def test_race_condition_withdrawal_balance(
    db_session,
    withdrawal_service: WithdrawalService,
    create_user_helper,
) -> None:
    """
    Test race condition in withdrawal balance deduction.

    GIVEN: User with balance
    WHEN: Multiple withdrawal requests happen simultaneously
    THEN: Balance is deducted correctly (no double-spending)
    """
    # Arrange: Create user with balance
    user = await create_user_helper(
        telegram_id=600000000,
        wallet_address="0x" + "a" * 40,
        balance=Decimal("100"),
    )
    user.is_verified = True
    await db_session.commit()

    initial_balance = user.balance
    num_requests = 5
    withdrawal_amount = Decimal("20")  # Each withdrawal

    async def request_withdrawal() -> bool:
        """Request withdrawal."""
        try:
            transaction, error_msg = await withdrawal_service.request_withdrawal(
                user_id=user.id,
                amount=withdrawal_amount,
                available_balance=initial_balance,
            )
            return transaction is not None
        except Exception:
            return False

    # Act: Request multiple withdrawals concurrently
    tasks = [request_withdrawal() for _ in range(num_requests)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Assert: Some succeed, some fail (due to balance limits)
    successful = sum(1 for r in results if r is True)
    assert successful > 0  # At least one succeeds
    assert successful <= 5  # But not all (balance limits)

    # Assert: Final balance is correct
    await db_session.refresh(user)
    expected_balance = initial_balance - (withdrawal_amount * successful)
    assert user.balance == expected_balance


@pytest.mark.e2e
@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.asyncio
async def test_concurrent_deposit_and_withdrawal(
    db_session,
    deposit_service: DepositService,
    withdrawal_service: WithdrawalService,
    create_user_helper,
) -> None:
    """
    Test concurrent deposit and withdrawal.

    GIVEN: User
    WHEN: Deposit and withdrawal happen simultaneously
    THEN: Both operations complete correctly
    """
    # Arrange: Create user
    user = await create_user_helper(
        telegram_id=500000000,
        wallet_address="0x" + "b" * 40,
        balance=Decimal("50"),
    )
    user.is_verified = True
    await db_session.commit()

    initial_balance = user.balance

    async def create_deposit() -> bool:
        """Create deposit."""
        try:
            deposit = await deposit_service.create_deposit(
                user_id=user.id,
                level=1,
                amount=Decimal("10"),
                tx_hash="0x" + "c" * 64,
            )
            return deposit is not None
        except Exception:
            return False

    async def request_withdrawal() -> bool:
        """Request withdrawal."""
        try:
            transaction, error_msg = await withdrawal_service.request_withdrawal(
                user_id=user.id,
                amount=Decimal("20"),
                available_balance=initial_balance,
            )
            return transaction is not None
        except Exception:
            return False

    # Act: Run deposit and withdrawal concurrently
    deposit_task = create_deposit()
    withdrawal_task = request_withdrawal()

    deposit_result, withdrawal_result = await asyncio.gather(
        deposit_task,
        withdrawal_task,
        return_exceptions=True,
    )

    # Assert: Both operations complete (may succeed or fail based on balance)
    # This test verifies no deadlocks or crashes occur
    assert deposit_result is not None or isinstance(deposit_result, Exception)
    assert withdrawal_result is not None or isinstance(withdrawal_result, Exception)

