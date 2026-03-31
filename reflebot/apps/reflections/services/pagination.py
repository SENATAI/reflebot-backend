"""
Сервис для пагинации списков.
"""

from typing import Protocol, Any

from ..schemas import TelegramButtonSchema


class PaginationServiceProtocol(Protocol):
    """Протокол сервиса пагинации."""
    
    def paginate(
        self, 
        items: list[Any], 
        page: int, 
        page_size: int
    ) -> dict[str, Any]:
        """Разбить список на страницы."""
        ...
    
    def get_pagination_buttons(
        self, 
        current_page: int, 
        total_pages: int, 
        action_prefix: str
    ) -> list[TelegramButtonSchema]:
        """Сгенерировать кнопки навигации для пагинации."""
        ...


class PaginationService(PaginationServiceProtocol):
    """Сервис для пагинации списков."""
    
    def paginate(
        self, 
        items: list[Any], 
        page: int, 
        page_size: int
    ) -> dict[str, Any]:
        """
        Разбить список на страницы.
        
        Args:
            items: Список элементов для пагинации
            page: Номер текущей страницы (начиная с 1)
            page_size: Количество элементов на странице
        
        Returns:
            Словарь с полями:
            - items: список элементов текущей страницы
            - total: общее количество элементов
            - page: текущая страница
            - page_size: размер страницы
            - total_pages: общее количество страниц
        """
        total = len(items)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        
        # Валидация номера страницы
        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages
        
        # Вычисление индексов для среза
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        # Получение элементов текущей страницы
        page_items = items[start_index:end_index]
        
        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
    
    def get_pagination_buttons(
        self, 
        current_page: int, 
        total_pages: int, 
        action_prefix: str
    ) -> list[TelegramButtonSchema]:
        """
        Сгенерировать кнопки навигации для пагинации.
        
        Args:
            current_page: Номер текущей страницы
            total_pages: Общее количество страниц
            action_prefix: Префикс для action кнопок (например, "view_lections")
        
        Returns:
            Список кнопок для навигации по страницам
        """
        buttons: list[TelegramButtonSchema] = []
        
        # Кнопка "Предыдущая страница" (если не первая страница)
        if current_page > 1:
            buttons.append(TelegramButtonSchema(
                text="◀️ Предыдущая страница",
                action=f"{action_prefix}_page_{current_page - 1}"
            ))
        
        # Кнопка "Следующая страница" (если не последняя страница)
        if current_page < total_pages:
            buttons.append(TelegramButtonSchema(
                text="Следующая страница ▶️",
                action=f"{action_prefix}_page_{current_page + 1}"
            ))
        
        return buttons
