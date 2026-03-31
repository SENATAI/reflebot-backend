"""
Основной модуль для роутов приложения.
"""

from fastapi import FastAPI

from reflebot.apps.reflections.router import router as reflections_router


def apply_routes(app: FastAPI) -> FastAPI:
    """
    Применяем роуты приложения.
    """
    app.include_router(reflections_router)
    return app