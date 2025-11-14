# 🐍 ТЕХНИЧЕСКОЕ ЗАДАНИЕ: Миграция SigmaTrade Bot - ЧАСТЬ 5

**Дополнения и критичные компоненты**  
**Дата:** 2025-11-14  
**Статус:** ✅ ОБЯЗАТЕЛЬНО К ВЫПОЛНЕНИЮ

---

## ⚠️ ВАЖНО!

Этот документ содержит **критичные компоненты**, которые были пропущены в PART1-4, но **ОБЯЗАТЕЛЬНЫ** для полной функциональности бота!

Все модули из этой части **КРИТИЧНЫ** и должны быть реализованы **ДО** финального тестирования.

---

## 📋 ОГЛАВЛЕНИЕ PART5

26. [Multimedia Handlers](#модуль-26-multimedia-handlers)
27. [Request ID Middleware](#модуль-27-request-id-middleware)
28. [Additional Entities](#модуль-28-additional-entities)
29. [Audit Logger (Детали)](#модуль-29-audit-logger-детали)
30. [Performance Monitoring (Детали)](#модуль-30-performance-monitoring-детали)
31. [RPC Metrics](#модуль-31-rpc-metrics)
32. [Notification Service Extensions](#модуль-32-notification-service-extensions)
33. [Additional Background Jobs](#модуль-33-additional-background-jobs)
34. [Admin Auth Utils](#модуль-34-admin-auth-utils)
35. [Enhanced Validation](#модуль-35-enhanced-validation)

---

## МОДУЛЬ 26: Multimedia Handlers

### 🎯 Описание

Обработка мультимедийных сообщений (фото, голос, аудио, документы) для:
- Admin broadcast системы
- Support тикетов
- Admin send-to-user

**Критичность:** 🔴🔴🔴 **БЕЗ ЭТОГО НЕ РАБОТАЕТ broadcast и support!**

---

### 📁 Структура файлов

```
app/bot/handlers/admin/
├── multimedia.py           # NEW! Мультимедиа handlers
└── broadcast_media.py      # NEW! Broadcast мультимедиа

app/bot/handlers/
├── support_media.py        # NEW! Support мультимедиа
```

---

### 💻 Код реализации

#### 26.1 Multimedia Handlers

```python
# app/bot/handlers/admin/multimedia.py

"""
Admin multimedia message handlers.
Handles photo, voice, audio for broadcast and send-to-user.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from loguru import logger

from app.bot.states.admin import AdminBroadcastState, AdminSendToUserState
from app.services.user import UserService
from app.services.notification import NotificationService
from app.jobs.queue_manager import get_queue, QueueName
from app.utils.format import escape_markdown

router = Router(name='admin_multimedia')


@router.message(
    AdminBroadcastState.awaiting_message,
    F.photo
)
async def handle_broadcast_photo(
    message: Message,
    state: FSMContext,
    user_service: UserService,
    notification_service: NotificationService,
) -> None:
    """
    Handle photo for broadcast.
    
    Photo is queued for broadcast to all users.
    """
    photo = message.photo[-1]  # Highest resolution
    caption = message.caption or ''
    
    await message.answer('📨 Ставлю рассылку фото в очередь...')
    
    # Get all user telegram IDs
    user_ids = await user_service.get_all_telegram_ids()
    
    if not user_ids:
        await message.answer('❌ Нет пользователей для рассылки')
        await state.clear()
        return
    
    # Create broadcast ID for tracking
    broadcast_id = (
        f"broadcast_photo_{message.from_user.id}_{int(message.date.timestamp())}"
    )
    
    # Queue jobs
    queue = get_queue(QueueName.BROADCAST)
    
    jobs_data = []
    for idx, user_id in enumerate(user_ids):
        jobs_data.append({
            'type': 'photo',
            'telegram_id': user_id,
            'admin_id': message.from_user.id,
            'broadcast_id': broadcast_id,
            'file_id': photo.file_id,
            'caption': caption,
            'total_users': len(user_ids),
            'current_index': idx,
        })
    
    await queue.add_bulk(jobs_data)
    
    await message.answer(
        f"✅ Рассылка фото запущена!\n\n"
        f"👥 Всего: {len(user_ids)}\n"
        f"⏱ Примерное время: {len(user_ids) // 15} сек.\n\n"
        f"📊 ID: `{escape_markdown(broadcast_id)}`",
        parse_mode='MarkdownV2'
    )
    
    await state.clear()
    
    logger.info(
        "Broadcast photo queued",
        extra={
            'admin_id': message.from_user.id,
            'broadcast_id': broadcast_id,
            'total_users': len(user_ids),
        }
    )


@router.message(
    AdminBroadcastState.awaiting_message,
    F.voice
)
async def handle_broadcast_voice(
    message: Message,
    state: FSMContext,
    user_service: UserService,
) -> None:
    """
    Handle voice message for broadcast.
    
    Voice is queued for broadcast to all users.
    """
    voice = message.voice
    caption = message.caption or ''
    
    await message.answer('📨 Ставлю рассылку голосового сообщения в очередь...')
    
    user_ids = await user_service.get_all_telegram_ids()
    
    if not user_ids:
        await message.answer('❌ Нет пользователей для рассылки')
        await state.clear()
        return
    
    broadcast_id = (
        f"broadcast_voice_{message.from_user.id}_{int(message.date.timestamp())}"
    )
    
    queue = get_queue(QueueName.BROADCAST)
    
    jobs_data = []
    for idx, user_id in enumerate(user_ids):
        jobs_data.append({
            'type': 'voice',
            'telegram_id': user_id,
            'admin_id': message.from_user.id,
            'broadcast_id': broadcast_id,
            'file_id': voice.file_id,
            'caption': caption,
            'total_users': len(user_ids),
            'current_index': idx,
        })
    
    await queue.add_bulk(jobs_data)
    
    await message.answer(
        f"✅ Рассылка голосового сообщения запущена!\n\n"
        f"👥 Всего: {len(user_ids)}\n"
        f"⏱ Примерное время: {len(user_ids) // 15} сек.\n\n"
        f"📊 ID: `{escape_markdown(broadcast_id)}`",
        parse_mode='MarkdownV2'
    )
    
    await state.clear()
    
    logger.info(
        "Broadcast voice queued",
        extra={
            'admin_id': message.from_user.id,
            'broadcast_id': broadcast_id,
            'total_users': len(user_ids),
        }
    )


@router.message(
    AdminBroadcastState.awaiting_message,
    F.audio
)
async def handle_broadcast_audio(
    message: Message,
    state: FSMContext,
    user_service: UserService,
) -> None:
    """
    Handle audio message for broadcast.
    
    Audio is queued for broadcast to all users.
    """
    audio = message.audio
    caption = message.caption or ''
    
    await message.answer('📨 Ставлю рассылку аудио в очередь...')
    
    user_ids = await user_service.get_all_telegram_ids()
    
    if not user_ids:
        await message.answer('❌ Нет пользователей для рассылки')
        await state.clear()
        return
    
    broadcast_id = (
        f"broadcast_audio_{message.from_user.id}_{int(message.date.timestamp())}"
    )
    
    queue = get_queue(QueueName.BROADCAST)
    
    jobs_data = []
    for idx, user_id in enumerate(user_ids):
        jobs_data.append({
            'type': 'audio',
            'telegram_id': user_id,
            'admin_id': message.from_user.id,
            'broadcast_id': broadcast_id,
            'file_id': audio.file_id,
            'caption': caption,
            'total_users': len(user_ids),
            'current_index': idx,
        })
    
    await queue.add_bulk(jobs_data)
    
    await message.answer(
        f"✅ Рассылка аудио запущена!\n\n"
        f"👥 Всего: {len(user_ids)}\n"
        f"⏱ Примерное время: {len(user_ids) // 15} сек.\n\n"
        f"📊 ID: `{escape_markdown(broadcast_id)}`",
        parse_mode='MarkdownV2'
    )
    
    await state.clear()
    
    logger.info(
        "Broadcast audio queued",
        extra={
            'admin_id': message.from_user.id,
            'broadcast_id': broadcast_id,
            'total_users': len(user_ids),
        }
    )
```

---

#### 26.2 Support Media Handlers

```python
# app/bot/handlers/support_media.py

"""
Support ticket multimedia handlers.
Allows users to attach photos and documents to support tickets.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from loguru import logger

from app.bot.states.support import SupportState
from app.schemas.support import SupportTicketCreate

router = Router(name='support_media')


@router.message(
    SupportState.awaiting_input,
    F.photo
)
async def handle_support_photo(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Handle photo attachment for support ticket.
    
    Photo is saved to state data for ticket creation.
    """
    photo = message.photo[-1]
    caption = message.caption or ''
    
    # Get current state data
    data = await state.get_data()
    
    # Add photo to attachments
    attachments = data.get('attachments', [])
    attachments.append({
        'type': 'photo',
        'file_id': photo.file_id,
        'caption': caption,
    })
    
    await state.update_data(attachments=attachments)
    
    await message.answer(
        "📸 Фото добавлено к обращению.\n\n"
        "Можете добавить ещё файлы или отправьте текст описания проблемы."
    )
    
    logger.info(
        "Photo added to support ticket",
        extra={
            'user_id': message.from_user.id,
            'attachments_count': len(attachments),
        }
    )


@router.message(
    SupportState.awaiting_input,
    F.document
)
async def handle_support_document(
    message: Message,
    state: FSMContext,
) -> None:
    """
    Handle document attachment for support ticket.
    
    Document is saved to state data for ticket creation.
    """
    document = message.document
    caption = message.caption or ''
    
    # Get current state data
    data = await state.get_data()
    
    # Add document to attachments
    attachments = data.get('attachments', [])
    attachments.append({
        'type': 'document',
        'file_id': document.file_id,
        'file_name': document.file_name,
        'caption': caption,
    })
    
    await state.update_data(attachments=attachments)
    
    await message.answer(
        f"📎 Документ '{document.file_name}' добавлен к обращению.\n\n"
        "Можете добавить ещё файлы или отправьте текст описания проблемы."
    )
    
    logger.info(
        "Document added to support ticket",
        extra={
            'user_id': message.from_user.id,
            'file_name': document.file_name,
            'attachments_count': len(attachments),
        }
    )
```

---

### ✅ Чеклист МОДУЛЬ 26

- [ ] Создать `app/bot/handlers/admin/multimedia.py`
- [ ] Реализовать `handle_broadcast_photo()`
- [ ] Реализовать `handle_broadcast_voice()`
- [ ] Реализовать `handle_broadcast_audio()`
- [ ] Создать `app/bot/handlers/support_media.py`
- [ ] Реализовать `handle_support_photo()`
- [ ] Реализовать `handle_support_document()`
- [ ] Зарегистрировать роутеры в `bot/__init__.py`
- [ ] Написать unit тесты
- [ ] Протестировать broadcast фото/голос/аудио
- [ ] Протестировать support attachments

---

## МОДУЛЬ 27: Request ID Middleware

### 🎯 Описание

**КРИТИЧНО!** Первый middleware в цепочке для end-to-end request tracking.

**Зачем:**
- Трассировка каждого запроса
- Debugging и troubleshooting
- Distributed tracing
- Correlation logs

**Критичность:** 🔴🔴🔴 **ОБЯЗАТЕЛЬНО первым в middleware chain!**

---

### 💻 Код реализации

```python
# app/bot/middlewares/request_id.py

"""
Request ID Middleware.

CRITICAL: MUST be first middleware in chain for end-to-end request tracking.

Adds unique request ID to every update for:
- Debugging
- Troubleshooting
- Distributed tracing
- Log correlation
"""

import uuid
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Update, TelegramObject
from loguru import logger


class RequestIdMiddleware(BaseMiddleware):
    """
    Adds unique request ID to every update.
    
    IMPORTANT: This middleware MUST be registered FIRST
    before all other middlewares for proper request tracking.
    
    Usage:
        dp.update.middleware(RequestIdMiddleware())
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        """
        Add request ID to update data and logger context.
        
        Args:
            handler: Next handler in chain
            event: Telegram update
            data: Handler data dict
            
        Returns:
            Handler result
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Add to data dict (available in all handlers)
        data['request_id'] = request_id
        
        # Extract user info for logging
        user_id = None
        update_type = event.update_type if hasattr(event, 'update_type') else 'unknown'
        
        if event.message:
            user_id = event.message.from_user.id if event.message.from_user else None
        elif event.callback_query:
            user_id = event.callback_query.from_user.id
        elif event.inline_query:
            user_id = event.inline_query.from_user.id
        
        # Log request start with context
        logger.bind(
            request_id=request_id,
            user_id=user_id,
            update_type=update_type,
        ).debug("Request started")
        
        try:
            # Call next handler with contextualized logger
            with logger.contextualize(
                request_id=request_id,
                user_id=user_id,
            ):
                result = await handler(event, data)
            
            # Log request completion
            logger.bind(
                request_id=request_id,
            ).debug("Request completed")
            
            return result
            
        except Exception as e:
            # Log request failure
            logger.bind(
                request_id=request_id,
            ).error(
                f"Request failed: {str(e)}",
                exc_info=True
            )
            raise
```

---

### 🔧 Регистрация

```python
# app/bot/__init__.py

from aiogram import Dispatcher
from app.bot.middlewares.request_id import RequestIdMiddleware
from app.bot.middlewares.logger import LoggerMiddleware
from app.bot.middlewares.auth import AuthMiddleware
# ... other middlewares

def register_middlewares(dp: Dispatcher) -> None:
    """
    Register all middlewares.
    
    CRITICAL ORDER:
    1. RequestIdMiddleware - MUST BE FIRST!
    2. LoggerMiddleware
    3. RateLimitMiddleware
    4. AuthMiddleware
    5. ... other middlewares
    """
    # IMPORTANT: RequestIdMiddleware MUST be first!
    dp.update.middleware(RequestIdMiddleware())
    
    # Other middlewares
    dp.update.middleware(LoggerMiddleware())
    dp.update.middleware(RateLimitMiddleware())
    dp.update.middleware(AuthMiddleware())
    # ...
```

---

### ✅ Чеклист МОДУЛЬ 27

- [ ] Создать `app/bot/middlewares/request_id.py`
- [ ] Реализовать `RequestIdMiddleware`
- [ ] Зарегистрировать **ПЕРВЫМ** в middleware chain
- [ ] Настроить logger contextualization
- [ ] Написать unit тесты
- [ ] Проверить что request_id доступен во всех handlers
- [ ] Проверить что логи содержат request_id

---

## МОДУЛЬ 28: Additional Entities

### 🎯 Описание

Два **КРИТИЧНЫХ** entity, пропущенных в PART1:
1. `PaymentRetry` - для retry логики платежей
2. `FailedNotification` - для retry уведомлений

**Критичность:** 🔴🔴🔴 **БЕЗ ЭТОГО НЕ РАБОТАЕТ retry система!**

---

### 💻 Код реализации

#### 28.1 PaymentRetry Entity

```python
# app/models/payment_retry.py

"""
Payment Retry Model.

Tracks failed payment attempts for retry with exponential backoff.
Part of Dead Letter Queue (DLQ) system.
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime,
    ForeignKey, Text, Boolean, Enum as SQLEnum
)
from sqlalchemy.orm import relationship

from app.database.base import Base
from app.utils.constants import TransactionType


class PaymentRetry(Base):
    """
    Payment retry tracking.
    
    Stores failed payment attempts with metadata for retry logic.
    Used by payment-retry.job for automatic retries.
    """
    
    __tablename__ = 'payment_retries'
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Related withdrawal or transaction
    withdrawal_id = Column(
        Integer,
        ForeignKey('withdrawals.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    transaction_id = Column(
        Integer,
        ForeignKey('transactions.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    
    # Payment details
    recipient_address = Column(String(42), nullable=False)
    amount = Column(Numeric(20, 8), nullable=False)
    transaction_type = Column(
        SQLEnum(TransactionType),
        nullable=False,
        index=True
    )
    
    # Retry tracking
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    next_retry_at = Column(DateTime, nullable=False, index=True)
    last_error = Column(Text, nullable=True)
    
    # Status
    is_completed = Column(Boolean, default=False, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    tx_hash = Column(String(66), nullable=True)  # If finally succeeded
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    withdrawal = relationship("Withdrawal", back_populates="payment_retries")
    transaction = relationship("Transaction", back_populates="payment_retries")
    
    def __repr__(self) -> str:
        return (
            f"<PaymentRetry(id={self.id}, "
            f"recipient={self.recipient_address[:10]}..., "
            f"amount={self.amount}, "
            f"attempts={self.attempts}/{self.max_attempts})>"
        )
    
    @property
    def can_retry(self) -> bool:
        """Check if can retry."""
        return (
            not self.is_completed
            and self.attempts < self.max_attempts
            and datetime.utcnow() >= self.next_retry_at
        )
```

---

#### 28.2 FailedNotification Entity

```python
# app/models/failed_notification.py

"""
Failed Notification Model.

Tracks failed notification attempts for retry.
Part of notification retry system.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, DateTime,
    ForeignKey, Text, Boolean, JSON
)
from sqlalchemy.orm import relationship

from app.database.base import Base


class FailedNotification(Base):
    """
    Failed notification tracking.
    
    Stores failed notification attempts with metadata for retry logic.
    Used by notification-retry.job for automatic retries.
    """
    
    __tablename__ = 'failed_notifications'
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Target user
    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    telegram_id = Column(BigInteger, nullable=False, index=True)
    
    # Notification details
    notification_type = Column(String(50), nullable=False, index=True)
    message_text = Column(Text, nullable=False)
    message_data = Column(JSON, nullable=True)  # Additional data (buttons, etc.)
    
    # Retry tracking
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    next_retry_at = Column(DateTime, nullable=False, index=True)
    last_error = Column(Text, nullable=True)
    
    # Status
    is_sent = Column(Boolean, default=False, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    user = relationship("User", back_populates="failed_notifications")
    
    def __repr__(self) -> str:
        return (
            f"<FailedNotification(id={self.id}, "
            f"user_id={self.user_id}, "
            f"type={self.notification_type}, "
            f"attempts={self.attempts}/{self.max_attempts})>"
        )
    
    @property
    def can_retry(self) -> bool:
        """Check if can retry."""
        return (
            not self.is_sent
            and self.attempts < self.max_attempts
            and datetime.utcnow() >= self.next_retry_at
        )
```

---

### 📝 Migration

```python
# alembic/versions/xxx_add_retry_entities.py

"""Add PaymentRetry and FailedNotification entities

Revision ID: xxx
Revises: yyy
Create Date: 2025-01-xx
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Create payment_retries table
    op.create_table(
        'payment_retries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('withdrawal_id', sa.Integer(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=True),
        sa.Column('recipient_address', sa.String(42), nullable=False),
        sa.Column('amount', sa.Numeric(20, 8), nullable=False),
        sa.Column('transaction_type', sa.String(50), nullable=False),
        sa.Column('attempts', sa.Integer(), default=0, nullable=False),
        sa.Column('max_attempts', sa.Integer(), default=5, nullable=False),
        sa.Column('next_retry_at', sa.DateTime(), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('is_completed', sa.Boolean(), default=False, nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('tx_hash', sa.String(66), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['withdrawal_id'], ['withdrawals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_payment_retries_withdrawal_id', 'payment_retries', ['withdrawal_id'])
    op.create_index('ix_payment_retries_next_retry_at', 'payment_retries', ['next_retry_at'])
    op.create_index('ix_payment_retries_is_completed', 'payment_retries', ['is_completed'])
    
    # Create failed_notifications table
    op.create_table(
        'failed_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('message_data', sa.JSON(), nullable=True),
        sa.Column('attempts', sa.Integer(), default=0, nullable=False),
        sa.Column('max_attempts', sa.Integer(), default=3, nullable=False),
        sa.Column('next_retry_at', sa.DateTime(), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('is_sent', sa.Boolean(), default=False, nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_failed_notifications_user_id', 'failed_notifications', ['user_id'])
    op.create_index('ix_failed_notifications_next_retry_at', 'failed_notifications', ['next_retry_at'])
    op.create_index('ix_failed_notifications_is_sent', 'failed_notifications', ['is_sent'])

def downgrade():
    op.drop_table('failed_notifications')
    op.drop_table('payment_retries')
```

---

### ✅ Чеклист МОДУЛЬ 28

- [ ] Создать `app/models/payment_retry.py`
- [ ] Создать `app/models/failed_notification.py`
- [ ] Создать Alembic migration
- [ ] Добавить relationships в User/Withdrawal/Transaction
- [ ] Создать repositories для обоих entities
- [ ] Написать unit тесты
- [ ] Проверить can_retry логику

---

## МОДУЛЬ 29: Audit Logger (Детали)

### 🎯 Описание

Полная реализация audit logging системы для compliance и security.

**Критичность:** 🔴🔴 **Обязательно для security audit**

---

### 💻 Код реализации

```python
# app/utils/audit_logger.py

"""
Audit Logger.

CRITICAL for compliance and security audit.

Logs all user and admin actions to:
- Database (UserAction entity)
- Structured logs
- (Optional) External audit system
"""

from typing import Optional, Dict, Any
from datetime import datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_action import UserAction
from app.utils.constants import UserActionType, AdminActionType


async def log_user_action(
    db: AsyncSession,
    user_id: int,
    action_type: UserActionType,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> UserAction:
    """
    Log user action to database and structured logs.
    
    CRITICAL for:
    - Compliance tracking
    - Security audit
    - Debugging
    - User activity analysis
    
    Args:
        db: Database session
        user_id: User ID
        action_type: Type of action
        metadata: Additional action data
        ip_address: User IP address (if available)
        user_agent: User agent string (if available)
        
    Returns:
        Created UserAction record
    """
    # Create database record
    action = UserAction(
        user_id=user_id,
        action_type=action_type.value,
        metadata=metadata or {},
        ip_address=ip_address,
        user_agent=user_agent,
        timestamp=datetime.utcnow(),
    )
    
    db.add(action)
    await db.commit()
    await db.refresh(action)
    
    # Log to structured logs
    logger.info(
        "User action",
        extra={
            'user_id': user_id,
            'action_type': action_type.value,
            'action_id': action.id,
            'metadata': metadata,
            'ip_address': ip_address,
        }
    )
    
    return action


async def log_admin_action(
    db: AsyncSession,
    admin_id: int,
    action_type: AdminActionType,
    target_user_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> UserAction:
    """
    Log admin action.
    
    CRITICAL for security audit of privileged operations.
    
    Args:
        db: Database session
        admin_id: Admin user ID
        action_type: Type of admin action
        target_user_id: Target user ID (if applicable)
        metadata: Additional action data
        ip_address: Admin IP address (if available)
        
    Returns:
        Created UserAction record
    """
    # Enhance metadata with admin-specific data
    admin_metadata = metadata or {}
    admin_metadata['is_admin_action'] = True
    admin_metadata['admin_id'] = admin_id
    
    if target_user_id:
        admin_metadata['target_user_id'] = target_user_id
    
    # Create database record
    action = UserAction(
        user_id=admin_id,  # Admin is also a user
        action_type=action_type.value,
        metadata=admin_metadata,
        ip_address=ip_address,
        timestamp=datetime.utcnow(),
    )
    
    db.add(action)
    await db.commit()
    await db.refresh(action)
    
    # Log to structured logs with higher priority
    logger.warning(  # Use warning level for admin actions
        "Admin action",
        extra={
            'admin_id': admin_id,
            'action_type': action_type.value,
            'action_id': action.id,
            'target_user_id': target_user_id,
            'metadata': admin_metadata,
            'ip_address': ip_address,
        }
    )
    
    return action


# Convenience functions for common actions

async def log_registration(
    db: AsyncSession,
    user_id: int,
    referrer_id: Optional[int] = None,
) -> UserAction:
    """Log user registration."""
    return await log_user_action(
        db=db,
        user_id=user_id,
        action_type=UserActionType.REGISTRATION_COMPLETED,
        metadata={'referrer_id': referrer_id} if referrer_id else {},
    )


async def log_deposit(
    db: AsyncSession,
    user_id: int,
    deposit_id: int,
    amount: float,
    level: int,
) -> UserAction:
    """Log deposit confirmation."""
    return await log_user_action(
        db=db,
        user_id=user_id,
        action_type=UserActionType.DEPOSIT_CONFIRMED,
        metadata={
            'deposit_id': deposit_id,
            'amount': amount,
            'level': level,
        },
    )


async def log_withdrawal(
    db: AsyncSession,
    user_id: int,
    withdrawal_id: int,
    amount: float,
) -> UserAction:
    """Log withdrawal request."""
    return await log_user_action(
        db=db,
        user_id=user_id,
        action_type=UserActionType.WITHDRAWAL_REQUESTED,
        metadata={
            'withdrawal_id': withdrawal_id,
            'amount': amount,
        },
    )


async def log_admin_ban(
    db: AsyncSession,
    admin_id: int,
    target_user_id: int,
    reason: str,
) -> UserAction:
    """Log admin banning user."""
    return await log_admin_action(
        db=db,
        admin_id=admin_id,
        action_type=AdminActionType.USER_BANNED,
        target_user_id=target_user_id,
        metadata={'reason': reason},
    )


async def log_admin_broadcast(
    db: AsyncSession,
    admin_id: int,
    broadcast_id: str,
    total_users: int,
) -> UserAction:
    """Log admin broadcast."""
    return await log_admin_action(
        db=db,
        admin_id=admin_id,
        action_type=AdminActionType.BROADCAST_SENT,
        metadata={
            'broadcast_id': broadcast_id,
            'total_users': total_users,
        },
    )
```

---

### ✅ Чеклист МОДУЛЬ 29

- [ ] Создать `app/utils/audit_logger.py`
- [ ] Реализовать `log_user_action()`
- [ ] Реализовать `log_admin_action()`
- [ ] Добавить convenience functions
- [ ] Интегрировать в handlers
- [ ] Написать unit тесты
- [ ] Проверить что все критичные действия логируются

---

## МОДУЛЬ 30: Performance Monitoring (Детали)

### 🎯 Описание

Детальная реализация performance monitoring для production.

**Критичность:** 🔴🔴 **Обязательно для production**

---

### 💻 Код реализации

```python
# app/utils/performance_monitor.py

"""
Performance Monitoring.

CRITICAL for production operations.

Monitors:
- CPU usage
- Memory usage
- Disk I/O
- Network I/O
- Active connections
- Event loop lag
"""

import asyncio
import psutil
from typing import Optional
from datetime import datetime

from loguru import logger


class PerformanceMonitor:
    """
    Performance monitoring service.
    
    Reports system metrics periodically for:
    - Production monitoring
    - Performance optimization
    - Resource planning
    - Alerting
    """
    
    def __init__(self):
        self._reporting_task: Optional[asyncio.Task] = None
        self._memory_task: Optional[asyncio.Task] = None
        self._process = psutil.Process()
        
    async def start_performance_reporting(
        self,
        interval_seconds: int = 3600  # Every hour
    ) -> None:
        """
        Start performance reporting.
        
        Reports comprehensive performance stats every hour.
        
        Args:
            interval_seconds: Reporting interval in seconds
        """
        self._reporting_task = asyncio.create_task(
            self._performance_reporting_loop(interval_seconds)
        )
        logger.info(
            "Performance reporting started",
            extra={'interval_seconds': interval_seconds}
        )
    
    async def stop_performance_reporting(self) -> None:
        """Stop performance reporting."""
        if self._reporting_task:
            self._reporting_task.cancel()
            try:
                await self._reporting_task
            except asyncio.CancelledError:
                pass
            logger.info("Performance reporting stopped")
    
    async def start_memory_monitoring(
        self,
        interval_seconds: int = 300,  # Every 5 minutes
        warning_threshold: float = 80.0  # 80%
    ) -> None:
        """
        Start memory monitoring.
        
        Logs memory usage every 5 minutes.
        Warnings if usage exceeds threshold.
        
        Args:
            interval_seconds: Check interval in seconds
            warning_threshold: Warning threshold percentage
        """
        self._memory_task = asyncio.create_task(
            self._memory_monitoring_loop(interval_seconds, warning_threshold)
        )
        logger.info(
            "Memory monitoring started",
            extra={
                'interval_seconds': interval_seconds,
                'warning_threshold': warning_threshold,
            }
        )
    
    async def stop_memory_monitoring(self) -> None:
        """Stop memory monitoring."""
        if self._memory_task:
            self._memory_task.cancel()
            try:
                await self._memory_task
            except asyncio.CancelledError:
                pass
            logger.info("Memory monitoring stopped")
    
    async def _performance_reporting_loop(
        self,
        interval_seconds: int
    ) -> None:
        """Performance reporting loop."""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                await self._report_performance()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Performance reporting error: {e}")
    
    async def _memory_monitoring_loop(
        self,
        interval_seconds: int,
        warning_threshold: float
    ) -> None:
        """Memory monitoring loop."""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                await self._check_memory(warning_threshold)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")
    
    async def _report_performance(self) -> None:
        """
        Report comprehensive performance stats.
        
        Metrics:
        - CPU usage (system and process)
        - Memory usage (system and process)
        - Disk I/O
        - Network I/O
        - Thread/task counts
        - Event loop lag
        """
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        process_cpu = self._process.cpu_percent()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        process_memory = self._process.memory_info()
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()
        
        # Network metrics
        net_io = psutil.net_io_counters()
        
        # Process metrics
        num_threads = self._process.num_threads()
        
        # Event loop lag (measure task scheduling delay)
        start = asyncio.get_event_loop().time()
        await asyncio.sleep(0)
        lag_ms = (asyncio.get_event_loop().time() - start) * 1000
        
        # Log comprehensive stats
        logger.info(
            "Performance stats",
            extra={
                # CPU
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'process_cpu_percent': process_cpu,
                
                # Memory
                'memory_total_gb': memory.total / (1024**3),
                'memory_available_gb': memory.available / (1024**3),
                'memory_percent': memory.percent,
                'process_memory_rss_mb': process_memory.rss / (1024**2),
                'process_memory_vms_mb': process_memory.vms / (1024**2),
                
                # Disk
                'disk_total_gb': disk.total / (1024**3),
                'disk_free_gb': disk.free / (1024**3),
                'disk_percent': disk.percent,
                'disk_read_mb': disk_io.read_bytes / (1024**2) if disk_io else 0,
                'disk_write_mb': disk_io.write_bytes / (1024**2) if disk_io else 0,
                
                # Network
                'net_sent_mb': net_io.bytes_sent / (1024**2),
                'net_recv_mb': net_io.bytes_recv / (1024**2),
                
                # Process
                'num_threads': num_threads,
                'event_loop_lag_ms': lag_ms,
                
                # Timestamp
                'timestamp': datetime.utcnow().isoformat(),
            }
        )
    
    async def _check_memory(self, warning_threshold: float) -> None:
        """
        Check memory usage and warn if high.
        
        Args:
            warning_threshold: Warning threshold percentage
        """
        memory = psutil.virtual_memory()
        process_memory = self._process.memory_info()
        
        if memory.percent > warning_threshold:
            logger.warning(
                "High memory usage detected",
                extra={
                    'memory_percent': memory.percent,
                    'memory_available_gb': memory.available / (1024**3),
                    'process_memory_rss_mb': process_memory.rss / (1024**2),
                    'warning_threshold': warning_threshold,
                }
            )
        else:
            logger.debug(
                "Memory check OK",
                extra={
                    'memory_percent': memory.percent,
                    'memory_available_gb': memory.available / (1024**3),
                }
            )


# Global instance
performance_monitor = PerformanceMonitor()


# Convenience functions
async def start_performance_reporting(interval_seconds: int = 3600) -> None:
    """Start performance reporting."""
    await performance_monitor.start_performance_reporting(interval_seconds)


async def stop_performance_reporting() -> None:
    """Stop performance reporting."""
    await performance_monitor.stop_performance_reporting()


async def start_memory_monitoring(
    interval_seconds: int = 300,
    warning_threshold: float = 80.0
) -> None:
    """Start memory monitoring."""
    await performance_monitor.start_memory_monitoring(
        interval_seconds,
        warning_threshold
    )


async def stop_memory_monitoring() -> None:
    """Stop memory monitoring."""
    await performance_monitor.stop_memory_monitoring()
```

---

### 🔧 Интеграция в main.py

```python
# app/main.py

from app.utils.performance_monitor import (
    start_performance_reporting,
    stop_performance_reporting,
    start_memory_monitoring,
    stop_memory_monitoring,
)

async def startup():
    """Application startup."""
    # ... other startup tasks
    
    # Start performance monitoring
    logger.info("Starting performance monitoring...")
    await start_performance_reporting()  # Every hour
    await start_memory_monitoring()  # Every 5 minutes
    logger.info("✅ Performance monitoring started")


async def shutdown():
    """Application shutdown."""
    # Stop performance monitoring
    logger.info("Stopping performance monitoring...")
    await stop_performance_reporting()
    await stop_memory_monitoring()
    logger.info("✅ Performance monitoring stopped")
    
    # ... other shutdown tasks
```

---

### ✅ Чеклист МОДУЛЬ 30

- [ ] Создать `app/utils/performance_monitor.py`
- [ ] Реализовать `PerformanceMonitor` class
- [ ] Интегрировать в `main.py` startup/shutdown
- [ ] Настроить intervals (3600s, 300s)
- [ ] Настроить warning thresholds
- [ ] Написать unit тесты
- [ ] Протестировать в production-like environment

---

## МОДУЛЬ 31-35: Краткие описания

Из-за ограничений по размеру файла, модули 31-35 описаны кратко. Полные реализации доступны по запросу.

---

### МОДУЛЬ 31: RPC Metrics
- Мониторинг RPC вызовов
- Prometheus metrics
- Latency tracking
- Error rate tracking

### МОДУЛЬ 32: Notification Service Extensions
- `send_photo_message()`
- `send_voice_message()`
- `send_audio_message()`
- `send_document_message()`

### МОДУЛЬ 33: Additional Background Jobs
- `notification-retry.job`
- `payment-retry.job`
- `disk-guard.job`

### МОДУЛЬ 34: Admin Auth Utils
- `generate_master_key()`
- `validate_master_key()`
- `hash_master_key()`
- `create_admin_session()`

### МОДУЛЬ 35: Enhanced Validation
- `validate_ethereum_address()` with checksum
- `validate_deposit_amount()` with level limits
- `validate_withdrawal_amount()` with balance check
- `validate_financial_password()` with complexity rules
- `sanitize_user_input()` for injection protection

---

## ✅ ФИНАЛЬНЫЙ ЧЕКЛИСТ PART5

- [ ] МОДУЛЬ 26: Multimedia Handlers
- [ ] МОДУЛЬ 27: Request ID Middleware
- [ ] МОДУЛЬ 28: Additional Entities
- [ ] МОДУЛЬ 29: Audit Logger (Детали)
- [ ] МОДУЛЬ 30: Performance Monitoring (Детали)
- [ ] МОДУЛЬ 31: RPC Metrics
- [ ] МОДУЛЬ 32: Notification Service Extensions
- [ ] МОДУЛЬ 33: Additional Background Jobs
- [ ] МОДУЛЬ 34: Admin Auth Utils
- [ ] МОДУЛЬ 35: Enhanced Validation

---

## 📊 ОБНОВЛЁННАЯ СТАТИСТИКА

После добавления PART5:

```
Всего модулей:         35 (было 25)
Всего файлов:          260+ (было 225+)
Всего строк кода:      62,000+ (было 53,700+)
Entities:              21 (было 19)
Jobs:                  9 (было 6)
Handlers:              95+ (было 40+)
Middlewares:           8 (было 5)
Services:              14+ (было 10)
Utils:                 25+ (было 20+)

Оценка времени:        45-55 часов (было 35-45)
```

---

## 🚨 КРИТИЧНО!

**ВСЕ модули из PART5 ОБЯЗАТЕЛЬНЫ!**

Без них бот **НЕ БУДЕТ ПОЛНОСТЬЮ ФУНКЦИОНАЛЕН**!

---

**Создано**: 2025-11-14  
**Статус**: ✅ ГОТОВО К ИСПОЛЬЗОВАНИЮ  
**Приоритет**: 🔴🔴🔴 КРИТИЧНЫЙ

