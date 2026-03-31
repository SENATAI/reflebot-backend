"""
Сервис для работы с администраторами.
"""

from typing import Protocol

from ..repositories.student import StudentRepositoryProtocol
from ..repositories.teacher import TeacherRepositoryProtocol
from ..repositories.admin import AdminRepositoryProtocol
from ..schemas import AdminCreateSchema, AdminReadSchema


class AdminServiceProtocol(Protocol):
    """Протокол сервиса администраторов."""
    
    async def create_admin(self, data: AdminCreateSchema) -> AdminReadSchema:
        """Создать администратора."""
        ...
    
    async def get_by_telegram_username(self, telegram_username: str) -> AdminReadSchema:
        """Получить администратора по никнейму в Telegram."""
        ...
    
    async def get_by_telegram_id(self, telegram_id: int) -> AdminReadSchema:
        """Получить администратора по ID в Telegram."""
        ...
    
    async def update_telegram_id(
        self, telegram_username: str, telegram_id: int
    ) -> AdminReadSchema:
        """Обновить telegram_id администратора."""
        ...


class AdminService(AdminServiceProtocol):
    """Сервис для работы с администраторами."""
    
    def __init__(
        self,
        repository: AdminRepositoryProtocol,
        student_repository: StudentRepositoryProtocol | None = None,
        teacher_repository: TeacherRepositoryProtocol | None = None,
    ):
        self.repository = repository
        self.student_repository = student_repository
        self.teacher_repository = teacher_repository

    async def _get_related_telegram_id(self, telegram_username: str) -> int | None:
        """Получить telegram_id из соседних таблиц по username."""
        if self.teacher_repository is not None:
            teacher = await self.teacher_repository.get_by_telegram_username(telegram_username)
            if teacher and teacher.telegram_id is not None:
                return teacher.telegram_id

        if self.student_repository is not None:
            student = await self.student_repository.get_by_telegram_username(telegram_username)
            if student and student.telegram_id is not None:
                return student.telegram_id

        return None
    
    async def create_admin(self, data: AdminCreateSchema) -> AdminReadSchema:
        """Создать администратора."""
        if data.telegram_id is not None:
            return await self.repository.create(data)

        inherited_telegram_id = await self._get_related_telegram_id(data.telegram_username)
        create_data = data.model_copy(update={"telegram_id": inherited_telegram_id})
        return await self.repository.create(create_data)
    
    async def get_by_telegram_username(self, telegram_username: str) -> AdminReadSchema:
        """Получить администратора по никнейму в Telegram."""
        return await self.repository.get_by_telegram_username(telegram_username)
    
    async def get_by_telegram_id(self, telegram_id: int) -> AdminReadSchema:
        """Получить администратора по ID в Telegram."""
        return await self.repository.get_by_telegram_id(telegram_id)
    
    async def update_telegram_id(
        self, telegram_username: str, telegram_id: int
    ) -> AdminReadSchema:
        """Обновить telegram_id администратора."""
        return await self.repository.update_telegram_id(telegram_username, telegram_id)
