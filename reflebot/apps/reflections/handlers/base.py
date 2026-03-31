"""
Общие хелперы для action handlers.
"""

from dataclasses import dataclass
import logging

from reflebot.core.utils.exceptions import PermissionDeniedError, ValidationError
from ..exceptions import CSVParsingError, ExcelParsingError
from ..schemas import (
    ActionResponseSchema,
    AdminReadSchema,
    StudentReadSchema,
    TelegramButtonSchema,
    TeacherReadSchema,
)
from ..services.context import ContextServiceProtocol
from ..services.admin import AdminServiceProtocol
from ..services.student import StudentServiceProtocol
from ..services.teacher import TeacherServiceProtocol
from ..telegram.buttons import TelegramButtons
from ..telegram.messages import TelegramMessages


logger = logging.getLogger(__name__)


@dataclass
class ResolvedRoles:
    """Набор ролей текущего пользователя."""

    admin: AdminReadSchema | None
    teacher: TeacherReadSchema | None
    student: StudentReadSchema | None

    @property
    def primary_user(self) -> AdminReadSchema | TeacherReadSchema | StudentReadSchema | None:
        return self.admin or self.teacher or self.student

    @property
    def is_admin(self) -> bool:
        return self.admin is not None

    @property
    def is_teacher(self) -> bool:
        return self.teacher is not None

    @property
    def is_student(self) -> bool:
        return self.student is not None


class BaseHandler:
    """Базовый обработчик с логикой разрешения ролей и главного меню."""

    def __init__(
        self,
        admin_service: AdminServiceProtocol,
        teacher_service: TeacherServiceProtocol,
        student_service: StudentServiceProtocol,
        context_service: ContextServiceProtocol | None = None,
    ):
        self.admin_service = admin_service
        self.teacher_service = teacher_service
        self.student_service = student_service
        self.context_service = context_service

    async def resolve_roles(self, telegram_id: int) -> ResolvedRoles:
        """Разрешить все роли пользователя по telegram_id."""
        try:
            admin = await self.admin_service.get_by_telegram_id(telegram_id)
        except Exception:
            admin = None
        try:
            teacher = await self.teacher_service.get_by_telegram_id(telegram_id)
        except Exception:
            teacher = None
        try:
            student = await self.student_service.get_by_telegram_id(telegram_id)
        except Exception:
            student = None
        return ResolvedRoles(admin=admin, teacher=teacher, student=student)

    async def build_main_menu_response(
        self,
        telegram_id: int,
        message: str | None = None,
    ) -> ActionResponseSchema:
        """Построить ответ с главным меню согласно ролям."""
        roles = await self.resolve_roles(telegram_id)
        primary_user = roles.primary_user
        buttons = [
            TelegramButtonSchema(text=button.text, action=button.action)
            for button in TelegramButtons.get_login_buttons(
                is_admin=roles.is_admin,
                is_teacher=roles.is_teacher,
                is_student=roles.is_student,
            )
        ]

        if message is None and primary_user is not None:
            message = TelegramMessages.get_login_message(
                full_name=primary_user.full_name,
                is_admin=roles.is_admin,
                is_teacher=roles.is_teacher,
                is_student=roles.is_student,
            )
        elif message is None:
            message = TelegramMessages.get_permission_denied()

        return ActionResponseSchema(message=message, buttons=buttons)

    async def build_error_response(
        self,
        telegram_id: int,
        exc: Exception,
        *,
        awaiting_input: bool = False,
    ) -> ActionResponseSchema:
        """Преобразовать исключение handler-слоя в безопасный ответ пользователю."""
        logger.exception(
            "Ошибка обработки Telegram workflow: telegram_id=%s, error=%s",
            telegram_id,
            exc,
        )

        if isinstance(exc, PermissionDeniedError):
            return await self.build_main_menu_response(
                telegram_id,
                TelegramMessages.get_permission_denied(),
            )

        if isinstance(exc, (ExcelParsingError, CSVParsingError)):
            return ActionResponseSchema(
                message=TelegramMessages.get_file_parsing_error(str(exc.detail)),
                awaiting_input=True,
            )

        if isinstance(exc, ValidationError):
            return ActionResponseSchema(
                message=str(exc.detail),
                awaiting_input=awaiting_input,
            )

        if self.context_service is not None:
            await self.context_service.clear_context(telegram_id)

        return await self.build_main_menu_response(
            telegram_id,
            TelegramMessages.get_generic_error(),
        )
