"""
Unit tests for Deposit model.

Тестирование модели Deposit со всеми уровнями и ROI логикой.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from app.models.deposit import Deposit
from tests.conftest import DEPOSIT_LEVELS, ROI_CAP_MULTIPLIER


class TestDepositModel:
    """Тесты модели Deposit."""
    
    @pytest.mark.asyncio
    async def test_create_deposit_success(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем депозит
        THEN: Депозит создан с корректными данными
        """
        # Arrange & Act
        deposit = await create_deposit_helper(
            test_user,
            level=3,
            amount=Decimal("100")
        )
        
        # Assert
        assert deposit.id is not None
        assert deposit.user_id == test_user.id
        assert deposit.level == 3
        assert deposit.amount == Decimal("100")
        assert deposit.status == "confirmed"
        assert deposit.roi_cap_amount == Decimal("500")  # 5x multiplier
        assert deposit.roi_paid_amount == Decimal("0")
        assert deposit.is_roi_completed is False
        assert isinstance(deposit.created_at, datetime)
    
    @pytest.mark.parametrize("level,amount,expected_cap", [
        (1, Decimal("10"), Decimal("50")),
        (2, Decimal("50"), Decimal("250")),
        (3, Decimal("100"), Decimal("500")),
        (4, Decimal("150"), Decimal("750")),
        (5, Decimal("300"), Decimal("1500")),
    ])
    @pytest.mark.asyncio
    async def test_all_deposit_levels_roi_cap(
        self,
        db_session,
        test_user,
        create_deposit_helper,
        level,
        amount,
        expected_cap
    ):
        """
        GIVEN: Разные уровни депозитов
        WHEN: Создаем депозиты всех уровней
        THEN: ROI cap рассчитывается корректно (amount * 5)
        """
        # Arrange & Act
        deposit = await create_deposit_helper(
            test_user,
            level=level,
            amount=amount
        )
        
        # Assert
        assert deposit.level == level
        assert deposit.amount == amount
        assert deposit.roi_cap_amount == expected_cap
    
    @pytest.mark.asyncio
    async def test_deposit_level_range_constraint_min(
        self,
        db_session,
        test_user
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем депозит с level < 1
        THEN: Возникает IntegrityError
        """
        # Arrange
        deposit = Deposit(
            user_id=test_user.id,
            level=0,  # Меньше минимума
            amount=Decimal("10"),
            roi_cap_amount=Decimal("50")
        )
        
        # Act & Assert
        db_session.add(deposit)
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_deposit_level_range_constraint_max(
        self,
        db_session,
        test_user
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем депозит с level > 5
        THEN: Возникает IntegrityError
        """
        # Arrange
        deposit = Deposit(
            user_id=test_user.id,
            level=6,  # Больше максимума
            amount=Decimal("10"),
            roi_cap_amount=Decimal("50")
        )
        
        # Act & Assert
        db_session.add(deposit)
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_deposit_amount_positive_constraint(
        self,
        db_session,
        test_user
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем депозит с amount <= 0
        THEN: Возникает IntegrityError
        """
        # Arrange
        deposit = Deposit(
            user_id=test_user.id,
            level=1,
            amount=Decimal("0"),  # Нулевая сумма
            roi_cap_amount=Decimal("0")
        )
        
        # Act & Assert
        db_session.add(deposit)
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_deposit_roi_cap_non_negative_constraint(
        self,
        db_session,
        test_user
    ):
        """
        GIVEN: Пользователь и депозит
        WHEN: Устанавливаем roi_cap_amount < 0
        THEN: Возникает IntegrityError
        """
        # Arrange
        deposit = Deposit(
            user_id=test_user.id,
            level=1,
            amount=Decimal("10"),
            roi_cap_amount=Decimal("-10")  # Отрицательный cap
        )
        
        # Act & Assert
        db_session.add(deposit)
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_deposit_roi_paid_non_negative_constraint(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Депозит
        WHEN: Устанавливаем roi_paid_amount < 0
        THEN: Возникает IntegrityError
        """
        # Arrange
        deposit = await create_deposit_helper(test_user)
        deposit.roi_paid_amount = Decimal("-5")
        
        # Act & Assert
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_deposit_roi_paid_not_exceeds_cap_constraint(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Депозит с cap = 50
        WHEN: Устанавливаем roi_paid > cap
        THEN: Возникает IntegrityError
        """
        # Arrange
        deposit = await create_deposit_helper(
            test_user,
            level=1,
            amount=Decimal("10")
        )
        # cap = 50, пытаемся установить paid = 51
        deposit.roi_paid_amount = Decimal("51")
        
        # Act & Assert
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_deposit_unique_tx_hash(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Депозит с tx_hash
        WHEN: Создаем еще один депозит с тем же tx_hash
        THEN: Возникает IntegrityError
        """
        # Arrange
        tx_hash = "0x" + "unique" + "0" * 58
        deposit1 = await create_deposit_helper(
            test_user,
            tx_hash=tx_hash
        )
        
        deposit2 = Deposit(
            user_id=test_user.id,
            level=1,
            amount=Decimal("10"),
            roi_cap_amount=Decimal("50"),
            tx_hash=tx_hash  # Дубликат
        )
        
        # Act & Assert
        db_session.add(deposit2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_deposit_status_values(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем депозиты с разными статусами
        THEN: Все статусы корректно сохраняются
        """
        # Arrange & Act
        pending = await create_deposit_helper(
            test_user,
            status="pending"
        )
        confirmed = await create_deposit_helper(
            test_user,
            status="confirmed"
        )
        failed = await create_deposit_helper(
            test_user,
            status="failed"
        )
        
        # Assert
        assert pending.status == "pending"
        assert confirmed.status == "confirmed"
        assert failed.status == "failed"
    
    @pytest.mark.asyncio
    async def test_deposit_blockchain_data(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем депозит с блокчейн данными
        THEN: Данные корректно сохраняются
        """
        # Arrange & Act
        deposit = await create_deposit_helper(
            test_user,
            tx_hash="0x" + "abc123" + "0" * 58,
            block_number=123456,
            wallet_address="0x" + "sender" + "0" * 54
        )
        
        # Assert
        assert deposit.tx_hash is not None
        assert deposit.block_number == 123456
        assert deposit.wallet_address is not None
    
    @pytest.mark.asyncio
    async def test_deposit_confirmed_at_tracking(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Депозит со статусом pending
        WHEN: Подтверждаем депозит
        THEN: confirmed_at устанавливается
        """
        # Arrange
        deposit = await create_deposit_helper(
            test_user,
            status="pending"
        )
        assert deposit.confirmed_at is None
        
        # Act
        deposit.status = "confirmed"
        deposit.confirmed_at = datetime.now(timezone.utc)
        await db_session.commit()
        await db_session.refresh(deposit)
        
        # Assert
        assert deposit.status == "confirmed"
        assert deposit.confirmed_at is not None
        assert isinstance(deposit.confirmed_at, datetime)
    
    @pytest.mark.asyncio
    async def test_deposit_roi_completion(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Депозит с cap = 500
        WHEN: roi_paid достигает cap
        THEN: is_roi_completed устанавливается в True
        """
        # Arrange
        deposit = await create_deposit_helper(
            test_user,
            amount=Decimal("100")
        )
        assert deposit.is_roi_completed is False
        
        # Act - заполняем ROI до cap
        deposit.roi_paid_amount = deposit.roi_cap_amount
        deposit.is_roi_completed = True
        await db_session.commit()
        await db_session.refresh(deposit)
        
        # Assert
        assert deposit.roi_paid_amount == Decimal("500")
        assert deposit.is_roi_completed is True
    
    @pytest.mark.asyncio
    async def test_deposit_user_relationship(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Пользователь и депозит
        WHEN: Загружаем relationship
        THEN: Связь корректная
        """
        # Arrange & Act
        deposit = await create_deposit_helper(test_user)
        await db_session.refresh(deposit)
        
        # Assert
        assert deposit.user is not None
        assert deposit.user.id == test_user.id
        assert deposit.user.telegram_id == test_user.telegram_id
    
    @pytest.mark.asyncio
    async def test_deposit_repr(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Депозит
        WHEN: Получаем строковое представление
        THEN: Возвращается корректный repr
        """
        # Arrange & Act
        deposit = await create_deposit_helper(
            test_user,
            level=3,
            amount=Decimal("100")
        )
        repr_str = repr(deposit)
        
        # Assert
        assert "Deposit" in repr_str
        assert str(deposit.id) in repr_str
        assert str(deposit.user_id) in repr_str
        assert str(deposit.level) in repr_str
        assert "100" in repr_str


class TestDepositModelROICalculations:
    """Тесты расчетов ROI для депозитов."""
    
    @pytest.mark.parametrize("amount,expected_daily_roi", [
        (Decimal("10"), Decimal("0.2")),    # 2% от 10
        (Decimal("50"), Decimal("1")),      # 2% от 50
        (Decimal("100"), Decimal("2")),     # 2% от 100
        (Decimal("150"), Decimal("3")),     # 2% от 150
        (Decimal("300"), Decimal("6")),     # 2% от 300
    ])
    @pytest.mark.asyncio
    async def test_daily_roi_calculation(
        self,
        db_session,
        test_user,
        create_deposit_helper,
        amount,
        expected_daily_roi
    ):
        """
        GIVEN: Депозиты разных размеров
        WHEN: Рассчитываем дневной ROI (2%)
        THEN: Расчет корректный
        """
        # Arrange
        deposit = await create_deposit_helper(
            test_user,
            amount=amount
        )
        
        # Act
        daily_roi = amount * Decimal("0.02")
        
        # Assert
        assert daily_roi == expected_daily_roi
    
    @pytest.mark.asyncio
    async def test_roi_progress_tracking(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Депозит 100 USDT (cap = 500)
        WHEN: Постепенно выплачиваем ROI
        THEN: Прогресс корректно отслеживается
        """
        # Arrange
        deposit = await create_deposit_helper(
            test_user,
            amount=Decimal("100")
        )
        
        # Act & Assert - симулируем выплаты
        days_paid = 0
        daily_roi = Decimal("2")  # 2% от 100
        
        # День 1
        deposit.roi_paid_amount += daily_roi
        days_paid += 1
        await db_session.commit()
        assert deposit.roi_paid_amount == Decimal("2")
        assert deposit.roi_paid_amount < deposit.roi_cap_amount
        
        # День 100
        deposit.roi_paid_amount = daily_roi * 100
        await db_session.commit()
        assert deposit.roi_paid_amount == Decimal("200")
        
        # День 250 (полный cap)
        deposit.roi_paid_amount = daily_roi * 250
        deposit.is_roi_completed = True
        await db_session.commit()
        assert deposit.roi_paid_amount == Decimal("500")
        assert deposit.is_roi_completed is True
    
    @pytest.mark.asyncio
    async def test_roi_remaining_calculation(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Депозит с частично выплаченным ROI
        WHEN: Рассчитываем остаток
        THEN: Остаток корректный
        """
        # Arrange
        deposit = await create_deposit_helper(
            test_user,
            amount=Decimal("100")
        )
        deposit.roi_paid_amount = Decimal("100")  # Выплачено 100 из 500
        await db_session.commit()
        
        # Act
        remaining = deposit.roi_cap_amount - deposit.roi_paid_amount
        
        # Assert
        assert remaining == Decimal("400")
        assert deposit.is_roi_completed is False


class TestDepositModelEdgeCases:
    """Тесты граничных случаев."""
    
    @pytest.mark.asyncio
    async def test_deposit_exact_roi_cap_reached(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Депозит
        WHEN: roi_paid точно равен cap
        THEN: Constraint не нарушен
        """
        # Arrange
        deposit = await create_deposit_helper(
            test_user,
            amount=Decimal("100")
        )
        
        # Act
        deposit.roi_paid_amount = deposit.roi_cap_amount
        await db_session.commit()
        await db_session.refresh(deposit)
        
        # Assert
        assert deposit.roi_paid_amount == deposit.roi_cap_amount
        # Не должно быть ошибки
    
    @pytest.mark.asyncio
    async def test_multiple_deposits_same_user(
        self,
        db_session,
        test_user,
        create_deposit_helper
    ):
        """
        GIVEN: Пользователь
        WHEN: Создаем несколько депозитов
        THEN: Все депозиты создаются независимо
        """
        # Arrange & Act
        deposits = []
        for level in range(1, 6):
            deposit = await create_deposit_helper(
                test_user,
                level=level,
                amount=DEPOSIT_LEVELS[level]["amount"]
            )
            deposits.append(deposit)
        
        # Assert
        assert len(deposits) == 5
        for i, deposit in enumerate(deposits, 1):
            assert deposit.level == i
            assert deposit.user_id == test_user.id
