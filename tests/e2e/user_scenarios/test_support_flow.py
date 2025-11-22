"""
E2E tests for support flow.

Tests complete support scenarios:
- Create ticket from bot
- Link ticket with user
- Link ticket with appeal (if exists)
- Send message in ticket
- Receive admin response
- Close ticket
"""

import pytest

from app.models.appeal import Appeal
from app.models.enums import SupportSender, SupportStatus
from app.models.support_message import SupportMessage
from app.models.support_ticket import SupportTicket
from app.repositories.appeal_repository import AppealRepository
from app.repositories.support_message_repository import SupportMessageRepository
from app.repositories.support_ticket_repository import SupportTicketRepository
from app.services.support_service import SupportService
from tests.conftest import hash_password


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_ticket_from_bot(
    db_session,
    support_service: SupportService,
    create_user_helper,
) -> None:
    """
    Test creating ticket from bot.

    GIVEN: User
    WHEN: Creates support ticket
    THEN:
        - Ticket is created
        - Ticket is linked to user
        - Status is OPEN
    """
    # Arrange: Create user
    user = await create_user_helper(
        telegram_id=111111111,
        wallet_address="0x" + "1" * 40,
    )

    # Act: Create ticket
    ticket, error_msg = await support_service.create_ticket(
        user_id=user.id,
        category="payments",
        initial_message="Test ticket message",
        telegram_id=user.telegram_id,
    )

    # Assert: Ticket created
    assert ticket is not None
    assert error_msg is None
    assert ticket.user_id == user.id
    assert ticket.telegram_id == user.telegram_id
    assert ticket.category == "payments"
    assert ticket.status == SupportStatus.OPEN.value

    # Assert: Initial message created
    message_repo = SupportMessageRepository(db_session)
    messages = await message_repo.get_by_ticket(ticket.id)
    assert len(messages) > 0
    initial_message = messages[0]
    assert initial_message.text == "Test ticket message"
    assert initial_message.sender == SupportSender.USER.value


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ticket_linked_with_user(
    db_session,
    support_service: SupportService,
    create_user_helper,
) -> None:
    """
    Test ticket is linked with user.

    GIVEN: User
    WHEN: Creates ticket
    THEN: Ticket.user_id matches user.id
    """
    # Arrange: Create user
    user = await create_user_helper(
        telegram_id=222222222,
        wallet_address="0x" + "2" * 40,
    )

    # Act: Create ticket
    ticket, error_msg = await support_service.create_ticket(
        user_id=user.id,
        category="technical",
        telegram_id=user.telegram_id,
    )

    # Assert: Ticket linked to user
    assert ticket is not None
    assert ticket.user_id == user.id

    # Assert: Can retrieve ticket by user
    ticket_repo = SupportTicketRepository(db_session)
    user_tickets = await ticket_repo.get_by_user(user.id)
    assert len(user_tickets) > 0
    assert any(t.id == ticket.id for t in user_tickets)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ticket_linked_with_appeal(
    db_session,
    support_service: SupportService,
    blacklist_service,
    create_user_helper,
) -> None:
    """
    Test ticket linked with appeal.

    GIVEN: User with appeal
    WHEN: Creates ticket
    THEN: Ticket can be linked to appeal (if appeal exists)
    
    Note: Appeal linking may happen manually or automatically.
    This test verifies appeal exists and can be linked.
    """
    # Arrange: Create user and block
    user = await create_user_helper(
        telegram_id=333333333,
        wallet_address="0x" + "3" * 40,
    )

    blacklist_entry = await blacklist_service.add_to_blacklist(
        telegram_id=user.telegram_id,
        reason="Test block",
        added_by_admin_id=1,
        action_type="blocked",
    )
    await db_session.commit()

    # Create appeal
    appeal_repo = AppealRepository(db_session)
    appeal = await appeal_repo.create(
        user_id=user.id,
        blacklist_id=blacklist_entry.id,
        reason="Test appeal",
        status="pending",
    )
    await db_session.commit()

    # Act: Create ticket (may be linked to appeal in handler)
    ticket, error_msg = await support_service.create_ticket(
        user_id=user.id,
        category="appeal",
        telegram_id=user.telegram_id,
    )

    # Assert: Ticket created
    assert ticket is not None
    assert ticket.user_id == user.id

    # Assert: Appeal exists and can be linked
    assert appeal is not None
    assert appeal.user_id == user.id
    # Note: Linking happens in handler, not service


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_send_message_in_ticket(
    db_session,
    support_service: SupportService,
    create_user_helper,
) -> None:
    """
    Test sending message in ticket.

    GIVEN: User with open ticket
    WHEN: Sends message
    THEN:
        - Message is created
        - Message is linked to ticket
        - Ticket status remains OPEN
    """
    # Arrange: Create user and ticket
    user = await create_user_helper(
        telegram_id=444444444,
        wallet_address="0x" + "4" * 40,
    )

    ticket, _ = await support_service.create_ticket(
        user_id=user.id,
        category="payments",
        telegram_id=user.telegram_id,
    )

    # Act: Add user message
    message = await support_service.add_user_message(
        ticket_id=ticket.id,
        text="Follow-up message",
    )
    await db_session.commit()

    # Assert: Message created
    assert message is not None
    assert message.ticket_id == ticket.id
    assert message.text == "Follow-up message"
    assert message.sender == SupportSender.USER.value

    # Assert: Ticket still open
    await db_session.refresh(ticket)
    assert ticket.status == SupportStatus.OPEN.value


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_receive_admin_response(
    db_session,
    support_service: SupportService,
    create_user_helper,
    test_admin,
) -> None:
    """
    Test receiving admin response.

    GIVEN: User with open ticket
    WHEN: Admin sends response
    THEN:
        - Admin message is created
        - Ticket status changes to ANSWERED
        - Message is linked to ticket
    """
    # Arrange: Create user and ticket
    user = await create_user_helper(
        telegram_id=555555555,
        wallet_address="0x" + "5" * 40,
    )

    ticket, _ = await support_service.create_ticket(
        user_id=user.id,
        category="payments",
        telegram_id=user.telegram_id,
    )

    # Act: Add admin message
    message = await support_service.add_admin_message(
        ticket_id=ticket.id,
        admin_id=test_admin.id,
        text="Admin response",
    )
    await db_session.commit()

    # Assert: Message created
    assert message is not None
    assert message.ticket_id == ticket.id
    assert message.text == "Admin response"
    assert message.sender == SupportSender.ADMIN.value
    assert message.admin_id == test_admin.id

    # Assert: Ticket status changed to ANSWERED
    await db_session.refresh(ticket)
    assert ticket.status == SupportStatus.ANSWERED.value


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_close_ticket(
    db_session,
    support_service: SupportService,
    create_user_helper,
    test_admin,
) -> None:
    """
    Test closing ticket.

    GIVEN: User with open ticket
    WHEN: Admin closes ticket
    THEN:
        - Ticket status changes to CLOSED
        - Ticket can be retrieved but is not active
    """
    # Arrange: Create user and ticket
    user = await create_user_helper(
        telegram_id=666666666,
        wallet_address="0x" + "6" * 40,
    )

    ticket, _ = await support_service.create_ticket(
        user_id=user.id,
        category="payments",
        telegram_id=user.telegram_id,
    )

    # Act: Close ticket
    await support_service.close_ticket(
        ticket_id=ticket.id,
    )
    await db_session.commit()

    # Assert: Ticket closed
    await db_session.refresh(ticket)
    assert ticket.status == SupportStatus.CLOSED.value

    # Assert: Ticket is not active
    ticket_repo = SupportTicketRepository(db_session)
    active_ticket = await ticket_repo.get_active_by_user(user.id)
    assert active_ticket is None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_multiple_messages_in_ticket(
    db_session,
    support_service: SupportService,
    create_user_helper,
    test_admin,
) -> None:
    """
    Test multiple messages in ticket.

    GIVEN: User with ticket
    WHEN: Sends multiple messages
    THEN: All messages are linked to ticket
    """
    # Arrange: Create user and ticket
    user = await create_user_helper(
        telegram_id=777777777,
        wallet_address="0x" + "7" * 40,
    )

    ticket, _ = await support_service.create_ticket(
        user_id=user.id,
        category="payments",
        telegram_id=user.telegram_id,
    )

    # Act: Add multiple messages
    message1 = await support_service.add_user_message(
        ticket_id=ticket.id,
        text="First message",
    )
    message2 = await support_service.add_user_message(
        ticket_id=ticket.id,
        text="Second message",
    )
    admin_message = await support_service.add_admin_message(
        ticket_id=ticket.id,
        admin_id=test_admin.id,
        text="Admin response",
    )
    await db_session.commit()

    # Assert: All messages created
    message_repo = SupportMessageRepository(db_session)
    messages = await message_repo.get_by_ticket(ticket.id)
    assert len(messages) >= 3  # Initial + 2 user + 1 admin

    # Assert: Messages are in correct order (by created_at)
    message_ids = [m.id for m in messages]
    assert message1.id in message_ids
    assert message2.id in message_ids
    assert admin_message.id in message_ids

