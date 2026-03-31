import uuid
from typing_extensions import Self
import sqlalchemy as sa

from reflebot.core.repositories.base_repository import (
    BaseRepositoryImpl,
    BaseRepositoryProtocol,
)
from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from ..models import File
from ..schemas import FileCreateSchema, FileReadSchema, FileUpdateSchema


class FileRepositoryProtocol(
    BaseRepositoryProtocol[File, FileReadSchema, FileCreateSchema, FileUpdateSchema]
):
    """Протокол репозитория файлов"""

    async def get_by_path(self: Self, path: str) -> FileReadSchema: ...
    async def find_by_path(self: Self, path: str) -> FileReadSchema | None: ...


class FileRepository(
    BaseRepositoryImpl[File, FileReadSchema, FileCreateSchema, FileUpdateSchema],
    FileRepositoryProtocol,
):
    """Репозиторий для работы с файлами в БД"""

    async def get_by_path(self: Self, path: str) -> FileReadSchema:
        """Получить файл по пути"""
        stmt = sa.select(self.model_type).where(self.model_type.path == path)
        result = (await self.session.execute(stmt)).scalar_one_or_none()
        if not result:
            raise ModelFieldNotFoundException(self.model_type, "path", path)
        return self.read_schema_type.model_validate(result, from_attributes=True)

    async def find_by_path(self: Self, path: str) -> FileReadSchema | None:
        """Найти файл по пути (возвращает None если не найден)"""
        stmt = sa.select(self.model_type).where(self.model_type.path == path)
        result = (await self.session.execute(stmt)).scalar_one_or_none()
        return (
            self.read_schema_type.model_validate(result, from_attributes=True)
            if result
            else None
        )
