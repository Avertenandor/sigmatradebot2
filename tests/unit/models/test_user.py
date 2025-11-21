"""
Unit tests for User model.

Тестирование модели User со всеми ограничениями и валидациями.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.utils.encryption import hash_password, verify_password


class TestUserModel:
    """Тесты модели User."""
    
    @pytest.mark.asyncio
    async def test_create_user_success(self, db_session, test_user_data):
        """
        GIVEN: Валидные данные пользователя
        WHEN: Создаем нового пользователя
        THEN: Пользователь успешно создан с корректными данными
        """
        # Arrange & Act
        user = User(**test_user_data)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Assert
        assert user.id is not None
        assert user.telegram_id == test_user_data["telegram_id"]
        assert user.username == test_user_data["username"]
        assert user.wallet_address == test_user_data["wallet_address"]
        assert user.balance == Decimal("0")
        assert user.total_earned == Decimal("0")
        assert user.pending_earnings == Decimal("0")
        assert user.is_active is True
        assert user.is_verified is False
        assert user.is_banned is False
        assert user.is_admin is False
        assert user.earnings_blocked is False
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)
    
    @pytest.mark.asyncio
    async def test_unique_telegram_id(self, db_session, test_user):
        """
        GIVEN: Существующий пользователь с telegram_id
        WHEN: Пытаемся создать другого пользователя с тем же telegram_id
        THEN: Возникает IntegrityError
        """
        # Arrange
        duplicate_user = User(
            telegram_id=test_user.telegram_id,
            username="different_user",
            wallet_address="0x" + "2" * 40,
            financial_password=hash_password("test456")
        )
        
        # Act & Assert
        db_session.add(duplicate_user)
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_balance_non_negative_constraint(self, db_session, test_user):
        """
        GIVEN: Пользователь с балансом 0
        WHEN: Пытаемся установить отрицательный баланс
        THEN: Возникает IntegrityError
        """
        # Arrange
        test_user.balance = Decimal("-10")
        
        # Act & Assert
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_total_earned_non_negative_constraint(self, db_session, test_user):
        """
        GIVEN: Пользователь
        WHEN: Пытаемся установить отрицательный total_earned
        THEN: Возникает IntegrityError
        """
        # Arrange
        test_user.total_earned = Decimal("-5")
        
        # Act & Assert
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_pending_earnings_non_negative_constraint(
        self,
        db_session,
        test_user
    ):
        """
        GIVEN: Пользователь
        WHEN: Пытаемся установить отрицательный pending_earnings
        THEN: Возникает IntegrityError
        """
        # Arrange
        test_user.pending_earnings = Decimal("-3")
        
        # Act & Assert
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_masked_wallet_property(self, test_user):
        """
        GIVEN: Пользователь с кошельком
        WHEN: Получаем masked_wallet
        THEN: Возвращается замаскированный адрес
        """
        # Arrange
        wallet = "0x1234567890abcdefABCDEF1234567890abcdefAB"
        test_user.wallet_address = wallet
        
        # Act
        masked = test_user.masked_wallet
        
        # Assert
        assert masked == "0x12345678...cdefAB"
        assert len(masked) < len(wallet)
    
    @pytest.mark.asyncio
    async def test_user_with_referrer(
        self,
        db_session,
        create_user_helper
    ):
        """
        GIVEN: Два пользователя
        WHEN: Устанавливаем реферальную связь
        THEN: Связь корректно сохраняется
        """
        # Arrange
        referrer = await create_user_helper(telegram_id=300000001)
        referred = await create_user_helper(
            telegram_id=300000002,
            referrer_id=referrer.id
        )
        
        # Act
        await db_session.refresh(referrer)
        await db_session.refresh(referred)
        
        # Assert
        assert referred.referrer_id == referrer.id
        assert referred.referrer.id == referrer.id
        assert referred in referrer.referrals
    
    @pytest.mark.asyncio
    async def test_user_ban_flag(self, db_session, test_user):
        """
        GIVEN: Активный пользователь
        WHEN: Банним пользователя
        THEN: Флаг is_banned установлен
        """
        # Arrange
        assert test_user.is_banned is False
        
        # Act
        test_user.is_banned = True
        await db_session.commit()
        await db_session.refresh(test_user)
        
        # Assert
        assert test_user.is_banned is True
    
    @pytest.mark.asyncio
    async def test_user_admin_flag(self, db_session, test_user):
        """
        GIVEN: Обычный пользователь
        WHEN: Делаем пользователя админом
        THEN: Флаг is_admin установлен
        """
        # Arrange
        assert test_user.is_admin is False
        
        # Act
        test_user.is_admin = True
        await db_session.commit()
        await db_session.refresh(test_user)
        
        # Assert
        assert test_user.is_admin is True
    
    @pytest.mark.asyncio
    async def test_user_financial_password_hashed(self, test_user):
        """
        GIVEN: Пользователь с зашифрованным паролем
        WHEN: Проверяем пароль
        THEN: Пароль корректно хешируется и проверяется
        """
        # Arrange
        original_password = "test123"
        
        # Act
        is_valid = verify_password(
            original_password,
            test_user.financial_password
        )
        
        # Assert
        assert is_valid is True
        assert test_user.financial_password != original_password
    
    @pytest.mark.asyncio
    async def test_user_relationships_cascade_delete(
        self,
        db_session,
        test_user,
        create_deposit_helper,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь с депозитами и транзакциями
        WHEN: Удаляем пользователя
        THEN: Связанные депозиты и транзакции также удаляются
        """
        # Arrange
        deposit = await create_deposit_helper(test_user)
        transaction = await create_transaction_helper(test_user)
        
        deposit_id = deposit.id
        transaction_id = transaction.id
        
        # Act
        await db_session.delete(test_user)
        await db_session.commit()
        
        # Assert - проверяем что депозит и транзакция удалены
        from app.models.deposit import Deposit
        from app.models.transaction import Transaction
        
        deleted_deposit = await db_session.get(Deposit, deposit_id)
        deleted_transaction = await db_session.get(Transaction, transaction_id)
        
        assert deleted_deposit is None
        assert deleted_transaction is None
    
    @pytest.mark.asyncio
    async def test_user_optional_contacts(self, db_session):
        """
        GIVEN: Данные пользователя с контактами
        WHEN: Создаем пользователя с phone и email
        THEN: Контакты корректно сохраняются
        """
        # Arrange & Act
        user = User(
            telegram_id=400000001,
            username="user_with_contacts",
            wallet_address="0x" + "c" * 40,
            financial_password=hash_password("test123"),
            phone="+1234567890",
            email="test@example.com"
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Assert
        assert user.phone == "+1234567890"
        assert user.email == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_user_repr(self, test_user):
        """
        GIVEN: Пользователь
        WHEN: Получаем строковое представление
        THEN: Возвращается корректный repr
        """
        # Act
        repr_str = repr(test_user)
        
        # Assert
        assert "User" in repr_str
        assert str(test_user.id) in repr_str
        assert str(test_user.telegram_id) in repr_str
        assert test_user.username in repr_str


class TestUserModelEdgeCases:
    """Тесты граничных случаев модели User."""
    
    @pytest.mark.asyncio
    async def test_user_with_very_large_balance(self, db_session, test_user):
        """
        GIVEN: Пользователь
        WHEN: Устанавливаем очень большой баланс
        THEN: Баланс корректно сохраняется
        """
        # Arrange
        large_balance = Decimal("999999999.99999999")
        
        # Act
        test_user.balance = large_balance
        await db_session.commit()
        await db_session.refresh(test_user)
        
        # Assert
        assert test_user.balance == large_balance
    
    @pytest.mark.asyncio
    async def test_user_with_very_small_balance(self, db_session, test_user):
        """
        GIVEN: Пользователь
        WHEN: Устанавливаем очень маленький баланс (но > 0)
        THEN: Баланс корректно сохраняется
        """
        # Arrange
        small_balance = Decimal("0.00000001")
        
        # Act
        test_user.balance = small_balance
        await db_session.commit()
        await db_session.refresh(test_user)
        
        # Assert
        assert test_user.balance == small_balance
    
    @pytest.mark.asyncio
    async def test_user_without_username(self, db_session):
        """
        GIVEN: Данные пользователя без username
        WHEN: Создаем пользователя
        THEN: Пользователь создается с None в username
        """
        # Arrange & Act
        user = User(
            telegram_id=500000001,
            username=None,
            wallet_address="0x" + "d" * 40,
            financial_password=hash_password("test123")
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Assert
        assert user.username is None
        assert user.id is not None
    
    @pytest.mark.asyncio
    async def test_user_last_active_tracking(self, db_session, test_user):
        """
        GIVEN: Пользователь
        WHEN: Обновляем last_active
        THEN: Время корректно сохраняется
        """
        # Arrange
        now = datetime.now(timezone.utc)
        
        # Act
        test_user.last_active = now
        await db_session.commit()
        await db_session.refresh(test_user)
        
        # Assert
        assert test_user.last_active is not None
        assert isinstance(test_user.last_active, datetime)
        # Проверяем что разница меньше 1 секунды
        assert abs((test_user.last_active - now).total_seconds()) < 1
    
    @pytest.mark.asyncio
    async def test_user_earnings_blocked_flag(self, db_session, test_user):
        """
        GIVEN: Пользователь
        WHEN: Блокируем заработки
        THEN: Флаг earnings_blocked установлен
        """
        # Arrange
        assert test_user.earnings_blocked is False
        
        # Act
        test_user.earnings_blocked = True
        await db_session.commit()
        await db_session.refresh(test_user)
        
        # Assert
        assert test_user.earnings_blocked is True


class TestUserModelTransactions:
    """Тесты связи User с Transaction."""
    
    @pytest.mark.asyncio
    async def test_user_transactions_relationship(
        self,
        db_session,
        test_user,
        create_transaction_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем несколько транзакций
        THEN: Все транзакции доступны через relationship
        """
        # Arrange & Act
        tx1 = await create_transaction_helper(
            test_user,
            type="deposit",
            amount=Decimal("100")
        )
        tx2 = await create_transaction_helper(
            test_user,
            type="withdrawal",
            amount=Decimal("50")
        )
        tx3 = await create_transaction_helper(
            test_user,
            type="referral_reward",
            amount=Decimal("3")
        )
        
        await db_session.refresh(test_user)
        
        # Assert
        assert len(test_user.transactions) == 3
        transaction_ids = [tx.id for tx in test_user.transactions]
        assert tx1.id in transaction_ids
        assert tx2.id in transaction_ids
        assert tx3.id in transaction_ids


class TestUserModelDeposits:
    """Тесты связи User с Deposit."""
    
    @pytest.mark.asyncio
    async def test_user_deposits_relationship(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем несколько депозитов
        THEN: Все депозиты доступны через relationship
        """
        # Arrange & Act
        deposit1 = await create_deposit_helper(test_user, level=1)
        deposit2 = await create_deposit_helper(test_user, level=3)
        deposit3 = await create_deposit_helper(test_user, level=5)
        
        await db_session.refresh(test_user)
        
        # Assert
        assert len(test_user.deposits) == 3
        deposit_ids = [d.id for d in test_user.deposits]
        assert deposit1.id in deposit_ids
        assert deposit2.id in deposit_ids
        assert deposit3.id in deposit_ids
