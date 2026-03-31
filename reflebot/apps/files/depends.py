from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from reflebot.core.db import get_async_session
from reflebot.core.clients.s3_client import S3ClientFactory
from reflebot.settings import Settings, get_settings

from .repositories.file import FileRepository, FileRepositoryProtocol
from .services.minio_service import MinioService, MinioServiceProtocol
from .services.file_service import FileService, FileServiceProtocol


def __get_file_repository(
    session: AsyncSession = Depends(get_async_session),
) -> FileRepositoryProtocol:
    """Приватная фабрика репозитория файлов"""
    return FileRepository(session=session)


def get_s3_client_factory(
    settings: Settings = Depends(get_settings),
) -> S3ClientFactory:
    """Фабрика S3 клиента"""
    return S3ClientFactory(
        endpoint_url=settings.minio.endpoint,
        access_key=settings.minio.access_key,
        secret_key=settings.minio.secret_key,
    )


def get_minio_service(
    client_factory: S3ClientFactory = Depends(get_s3_client_factory),
    settings: Settings = Depends(get_settings),
) -> MinioServiceProtocol:
    """Фабрика сервиса MinIO"""
    return MinioService(
        client_factory=client_factory,
        bucket_name=settings.minio.bucket_name,
        real_url=settings.minio.real_url,
        url_to_change=settings.minio.url_to_change,
    )


def get_file_service(
    session: AsyncSession = Depends(get_async_session),
    minio_service: MinioServiceProtocol = Depends(get_minio_service),
    settings: Settings = Depends(get_settings),
) -> FileServiceProtocol:
    """Фабрика сервиса файлов"""
    file_repository = FileRepository(session=session)
    return FileService(
        session=session,
        file_repository=file_repository,
        minio_service=minio_service,
        standart_path=settings.minio.standart_path,
    )


FileServiceDep = Annotated[FileServiceProtocol, Depends(get_file_service)]
