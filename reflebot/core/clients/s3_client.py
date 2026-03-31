import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from typing_extensions import Self

from aiobotocore.session import get_session
from types_aiobotocore_s3 import S3Client

logger = logging.getLogger(__name__)


class S3ClientFactory:
    """Фабрика для создания S3 клиентов"""

    def __init__(
        self: Self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
    ):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self._session = get_session()

    @asynccontextmanager
    async def get_client(self: Self) -> AsyncGenerator[S3Client, None]:
        """Создает асинхронный S3 клиент"""
        async with self._session.create_client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        ) as client:
            yield client
