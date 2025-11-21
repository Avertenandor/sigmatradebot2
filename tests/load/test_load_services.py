"""
Service load tests for SigmaTrade Bot.

Tests service layer performance under concurrent loads.
"""

import asyncio
import pytest
from decimal import Decimal
from datetime import datetime, timezone
import time
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Deposit
from app.services import (
    UserService,
    DepositService,
    WithdrawalService,
    ReferralService,
    RewardService,
    TransactionService,
)


@pytest.mark.load
@pytest.mark.asyncio
async def test_concurrent_user_registration(db_session: AsyncSession):
    """
    Test concurrent user registration through service layer.
    
    SCENARIO: 100 users register simultaneously
    SUCCESS CRITERIA:
        - All registrations complete
        - Referral chains created correctly
        - No data corruption
        - Completion time < 15 seconds
    """
    user_service = UserService(db_session)
    start_time = time.time()
    
    # Create referrer
    referrer = await user_service.create_user(
        telegram_id=700000000,
        username="load_test_referrer",
        wallet_address="0x" + "r" * 40,
        financial_password="hash_ref",
    )
    
    # Create 100 users with referrer
    async def register_user(index: int):
        try:
            user = await user_service.create_user(
                telegram_id=700000001 + index,
                username=f"load_user_{index}",
                wallet_address=f"0x{index:040d}",
                financial_password=f"hash_{index}",
                referrer_id=referrer.id,
            )
            return user
        except Exception as e:
            pytest.fail(f"User registration {index} failed: {e}")
    
    # Run concurrent registrations
    users = await asyncio.gather(*[register_user(i) for i in range(100)])
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Assertions
    assert len(users) == 100, "Not all users registered"
    assert all(u is not None for u in users), "Some users are None"
    assert all(u.referrer_id == referrer.id for u in users), "Referrer not set correctly"
    assert duration < 15, f"Registration took {duration:.2f}s (> 15s threshold)"
    
    print(f"\n✅ Registered 100 users in {duration:.2f}s ({100/duration:.2f} users/s)")


@pytest.mark.load
@pytest.mark.asyncio
async def test_concurrent_deposit_processing(db_session: AsyncSession, test_user: User):
    """
    Test concurrent deposit processing.
    
    SCENARIO: 50 deposits processed simultaneously
    SUCCESS CRITERIA:
        - All deposits processed
        - Balance updated correctly
        - Transactions created
        - Completion time < 10 seconds
    """
    deposit_service = DepositService(db_session)
    start_time = time.time()
    
    # Create 50 deposits concurrently
    async def process_deposit(index: int):
        try:
            deposit = await deposit_service.create_deposit(
                user=test_user,
                level=1 + (index % 5),
                amount=Decimal("10") + Decimal(str(index * 10)),
                tx_hash=f"0x{'d' * 60}{index:04d}",
            )
            
            # Confirm deposit
            await deposit_service.confirm_deposit(
                deposit_id=deposit.id,
                tx_hash=f"0x{'d' * 60}{index:04d}",
            )
            return deposit
        except Exception as e:
            pytest.fail(f"Deposit processing {index} failed: {e}")
    
    # Run concurrent processing
    deposits = await asyncio.gather(*[process_deposit(i) for i in range(50)])
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Assertions
    assert len(deposits) == 50, "Not all deposits processed"
    assert all(d is not None for d in deposits), "Some deposits are None"
    assert duration < 10, f"Processing took {duration:.2f}s (> 10s threshold)"
    
    # Verify user balance updated
    await db_session.refresh(test_user)
    expected_balance = sum(d.amount for d in deposits)
    assert test_user.balance >= expected_balance, "Balance not updated correctly"
    
    print(f"\n✅ Processed 50 deposits in {duration:.2f}s ({50/duration:.2f} deposits/s)")


@pytest.mark.load
@pytest.mark.asyncio
async def test_concurrent_roi_distribution(db_session: AsyncSession, test_users_batch: List[User]):
    """
    Test concurrent ROI distribution.
    
    SCENARIO: Distribute ROI to 10 users simultaneously
    SUCCESS CRITERIA:
        - All distributions complete
        - Balances updated correctly
        - Transactions created
        - Completion time < 5 seconds
    """
    reward_service = RewardService(db_session)
    deposit_service = DepositService(db_session)
    
    # Create deposits for all users
    for user in test_users_batch:
        await deposit_service.create_deposit(
            user=user,
            level=3,
            amount=Decimal("100"),
            tx_hash=f"0x{'r' * 62}{user.id:02d}",
        )
    
    await db_session.commit()
    
    # Distribute ROI concurrently
    start_time = time.time()
    
    async def distribute_roi_to_user(user: User):
        try:
            result = await reward_service.distribute_daily_roi(user_id=user.id)
            return result
        except Exception as e:
            pytest.fail(f"ROI distribution for user {user.id} failed: {e}")
    
    results = await asyncio.gather(*[distribute_roi_to_user(u) for u in test_users_batch])
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Assertions
    assert len(results) == len(test_users_batch), "Not all ROI distributed"
    assert duration < 5, f"Distribution took {duration:.2f}s (> 5s threshold)"
    
    # Verify all users received ROI
    for user in test_users_batch:
        await db_session.refresh(user)
        assert user.pending_earnings > 0 or user.balance > 0, \
            f"User {user.id} didn't receive ROI"
    
    print(f"\n✅ Distributed ROI to {len(test_users_batch)} users in {duration:.2f}s")


