import uuid
import logging
from typing import Protocol
from typing_extensions import Self
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.file import FileRepositoryProtocol
from ..schemas import FileCreateSchema, FileReadSchema, FileUploadResponseSchema
from .minio_service import MinioServiceProtocol

logger = logging.getLogger(__name__)


class FileServiceProtocol(Protocol):
    """Протокол сервиса файлов"""

    async def upload_file(
        self: Self, file: UploadFile, custom_path: str | None = None
    ) -> FileUploadResponseSchema: ...

    async def get_file_url(
        self: Self, file_id: uuid.UUID, expires_in: int = 1800
    ) -> str: ...
    async def get_file(self: Self, file_id: uuid.UUID) -> FileReadSchema: ...
    async def delete_file(self: Self, file_id: uuid.UUID) -> bool: ...


class FileService(FileServiceProtocol):
    """Сервис для работы с файлами"""

    def __init__(
        self: Self,
        session: AsyncSession,
        file_repository: FileRepositoryProtocol,
        minio_service: MinioServiceProtocol,
        standart_path: str = "files",
    ):
        self.session = session
        self.file_repository = file_repository
        self.minio_service = minio_service
        self.standart_path = standart_path

    async def upload_file(
        self: Self, file: UploadFile, custom_path: str | None = None
    ) -> FileUploadResponseSchema:
        """Загрузить файл в MinIO и сохранить метаданные в БД"""
        file_id = uuid.uuid4()
        filename = file.filename or f"file_{file_id}"

        if custom_path:
            path = f"{custom_path}/{file_id}_{filename}"
        else:
            path = f"{self.standart_path}/{file_id}_{filename}"

        content = await file.read()
        size = len(content)
        content_type = file.content_type or "application/octet-stream"

        await file.seek(0)

        success = await self.minio_service.upload_file(path, file)
        if not success:
            raise Exception(f"Failed to upload file to MinIO: {path}")

        file_create = FileCreateSchema(
            id=file_id,
            path=path,
            filename=filename,
            content_type=content_type,
            size=size,
        )

        file_record = await self.file_repository.create(file_create)

        await self.session.commit()

        url = await self.minio_service.get_presigned_url(path)

        return FileUploadResponseSchema(
            file_id=file_record.id,
            path=file_record.path,
            filename=file_record.filename,
            url=url,
            size=file_record.size,
        )

    async def get_file_url(
        self: Self, file_id: uuid.UUID, expires_in: int = 1800
    ) -> str:
        """Получить URL для доступа к файлу"""
        file_record = await self.file_repository.get(file_id)
        return await self.minio_service.get_presigned_url(file_record.path, expires_in)

    async def get_file(self: Self, file_id: uuid.UUID) -> FileReadSchema:
        """Получить метаданные файла по идентификатору."""
        return await self.file_repository.get(file_id)

    async def delete_file(self: Self, file_id: uuid.UUID) -> bool:
        """Удалить файл из MinIO и БД"""
        file_record = await self.file_repository.get(file_id)

        minio_deleted = await self.minio_service.delete_file(file_record.path)
        if not minio_deleted:
            logger.warning(f"Failed to delete file from MinIO: {file_record.path}")

        db_deleted = await self.file_repository.delete(file_id)

        await self.session.commit()

        return minio_deleted and db_deleted
