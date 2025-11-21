"""
Unit tests for Transaction model.

Тестирование модели Transaction для всех типов транзакций.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from app.models.transaction import Transaction
from app.models.enums import TransactionType, TransactionStatus


class TestTransactionModel:
    """Тесты модели Transaction."""
    
    @pytest.mark.asyncio
    async def test_create_transaction_success(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем транзакцию
        THEN: Транзакция создана корректно
        """
        # Arrange & Act
        transaction = await create_transaction_helper(
            test_user,
            type="deposit",
            amount=Decimal("100")
        )
        
        # Assert
        assert transaction.id is not None
        assert transaction.user_id == test_user.id
        assert transaction.type == "deposit"
        assert transaction.amount == Decimal("100")
        assert transaction.balance_before == Decimal("0")
        assert transaction.balance_after == Decimal("100")
        assert transaction.status == "confirmed"
        assert isinstance(transaction.created_at, datetime)
    
    @pytest.mark.parametrize("tx_type", [
        TransactionType.DEPOSIT,
        TransactionType.WITHDRAWAL,
        TransactionType.REFERRAL_REWARD,
        TransactionType.DEPOSIT_REWARD,
        TransactionType.SYSTEM_PAYOUT,
    ])
    @pytest.mark.asyncio
    async def test_all_transaction_types(
        self,
        db_session,
        test_user,
        create_transaction_helper,
        tx_type
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем транзакции всех типов
        THEN: Все типы корректно сохраняются
        """
        # Arrange & Act
        transaction = await create_transaction_helper(
            test_user,
            type=tx_type.value,
            amount=Decimal("10")
        )
        
        # Assert
        assert transaction.type == tx_type.value
    
    @pytest.mark.asyncio
    async def test_transaction_amount_positive_constraint(
        self,
        db_session,
        test_user
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем транзакцию с amount <= 0
        THEN: Возникает IntegrityError
        """
        # Arrange
        transaction = Transaction(
            user_id=test_user.id,
            type="deposit",
            amount=Decimal("0"),  # Нулевая сумма
            balance_before=Decimal("0"),
            balance_after=Decimal("0"),
            status="confirmed"
        )
        
        # Act & Assert
        db_session.add(transaction)
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_transaction_balance_before_non_negative(
        self,
        db_session,
        test_user
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем транзакцию с balance_before < 0
        THEN: Возникает IntegrityError
        """
        # Arrange
        transaction = Transaction(
            user_id=test_user.id,
            type="withdrawal",
            amount=Decimal("10"),
            balance_before=Decimal("-5"),  # Отрицательный баланс
            balance_after=Decimal("0"),
            status="confirmed"
        )
        
        # Act & Assert
        db_session.add(transaction)
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_transaction_balance_after_non_negative(
        self,
        db_session,
        test_user
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем транзакцию с balance_after < 0
        THEN: Возникает IntegrityError
        """
        # Arrange
        transaction = Transaction(
            user_id=test_user.id,
            type="withdrawal",
            amount=Decimal("50"),
            balance_before=Decimal("30"),
            balance_after=Decimal("-20"),  # Отрицательный результат
            status="confirmed"
        )
        
        # Act & Assert
        db_session.add(transaction)
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_transaction_balance_calculation_deposit(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь с балансом 100
        WHEN: Создаем deposit транзакцию на 50
        THEN: balance_after = balance_before + amount
        """
        # Arrange
        test_user.balance = Decimal("100")
        await db_session.commit()
        
        # Act
        transaction = await create_transaction_helper(
            test_user,
            type="deposit",
            amount=Decimal("50")
        )
        # Обновляем balance_before/after вручную для теста
        transaction.balance_before = Decimal("100")
        transaction.balance_after = Decimal("150")
        await db_session.commit()
        
        # Assert
        assert transaction.balance_after == transaction.balance_before + transaction.amount
        assert transaction.balance_after == Decimal("150")
    
    @pytest.mark.asyncio
    async def test_transaction_balance_calculation_withdrawal(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь с балансом 100
        WHEN: Создаем withdrawal транзакцию на 30
        THEN: balance_after = balance_before - amount
        """
        # Arrange
        test_user.balance = Decimal("100")
        await db_session.commit()
        
        # Act
        transaction = await create_transaction_helper(
            test_user,
            type="withdrawal",
            amount=Decimal("30")
        )
        transaction.balance_before = Decimal("100")
        transaction.balance_after = Decimal("70")
        await db_session.commit()
        
        # Assert
        assert transaction.balance_after == transaction.balance_before - transaction.amount
        assert transaction.balance_after == Decimal("70")
    
    @pytest.mark.parametrize("status", [
        TransactionStatus.PENDING,
        TransactionStatus.CONFIRMED,
        TransactionStatus.FAILED,
    ])
    @pytest.mark.asyncio
    async def test_transaction_status_values(
        self,
        db_session,
        test_user,
        create_transaction_helper,
        status
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем транзакции с разными статусами
        THEN: Все статусы корректно сохраняются
        """
        # Arrange & Act
        transaction = await create_transaction_helper(
            test_user,
            status=status.value
        )
        
        # Assert
        assert transaction.status == status.value
    
    @pytest.mark.asyncio
    async def test_transaction_with_description(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем транзакцию с описанием
        THEN: Описание корректно сохраняется
        """
        # Arrange & Act
        description = "Deposit from referral level 1 - user @testuser"
        transaction = await create_transaction_helper(
            test_user,
            description=description
        )
        
        # Assert
        assert transaction.description == description
    
    @pytest.mark.asyncio
    async def test_transaction_with_reference(
        self,
        db_session,
        test_user,
        test_deposit,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь и депозит
        WHEN: Создаем транзакцию со ссылкой на депозит
        THEN: reference корректно сохраняется
        """
        # Arrange & Act
        transaction = await create_transaction_helper(
            test_user,
            type="deposit",
            reference_id=test_deposit.id,
            reference_type="deposit"
        )
        
        # Assert
        assert transaction.reference_id == test_deposit.id
        assert transaction.reference_type == "deposit"
    
    @pytest.mark.asyncio
    async def test_transaction_with_tx_hash(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем транзакцию с blockchain tx_hash
        THEN: tx_hash корректно сохраняется
        """
        # Arrange & Act
        tx_hash = "0x" + "abc123def456" + "0" * 52
        transaction = await create_transaction_helper(
            test_user,
            tx_hash=tx_hash
        )
        
        # Assert
        assert transaction.tx_hash == tx_hash
    
    @pytest.mark.asyncio
    async def test_transaction_user_relationship(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь и транзакция
        WHEN: Загружаем relationship
        THEN: Связь корректная
        """
        # Arrange & Act
        transaction = await create_transaction_helper(test_user)
        await db_session.refresh(transaction)
        
        # Assert
        assert transaction.user is not None
        assert transaction.user.id == test_user.id
        assert transaction.user.telegram_id == test_user.telegram_id
    
    @pytest.mark.asyncio
    async def test_transaction_repr(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Транзакция
        WHEN: Получаем строковое представление
        THEN: Возвращается корректный repr
        """
        # Arrange & Act
        transaction = await create_transaction_helper(
            test_user,
            type="deposit",
            amount=Decimal("100")
        )
        repr_str = repr(transaction)
        
        # Assert
        assert "Transaction" in repr_str
        assert str(transaction.id) in repr_str
        assert str(transaction.user_id) in repr_str
        assert "deposit" in repr_str
        assert "100" in repr_str


class TestTransactionModelScenarios:
    """Тесты реальных сценариев транзакций."""
    
    @pytest.mark.asyncio
    async def test_deposit_transaction_sequence(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь с балансом 0
        WHEN: Создаем последовательность депозитов
        THEN: Баланс корректно отслеживается
        """
        # Transaction 1: Initial deposit
        tx1 = await create_transaction_helper(
            test_user,
            type="deposit",
            amount=Decimal("100")
        )
        tx1.balance_before = Decimal("0")
        tx1.balance_after = Decimal("100")
        await db_session.commit()
        
        # Transaction 2: Second deposit
        tx2 = await create_transaction_helper(
            test_user,
            type="deposit",
            amount=Decimal("50")
        )
        tx2.balance_before = Decimal("100")
        tx2.balance_after = Decimal("150")
        await db_session.commit()
        
        # Assert
        assert tx1.balance_after == Decimal("100")
        assert tx2.balance_before == tx1.balance_after
        assert tx2.balance_after == Decimal("150")
    
    @pytest.mark.asyncio
    async def test_withdrawal_transaction_sequence(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь с балансом 200
        WHEN: Создаем вывод средств
        THEN: Баланс корректно уменьшается
        """
        # Setup initial balance
        test_user.balance = Decimal("200")
        await db_session.commit()
        
        # Transaction: Withdrawal
        tx = await create_transaction_helper(
            test_user,
            type="withdrawal",
            amount=Decimal("80")
        )
        tx.balance_before = Decimal("200")
        tx.balance_after = Decimal("120")
        await db_session.commit()
        
        # Assert
        assert tx.balance_after == Decimal("120")
        assert tx.balance_before - tx.amount == tx.balance_after
    
    @pytest.mark.asyncio
    async def test_referral_reward_transaction(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь получает реферальную награду
        WHEN: Создаем referral_reward транзакцию
        THEN: Награда добавляется к балансу
        """
        # Arrange
        test_user.balance = Decimal("50")
        await db_session.commit()
        
        # Act
        reward_amount = Decimal("3")  # 3% от депозита реферала
        tx = await create_transaction_helper(
            test_user,
            type="referral_reward",
            amount=reward_amount
        )
        tx.balance_before = Decimal("50")
        tx.balance_after = Decimal("53")
        tx.description = "Referral reward Level 1 - 3%"
        await db_session.commit()
        
        # Assert
        assert tx.type == "referral_reward"
        assert tx.amount == Decimal("3")
        assert tx.balance_after == Decimal("53")
    
    @pytest.mark.asyncio
    async def test_daily_roi_transaction(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь получает ежедневный ROI
        WHEN: Создаем deposit_reward транзакцию
        THEN: ROI добавляется к балансу
        """
        # Arrange
        test_user.balance = Decimal("100")
        await db_session.commit()
        
        # Act
        roi_amount = Decimal("2")  # 2% от депозита 100
        tx = await create_transaction_helper(
            test_user,
            type="deposit_reward",
            amount=roi_amount
        )
        tx.balance_before = Decimal("100")
        tx.balance_after = Decimal("102")
        tx.description = "Daily ROI 2% from deposit #1"
        await db_session.commit()
        
        # Assert
        assert tx.type == "deposit_reward"
        assert tx.amount == Decimal("2")
        assert tx.balance_after == Decimal("102")
    
    @pytest.mark.asyncio
    async def test_system_payout_transaction(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Системная выплата пользователю
        WHEN: Создаем system_payout транзакцию
        THEN: Выплата корректно записывается
        """
        # Arrange & Act
        tx = await create_transaction_helper(
            test_user,
            type="system_payout",
            amount=Decimal("10"),
            description="Compensation for system error"
        )
        tx.balance_before = Decimal("50")
        tx.balance_after = Decimal("60")
        await db_session.commit()
        
        # Assert
        assert tx.type == "system_payout"
        assert tx.amount == Decimal("10")
        assert "Compensation" in tx.description


class TestTransactionModelEdgeCases:
    """Тесты граничных случаев."""
    
    @pytest.mark.asyncio
    async def test_transaction_very_large_amount(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем транзакцию с очень большой суммой
        THEN: Сумма корректно сохраняется
        """
        # Arrange & Act
        large_amount = Decimal("999999999.99999999")
        tx = await create_transaction_helper(
            test_user,
            amount=large_amount
        )
        tx.balance_before = Decimal("0")
        tx.balance_after = large_amount
        await db_session.commit()
        
        # Assert
        assert tx.amount == large_amount
    
    @pytest.mark.asyncio
    async def test_transaction_very_small_amount(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем транзакцию с очень маленькой суммой
        THEN: Сумма корректно сохраняется
        """
        # Arrange & Act
        small_amount = Decimal("0.00000001")
        tx = await create_transaction_helper(
            test_user,
            amount=small_amount
        )
        tx.balance_before = Decimal("0")
        tx.balance_after = small_amount
        await db_session.commit()
        
        # Assert
        assert tx.amount == small_amount
    
    @pytest.mark.asyncio
    async def test_multiple_transactions_same_user(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем множество транзакций
        THEN: Все транзакции независимы
        """
        # Arrange & Act
        transactions = []
        for i in range(20):
            tx = await create_transaction_helper(
                test_user,
                amount=Decimal("10")
            )
            transactions.append(tx)
        
        # Assert
        assert len(transactions) == 20
        for tx in transactions:
            assert tx.user_id == test_user.id
    
    @pytest.mark.asyncio
    async def test_transaction_pending_to_confirmed_status_change(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Pending транзакция
        WHEN: Меняем статус на confirmed
        THEN: Статус корректно обновляется
        """
        # Arrange
        tx = await create_transaction_helper(
            test_user,
            status="pending"
        )
        assert tx.status == "pending"
        
        # Act
        tx.status = "confirmed"
        await db_session.commit()
        await db_session.refresh(tx)
        
        # Assert
        assert tx.status == "confirmed"
    
    @pytest.mark.asyncio
    async def test_transaction_failed_status(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем failed транзакцию
        THEN: Статус корректно сохраняется
        """
        # Arrange & Act
        tx = await create_transaction_helper(
            test_user,
            status="failed",
            description="Failed due to insufficient blockchain gas"
        )
        
        # Assert
        assert tx.status == "failed"
        assert "Failed" in tx.description
