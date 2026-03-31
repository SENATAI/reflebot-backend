"""
Сервис для работы с контекстом пользователя.
"""

from typing import Protocol, Any

from ..repositories.user import UserRepositoryProtocol
from ..schemas import UserReadSchema


class ContextServiceProtocol(Protocol):
    """Протокол сервиса контекста."""
    
    async def get_context(self, telegram_id: int) -> dict | None:
        """Получить контекст пользователя."""
        ...
    
    async def set_context(
        self, telegram_id: int, action: str, step: str, data: dict | None = None
    ) -> UserReadSchema:
        """Установить контекст пользователя."""
        ...
    
    async def update_context_data(
        self, telegram_id: int, key: str, value: Any
    ) -> UserReadSchema:
        """Обновить данные в контексте пользователя."""
        ...
    
    async def clear_context(self, telegram_id: int) -> UserReadSchema | None:
        """Очистить контекст пользователя."""
        ...
    
    async def push_navigation(self, telegram_id: int, screen: str) -> UserReadSchema:
        """Добавить экран в историю навигации."""
        ...
    
    async def pop_navigation(self, telegram_id: int) -> str | None:
        """Вернуться на предыдущий экран."""
        ...


class ContextService(ContextServiceProtocol):
    """Сервис для работы с контекстом пользователя."""
    
    def __init__(self, user_repository: UserRepositoryProtocol):
        self.user_repository = user_repository
    
    async def get_context(self, telegram_id: int) -> dict | None:
        """Получить контекст пользователя."""
        user = await self.user_repository.get_by_telegram_id(telegram_id)
        return user.user_context if user else None
    
    async def set_context(
        self, telegram_id: int, action: str, step: str, data: dict | None = None
    ) -> UserReadSchema:
        """
        Установить контекст пользователя.
        
        Args:
            telegram_id: ID пользователя в Telegram
            action: Действие (например, "create_admin")
            step: Текущий шаг (например, "awaiting_fullname")
            data: Дополнительные данные контекста
        """
        existing_context = await self.get_context(telegram_id)
        context = {
            "action": action,
            "step": step,
            "data": data or {},
        }
        if existing_context and "navigation_history" in existing_context:
            context["navigation_history"] = existing_context["navigation_history"]
        return await self.user_repository.upsert_context(telegram_id, context)
    
    async def update_context_data(
        self, telegram_id: int, key: str, value: Any
    ) -> UserReadSchema:
        """
        Обновить данные в контексте пользователя.
        
        Args:
            telegram_id: ID пользователя в Telegram
            key: Ключ данных
            value: Значение
        """
        context = await self.get_context(telegram_id)
        
        if not context:
            raise ValueError("Контекст пользователя не найден")
        
        if "data" not in context:
            context["data"] = {}
        
        context["data"][key] = value
        
        return await self.user_repository.upsert_context(telegram_id, context)
    
    async def clear_context(self, telegram_id: int) -> UserReadSchema | None:
        """Очистить контекст пользователя."""
        return await self.user_repository.clear_context(telegram_id)
    
    async def push_navigation(self, telegram_id: int, screen: str) -> UserReadSchema:
        """
        Добавить экран в историю навигации.
        
        Args:
            telegram_id: ID пользователя в Telegram
            screen: Идентификатор экрана для добавления в историю
        
        Returns:
            Обновленная схема пользователя
        """
        context = await self.get_context(telegram_id)
        
        if not context:
            # Если контекста нет, создаем новый с историей навигации
            context = {
                "action": None,
                "step": None,
                "data": {},
                "navigation_history": [screen]
            }
        else:
            # Добавляем экран в историю навигации
            if "navigation_history" not in context:
                context["navigation_history"] = []
            context["navigation_history"].append(screen)
        
        return await self.user_repository.upsert_context(telegram_id, context)
    
    async def pop_navigation(self, telegram_id: int) -> str | None:
        """
        Вернуться на предыдущий экран.
        
        Удаляет текущий экран из истории и возвращает предыдущий.
        
        Args:
            telegram_id: ID пользователя в Telegram
        
        Returns:
            Идентификатор предыдущего экрана или None, если история пуста
        """
        context = await self.get_context(telegram_id)
        
        if not context or "navigation_history" not in context:
            return None
        
        navigation_history = context["navigation_history"]
        
        if not navigation_history:
            return None
        
        # Удаляем текущий экран
        if len(navigation_history) > 0:
            navigation_history.pop()
        
        # Получаем предыдущий экран (если есть)
        previous_screen = navigation_history[-1] if navigation_history else None
        
        # Обновляем контекст
        await self.user_repository.upsert_context(telegram_id, context)
        
        return previous_screen