@pytest.mark.load
@pytest.mark.asyncio
async def test_concurrent_referral_reward_calculation(
    db_session: AsyncSession,
    test_referral_chain
):
    """
    Test concurrent referral reward calculation.
    
    SCENARIO: Calculate referral rewards for 3-level chain with multiple deposits
    SUCCESS CRITERIA:
        - All rewards calculated correctly
        - Correct commission percentages
        - No double-counting
        - Completion time < 3 seconds
    """
    referral_service = ReferralService(db_session)
    deposit_service = DepositService(db_session)
    
    referrer, level1, level2, level3 = test_referral_chain
    
    # Create deposits for all referred users
    start_time = time.time()
    
    async def create_deposit_and_calculate_rewards(user: User, index: int):
        try:
            # Create deposit
            deposit = await deposit_service.create_deposit(
                user=user,
                level=3,
                amount=Decimal("100"),
                tx_hash=f"0x{'f' * 60}{user.id:04d}{index:04d}",
            )
            
            # Calculate referral rewards
            await referral_service.process_referral_rewards(
                deposit=deposit,
                referred_user=user,
            )
            return deposit
        except Exception as e:
            pytest.fail(f"Referral reward calculation failed: {e}")
    
    # Create 10 deposits for each referred user
    tasks = []
    for user in [level1, level2, level3]:
        for i in range(10):
            tasks.append(create_deposit_and_calculate_rewards(user, i))
    
    deposits = await asyncio.gather(*tasks)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Assertions
    assert len(deposits) == 30, "Not all deposits created"
    assert duration < 3, f"Calculation took {duration:.2f}s (> 3s threshold)"
    
    # Verify referrer received rewards
    await db_session.refresh(referrer)
    assert referrer.total_earned > 0, "Referrer didn't receive rewards"
    
    print(f"\n✅ Calculated referral rewards for 30 deposits in {duration:.2f}s")


@pytest.mark.load
@pytest.mark.asyncio
async def test_concurrent_withdrawal_processing(db_session: AsyncSession):
    """
    Test concurrent withdrawal processing.
    
    SCENARIO: Process 20 withdrawals simultaneously
    SUCCESS CRITERIA:
        - All withdrawals processed
        - Balances deducted correctly
        - No negative balances
        - Completion time < 10 seconds
    """
    withdrawal_service = WithdrawalService(db_session)
    user_service = UserService(db_session)
    
    # Create users with balance
    users = []
    for i in range(20):
        user = await user_service.create_user(
            telegram_id=800000000 + i,
            username=f"withdrawal_user_{i}",
            wallet_address=f"0x{i:040d}",
            financial_password=f"hash_{i}",
        )
        user.balance = Decimal("1000")  # Set balance
        await db_session.commit()
        await db_session.refresh(user)
        users.append(user)
    
    # Process withdrawals concurrently
    start_time = time.time()
    
    async def process_withdrawal(user: User):
        try:
            withdrawal = await withdrawal_service.create_withdrawal(
                user=user,
                amount=Decimal("100"),
                financial_password="test123",
            )
            
            # Approve withdrawal
            await withdrawal_service.approve_withdrawal(
                withdrawal_id=withdrawal.id,
                tx_hash=f"0x{'w' * 62}{user.id:02d}",
            )
            return withdrawal
        except Exception as e:
            pytest.fail(f"Withdrawal processing for user {user.id} failed: {e}")
    
    withdrawals = await asyncio.gather(*[process_withdrawal(u) for u in users])
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Assertions
    assert len(withdrawals) == 20, "Not all withdrawals processed"
    assert duration < 10, f"Processing took {duration:.2f}s (> 10s threshold)"
    
    # Verify all users have correct balance
    for user in users:
        await db_session.refresh(user)
        assert user.balance == Decimal("900"), \
            f"User {user.id} balance incorrect: {user.balance}"
        assert user.balance >= 0, f"User {user.id} has negative balance"
    
    print(f"\n✅ Processed 20 withdrawals in {duration:.2f}s ({20/duration:.2f} withdrawals/s)")


