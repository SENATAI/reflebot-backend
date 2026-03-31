"""
Основной модуль для middleware приложения.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from .settings import settings


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware для проверки API ключа в заголовке X-Service-API-Key.
    """
    
    # Пути, которые не требуют проверки API ключа
    EXCLUDED_PATHS = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/docs.json",
    ]
    
    async def dispatch(self, request: Request, call_next):
        """
        Проверяем API ключ для всех запросов, кроме исключённых.
        """
        # Пропускаем проверку для документации
        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)
        
        # Получаем API ключ из заголовка
        api_key = request.headers.get("X-Service-API-Key")
        
        # Проверяем наличие и корректность API ключа
        if not api_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Отсутствует заголовок X-Service-API-Key",
                    "error_code": "MISSING_API_KEY"
                }
            )
        
        if api_key != settings.telegram_secret_token:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "Неверный API ключ",
                    "error_code": "INVALID_API_KEY"
                }
            )
        
        # API ключ корректен, продолжаем обработку запроса
        response = await call_next(request)
        return response


def apply_middleware(app: FastAPI) -> FastAPI:
    """
    Применяем middleware.
    """
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    
    # API Key middleware
    app.add_middleware(APIKeyMiddleware)
    
    return app