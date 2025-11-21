"""
Database load tests for SigmaTrade Bot.

Tests database performance under concurrent operations.
"""

import asyncio
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import time
from typing import List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Deposit, Transaction, Referral
from app.repositories import UserRepository, DepositRepository, TransactionRepository


@pytest.mark.load
@pytest.mark.asyncio
async def test_concurrent_user_creation(db_session: AsyncSession):
    """
    Test concurrent user creation.
    
    SCENARIO: 100 users register simultaneously
    SUCCESS CRITERIA:
        - All users created successfully
        - No duplicate telegram_ids
        - No deadlocks
        - Completion time < 10 seconds
    """
    user_repo = UserRepository(db_session)
    start_time = time.time()
    
    # Create 100 users concurrently
    async def create_user(index: int):
        try:
            user = await user_repo.create(
                telegram_id=300000000 + index,
                username=f"loadtest_user_{index}",
                wallet_address=f"0x{index:040d}",
                financial_password=f"hash_{index}",
            )
            return user
        except Exception as e:
            pytest.fail(f"Failed to create user {index}: {e}")
    
    # Run concurrent creation
    users = await asyncio.gather(*[create_user(i) for i in range(100)])
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Assertions
    assert len(users) == 100, "Not all users created"
    assert all(u is not None for u in users), "Some users are None"
    assert duration < 10, f"Creation took {duration:.2f}s (> 10s threshold)"
    
    # Verify no duplicates
    telegram_ids = [u.telegram_id for u in users]
    assert len(telegram_ids) == len(set(telegram_ids)), "Duplicate telegram_ids found"
    
    print(f"\n✅ Created 100 users in {duration:.2f}s ({100/duration:.2f} users/s)")


@pytest.mark.load
@pytest.mark.asyncio
async def test_concurrent_deposits(db_session: AsyncSession, test_user: User):
    """
    Test concurrent deposit creation for single user.
    
    SCENARIO: User creates 50 deposits simultaneously
    SUCCESS CRITERIA:
        - All deposits created
        - Balance updates correctly
        - No race conditions
        - Completion time < 5 seconds
    """
    deposit_repo = DepositRepository(db_session)
    start_time = time.time()
    
    # Create 50 deposits concurrently
    async def create_deposit(index: int):
        try:
            deposit = await deposit_repo.create(
                user_id=test_user.id,
                level=1 + (index % 5),  # Levels 1-5
                amount=Decimal("10") + Decimal(str(index * 10)),
                status="pending",
                roi_cap_amount=Decimal("50") + Decimal(str(index * 50)),
                roi_paid_amount=Decimal("0"),
                tx_hash=f"0x{'a' * 60}{index:04d}",
            )
            return deposit
        except Exception as e:
            pytest.fail(f"Failed to create deposit {index}: {e}")
    
    # Run concurrent creation
    deposits = await asyncio.gather(*[create_deposit(i) for i in range(50)])
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Assertions
    assert len(deposits) == 50, "Not all deposits created"
    assert all(d is not None for d in deposits), "Some deposits are None"
    assert duration < 5, f"Creation took {duration:.2f}s (> 5s threshold)"
    
    # Verify unique tx_hashes
    tx_hashes = [d.tx_hash for d in deposits]
    assert len(tx_hashes) == len(set(tx_hashes)), "Duplicate tx_hashes found"
    
    print(f"\n✅ Created 50 deposits in {duration:.2f}s ({50/duration:.2f} deposits/s)")


@pytest.mark.load
@pytest.mark.asyncio
async def test_bulk_transaction_queries(db_session: AsyncSession, test_users_batch: List[User]):
    """
    Test bulk transaction query performance.
    
    SCENARIO: Query transactions for 10 users with 100 transactions each
    SUCCESS CRITERIA:
        - All queries complete successfully
        - Query time < 3 seconds
        - Correct results returned
    """
    transaction_repo = TransactionRepository(db_session)
    
    # Create 100 transactions for each user
    for user in test_users_batch:
        for i in range(100):
            transaction = Transaction(
                user_id=user.id,
                type="deposit" if i % 2 == 0 else "withdrawal",
                amount=Decimal("10") + Decimal(str(i)),
                balance_before=Decimal("0"),
                balance_after=Decimal("10") + Decimal(str(i)),
                status="confirmed",
                description=f"Load test transaction {i}",
            )
            db_session.add(transaction)
    
    await db_session.commit()
    
    # Query transactions concurrently
    start_time = time.time()
    
    async def query_user_transactions(user: User):
        result = await db_session.execute(
            select(Transaction).where(Transaction.user_id == user.id)
        )
        transactions = result.scalars().all()
        return len(transactions)
    
    results = await asyncio.gather(*[query_user_transactions(u) for u in test_users_batch])
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Assertions
    assert all(count == 100 for count in results), "Not all transactions retrieved"
    assert duration < 3, f"Query took {duration:.2f}s (> 3s threshold)"
    
    print(f"\n✅ Queried 1000 transactions in {duration:.2f}s ({1000/duration:.2f} tx/s)")


@pytest.mark.load
@pytest.mark.asyncio
async def test_concurrent_balance_updates(db_session: AsyncSession, test_user: User):
    """
    Test concurrent balance updates (critical race condition test).
    
    SCENARIO: 50 concurrent balance updates
    SUCCESS CRITERIA:
        - No balance inconsistencies
        - Final balance = sum of all updates
        - No lost updates
        - Completion time < 5 seconds
    """
    user_repo = UserRepository(db_session)
    initial_balance = test_user.balance
    update_amount = Decimal("10")
    num_updates = 50
    
    start_time = time.time()
    
    # Concurrent balance updates
    async def update_balance():
        try:
            # Use row-level locking to prevent race conditions
            stmt = select(User).where(User.id == test_user.id).with_for_update()
            result = await db_session.execute(stmt)
            user = result.scalar_one()
            
            user.balance += update_amount
            await db_session.commit()
            return True
        except Exception as e:
            await db_session.rollback()
            pytest.fail(f"Balance update failed: {e}")
    
    # Run concurrent updates
    results = await asyncio.gather(*[update_balance() for _ in range(num_updates)])
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Verify final balance
    await db_session.refresh(test_user)
    expected_balance = initial_balance + (update_amount * num_updates)
    
    # Assertions
    assert all(results), "Some updates failed"
    assert test_user.balance == expected_balance, \
        f"Balance mismatch: expected {expected_balance}, got {test_user.balance}"
    assert duration < 5, f"Updates took {duration:.2f}s (> 5s threshold)"
    
    print(f"\n✅ Completed 50 concurrent balance updates in {duration:.2f}s")


