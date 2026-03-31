"""
Use cases для работы с администраторами.
"""

from typing import Protocol

from reflebot.core.use_cases import UseCaseProtocol
from ..services.admin import AdminServiceProtocol
from ..schemas import AdminCreateSchema, AdminReadSchema, AdminLoginSchema, UserLoginResponseSchema


class CreateAdminUseCaseProtocol(UseCaseProtocol[AdminReadSchema]):
    """Протокол use case создания администратора."""
    
    async def __call__(
        self, data: AdminCreateSchema, current_admin: AdminReadSchema
    ) -> AdminReadSchema:
        ...


class CreateAdminUseCase(CreateAdminUseCaseProtocol):
    """Use case для создания администратора."""
    
    def __init__(self, admin_service: AdminServiceProtocol):
        self.admin_service = admin_service
    
    async def __call__(
        self, data: AdminCreateSchema, current_admin: AdminReadSchema
    ) -> AdminReadSchema:
        """
        Создать администратора.
        
        Доступ к use case должен контролироваться вызывающим workflow.
        Если current_admin передан, значит проверка прав уже выполнена.
        """
        return await self.admin_service.create_admin(data)


class AdminLoginUseCaseProtocol(UseCaseProtocol[UserLoginResponseSchema]):
    """Протокол use case входа пользователя."""
    
    async def __call__(
        self, telegram_username: str, login_data: AdminLoginSchema
    ) -> UserLoginResponseSchema:
        ...


class AdminLoginUseCase(AdminLoginUseCaseProtocol):
    """Use case для входа пользователя."""
    
    def __init__(self, auth_service):
        self.auth_service = auth_service
    
    async def __call__(
        self, telegram_username: str, login_data: AdminLoginSchema
    ) -> UserLoginResponseSchema:
        """
        Вход пользователя.
        
        Проверяет наличие пользователя в Admin, Student, Teacher
        и обновляет telegram_id во всех найденных записях.
        """
        return await self.auth_service.login_user(telegram_username, login_data)
