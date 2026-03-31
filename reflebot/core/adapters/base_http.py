import httpx
import logging
from typing import Any, Type, Protocol, TypeVar, Optional
from pydantic import BaseModel, ValidationError
from ..utils.exceptions import (
    ExternalServiceError, 
    ExternalServiceTimeoutError, 
)
from ..utils.token_manager import ServiceTokenManager


logger = logging.getLogger(__name__)


T = TypeVar('T', bound=BaseModel)
E = TypeVar('E', bound=BaseModel)


token_manager = ServiceTokenManager()

async def initialize_token_manager():
    """Инициализация менеджера токенов (вызывать при старте приложения)"""
    await token_manager.initialize()

class HttpClientProtocol(Protocol):
    """Простой протокол без навязанного CRUD"""
    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        response_model: Type[T],
        error_model: Type[E] = BaseModel,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
        allow_empty: bool = False
    ) -> T:
        ...

class BaseHttpClientImpl:
    """
    Базовый HTTP-клиент с гибкой типизацией для работы с разными схемами ответов.
    
    Особенности:
    - Схема ответа указывается для каждого запроса отдельно через параметр response_model
    - Поддержка кастомных схем ошибок через error_model
    - Автоматическая обработка стандартных HTTP-ошибок (404, 403 и т.д.)
    - Полная типобезопасность благодаря TypeVar
    """
    
    def __init__(
        self,
        base_url: str,
        target_service: str,
        permissions: list[str],
        timeout: float = 15.0,
        headers: Optional[dict[str, str]] = None,
    ):
        """
        Инициализация HTTP-клиента.
        
        :param base_url: Базовый URL сервиса (без завершающего слеша)
        :param target_service: Название целевого сервиса для логирования и аутентификации
        :param permissions: Список необходимых разрешений для доступа к сервису
        :param timeout: Таймаут запроса в секундах
        :param headers: Общие заголовки для всех запросов
        """
        self.base_url = base_url.rstrip('/')
        self.target_service = target_service
        self.permissions = permissions
        self.timeout = timeout
        self.headers = headers or {}
        
    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        response_model: Type[T],
        error_model: Type[E] = BaseModel,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
        allow_empty: bool = False
    ) -> T:
        """
        Универсальный метод для выполнения HTTP-запросов с указанием схемы ответа.
        
        :param method: HTTP метод (GET, POST, PUT и т.д.)
        :param endpoint: Конечная точка API (без базового URL)
        :param response_model: Pydantic-модель для успешного ответа
        :param error_model: Pydantic-модель для ошибки
        :param params: Параметры запроса (для GET)
        :param json: JSON-тело запроса
        :param data: Form-data тело запроса
        :param headers: Дополнительные заголовки
        :param timeout: Таймаут запроса
        :param allow_empty: Разрешить пустой ответ (204 No Content)
        
        :return: Распарсенный ответ в соответствии с response_model
        """
        # Получаем токен для доступа к сервису
        token = await token_manager.get_token(
            target_service=self.target_service,
            permissions=self.permissions
        )
        
        # Формируем полный URL
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Формируем заголовки запроса
        request_headers = {
            **self.headers,
            **(headers or {}),
            "Authorization": f"Bearer {token}"
        }
        
        # Определяем таймаут
        request_timeout = timeout or self.timeout
        
        # Логируем запрос
        logger.debug(
            "HTTP request: %s %s, headers=%s, params=%s, json=%s", 
            method, url, request_headers, params, json
        )
        
        try:
            # Выполняем запрос
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    data=data,
                    headers=request_headers
                )
                
                # Логируем ответ
                logger.debug(
                    "HTTP response: %s %s, status=%d, body=%s", 
                    method, url, response.status_code, response.text
                )
                
                # Обработка пустого ответа (204 No Content)
                if allow_empty and response.status_code == 204:
                    return None  # type: ignore
                
                # Проверяем статус ответа
                response.raise_for_status()
                
                # Парсим успешный ответ
                return response_model.model_validate(response.json())
                
        except httpx.TimeoutException as e:
            logger.error("HTTP request timed out: %s %s", method, url)
            raise ExternalServiceTimeoutError(
                self.target_service, 
                method, 
                url, 
                "Request timed out", 
                "504"
            ) from e
            
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(
                "HTTP request failed with status %d: %s %s, response=%s", 
                status_code, method, url, e.response.text
            )
            
            # Попытка распарсить тело ошибки
            try:
                error_data = e.response.json()
                error = error_model.model_validate(error_data)

                error_detail = (
                    error.detail if hasattr(error, 'detail') 
                    else str(error) if hasattr(error, '__str__') 
                    else "Unknown error"
                )
                
                raise ExternalServiceError(
                    self.target_service, 
                    method, 
                    url, 
                    error_detail, 
                    error.error_code,
                    status_code=status_code,
                    extras=error.extras
                ) from e
                
            except (ValueError, ValidationError, KeyError, AttributeError) as parse_error:
                # Если не удалось распарсить ошибку, используем общее сообщение
                logger.warning("Failed to parse error response: %s", parse_error)
                error_detail = f"HTTP error {status_code}"
                raise ExternalServiceError(
                    self.target_service, 
                    method, 
                    url, 
                    error_detail, 
                    status_code,
                    status_code=status_code
                ) from e
            