"""
PostgreSQL FSM storage for aiogram.

R11-3: Custom FSM storage using PostgreSQL when Redis is unavailable.
Stores FSM states in user_fsm_states table.
"""

from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import async_session_maker
from app.models.user_fsm_state import UserFsmState
from app.repositories.user_repository import UserRepository


class PostgreSQLFSMStorage(BaseStorage):
    """
    PostgreSQL-based FSM storage.

    R11-3: Stores FSM states in PostgreSQL when Redis is unavailable.
    Uses user_fsm_states table to persist states across restarts.
    """

    def __init__(self) -> None:
        """Initialize PostgreSQL FSM storage."""
        self._session_factory = async_session_maker

    async def close(self) -> None:
        """Close storage (no-op for PostgreSQL)."""
        pass

    async def set_state(
        self,
        key: StorageKey,
        state: StateType | None = None,
    ) -> None:
        """
        Set FSM state for user.

        Args:
            key: Storage key (contains chat_id, user_id, etc.)
            state: State to set (None to clear)
        """
        try:
            async with self._session_factory() as session:
                user_repo = UserRepository(session)
                user = await user_repo.get_by_telegram_id(key.user_id)

                if not user:
                    logger.warning(
                        f"R11-3: Cannot set FSM state for unknown user {key.user_id}"
                    )
                    return

                # Get or create FSM state record
                stmt = select(UserFsmState).where(
                    UserFsmState.user_id == user.id
                )
                result = await session.execute(stmt)
                fsm_state = result.scalar_one_or_none()

                state_str = (
                    state.state
                    if isinstance(state, State)
                    else str(state)
                    if state
                    else None
                )

                if fsm_state:
                    # Update existing
                    fsm_state.state = state_str
                    await session.flush()
                else:
                    # Create new
                    fsm_state = UserFsmState(
                        user_id=user.id,
                        state=state_str,
                    )
                    session.add(fsm_state)
                    await session.flush()

                await session.commit()
                logger.debug(
                    f"R11-3: Set FSM state for user {key.user_id}: {state_str}"
                )

        except Exception as e:
            logger.error(
                f"R11-3: Failed to set FSM state for user {key.user_id}: {e}",
                exc_info=True,
            )

    async def get_state(
        self,
        key: StorageKey,
    ) -> str | None:
        """
        Get FSM state for user.

        Args:
            key: Storage key

        Returns:
            State string or None
        """
        try:
            async with self._session_factory() as session:
                user_repo = UserRepository(session)
                user = await user_repo.get_by_telegram_id(key.user_id)

                if not user:
                    return None

                stmt = select(UserFsmState).where(
                    UserFsmState.user_id == user.id
                )
                result = await session.execute(stmt)
                fsm_state = result.scalar_one_or_none()

                if fsm_state and fsm_state.state:
                    return fsm_state.state

                return None

        except Exception as e:
            logger.error(
                f"R11-3: Failed to get FSM state for user {key.user_id}: {e}",
                exc_info=True,
            )
            return None

    async def set_data(
        self,
        key: StorageKey,
        data: dict[str, Any],
    ) -> None:
        """
        Set FSM data for user.

        Args:
            key: Storage key
            data: Data dictionary
        """
        try:
            async with self._session_factory() as session:
                user_repo = UserRepository(session)
                user = await user_repo.get_by_telegram_id(key.user_id)

                if not user:
                    logger.warning(
                        f"R11-3: Cannot set FSM data for unknown user {key.user_id}"
                    )
                    return

                # Get or create FSM state record
                stmt = select(UserFsmState).where(
                    UserFsmState.user_id == user.id
                )
                result = await session.execute(stmt)
                fsm_state = result.scalar_one_or_none()

                if fsm_state:
                    # Update existing
                    if fsm_state.data:
                        fsm_state.data.update(data)
                    else:
                        fsm_state.data = data
                    await session.flush()
                else:
                    # Create new
                    fsm_state = UserFsmState(
                        user_id=user.id,
                        data=data,
                    )
                    session.add(fsm_state)
                    await session.flush()

                await session.commit()
                logger.debug(
                    f"R11-3: Set FSM data for user {key.user_id}: {len(data)} keys"
                )

        except Exception as e:
            logger.error(
                f"R11-3: Failed to set FSM data for user {key.user_id}: {e}",
                exc_info=True,
            )

    async def get_data(
        self,
        key: StorageKey,
    ) -> dict[str, Any]:
        """
        Get FSM data for user.

        Args:
            key: Storage key

        Returns:
            Data dictionary
        """
        try:
            async with self._session_factory() as session:
                user_repo = UserRepository(session)
                user = await user_repo.get_by_telegram_id(key.user_id)

                if not user:
                    return {}

                stmt = select(UserFsmState).where(
                    UserFsmState.user_id == user.id
                )
                result = await session.execute(stmt)
                fsm_state = result.scalar_one_or_none()

                if fsm_state and fsm_state.data:
                    return fsm_state.data

                return {}

        except Exception as e:
            logger.error(
                f"R11-3: Failed to get FSM data for user {key.user_id}: {e}",
                exc_info=True,
            )
            return {}

    async def update_data(
        self,
        key: StorageKey,
        data: dict[str, Any],
    ) -> None:
        """
        Update FSM data for user (merge with existing).

        Args:
            key: Storage key
            data: Data dictionary to merge
        """
        try:
            async with self._session_factory() as session:
                user_repo = UserRepository(session)
                user = await user_repo.get_by_telegram_id(key.user_id)

                if not user:
                    logger.warning(
                        f"R11-3: Cannot update FSM data for unknown user {key.user_id}"
                    )
                    return

                # Get or create FSM state record
                stmt = select(UserFsmState).where(
                    UserFsmState.user_id == user.id
                )
                result = await session.execute(stmt)
                fsm_state = result.scalar_one_or_none()

                if fsm_state:
                    # Update existing
                    if fsm_state.data:
                        fsm_state.data.update(data)
                    else:
                        fsm_state.data = data
                    await session.flush()
                else:
                    # Create new
                    fsm_state = UserFsmState(
                        user_id=user.id,
                        data=data,
                    )
                    session.add(fsm_state)
                    await session.flush()

                await session.commit()
                logger.debug(
                    f"R11-3: Updated FSM data for user {key.user_id}: {len(data)} keys"
                )

        except Exception as e:
            logger.error(
                f"R11-3: Failed to update FSM data for user {key.user_id}: {e}",
                exc_info=True,
            )

