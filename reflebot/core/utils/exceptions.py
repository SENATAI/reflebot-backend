import uuid
from typing import Any, Generic, TypeVar

from fastapi import HTTPException, status

from ..db import Base

ModelType = TypeVar('ModelType', bound=Base)


class CoreException(HTTPException):
    """
    Базовый класс для всех исключений приложения.
    """
    error_code: str = "UNKNOWN_ERROR"
    
    def __init__(
        self, 
        status_code: int, 
        detail: str, 
        error_code: str | None = None,
        headers: dict[str, Any] | None = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        if error_code:
            self.error_code = error_code

    def to_dict(self) -> dict:
        return {
            "detail": self.detail,
            "error_code": self.error_code,
        }


class ModelNotFoundException(CoreException, Generic[ModelType]):
    """
    Исключение не найденной модели.
    """
    error_code = "MODEL_NOT_FOUND"
    
    def __init__(
        self,
        model: type[ModelType],
        model_id: uuid.UUID | int | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        detail = (
            f'Unable to find the {model.__name__} with id {model_id}.'
            if model_id is not None
            else f'{model.__name__} id not found.'
        )
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=detail, 
            error_code=self.error_code,
            headers=headers
        )


class ModelFieldNotFoundException(CoreException, Generic[ModelType]):
    """
    Исключение, возникающее при отсутствии модели с указанным значением поля.
    """
    error_code = "MODEL_FIELD_NOT_FOUND"
    
    def __init__(
        self,
        model: type[ModelType],
        field: str,
        value: Any,
        headers: dict[str, Any] | None = None,
    ) -> None:
        detail = f'Unable to find the {model.__name__} with {field} equal to {value}.'
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=detail,
            error_code=self.error_code,
            headers=headers
        )


class PermissionDeniedError(CoreException):
    """
    Ошибка, возникающая при недостатке прав для выполнения действия.
    """
    error_code = "PERMISSION_DENIED"
    
    def __init__(
        self,
        detail: str = 'Insufficient rights to perform the action',
        headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=detail,
            error_code=self.error_code,
            headers=headers
        )


class ModelAlreadyExistsError(CoreException):
    """
    Ошибка, возникающая при попытке создать модель с существующим уникальным полем.
    """
    error_code = "MODEL_ALREADY_EXISTS"
    
    def __init__(
        self,
        model: type[ModelType],
        field: str, 
        message: str, 
        headers: dict[str, Any] | None = None
    ) -> None:
        detail = f'Model {model.__name__} with {field} already exists: {message}'
        super().__init__(
            status_code=status.HTTP_409_CONFLICT, 
            detail=detail,
            error_code=self.error_code,
            headers=headers
        )
        self.field = field


class ValidationError(CoreException):
    """
    Ошибка валидации.
    """
    error_code = "VALIDATION_ERROR"
    
    def __init__(
        self, 
        field: str | list[str], 
        message: str, 
        headers: dict[str, Any] | None = None
    ) -> None:
        detail = f'Validation error in {field}: {message}'
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=detail,
            error_code=self.error_code,
            headers=headers
        )
        self.field = field


class SortingFieldNotFoundError(CoreException):
    """
    Ошибка, возникающая при невозможности найти поле для сортировки.
    """
    error_code = "SORTING_FIELD_NOT_FOUND"
    
    def __init__(
        self, 
        field: str, 
        headers: dict[str, Any] | None = None
    ) -> None:
        detail = f'Failed to find a field to sort: {field}'
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=detail,
            error_code=self.error_code,
            headers=headers
        )
        self.field = field


class FileNotFound(CoreException):
    """
    Исключение, если файл не найден.
    """
    error_code = "FILE_NOT_FOUND"
    
    def __init__(
        self, 
        path: str, 
        headers: dict[str, str] | None = None
    ) -> None:
        detail = f'File {path} not found.'
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=detail,
            error_code=self.error_code,
            headers=headers
        )
        self.path = path


class UnauthorizedError(CoreException):
    """
    Ошибка неавторизованного доступа.
    """
    error_code = "UNAUTHORIZED"
    
    def __init__(
        self,
        detail: str = 'Authentication required',
        headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code=self.error_code,
            headers=headers
        )


class InvalidAPIKeyError(CoreException):
    """
    Ошибка неверного API ключа.
    """
    error_code = "INVALID_API_KEY"
    
    def __init__(
        self,
        detail: str = 'Invalid API key',
        headers: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code=self.error_code,
            headers=headers
        )
