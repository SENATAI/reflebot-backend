"""
Модуль, содержащий базовые схемы.
"""

import uuid
from typing import Generic, TypeVar

from pydantic import AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from datetime import datetime, timezone


class CreateBaseModel(BaseModel):
    """
    Контракт для создания моделей.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None


class UpdateBaseModel(BaseModel):
    """
    Контракт обновления моделей.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class StatusOkSchema(BaseModel):
    """
    Схема успешного результата.
    """

    status: str = 'ok'


class PaginationSchema(BaseModel):
    """
    Схема пагинации с помощью limit и offset.
    """

    limit: int
    offset: int


T = TypeVar('T')


class PaginationResultSchema(BaseModel, Generic[T]):
    """
    Схема результата пагинации.
    """

    objects: list[T]
    count: int
    

class InputApiSchema(BaseModel):
    """
    Входная API схема.
    """

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            validation_alias=to_camel,
        )
    )


class OutputApiSchema(BaseModel):
    """
    Выходная API схема.
    """

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        )
    )

class TimestampMixin(BaseModel):
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),  # Используем timezone-aware datetime
        description="Дата и время создания"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),  # Используем timezone-aware datetime
        description="Дата и время последнего обновления"
    )

    def update_timestamp(self):
        self.updated_at = datetime.now(timezone.utc)
