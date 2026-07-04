from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.db.models import UserModel


class PostgresUserRepository:
    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def count_users(self) -> int:
        with self.session_factory() as session:
            statement = select(func.count()).select_from(UserModel)
            return int(session.execute(statement).scalar_one())

    def get_by_email(self, email: str) -> Optional[UserModel]:
        normalized = email.strip().lower()
        with self.session_factory() as session:
            statement = select(UserModel).where(UserModel.email == normalized)
            return session.execute(statement).scalar_one_or_none()

    def create_user(
        self,
        *,
        user_id: str,
        email: str,
        full_name: str,
        password_hash: str,
        role: str,
        is_superuser: bool,
        is_active: bool,
        created_at: datetime,
        updated_at: datetime,
        last_login_at: Optional[datetime],
    ) -> UserModel:
        with self.session_factory() as session:
            user = UserModel(
                user_id=user_id,
                email=email.strip().lower(),
                full_name=full_name.strip(),
                password_hash=password_hash,
                role=role,
                is_superuser=is_superuser,
                is_active=is_active,
                created_at=created_at,
                updated_at=updated_at,
                last_login_at=last_login_at,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def update_last_login(self, email: str, at: datetime) -> Optional[UserModel]:
        normalized = email.strip().lower()
        with self.session_factory() as session:
            statement = select(UserModel).where(UserModel.email == normalized)
            user = session.execute(statement).scalar_one_or_none()
            if user is None:
                return None
            user.last_login_at = at
            user.updated_at = at
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
