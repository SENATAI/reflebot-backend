"""
Pydantic-схемы для модуля рефлексий.
"""

from typing import Any, Literal
import uuid
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from reflebot.core.schemas import CreateBaseModel, UpdateBaseModel
from .enums import NotificationDeliveryStatus, NotificationDeliveryType


# Admin schemas

class AdminBaseSchema(BaseModel):
    """Базовая схема администратора."""
    
    full_name: str = Field(..., max_length=255, description="ФИО администратора")
    telegram_username: str = Field(..., max_length=100, description="Никнейм в Telegram")
    is_active: bool = Field(default=True, description="Активен ли администратор")


class AdminCreateSchema(AdminBaseSchema, CreateBaseModel):
    """Схема создания администратора."""
    
    telegram_id: int | None = Field(default=None, description="ID в Telegram")


class AdminUpdateSchema(AdminBaseSchema, UpdateBaseModel):
    """Схема обновления администратора."""
    
    telegram_id: int | None = Field(default=None, description="ID в Telegram")


class AdminReadSchema(AdminBaseSchema):
    """Схема чтения администратора."""
    
    id: uuid.UUID
    telegram_id: int | None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Student schemas

class StudentBaseSchema(BaseModel):
    """Базовая схема студента."""
    
    full_name: str = Field(..., max_length=255, description="ФИО студента")
    telegram_username: str = Field(..., max_length=100, description="Никнейм в Telegram")
    is_active: bool = Field(default=True, description="Активен ли студент")


class StudentCreateSchema(StudentBaseSchema, CreateBaseModel):
    """Схема создания студента."""
    
    telegram_id: int | None = Field(default=None, description="ID в Telegram")


class StudentUpdateSchema(StudentBaseSchema, UpdateBaseModel):
    """Схема обновления студента."""
    
    telegram_id: int | None = Field(default=None, description="ID в Telegram")


class StudentReadSchema(StudentBaseSchema):
    """Схема чтения студента."""
    
    id: uuid.UUID
    telegram_id: int | None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Teacher schemas

class TeacherBaseSchema(BaseModel):
    """Базовая схема преподавателя."""
    
    full_name: str = Field(..., max_length=255, description="ФИО преподавателя")
    telegram_username: str = Field(..., max_length=100, description="Никнейм в Telegram")
    is_active: bool = Field(default=True, description="Активен ли преподаватель")


class TeacherCreateSchema(TeacherBaseSchema, CreateBaseModel):
    """Схема создания преподавателя."""
    
    telegram_id: int | None = Field(default=None, description="ID в Telegram")


class TeacherUpdateSchema(TeacherBaseSchema, UpdateBaseModel):
    """Схема обновления преподавателя."""
    
    telegram_id: int | None = Field(default=None, description="ID в Telegram")


class TeacherReadSchema(TeacherBaseSchema):
    """Схема чтения преподавателя."""
    
    id: uuid.UUID
    telegram_id: int | None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Telegram schemas

class TelegramButtonSchema(BaseModel):
    """Схема кнопки Telegram."""
    
    text: str = Field(..., description="Текст кнопки")
    action: str | None = Field(default=None, description="Действие кнопки")
    url: str | None = Field(default=None, description="URL для открытия внешней ссылки")


class TelegramFileReferenceSchema(BaseModel):
    """Ссылка на Telegram-файл для повторной отправки ботом."""

    telegram_file_id: str = Field(..., description="Telegram file_id")
    kind: str | None = Field(default=None, description="Тип файла")


class TelegramDialogMessageSchema(BaseModel):
    """Одно сообщение в последовательном диалоге для Telegram-бота."""

    message: str | None = Field(default=None, description="Текст сообщения")
    parse_mode: str = Field(default="HTML", description="Режим парсинга сообщения")
    buttons: list[TelegramButtonSchema] = Field(
        default_factory=list,
        description="Кнопки Telegram для этого шага диалога",
    )
    files: list[TelegramFileReferenceSchema] = Field(
        default_factory=list,
        description="Telegram file_id, которые бот должен отправить на этом шаге",
    )


# User schemas

class UserBaseSchema(BaseModel):
    """Базовая схема пользователя."""
    
    telegram_id: int = Field(..., description="ID в Telegram")
    user_context: dict | None = Field(None, description="Контекст диалога пользователя")


class UserCreateSchema(UserBaseSchema, CreateBaseModel):
    """Схема создания пользователя."""
    pass


class UserUpdateSchema(BaseModel):
    """Схема обновления пользователя."""
    
    user_context: dict | None = Field(None, description="Контекст диалога пользователя")


class UserReadSchema(UserBaseSchema):
    """Схема чтения пользователя."""
    
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Login schemas

class AdminLoginSchema(BaseModel):
    """Схема для входа пользователя."""
    
    telegram_id: int = Field(..., description="ID в Telegram")
    invite_token: str | None = Field(default=None, description="Токен deep link для записи на курс")


class UserLoginResponseSchema(BaseModel):
    """Схема ответа при входе пользователя."""
    
    full_name: str = Field(..., description="ФИО пользователя")
    telegram_username: str = Field(..., description="Никнейм в Telegram")
    telegram_id: int = Field(..., description="ID в Telegram")
    is_active: bool = Field(..., description="Активен ли пользователь")
    is_admin: bool = Field(..., description="Является ли администратором")
    is_teacher: bool = Field(..., description="Является ли преподавателем")
    is_student: bool = Field(..., description="Является ли студентом")
    message: str = Field(..., description="Сообщение для пользователя")
    parse_mode: str = Field(default="HTML", description="Режим парсинга сообщения (HTML, Markdown, MarkdownV2)")
    buttons: list[TelegramButtonSchema] = Field(default_factory=list, description="Кнопки для Telegram")
    awaiting_input: bool = Field(default=False, description="Ожидается ли дополнительный ввод")
    
    model_config = ConfigDict(from_attributes=True)


# CourseSession schemas

class CourseSessionBaseSchema(BaseModel):
    """Базовая схема сессии курса."""
    
    name: str = Field(..., max_length=255, description="Название курса")
    started_at: datetime = Field(..., description="Дата и время начала курса")
    ended_at: datetime = Field(..., description="Дата и время окончания курса")


class CourseSessionCreateSchema(CourseSessionBaseSchema, CreateBaseModel):
    """Схема создания сессии курса."""
    join_code: str = Field(..., min_length=4, max_length=4, description="Код курса")


class CourseSessionUpdateSchema(CourseSessionBaseSchema, UpdateBaseModel):
    """Схема обновления сессии курса."""
    pass


class CourseSessionReadSchema(CourseSessionBaseSchema):
    """Схема чтения сессии курса."""
    
    id: uuid.UUID
    join_code: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# LectionSession schemas

class LectionSessionBaseSchema(BaseModel):
    """Базовая схема сессии лекции."""
    
    course_session_id: uuid.UUID = Field(..., description="ID курса")
    topic: str = Field(..., max_length=500, description="Тема лекции")
    presentation_file_id: str | None = Field(None, description="Telegram file_id презентации")
    recording_file_id: str | None = Field(None, description="Telegram file_id записи лекции")
    started_at: datetime = Field(..., description="Дата и время начала лекции")
    ended_at: datetime = Field(..., description="Дата и время окончания лекции")
    deadline: datetime = Field(..., description="Дедлайн отправки рефлексии по лекции")


class LectionSessionCreateSchema(LectionSessionBaseSchema, CreateBaseModel):
    """Схема создания сессии лекции."""
    pass


class LectionSessionUpdateSchema(LectionSessionBaseSchema, UpdateBaseModel):
    """Схема обновления сессии лекции."""
    pass


class LectionSessionReadSchema(LectionSessionBaseSchema):
    """Схема чтения сессии лекции."""
    
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Question schemas

class QuestionBaseSchema(BaseModel):
    """Базовая схема вопроса."""
    
    lection_session_id: uuid.UUID = Field(..., description="ID лекции")
    question_text: str = Field(..., description="Текст вопроса")


class QuestionCreateSchema(QuestionBaseSchema, CreateBaseModel):
    """Схема создания вопроса."""
    pass


class QuestionUpdateSchema(UpdateBaseModel):
    """Схема обновления вопроса."""
    
    lection_session_id: uuid.UUID | None = Field(None, description="ID лекции")
    question_text: str | None = Field(None, description="Текст вопроса")


class QuestionReadSchema(QuestionBaseSchema):
    """Схема чтения вопроса."""
    
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# DefaultQuestion schemas

class DefaultQuestionBaseSchema(BaseModel):
    """Базовая схема стандартного вопроса."""

    question_text: str = Field(..., max_length=500, description="Текст стандартного вопроса")


class DefaultQuestionCreateSchema(DefaultQuestionBaseSchema, CreateBaseModel):
    """Схема создания стандартного вопроса."""
    pass


class DefaultQuestionUpdateSchema(UpdateBaseModel):
    """Схема обновления стандартного вопроса."""

    question_text: str | None = Field(None, max_length=500, description="Текст стандартного вопроса")


class DefaultQuestionReadSchema(DefaultQuestionBaseSchema):
    """Схема чтения стандартного вопроса."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# TeacherCourse schemas

class TeacherCourseBaseSchema(BaseModel):
    """Базовая схема привязки преподавателя к курсу."""
    
    teacher_id: uuid.UUID = Field(..., description="ID преподавателя")
    course_session_id: uuid.UUID = Field(..., description="ID курса")


class TeacherCourseCreateSchema(TeacherCourseBaseSchema, CreateBaseModel):
    """Схема создания привязки преподавателя к курсу."""
    pass


class TeacherCourseUpdateSchema(TeacherCourseBaseSchema, UpdateBaseModel):
    """Схема обновления привязки преподавателя к курсу."""
    pass


class TeacherCourseReadSchema(TeacherCourseBaseSchema):
    """Схема чтения привязки преподавателя к курсу."""
    
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# TeacherLection schemas

class TeacherLectionBaseSchema(BaseModel):
    """Базовая схема привязки преподавателя к лекции."""
    
    teacher_id: uuid.UUID = Field(..., description="ID преподавателя")
    lection_session_id: uuid.UUID = Field(..., description="ID лекции")


class TeacherLectionCreateSchema(TeacherLectionBaseSchema, CreateBaseModel):
    """Схема создания привязки преподавателя к лекции."""
    pass


class TeacherLectionUpdateSchema(TeacherLectionBaseSchema, UpdateBaseModel):
    """Схема обновления привязки преподавателя к лекции."""
    pass


class TeacherLectionReadSchema(TeacherLectionBaseSchema):
    """Схема чтения привязки преподавателя к лекции."""
    
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# StudentCourse schemas

class StudentCourseBaseSchema(BaseModel):
    """Базовая схема привязки студента к курсу."""
    
    student_id: uuid.UUID = Field(..., description="ID студента")
    course_session_id: uuid.UUID = Field(..., description="ID курса")


class StudentCourseCreateSchema(StudentCourseBaseSchema, CreateBaseModel):
    """Схема создания привязки студента к курсу."""
    pass


class StudentCourseUpdateSchema(StudentCourseBaseSchema, UpdateBaseModel):
    """Схема обновления привязки студента к курсу."""
    pass


class StudentCourseReadSchema(StudentCourseBaseSchema):
    """Схема чтения привязки студента к курсу."""
    
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# StudentLection schemas

class StudentLectionBaseSchema(BaseModel):
    """Базовая схема привязки студента к лекции."""
    
    student_id: uuid.UUID = Field(..., description="ID студента")
    lection_session_id: uuid.UUID = Field(..., description="ID лекции")


class StudentLectionCreateSchema(StudentLectionBaseSchema, CreateBaseModel):
    """Схема создания привязки студента к лекции."""
    pass


class StudentLectionUpdateSchema(StudentLectionBaseSchema, UpdateBaseModel):
    """Схема обновления привязки студента к лекции."""
    pass


class StudentLectionReadSchema(StudentLectionBaseSchema):
    """Схема чтения привязки студента к лекции."""
    
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# StudentHistoryLog schemas

class StudentHistoryLogBaseSchema(BaseModel):
    """Базовая схема лога действий студента."""

    student_id: uuid.UUID = Field(..., description="ID студента")
    action: str = Field(..., max_length=255, description="Действие студента")


class StudentHistoryLogCreateSchema(StudentHistoryLogBaseSchema, CreateBaseModel):
    """Схема создания лога действий студента."""
    pass


class StudentHistoryLogUpdateSchema(UpdateBaseModel):
    """Схема обновления лога действий студента."""

    student_id: uuid.UUID | None = Field(None, description="ID студента")
    action: str | None = Field(None, max_length=255, description="Действие студента")


class StudentHistoryLogReadSchema(StudentHistoryLogBaseSchema):
    """Схема чтения лога действий студента."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# NotificationDelivery schemas

class NotificationDeliveryBaseSchema(BaseModel):
    """Базовая схема доставки уведомления."""

    lection_session_id: uuid.UUID = Field(..., description="ID лекции")
    student_id: uuid.UUID = Field(..., description="ID студента")
    type: NotificationDeliveryType = Field(..., description="Тип уведомления")
    scheduled_for: datetime = Field(..., description="Плановое время доставки")
    status: NotificationDeliveryStatus = Field(..., description="Статус доставки")
    sent_at: datetime | None = Field(None, description="Время успешной отправки")
    attempts: int = Field(default=0, description="Количество попыток отправки")
    last_error: str | None = Field(None, description="Текст последней ошибки")


class NotificationDeliveryCreateSchema(NotificationDeliveryBaseSchema, CreateBaseModel):
    """Схема создания доставки уведомления."""
    pass


class NotificationDeliveryUpdateSchema(UpdateBaseModel):
    """Схема обновления доставки уведомления."""

    lection_session_id: uuid.UUID | None = Field(None, description="ID лекции")
    student_id: uuid.UUID | None = Field(None, description="ID студента")
    type: NotificationDeliveryType | None = Field(None, description="Тип уведомления")
    scheduled_for: datetime | None = Field(None, description="Плановое время доставки")
    status: NotificationDeliveryStatus | None = Field(None, description="Статус доставки")
    sent_at: datetime | None = Field(None, description="Время успешной отправки")
    attempts: int | None = Field(None, description="Количество попыток отправки")
    last_error: str | None = Field(None, description="Текст последней ошибки")


class NotificationDeliveryReadSchema(NotificationDeliveryBaseSchema):
    """Схема чтения доставки уведомления."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReflectionPromptCandidateSchema(BaseModel):
    """Кандидат на создание доставки запроса рефлексии."""

    lection_session_id: uuid.UUID = Field(..., description="ID лекции")
    student_id: uuid.UUID = Field(..., description="ID студента")
    telegram_id: int = Field(..., description="Telegram ID студента")
    scheduled_for: datetime = Field(..., description="Время, после которого нужно отправлять")


class ReflectionPromptMessageSchema(BaseModel):
    """Готовое сообщение для запроса рефлексии."""

    message_text: str = Field(..., description="Текст сообщения")
    parse_mode: str = Field(default="HTML", description="Telegram parse mode")
    buttons: list[TelegramButtonSchema] = Field(
        default_factory=list,
        description="Кнопки для bot-consumer сообщения",
    )


class ReflectionPromptCommandSchema(BaseModel):
    """Команда отправки запроса рефлексии для bot-consumer."""

    event_type: Literal["send_reflection_prompt"] = "send_reflection_prompt"
    delivery_id: uuid.UUID = Field(..., description="ID доставки")
    student_id: uuid.UUID = Field(..., description="ID студента")
    telegram_id: int = Field(..., description="Telegram ID студента")
    lection_session_id: uuid.UUID = Field(..., description="ID лекции")
    message_text: str = Field(..., description="Текст сообщения")
    parse_mode: str = Field(default="HTML", description="Telegram parse mode")
    buttons: list[TelegramButtonSchema] = Field(
        default_factory=list,
        description="Inline-кнопки для сообщения студенту",
    )
    scheduled_for: datetime = Field(..., description="Плановое время доставки")


class ReflectionPromptResultEventSchema(BaseModel):
    """Результат попытки отправки запроса рефлексии."""

    event_type: Literal["reflection_prompt_result"] = "reflection_prompt_result"
    delivery_id: uuid.UUID = Field(..., description="ID доставки")
    success: bool = Field(..., description="Признак успешной отправки")
    sent_at: datetime | None = Field(None, description="Время успешной отправки")
    telegram_message_id: int | None = Field(None, description="ID сообщения в Telegram")
    error: str | None = Field(None, description="Текст ошибки")


# Pagination schemas

class PaginatedResponse(BaseModel):
    """Схема пагинированного ответа."""
    
    items: list[Any] = Field(..., description="Список элементов")
    total: int = Field(..., description="Общее количество элементов")
    page: int = Field(..., description="Текущая страница")
    page_size: int = Field(..., description="Размер страницы")
    total_pages: int = Field(..., description="Общее количество страниц")


class ActionResponseSchema(BaseModel):
    """Унифицированный ответ для backend-driven Telegram действий."""

    message: str = Field(..., description="Сообщение для пользователя")
    parse_mode: str = Field(default="HTML", description="Режим парсинга сообщения")
    buttons: list[TelegramButtonSchema] = Field(default_factory=list, description="Кнопки для Telegram")
    files: list[TelegramFileReferenceSchema] = Field(
        default_factory=list,
        description="Telegram file_id, которые бот может переотправить пользователю",
    )
    dialog_messages: list[TelegramDialogMessageSchema] = Field(
        default_factory=list,
        description="Последовательные сообщения для отправки ботом друг за другом",
    )
    awaiting_input: bool = Field(default=False, description="Ожидается ли текстовый или файловый ввод")


class LectionDetailsSchema(BaseModel):
    """Схема детальной информации о лекции."""

    lection: LectionSessionReadSchema = Field(..., description="Данные лекции")
    questions: list[QuestionReadSchema] = Field(default_factory=list, description="Вопросы к лекции")
    has_presentation: bool = Field(..., description="Загружена ли презентация")
    has_recording: bool = Field(..., description="Загружена ли запись")
    presentation_filename: str | None = Field(None, description="Имя файла презентации")
    recording_filename: str | None = Field(None, description="Имя файла записи")


# LectionReflection schemas

class LectionReflectionBaseSchema(BaseModel):
    """Базовая схема рефлексии студента."""
    
    student_id: uuid.UUID = Field(..., description="ID студента")
    lection_session_id: uuid.UUID = Field(..., description="ID лекции")
    submitted_at: datetime = Field(..., description="Дата и время отправки")
    ai_analysis_status: str = Field(..., description="Статус AI анализа")


class LectionReflectionReadSchema(LectionReflectionBaseSchema):
    """Схема чтения рефлексии студента."""
    
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ReflectionVideo schemas

class ReflectionVideoReadSchema(BaseModel):
    """Схема чтения видео рефлексии."""
    
    id: uuid.UUID
    reflection_id: uuid.UUID = Field(..., description="ID рефлексии")
    file_id: str = Field(..., description="Telegram file_id")
    order_index: int = Field(..., description="Порядковый номер видео")
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# LectionQA schemas

class LectionQAReadSchema(BaseModel):
    """Схема чтения ответа на вопрос."""
    
    id: uuid.UUID
    reflection_id: uuid.UUID = Field(..., description="ID рефлексии")
    question_id: uuid.UUID = Field(..., description="ID вопроса")
    answer_submitted_at: datetime = Field(..., description="Дата и время отправки ответа")
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class QuestionAnswerDraftSchema(BaseModel):
    """Черновик ответа на вопрос для сохранения после завершения workflow."""

    question_id: uuid.UUID = Field(..., description="ID вопроса")
    file_ids: list[str] = Field(default_factory=list, description="Telegram file_id кружков")
    submitted_at: datetime = Field(..., description="Время подтверждения ответа")


# QAVideo schemas

class QAVideoReadSchema(BaseModel):
    """Схема чтения видео ответа на вопрос."""
    
    id: uuid.UUID
    lection_qa_id: uuid.UUID = Field(..., description="ID ответа на вопрос")
    file_id: str = Field(..., description="Telegram file_id")
    order_index: int = Field(..., description="Порядковый номер видео")
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Analytics schemas

class QADetailsSchema(BaseModel):
    """Схема детальной информации об ответе на вопрос."""
    
    question: QuestionReadSchema = Field(..., description="Вопрос")
    lection_qa: LectionQAReadSchema = Field(..., description="Ответ на вопрос")
    qa_videos: list[QAVideoReadSchema] = Field(
        default_factory=list,
        description="Видео ответов с Telegram file_id",
    )


class ReflectionDetailsSchema(BaseModel):
    """Схема детальной информации о рефлексии студента."""
    
    reflection: LectionReflectionReadSchema = Field(..., description="Рефлексия")
    reflection_videos: list[ReflectionVideoReadSchema] = Field(
        default_factory=list,
        description="Видео рефлексий с Telegram file_id"
    )
    qa_list: list[QADetailsSchema] = Field(default_factory=list, description="Список ответов на вопросы")


class LectionStatisticsSchema(BaseModel):
    """Схема статистики по лекции."""
    
    lection: LectionSessionReadSchema = Field(..., description="Лекция")
    questions: list[QuestionReadSchema] = Field(default_factory=list, description="Вопросы к лекции")
    total_students: int = Field(..., description="Общее количество студентов на лекции")
    reflections_count: int = Field(..., description="Количество отправленных рефлексий")
    qa_count: int = Field(..., description="Количество ответов на вопросы")
    students_with_reflections: list[StudentReadSchema] = Field(
        default_factory=list,
        description="Студенты, отправившие рефлексии"
    )


class StudentStatisticsSchema(BaseModel):
    """Схема статистики студента по курсу."""
    
    student: StudentReadSchema = Field(..., description="Студент")
    total_lections: int = Field(..., description="Общее количество лекций в курсе")
    reflections_count: int = Field(..., description="Количество отправленных рефлексий")
    qa_count: int = Field(..., description="Количество ответов на вопросы")
    lections_with_reflections: list[LectionSessionReadSchema] = Field(
        default_factory=list,
        description="Лекции, на которые студент отправил рефлексии"
    )
