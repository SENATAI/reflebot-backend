from typing import Annotated, AsyncGenerator
from fastapi import Depends
from sqlalchemy import MetaData, Integer
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from ..settings import settings

__all__ = (
    'Base',
    'Session',
    'AsyncSession',
    'get_async_session',
)

POSTGRES_INDEXES_NAMING_CONVENTION = {
    'ix': '%(column_0_label)s_idx',
    'uq': '%(table_name)s_%(column_0_name)s_key',
    'ck': '%(table_name)s_%(constraint_name)s_check',
    'fk': '%(table_name)s_%(column_0_name)s_fkey',
    'pk': '%(table_name)s_pkey',
}

metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)

asyncio_engine = create_async_engine(
    settings.db.dsn,
    connect_args={'options': f'-csearch_path={settings.db.scheme}'},
    echo=settings.debug
)

AsyncSessionFactory = async_sessionmaker(
    asyncio_engine,
    autocommit=False,
    expire_on_commit=False,
    future=True,
    autoflush=False,
)

class Base(AsyncAttrs, DeclarativeBase):
    """Базовый класс для всех моделей"""
    metadata = metadata

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Генератор асинхронных сессий для FastAPI"""
    async with AsyncSessionFactory() as session:
        # logger.debug(f"ASYNC Pool: {asyncio_engine.pool.status()}")
        yield session

Session = Annotated[AsyncSession, Depends(get_async_session)]