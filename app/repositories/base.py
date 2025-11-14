"""
Base repository.

Generic CRUD operations for all repositories.
"""

from typing import Any, Generic, List, Optional, Type, TypeVar, Dict

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeMeta

from app.models.base import Base

# Generic type for model
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository with generic CRUD operations.

    Provides async database operations for any SQLAlchemy model.

    Type Parameters:
        ModelType: SQLAlchemy model class

    Example:
        class UserRepository(BaseRepository[User]):
            def __init__(self, session: AsyncSession):
                super().__init__(User, session)
    """

    def __init__(
        self, model: Type[ModelType], session: AsyncSession
    ) -> None:
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """
        Get entity by ID.

        Args:
            id: Entity ID

        Returns:
            Entity or None if not found
        """
        return await self.session.get(self.model, id)

    async def get_by(
        self, **filters: Any
    ) -> Optional[ModelType]:
        """
        Get single entity by filters.

        Args:
            **filters: Column filters

        Returns:
            First matching entity or None
        """
        stmt = select(self.model).filter_by(**filters)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_all(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        **filters: Any,
    ) -> List[ModelType]:
        """
        Find all entities matching filters.

        Args:
            limit: Max number of results
            offset: Number of results to skip
            **filters: Column filters

        Returns:
            List of matching entities
        """
        stmt = select(self.model).filter_by(**filters)

        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_by(
        self, **filters: Any
    ) -> List[ModelType]:
        """
        Find entities by filters.

        Args:
            **filters: Column filters

        Returns:
            List of matching entities
        """
        return await self.find_all(**filters)

    async def create(self, **data: Any) -> ModelType:
        """
        Create new entity.

        Args:
            **data: Entity data

        Returns:
            Created entity
        """
        entity = self.model(**data)
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(
        self, id: int, **data: Any
    ) -> Optional[ModelType]:
        """
        Update entity by ID.

        Args:
            id: Entity ID
            **data: Updated data

        Returns:
            Updated entity or None if not found
        """
        entity = await self.get_by_id(id)
        if not entity:
            return None

        for key, value in data.items():
            setattr(entity, key, value)

        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, id: int) -> bool:
        """
        Delete entity by ID.

        Args:
            id: Entity ID

        Returns:
            True if deleted, False if not found
        """
        entity = await self.get_by_id(id)
        if not entity:
            return False

        await self.session.delete(entity)
        await self.session.flush()
        return True

    async def count(self, **filters: Any) -> int:
        """
        Count entities matching filters.

        Args:
            **filters: Column filters

        Returns:
            Count of matching entities
        """
        stmt = select(func.count()).select_from(self.model)

        if filters:
            stmt = stmt.filter_by(**filters)

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def exists(self, **filters: Any) -> bool:
        """
        Check if entity exists.

        Args:
            **filters: Column filters

        Returns:
            True if exists, False otherwise
        """
        count = await self.count(**filters)
        return count > 0

    async def bulk_create(
        self, items: List[Dict[str, Any]]
    ) -> List[ModelType]:
        """
        Create multiple entities.

        Args:
            items: List of entity data dicts

        Returns:
            List of created entities
        """
        entities = [self.model(**item) for item in items]
        self.session.add_all(entities)
        await self.session.flush()

        for entity in entities:
            await self.session.refresh(entity)

        return entities