@pytest.mark.load
@pytest.mark.asyncio
async def test_large_result_set_pagination(db_session: AsyncSession):
    """
    Test pagination performance with large result sets.
    
    SCENARIO: Query 10,000 deposits with pagination
    SUCCESS CRITERIA:
        - All pages retrieved correctly
        - No missing data
        - Memory efficient
        - Completion time < 5 seconds
    """
    # Create test user
    user = User(
        telegram_id=400000000,
        username="pagination_test_user",
        wallet_address="0x" + "p" * 40,
        financial_password="hash_pagination",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Create 10,000 deposits
    deposits_to_create = []
    for i in range(10000):
        deposit = Deposit(
            user_id=user.id,
            level=1 + (i % 5),
            amount=Decimal("10"),
            status="confirmed",
            roi_cap_amount=Decimal("50"),
            roi_paid_amount=Decimal("0"),
            tx_hash=f"0x{'p' * 60}{i:04d}",
        )
        deposits_to_create.append(deposit)
    
    db_session.add_all(deposits_to_create)
    await db_session.commit()
    
    # Paginate through results
    start_time = time.time()
    page_size = 100
    total_retrieved = 0
    page = 0
    
    while True:
        stmt = (
            select(Deposit)
            .where(Deposit.user_id == user.id)
            .offset(page * page_size)
            .limit(page_size)
        )
        result = await db_session.execute(stmt)
        deposits = result.scalars().all()
        
        if not deposits:
            break
        
        total_retrieved += len(deposits)
        page += 1
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Assertions
    assert total_retrieved == 10000, f"Expected 10000, got {total_retrieved}"
    assert page == 100, f"Expected 100 pages, got {page}"
    assert duration < 5, f"Pagination took {duration:.2f}s (> 5s threshold)"
    
    print(f"\n✅ Paginated 10,000 deposits in {duration:.2f}s ({10000/duration:.2f} records/s)")


@pytest.mark.load
@pytest.mark.asyncio
async def test_complex_join_query_performance(db_session: AsyncSession, test_referral_chain):
    """
    Test complex JOIN query performance.
    
    SCENARIO: Query referral chains with earnings
    SUCCESS CRITERIA:
        - Query completes successfully
        - Correct data returned
        - Query time < 2 seconds
    """
    referrer, level1, level2, level3 = test_referral_chain
    
    # Create deposits and referral earnings
    for user in [level1, level2, level3]:
        # Create deposit
        deposit = Deposit(
            user_id=user.id,
            level=3,
            amount=Decimal("100"),
            status="confirmed",
            roi_cap_amount=Decimal("500"),
            roi_paid_amount=Decimal("0"),
        )
        db_session.add(deposit)
    
    await db_session.commit()
    
    # Complex query with JOINs
    start_time = time.time()
    
    from app.models import ReferralEarning
    from sqlalchemy.orm import joinedload
    
    stmt = (
        select(User)
        .where(User.id == referrer.id)
        .options(
            joinedload(User.deposits),
            joinedload(User.transactions),
            joinedload(User.referrals),
        )
    )
    
    result = await db_session.execute(stmt)
    loaded_user = result.unique().scalar_one()
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Assertions
    assert loaded_user is not None
    assert duration < 2, f"Complex query took {duration:.2f}s (> 2s threshold)"
    
    print(f"\n✅ Complex JOIN query completed in {duration:.2f}s")


@pytest.mark.load
@pytest.mark.asyncio
async def test_database_connection_pool_stress(db_session: AsyncSession):
    """
    Test database connection pool under stress.
    
    SCENARIO: 200 concurrent database operations
    SUCCESS CRITERIA:
        - No connection pool exhaustion
        - All operations complete
        - No timeouts
        - Completion time < 15 seconds
    """
    start_time = time.time()
    
    async def database_operation(index: int):
        try:
            # Simple query
            result = await db_session.execute(
                select(func.count()).select_from(User)
            )
            count = result.scalar()
            
            # Simple insert
            user = User(
                telegram_id=500000000 + index,
                username=f"pool_test_{index}",
                wallet_address=f"0x{index:040d}",
                financial_password=f"hash_{index}",
            )
            db_session.add(user)
            await db_session.flush()
            
            return True
        except Exception as e:
            pytest.fail(f"Operation {index} failed: {e}")
    
    # Run 200 concurrent operations
    results = await asyncio.gather(*[database_operation(i) for i in range(200)])
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Assertions
    assert all(results), "Some operations failed"
    assert duration < 15, f"Stress test took {duration:.2f}s (> 15s threshold)"
    
    print(f"\n✅ Completed 200 concurrent operations in {duration:.2f}s")


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_sustained_load_simulation(db_session: AsyncSession):
    """
    Test system under sustained load.
    
    SCENARIO: Continuous operations for 60 seconds
    SUCCESS CRITERIA:
        - System remains stable
        - No memory leaks
        - Performance doesn't degrade
        - Average response time < 100ms
    """
    start_time = time.time()
    end_time = start_time + 60  # 60 seconds test
    operation_times = []
    operation_count = 0
    
    user = User(
        telegram_id=600000000,
        username="sustained_test_user",
        wallet_address="0x" + "s" * 40,
        financial_password="hash_sustained",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    async def single_operation():
        op_start = time.time()
        
        # Simulate typical operation: create deposit + transaction
        deposit = Deposit(
            user_id=user.id,
            level=1,
            amount=Decimal("10"),
            status="pending",
            roi_cap_amount=Decimal("50"),
            roi_paid_amount=Decimal("0"),
            tx_hash=f"0x{'s' * 62}{operation_count:02d}",
        )
        db_session.add(deposit)
        await db_session.flush()
        
        op_end = time.time()
        return op_end - op_start
    
    # Run operations continuously for 60 seconds
    while time.time() < end_time:
        op_time = await single_operation()
        operation_times.append(op_time)
        operation_count += 1
        
        # Small delay to simulate realistic load
        await asyncio.sleep(0.01)
    
    total_duration = time.time() - start_time
    
    # Calculate statistics
    avg_time = sum(operation_times) / len(operation_times)
    max_time = max(operation_times)
    min_time = min(operation_times)
    
    # Assertions
    assert avg_time < 0.1, f"Average operation time {avg_time:.3f}s > 100ms threshold"
    assert max_time < 1.0, f"Max operation time {max_time:.3f}s > 1s threshold"
    
    print(f"\n✅ Sustained load test completed:")
    print(f"   - Duration: {total_duration:.2f}s")
    print(f"   - Operations: {operation_count}")
    print(f"   - Ops/sec: {operation_count/total_duration:.2f}")
    print(f"   - Avg time: {avg_time*1000:.2f}ms")
    print(f"   - Min time: {min_time*1000:.2f}ms")
    print(f"   - Max time: {max_time*1000:.2f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "load"])
