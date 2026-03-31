import uuid
from pydantic import BaseModel, ConfigDict, Field

from reflebot.core.schemas import CreateBaseModel, UpdateBaseModel


class FileBaseSchema(BaseModel):
    """Базовая схема файла"""

    path: str = Field(..., max_length=256)
    filename: str = Field(..., max_length=256)
    content_type: str = Field(..., max_length=256)
    size: int = Field(..., ge=0)


class FileCreateSchema(FileBaseSchema, CreateBaseModel):
    """Схема создания файла"""

    pass


class FileUpdateSchema(UpdateBaseModel):
    """Схема обновления файла"""

    path: str | None = Field(None, max_length=256)
    filename: str | None = Field(None, max_length=256)
    content_type: str | None = Field(None, max_length=256)
    size: int | None = Field(None, ge=0)


class FileReadSchema(FileBaseSchema):
    """Схема чтения файла"""

    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


class FileUploadResponseSchema(BaseModel):
    """Схема ответа при загрузке файла"""

    file_id: uuid.UUID
    path: str
    filename: str
    url: str
    size: int
