"""SQLite UserStorage — CRUD for peer identities."""
from __future__ import annotations

import uuid

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.types.entities import User, UserId
from sqlalchemy import Engine

from peerpedia_storage_gitdb.db.engine import get_session
from peerpedia_storage_gitdb.db.models import UserModel


class SqlUserStorage:
    """Implements peerpedia_core.protocols.storage.UserStorage."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def create(self) -> UserId:
        with get_session(self._engine) as session:
            row = UserModel(id=str(uuid.uuid4()), name="")
            session.add(row)
            session.flush()
            return UserId(id=row.id)

    def read(self, key: UserId) -> User:
        with get_session(self._engine) as session:
            return self._require_user(session, key.id).to_entity()

    def update(self, key: UserId, user: User) -> None:
        with get_session(self._engine) as session:
            row = self._require_user(session, key.id)
            row.name = user.name
            row.public_key = user.public_key

    def delete(self, key: UserId) -> None:
        with get_session(self._engine) as session:
            row = self._require_user(session, key.id)
            session.delete(row)

    def search(self, query: str) -> list[User]:
        with get_session(self._engine) as session:
            rows = session.query(UserModel).filter(
                UserModel.name.ilike(f"%{query}%"),
            ).all()
            return [r.to_entity() for r in rows]

    def list(self) -> list[User]:
        with get_session(self._engine) as session:
            return [r.to_entity() for r in session.query(UserModel).all()]

    def _require_user(self, session, user_id: str) -> UserModel:
        row = session.query(UserModel).filter_by(id=user_id).first()
        if row is None:
            raise NotFoundError(resource_type="user", resource_id=user_id)
        return row
