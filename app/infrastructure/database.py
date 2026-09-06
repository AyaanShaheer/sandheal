from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    """


def create_engine() -> AsyncEngine:
    """
    Create the application's asynchronous SQLAlchemy engine.
    """
    settings = get_settings()

    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
    )


engine = create_engine()

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session for an application request.
    """
    async with SessionFactory() as session:
        yield session
