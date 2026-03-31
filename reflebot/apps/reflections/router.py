"""
Главный роутер модуля рефлексий.
"""

from fastapi import APIRouter

from .routers import actions, auth


router = APIRouter(prefix="/api/reflections", tags=["Reflections"])

# Подключаем роутеры
router.include_router(auth.router)
router.include_router(actions.router)
