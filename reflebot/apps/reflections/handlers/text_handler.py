"""
Handler для текстового ввода.
"""

from datetime import datetime
import re
from typing import Protocol
import uuid

from reflebot.core.utils.exceptions import ModelFieldNotFoundException
from ..datetime_utils import ensure_utc_datetime
from ..schemas import ActionResponseSchema, AdminCreateSchema
from ..services.admin import AdminServiceProtocol
from ..services.context import ContextServiceProtocol
from ..services.student_history_log import StudentHistoryLogServiceProtocol
from ..telegram.buttons import TelegramButtons
from ..telegram.messages import TelegramMessages
from ..use_cases.admin import CreateAdminUseCaseProtocol
from ..use_cases.course import (
    AttachTeachersToCourseUseCaseProtocol,
    SendCourseBroadcastMessageUseCaseProtocol,
)
from ..use_cases.lection import ManageQuestionsUseCaseProtocol, UpdateLectionUseCaseProtocol
from .base import BaseHandler
from .button_handler import ButtonActionHandler


class TextInputHandlerProtocol(Protocol):
    """Протокол обработчика текстового ввода."""

    async def handle(self, text: str, telegram_id: int) -> ActionResponseSchema:
        """Обработать текст пользователя."""
        ...


class TextInputHandler(BaseHandler, TextInputHandlerProtocol):
    """Обработчик текстового ввода для многошаговых диалогов."""

    DATE_TIME_PATTERN = re.compile(r"^(\d{2}\.\d{2}\.\d{4}) (\d{2}:\d{2})-(\d{2}:\d{2})$")

    def __init__(
        self,
        context_service: ContextServiceProtocol,
        admin_service: AdminServiceProtocol,
        teacher_service,
        student_service,
        create_admin_use_case: CreateAdminUseCaseProtocol,
        attach_teachers_to_course_use_case: AttachTeachersToCourseUseCaseProtocol,
        send_course_broadcast_message_use_case: SendCourseBroadcastMessageUseCaseProtocol,
        update_lection_use_case: UpdateLectionUseCaseProtocol,
        manage_questions_use_case: ManageQuestionsUseCaseProtocol,
        button_handler: ButtonActionHandler,
        student_history_log_service: StudentHistoryLogServiceProtocol | None = None,
    ):
        super().__init__(
            admin_service,
            teacher_service,
            student_service,
            context_service=context_service,
        )
        self.context_service = context_service
        self.create_admin_use_case = create_admin_use_case
        self.attach_teachers_to_course_use_case = attach_teachers_to_course_use_case
        self.send_course_broadcast_message_use_case = send_course_broadcast_message_use_case
        self.update_lection_use_case = update_lection_use_case
        self.manage_questions_use_case = manage_questions_use_case
        self.button_handler = button_handler
        self.student_history_log_service = student_history_log_service

    async def handle(self, text: str, telegram_id: int) -> ActionResponseSchema:
        """Обработать текст в соответствии с текущим контекстом."""
        context = await self.context_service.get_context(telegram_id)
        normalized_text = text.strip()
        if not context:
            if normalized_text.lower() in {"/join_course", "join_course"}:
                return await self._start_join_course_command(telegram_id)
            return await self.build_main_menu_response(
                telegram_id,
                TelegramMessages.get_no_active_action(),
            )

        try:
            action = context.get("action")
            step = context.get("step")
            data = context.get("data", {})
            if action == "student_reflection_workflow" and step in {
                "awaiting_reflection_video",
                "awaiting_question_video",
                "question_prompt",
            }:
                return ActionResponseSchema(
                    message=TelegramMessages.get_reflection_video_required(
                        data.get("lection_topic")
                    ),
                    awaiting_input=True,
                )
            if normalized_text.lower() in {"/join_course", "join_course"}:
                return await self._start_join_course_command(telegram_id)
            if action == "create_course" and step == "awaiting_course_name":
                if len(normalized_text) < 2:
                    return await self._validation_failure(
                        telegram_id,
                        action,
                        step,
                        data,
                        TelegramMessages.get_validation_error_course_name(),
                    )
                await self.context_service.set_context(
                    telegram_id,
                    action="create_course",
                    step="awaiting_file",
                    data={"course_name": normalized_text},
                )
                return ActionResponseSchema(
                    message=TelegramMessages.get_create_course_request_file(),
                    awaiting_input=True,
                )
            if action == "course_broadcast_message" and step == "awaiting_message_text":
                current_admin = await self.button_handler._require_admin(telegram_id)
                if not normalized_text:
                    return await self._validation_failure(
                        telegram_id,
                        action,
                        step,
                        data,
                        TelegramMessages.get_validation_error_empty_message(),
                    )
                sent_count = await self.send_course_broadcast_message_use_case(
                    course_id=uuid.UUID(str(data["course_id"])),
                    message_text=normalized_text,
                    current_admin=current_admin,
                )
                return await self.button_handler.render_admin_course_details(
                    telegram_id,
                    uuid.UUID(str(data["course_id"])),
                    page=int(data.get("page", 1)),
                    message_prefix=TelegramMessages.get_course_broadcast_success(sent_count),
                )
            if action in {"register_course_by_code", "join_course"} and step == "awaiting_course_code":
                try:
                    course = await self.button_handler.course_service.get_by_join_code(
                        normalized_text
                    )
                except ModelFieldNotFoundException:
                    return await self._validation_failure(
                        telegram_id,
                        action,
                        step,
                        data,
                        TelegramMessages.get_course_code_not_found(),
                    )
                if action == "join_course":
                    student_id = data.get("student_id")
                    telegram_username = str(data["telegram_username"])
                    if student_id is not None:
                        student = await self.student_service.get_by_id(uuid.UUID(str(student_id)))
                    else:
                        existing_student = await self.student_service.get_by_telegram_username(
                            telegram_username
                        )
                        if existing_student is None:
                            student = await self.student_service.create_student(
                                full_name=str(data["full_name"]),
                                telegram_username=telegram_username,
                                telegram_id=int(data["telegram_id"]),
                            )
                        else:
                            student = existing_student
                            if student.telegram_id != int(data["telegram_id"]):
                                student = await self.student_service.update_telegram_id(
                                    telegram_username,
                                    int(data["telegram_id"]),
                                )
                    if await self.student_service.is_attached_to_course(student.id, course.id):
                        await self.context_service.clear_context(telegram_id)
                        return ActionResponseSchema(
                            message=TelegramMessages.get_student_course_already_registered(),
                        )
                    lection_ids = await self.button_handler.lection_service.get_lection_ids_by_course(course.id)
                    await self.student_service.attach_to_course([student.id], course.id)
                    await self.student_service.attach_to_lections([student.id], lection_ids)
                    await self._log_student_action(student.id, "student_join_course_completed")
                    await self.context_service.clear_context(telegram_id)
                    return ActionResponseSchema(
                        message=TelegramMessages.get_student_course_registered(course.name),
                    )

                await self.context_service.set_context(
                    telegram_id,
                    action="register_course_by_code",
                    step="awaiting_fullname",
                    data={
                        "course_id": str(course.id),
                        "course_name": course.name,
                        "telegram_username": str(data["telegram_username"]),
                        "telegram_id": int(data["telegram_id"]),
                    },
                )
                return ActionResponseSchema(
                    message=TelegramMessages.get_student_course_fullname_request(course.name),
                    awaiting_input=True,
                )

            if action == "register_course_by_code" and step == "awaiting_fullname":
                if len(normalized_text) < 3:
                    return await self._validation_failure(
                        telegram_id,
                        action,
                        step,
                        data,
                        TelegramMessages.get_validation_error_fullname(),
                    )

                existing_student = await self.student_service.get_by_telegram_username(
                    str(data["telegram_username"])
                )
                if existing_student is None:
                    student = await self.student_service.create_student(
                        full_name=normalized_text,
                        telegram_username=str(data["telegram_username"]),
                        telegram_id=int(data["telegram_id"]),
                    )
                else:
                    student = existing_student
                    if student.telegram_id != int(data["telegram_id"]):
                        student = await self.student_service.update_telegram_id(
                            str(data["telegram_username"]),
                            int(data["telegram_id"]),
                        )

                course_id = uuid.UUID(str(data["course_id"]))
                if await self.student_service.is_attached_to_course(student.id, course_id):
                    await self.context_service.clear_context(telegram_id)
                    return ActionResponseSchema(
                        message=TelegramMessages.get_student_course_already_registered(),
                    )
                lection_ids = await self.button_handler.lection_service.get_lection_ids_by_course(course_id)
                await self.student_service.attach_to_course([student.id], course_id)
                await self.student_service.attach_to_lections([student.id], lection_ids)
                await self._log_student_action(student.id, "student_register_course_by_code_completed")
                await self.context_service.clear_context(telegram_id)
                return ActionResponseSchema(
                    message=TelegramMessages.get_student_course_registered(str(data["course_name"])),
                )

            if action == "create_admin" and step == "awaiting_fullname":
                current_admin = await self.button_handler._require_admin(telegram_id)
                if len(normalized_text) < 3:
                    return await self._validation_failure(
                        telegram_id,
                        action,
                        step,
                        data,
                        TelegramMessages.get_validation_error_fullname(),
                    )
                await self.context_service.set_context(
                    telegram_id,
                    action="create_admin",
                    step="awaiting_username",
                    data={"fullname": normalized_text},
                )
                await self.context_service.push_navigation(
                    telegram_id,
                    self.button_handler.CREATE_ADMIN_USERNAME_SCREEN,
                )
                return ActionResponseSchema(
                    message=TelegramMessages.get_create_admin_request_username(),
                    buttons=[
                        {"text": button.text, "action": button.action}
                        for button in TelegramButtons.get_back_button()
                    ],
                    awaiting_input=True,
                )

            if action == "create_admin" and step == "awaiting_username":
                current_admin = await self.button_handler._require_admin(telegram_id)
                if not self._is_valid_username(normalized_text):
                    return await self._validation_failure(
                        telegram_id,
                        action,
                        step,
                        data,
                        TelegramMessages.get_validation_error_username(),
                    )
                try:
                    await self.admin_service.get_by_telegram_username(normalized_text)
                    return await self._validation_failure(
                        telegram_id,
                        action,
                        step,
                        data,
                        TelegramMessages.get_username_already_exists(),
                    )
                except ModelFieldNotFoundException:
                    created_admin = await self.create_admin_use_case(
                        AdminCreateSchema(
                            full_name=data["fullname"],
                            telegram_username=normalized_text,
                            telegram_id=None,
                            is_active=True,
                        ),
                        current_admin,
                    )
                    await self.context_service.clear_context(telegram_id)
                    return await self.build_main_menu_response(
                        telegram_id,
                        TelegramMessages.get_admin_created_message(created_admin.full_name),
                    )

            if action == "attach_teacher" and step == "awaiting_fullname":
                current_admin = await self.button_handler._require_admin(telegram_id)
                if len(normalized_text) < 3:
                    return await self._validation_failure(
                        telegram_id,
                        action,
                        step,
                        data,
                        TelegramMessages.get_validation_error_fullname(),
                    )
                await self.context_service.set_context(
                    telegram_id,
                    action="attach_teacher",
                    step="awaiting_username",
                    data={"course_id": data["course_id"], "fullname": normalized_text},
                )
                await self.context_service.push_navigation(
                    telegram_id,
                    self.button_handler.ATTACH_TEACHER_USERNAME_SCREEN,
                )
                return ActionResponseSchema(
                    message=TelegramMessages.get_attach_teacher_request_username(),
                    buttons=[
                        {"text": button.text, "action": button.action}
                        for button in TelegramButtons.get_back_button()
                    ],
                    awaiting_input=True,
                )

            if action == "attach_teacher" and step == "awaiting_username":
                current_admin = await self.button_handler._require_admin(telegram_id)
                if not self._is_valid_username(normalized_text):
                    return await self._validation_failure(
                        telegram_id,
                        action,
                        step,
                        data,
                        TelegramMessages.get_validation_error_username(),
                    )
                teacher = await self.attach_teachers_to_course_use_case(
                    course_id=uuid.UUID(str(data["course_id"])),
                    full_name=data["fullname"],
                    telegram_username=normalized_text,
                    current_admin=current_admin,
                )
                await self.context_service.set_context(
                    telegram_id,
                    action="teacher_attached",
                    step="view",
                    data={"course_id": data["course_id"]},
                )
                return ActionResponseSchema(
                    message=TelegramMessages.get_teacher_attached(teacher.full_name),
                    buttons=[
                        {"text": button.text, "action": button.action}
                        for button in TelegramButtons.get_teacher_attached_buttons()
                    ],
                )

            if action == "edit_lection_topic" and step == "awaiting_topic":
                current_admin = await self.button_handler._require_admin(telegram_id)
                await self.update_lection_use_case.update_topic(
                    lection_id=uuid.UUID(str(data["lection_id"])),
                    topic=normalized_text,
                    current_admin=current_admin,
                )
                await self.context_service.pop_navigation(telegram_id)
                return await self.button_handler.render_lection_details(
                    telegram_id,
                    uuid.UUID(str(data["lection_id"])),
                    data.get("course_id"),
                )

            if action == "edit_lection_date" and step == "awaiting_datetime":
                current_admin = await self.button_handler._require_admin(telegram_id)
                parsed_datetime = await self._parse_datetime_input(
                    telegram_id,
                    action,
                    step,
                    data,
                    normalized_text,
                )
                if isinstance(parsed_datetime, ActionResponseSchema):
                    return parsed_datetime
                started_at, ended_at = parsed_datetime
                await self.update_lection_use_case.update_datetime(
                    lection_id=uuid.UUID(str(data["lection_id"])),
                    started_at=started_at,
                    ended_at=ended_at,
                    current_admin=current_admin,
                )
                await self.context_service.pop_navigation(telegram_id)
                return await self.button_handler.render_lection_details(
                    telegram_id,
                    uuid.UUID(str(data["lection_id"])),
                    data.get("course_id"),
                )

            if action == "add_question" and step == "awaiting_question_text":
                current_admin = await self.button_handler._require_admin(telegram_id)
                await self.manage_questions_use_case.create_question(
                    lection_id=uuid.UUID(str(data["lection_id"])),
                    text=normalized_text,
                    current_admin=current_admin,
                )
                await self.context_service.pop_navigation(telegram_id)
                return await self.button_handler.render_questions_menu(
                    telegram_id,
                    uuid.UUID(str(data["lection_id"])),
                )

            if action == "edit_question" and step == "awaiting_question_update":
                current_admin = await self.button_handler._require_admin(telegram_id)
                parts = normalized_text.split(maxsplit=1)
                if len(parts) != 2 or not parts[0].isdigit():
                    return await self._validation_failure(
                        telegram_id,
                        action,
                        step,
                        data,
                        TelegramMessages.get_edit_question_request(),
                    )
                question_number = int(parts[0])
                questions = await self.manage_questions_use_case.get_questions(
                    lection_id=uuid.UUID(str(data["lection_id"])),
                    current_admin=current_admin,
                )
                if question_number < 1 or question_number > len(questions):
                    return await self._validation_failure(
                        telegram_id,
                        action,
                        step,
                        data,
                        TelegramMessages.get_edit_question_request(),
                    )
                await self.manage_questions_use_case.update_question(
                    question_id=questions[question_number - 1].id,
                    text=parts[1].strip(),
                    current_admin=current_admin,
                )
                await self.context_service.pop_navigation(telegram_id)
                return await self.button_handler.render_questions_menu(
                    telegram_id,
                    uuid.UUID(str(data["lection_id"])),
                )

            support_button = TelegramButtons.create_support_button()
            return ActionResponseSchema(
                message=TelegramMessages.get_unknown_context_action(),
                buttons=[
                    {
                        "text": support_button.text,
                        "action": support_button.action,
                        "url": support_button.url,
                    }
                ],
            )
        except Exception as exc:
            return await self.build_error_response(telegram_id, exc, awaiting_input=True)

    async def _start_join_course_command(self, telegram_id: int) -> ActionResponseSchema:
        """Запустить глобальную команду записи на курс по коду."""
        roles = await self.resolve_roles(telegram_id)
        if roles.student is None and roles.primary_user is None:
            return await self.build_main_menu_response(
                telegram_id,
                TelegramMessages.get_join_course_permission_denied(),
            )
        context_data = {
            "telegram_id": telegram_id,
        }
        if roles.student is not None:
            context_data.update(
                {
                    "student_id": str(roles.student.id),
                    "telegram_username": roles.student.telegram_username,
                },
            )
        else:
            context_data.update(
                {
                    "full_name": roles.primary_user.full_name,
                    "telegram_username": roles.primary_user.telegram_username,
                },
            )
        await self.context_service.set_context(
            telegram_id,
            action="join_course",
            step="awaiting_course_code",
            data=context_data,
        )
        return ActionResponseSchema(
            message=TelegramMessages.get_join_course_code_request(),
            awaiting_input=True,
        )

    async def _validation_failure(
        self,
        telegram_id: int,
        action: str,
        step: str,
        data: dict,
        message: str,
    ) -> ActionResponseSchema:
        """Сохранить счётчик неудачных попыток и вернуть сообщение о валидации."""
        attempts = int(data.get("validation_attempts", 0)) + 1
        updated_data = dict(data)
        updated_data["validation_attempts"] = attempts
        await self.context_service.set_context(
            telegram_id,
            action=action,
            step=step,
            data=updated_data,
        )
        return ActionResponseSchema(
            message=message,
            buttons=[
                {"text": button.text, "action": button.action}
                for button in TelegramButtons.get_back_button()
            ],
            awaiting_input=True,
        )

    async def _parse_datetime_input(
        self,
        telegram_id: int,
        action: str,
        step: str,
        data: dict,
        text: str,
    ) -> tuple[datetime, datetime] | ActionResponseSchema:
        """Провалидировать и распарсить дату лекции."""
        match = self.DATE_TIME_PATTERN.match(text)
        if match is None:
            return await self._validation_failure(
                telegram_id,
                action,
                step,
                data,
                TelegramMessages.get_invalid_date_format(),
            )

        date_part, start_time, end_time = match.groups()
        try:
            started_at = datetime.strptime(f"{date_part} {start_time}", "%d.%m.%Y %H:%M")
            ended_at = datetime.strptime(f"{date_part} {end_time}", "%d.%m.%Y %H:%M")
        except ValueError:
            return await self._validation_failure(
                telegram_id,
                action,
                step,
                data,
                TelegramMessages.get_invalid_date_format(),
            )

        if ended_at <= started_at:
            return await self._validation_failure(
                telegram_id,
                action,
                step,
                data,
                TelegramMessages.get_invalid_date_range(),
            )

        return ensure_utc_datetime(started_at), ensure_utc_datetime(ended_at)

    @staticmethod
    def _is_valid_username(username: str) -> bool:
        """Проверить корректность telegram username в текстовом workflow."""
        return bool(username) and "@" not in username

    async def _log_student_action(self, student_id: uuid.UUID, action: str) -> None:
        """Записать действие студента, если сервис логирования подключён."""
        if self.student_history_log_service is None:
            return
        await self.student_history_log_service.log_action(student_id, action)