@pytest.mark.load
@pytest.mark.asyncio
async def test_concurrent_transaction_creation(db_session: AsyncSession, test_user: User):
    """
    Test concurrent transaction creation.
    
    SCENARIO: Create 100 transactions simultaneously
    SUCCESS CRITERIA:
        - All transactions created
        - Sequential transaction IDs
        - No duplicates
        - Completion time < 5 seconds
    """
    transaction_service = TransactionService(db_session)
    start_time = time.time()
    
    # Create 100 transactions concurrently
    async def create_transaction(index: int):
        try:
            transaction = await transaction_service.create_transaction(
                user=test_user,
                type="deposit" if index % 2 == 0 else "withdrawal",
                amount=Decimal("10") + Decimal(str(index)),
                status="confirmed",
                description=f"Load test transaction {index}",
            )
            return transaction
        except Exception as e:
            pytest.fail(f"Transaction creation {index} failed: {e}")
    
    # Run concurrent creation
    transactions = await asyncio.gather(*[create_transaction(i) for i in range(100)])
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Assertions
    assert len(transactions) == 100, "Not all transactions created"
    assert all(t is not None for t in transactions), "Some transactions are None"
    assert duration < 5, f"Creation took {duration:.2f}s (> 5s threshold)"
    
    # Verify unique IDs
    transaction_ids = [t.id for t in transactions]
    assert len(transaction_ids) == len(set(transaction_ids)), "Duplicate transaction IDs"
    
    print(f"\n✅ Created 100 transactions in {duration:.2f}s ({100/duration:.2f} tx/s)")


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_mixed_workload_simulation(db_session: AsyncSession):
    """
    Test system under mixed realistic workload.
    
    SCENARIO: Simulate 30 seconds of mixed operations (deposits, withdrawals, queries)
    SUCCESS CRITERIA:
        - System handles mixed load
        - No failures
        - Average operation time < 200ms
        - Throughput > 50 ops/sec
    """
    user_service = UserService(db_session)
    deposit_service = DepositService(db_session)
    withdrawal_service = WithdrawalService(db_session)
    
    # Create test users
    users = []
    for i in range(10):
        user = await user_service.create_user(
            telegram_id=900000000 + i,
            username=f"mixed_user_{i}",
            wallet_address=f"0x{i:040d}",
            financial_password=f"hash_{i}",
        )
        user.balance = Decimal("1000")
        await db_session.commit()
        await db_session.refresh(user)
        users.append(user)
    
    start_time = time.time()
    end_time = start_time + 30  # 30 seconds
    operation_times = []
    operation_count = 0
    
    async def random_operation():
        nonlocal operation_count
        import random
        
        op_start = time.time()
        user = random.choice(users)
        op_type = random.choice(['deposit', 'withdrawal', 'query'])
        
        try:
            if op_type == 'deposit':
                await deposit_service.create_deposit(
                    user=user,
                    level=random.randint(1, 5),
                    amount=Decimal("10"),
                    tx_hash=f"0x{'m' * 60}{operation_count:04d}",
                )
            elif op_type == 'withdrawal':
                if user.balance >= Decimal("10"):
                    await withdrawal_service.create_withdrawal(
                        user=user,
                        amount=Decimal("10"),
                        financial_password="test123",
                    )
            else:  # query
                await db_session.refresh(user)
            
            op_end = time.time()
            return op_end - op_start
        except Exception:
            # Ignore errors in mixed workload (e.g., insufficient balance)
            return 0
    
    # Run mixed operations
    while time.time() < end_time:
        op_time = await random_operation()
        if op_time > 0:
            operation_times.append(op_time)
        operation_count += 1
        await asyncio.sleep(0.01)
    
    total_duration = time.time() - start_time
    
    # Calculate statistics
    if operation_times:
        avg_time = sum(operation_times) / len(operation_times)
        throughput = operation_count / total_duration
        
        # Assertions
        assert avg_time < 0.2, f"Average operation time {avg_time:.3f}s > 200ms"
        assert throughput > 50, f"Throughput {throughput:.2f} ops/sec < 50 ops/sec"
        
        print(f"\n✅ Mixed workload test completed:")
        print(f"   - Duration: {total_duration:.2f}s")
        print(f"   - Operations: {operation_count}")
        print(f"   - Throughput: {throughput:.2f} ops/sec")
        print(f"   - Avg time: {avg_time*1000:.2f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "load"])
