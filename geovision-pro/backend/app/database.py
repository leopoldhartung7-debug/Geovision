"""Async SQLAlchemy engine/session setup."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=settings.debug, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_models() -> None:
    """Create tables on startup if they do not exist (dev convenience).

    For production use the SQL migration in sql/schema.sql or Alembic.
    """
    from . import models  # noqa: F401  (register models)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
