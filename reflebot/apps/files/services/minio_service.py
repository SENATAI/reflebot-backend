import logging
from typing import Protocol, cast
from typing_extensions import Self
from botocore.exceptions import ClientError
from fastapi import UploadFile
from types_aiobotocore_s3 import S3Client

from reflebot.core.clients.s3_client import S3ClientFactory

logger = logging.getLogger(__name__)


class MinioServiceProtocol(Protocol):
    """Протокол сервиса для работы с MinIO"""

    async def upload_file(self: Self, path: str, file: UploadFile) -> bool: ...
    async def upload_content(
        self: Self, path: str, content: bytes, content_type: str
    ) -> bool: ...
    async def get_presigned_url(self: Self, path: str, expires_in: int) -> str: ...
    async def delete_file(self: Self, path: str) -> bool: ...
    async def file_exists(self: Self, path: str) -> bool: ...


class MinioService(MinioServiceProtocol):
    """Сервис для работы с MinIO S3"""

    def __init__(
        self: Self,
        client_factory: S3ClientFactory,
        bucket_name: str,
        real_url: str,
        url_to_change: str,
    ):
        self.client_factory = client_factory
        self.bucket_name = bucket_name
        self.real_url = real_url
        self.url_to_change = url_to_change
        self._bucket_checked = False

    async def _ensure_bucket_exists(self: Self) -> None:
        """Проверка и создание bucket если не существует"""
        if self._bucket_checked:
            return

        try:
            async with self.client_factory.get_client() as client:
                s3_client = cast(S3Client, client)
                try:
                    await s3_client.head_bucket(Bucket=self.bucket_name)
                except ClientError as e:
                    if e.response["Error"]["Code"] == "404":
                        await s3_client.create_bucket(Bucket=self.bucket_name)
                        logger.info(f"Bucket {self.bucket_name} created")
                    else:
                        raise
            self._bucket_checked = True
        except Exception as e:
            logger.error(f"Failed to ensure bucket exists: {e}")
            raise

    async def upload_file(self: Self, path: str, file: UploadFile) -> bool:
        """Загрузить файл из UploadFile"""
        await self._ensure_bucket_exists()
        try:
            contents = await file.read()
            content_type = file.content_type or "application/octet-stream"
            return await self.upload_content(path, contents, content_type)
        except Exception as e:
            logger.error(f"Failed to upload file {path}: {e}")
            return False

    async def upload_content(
        self: Self, path: str, content: bytes, content_type: str
    ) -> bool:
        """Загрузить контент напрямую"""
        await self._ensure_bucket_exists()
        try:
            async with self.client_factory.get_client() as client:
                s3_client = cast(S3Client, client)
                await s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=path,
                    Body=content,
                    ContentType=content_type,
                )
            logger.info(f"File uploaded successfully: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload content {path}: {e}")
            return False

    async def get_presigned_url(self: Self, path: str, expires_in: int = 1800) -> str:
        """Получить presigned URL для доступа к файлу"""
        await self._ensure_bucket_exists()
        try:
            async with self.client_factory.get_client() as client:
                s3_client = cast(S3Client, client)
                url = await s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": path},
                    ExpiresIn=expires_in,
                )

            return url
        except Exception as e:
            logger.error(f"Failed to generate URL for {path}: {e}")
            raise

    async def delete_file(self: Self, path: str) -> bool:
        """Удалить файл из MinIO"""
        await self._ensure_bucket_exists()
        try:
            async with self.client_factory.get_client() as client:
                s3_client = cast(S3Client, client)

                if not await self.file_exists(path):
                    logger.warning(f"File not found for deletion: {path}")
                    return False

                await s3_client.delete_object(Bucket=self.bucket_name, Key=path)

            logger.info(f"File deleted successfully: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {path}: {e}")
            return False

    async def file_exists(self: Self, path: str) -> bool:
        """Проверить существование файла"""
        try:
            async with self.client_factory.get_client() as client:
                s3_client = cast(S3Client, client)
                await s3_client.head_object(Bucket=self.bucket_name, Key=path)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise
