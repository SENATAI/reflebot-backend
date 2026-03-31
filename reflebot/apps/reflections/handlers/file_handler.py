"""
Handler для загрузки файлов.
"""

import uuid
from typing import Protocol

from fastapi import UploadFile
from reflebot.core.utils.exceptions import ValidationError

from ..exceptions import CSVParsingError, ExcelParsingError
from ..schemas import ActionResponseSchema
from ..services.context import ContextServiceProtocol
from ..services.reflection import ReflectionWorkflowServiceProtocol
from ..telegram.messages import TelegramMessages
from ..use_cases.course import (
    AttachStudentsToCourseUseCaseProtocol,
    CreateCourseFromExcelUseCaseProtocol,
)
from ..use_cases.lection import ManageFilesUseCaseProtocol
from .button_handler import ButtonActionHandler


class FileUploadHandlerProtocol(Protocol):
    """Протокол обработчика файлов."""

    async def handle(
        self,
        file: UploadFile | None,
        telegram_id: int,
        telegram_file_id: str | None = None,
    ) -> ActionResponseSchema:
        """Обработать загруженный файл."""
        ...


class FileUploadHandler(FileUploadHandlerProtocol):
    """Обработчик загрузки файлов для workflow Telegram бота."""

    def __init__(
        self,
        context_service: ContextServiceProtocol,
        create_course_from_excel_use_case: CreateCourseFromExcelUseCaseProtocol,
        attach_students_to_course_use_case: AttachStudentsToCourseUseCaseProtocol,
        manage_files_use_case: ManageFilesUseCaseProtocol,
        reflection_workflow_service: ReflectionWorkflowServiceProtocol,
        button_handler: ButtonActionHandler,
    ):
        self.context_service = context_service
        self.create_course_from_excel_use_case = create_course_from_excel_use_case
        self.attach_students_to_course_use_case = attach_students_to_course_use_case
        self.manage_files_use_case = manage_files_use_case
        self.reflection_workflow_service = reflection_workflow_service
        self.button_handler = button_handler

    async def handle(
        self,
        file: UploadFile | None,
        telegram_id: int,
        telegram_file_id: str | None = None,
    ) -> ActionResponseSchema:
        """Обработать файл согласно текущему контексту пользователя."""
        context = await self.context_service.get_context(telegram_id)
        if not context:
            return await self.button_handler.build_main_menu_response(
                telegram_id,
                TelegramMessages.get_no_active_action(),
            )

        try:
            action = context.get("action")
            data = context.get("data", {})

            if action == "student_reflection_workflow":
                if not telegram_file_id:
                    raise ValidationError(
                        "telegram_file_id",
                        "Для кружка нужен Telegram file_id.",
                    )
                roles = await self.button_handler.resolve_roles(telegram_id)
                self.button_handler._require_roles_student(roles)
                updated_data = self.reflection_workflow_service.add_video_to_draft(
                    data,
                    telegram_file_id,
                )
                step = (
                    "review_question_videos"
                    if updated_data.get("stage") == "question"
                    else "review_reflection_videos"
                )
                await self.context_service.set_context(
                    telegram_id,
                    action="student_reflection_workflow",
                    step=step,
                    data=updated_data,
                )
                return await self.button_handler.render_student_video_review(
                    updated_data,
                    TelegramMessages.get_reflection_video_saved(),
                )

            current_admin = await self.button_handler._require_admin(telegram_id)

            if action == "create_course":
                if file is None:
                    raise ValidationError("file", "Для загрузки курса нужен Excel файл.")
                course_name = str(data.get("course_name", "")).strip()
                if not course_name:
                    raise ValidationError("course_name", "Сначала нужно ввести название курса.")
                course = await self.create_course_from_excel_use_case(
                    course_name,
                    file.file,
                    current_admin,
                )
                await self.context_service.push_navigation(telegram_id, "course_menu")
                return await self.button_handler.render_course_menu(telegram_id, course.id)

            if action == "attach_students":
                if file is None:
                    raise ValidationError("file", "Для привязки студентов нужен CSV файл.")
                count = await self.attach_students_to_course_use_case(
                    course_id=self._parse_uuid(data["course_id"]),
                    csv_file=file.file,
                    current_admin=current_admin,
                )
                await self.context_service.clear_context(telegram_id)
                return await self.button_handler.build_main_menu_response(
                    telegram_id,
                    TelegramMessages.get_students_attached(count),
                )

            if action == "edit_lection_presentation":
                if not telegram_file_id:
                    raise ValidationError(
                        "telegram_file_id",
                        "Для презентации нужен Telegram file_id.",
                    )
                await self.manage_files_use_case.upload_presentation(
                    lection_id=self._parse_uuid(data["lection_id"]),
                    telegram_file_id=telegram_file_id,
                    current_admin=current_admin,
                )
                await self.context_service.pop_navigation(telegram_id)
                return await self.button_handler.render_presentation_menu(
                    telegram_id,
                    self._parse_uuid(data["lection_id"]),
                )

            if action == "edit_lection_recording":
                if not telegram_file_id:
                    raise ValidationError(
                        "telegram_file_id",
                        "Для записи нужен Telegram file_id.",
                    )
                await self.manage_files_use_case.upload_recording(
                    lection_id=self._parse_uuid(data["lection_id"]),
                    telegram_file_id=telegram_file_id,
                    current_admin=current_admin,
                )
                await self.context_service.pop_navigation(telegram_id)
                return await self.button_handler.render_recording_menu(
                    telegram_id,
                    self._parse_uuid(data["lection_id"]),
                )
        except (ExcelParsingError, CSVParsingError) as exc:
            return await self.button_handler.build_error_response(
                telegram_id,
                exc,
                awaiting_input=True,
            )
        except Exception as exc:
            return await self.button_handler.build_error_response(
                telegram_id,
                exc,
                awaiting_input=True,
            )

        return ActionResponseSchema(message=TelegramMessages.get_unknown_context_action())

    @staticmethod
    def _parse_uuid(raw: str) -> uuid.UUID:
        return uuid.UUID(str(raw))
