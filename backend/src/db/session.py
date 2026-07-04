from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import Settings


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database.url,
        future=True,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if settings.database.url.startswith("sqlite") else {},
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
