"""
Base Repository — Generic CRUD Operations.

Provides a generic, reusable repository base class that handles
common CRUD operations for any SQLAlchemy model.

Follows Interface Segregation Principle: keeps the interface
small and focused on data access only.
"""

from __future__ import annotations

from typing import Generic, Type, TypeVar

from sqlalchemy.orm import Session

from app.models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """
    Generic repository providing CRUD operations.

    Subclasses specify the model type and can add domain-specific queries.

    Args:
        session: SQLAlchemy database session.
        model_class: The SQLAlchemy model class to operate on.
    """

    def __init__(self, session: Session, model_class: Type[T]) -> None:
        self._session = session
        self._model_class = model_class

    def get_by_id(self, entity_id: str) -> T | None:
        """
        Retrieve an entity by its primary key.

        Args:
            entity_id: The entity's primary key (UUID string).

        Returns:
            The entity or None if not found.
        """
        return self._session.get(self._model_class, entity_id)

    def get_all(self) -> list[T]:
        """
        Retrieve all entities.

        Returns:
            List of all entities.
        """
        return (
            self._session.query(self._model_class)
            .order_by(self._model_class.created_at.desc())
            .all()
        )

    def create(self, entity: T) -> T:
        """
        Persist a new entity.

        Args:
            entity: The entity to create.

        Returns:
            The persisted entity with generated ID.
        """
        self._session.add(entity)
        self._session.commit()
        self._session.refresh(entity)
        return entity

    def update(self, entity: T) -> T:
        """
        Update an existing entity.

        Args:
            entity: The entity with updated fields.

        Returns:
            The updated entity.
        """
        self._session.commit()
        self._session.refresh(entity)
        return entity

    def delete(self, entity: T) -> None:
        """
        Delete an entity.

        Args:
            entity: The entity to delete.
        """
        self._session.delete(entity)
        self._session.commit()

    def count(self) -> int:
        """Return the total count of entities."""
        return self._session.query(self._model_class).count()
