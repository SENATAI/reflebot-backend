"""
Модели базы данных для модуля рефлексий.
"""

import uuid
import secrets
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from reflebot.core.db import Base
from reflebot.core.models import TimestampMixin
from .enums import AIAnalysisStatus, NotificationDeliveryStatus, NotificationDeliveryType

COURSE_JOIN_CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_course_join_code() -> str:
    """Сгенерировать код курса для ORM-вставок вне CourseService."""
    return "".join(secrets.choice(COURSE_JOIN_CODE_CHARS) for _ in range(4))


class CourseSession(Base, TimestampMixin):
    """Сессия курса."""
    
    __tablename__ = "course_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    join_code: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        unique=True,
        index=True,
        default=_generate_course_join_code,
    )
    started_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    # Relationships
    lection_sessions: Mapped[list["LectionSession"]] = relationship(
        back_populates="course_session",
        cascade="all, delete-orphan"
    )
    student_courses: Mapped[list["StudentCourse"]] = relationship(
        back_populates="course_session",
        cascade="all, delete-orphan"
    )
    teacher_courses: Mapped[list["TeacherCourse"]] = relationship(
        back_populates="course_session",
        cascade="all, delete-orphan"
    )


class LectionSession(Base, TimestampMixin):
    """Сессия лекции."""
    
    __tablename__ = "lection_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("course_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    topic: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    presentation_file_id: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    recording_file_id: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    deadline: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    one_question_from_list: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
    )

    # Relationships
    course_session: Mapped["CourseSession"] = relationship(back_populates="lection_sessions")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="lection_session",
        cascade="all, delete-orphan"
    )
    student_lections: Mapped[list["StudentLection"]] = relationship(
        back_populates="lection_session",
        cascade="all, delete-orphan"
    )
    teacher_lections: Mapped[list["TeacherLection"]] = relationship(
        back_populates="lection_session",
        cascade="all, delete-orphan"
    )
    reflections: Mapped[list["LectionReflection"]] = relationship(
        back_populates="lection_session",
        cascade="all, delete-orphan"
    )
    notification_deliveries: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="lection_session",
        cascade="all, delete-orphan",
    )


class Question(Base, TimestampMixin):
    """Вопрос к лекции."""
    
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lection_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lection_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    question_text: Mapped[str] = mapped_column(sa.Text, nullable=False)

    # Relationships
    lection_session: Mapped["LectionSession"] = relationship(back_populates="questions")
    lection_qas: Mapped[list["LectionQA"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan"
    )


class DefaultQuestion(Base, TimestampMixin):
    """Базовый стандартный вопрос для лекций."""

    __tablename__ = "default_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_text: Mapped[str] = mapped_column(sa.String(500), nullable=False, unique=True)


class Student(Base, TimestampMixin):
    """Студент."""
    
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    telegram_username: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    telegram_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)

    # Relationships
    student_courses: Mapped[list["StudentCourse"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan"
    )
    student_lections: Mapped[list["StudentLection"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan"
    )
    reflections: Mapped[list["LectionReflection"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan"
    )
    history_logs: Mapped[list["StudentHistoryLog"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    notification_deliveries: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )


class StudentCourse(Base, TimestampMixin):
    """Привязка студента к курсу."""
    
    __tablename__ = "student_courses"
    __table_args__ = (
        sa.UniqueConstraint("student_id", "course_session_id", name="uq_student_course"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    course_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("course_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    student: Mapped["Student"] = relationship(back_populates="student_courses")
    course_session: Mapped["CourseSession"] = relationship(back_populates="student_courses")


class StudentLection(Base, TimestampMixin):
    """Привязка студента к лекции."""
    
    __tablename__ = "student_lections"
    __table_args__ = (
        sa.UniqueConstraint("student_id", "lection_session_id", name="uq_student_lection"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    lection_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lection_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    student: Mapped["Student"] = relationship(back_populates="student_lections")
    lection_session: Mapped["LectionSession"] = relationship(back_populates="student_lections")


class StudentHistoryLog(Base, TimestampMixin):
    """Лог действий студента в Telegram workflow."""

    __tablename__ = "student_history_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)

    student: Mapped["Student"] = relationship(back_populates="history_logs")


class Teacher(Base, TimestampMixin):
    """Преподаватель."""
    
    __tablename__ = "teachers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    telegram_username: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    telegram_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)

    # Relationships
    teacher_courses: Mapped[list["TeacherCourse"]] = relationship(
        back_populates="teacher",
        cascade="all, delete-orphan"
    )
    teacher_lections: Mapped[list["TeacherLection"]] = relationship(
        back_populates="teacher",
        cascade="all, delete-orphan"
    )


class TeacherCourse(Base, TimestampMixin):
    """Привязка преподавателя к курсу."""
    
    __tablename__ = "teacher_courses"
    __table_args__ = (
        sa.UniqueConstraint("teacher_id", "course_session_id", name="uq_teacher_course"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("teachers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    course_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("course_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    teacher: Mapped["Teacher"] = relationship(back_populates="teacher_courses")
    course_session: Mapped["CourseSession"] = relationship(back_populates="teacher_courses")


class TeacherLection(Base, TimestampMixin):
    """Привязка преподавателя к лекции."""
    
    __tablename__ = "teacher_lections"
    __table_args__ = (
        sa.UniqueConstraint("teacher_id", "lection_session_id", name="uq_teacher_lection"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("teachers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    lection_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lection_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    teacher: Mapped["Teacher"] = relationship(back_populates="teacher_lections")
    lection_session: Mapped["LectionSession"] = relationship(back_populates="teacher_lections")


class LectionReflection(Base, TimestampMixin):
    """Рефлексия студента по лекции."""
    
    __tablename__ = "lection_reflections"
    __table_args__ = (
        sa.UniqueConstraint("student_id", "lection_session_id", name="uq_student_lection_reflection"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    lection_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lection_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    submitted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    ai_analysis_status: Mapped[str] = mapped_column(
        sa.Enum(AIAnalysisStatus, name="ai_analysis_status_enum"),
        default=AIAnalysisStatus.PENDING,
        nullable=False
    )

    # Relationships
    student: Mapped["Student"] = relationship(back_populates="reflections")
    lection_session: Mapped["LectionSession"] = relationship(back_populates="reflections")
    reflection_videos: Mapped[list["ReflectionVideo"]] = relationship(
        back_populates="reflection",
        cascade="all, delete-orphan",
        order_by="ReflectionVideo.order_index"
    )
    lection_qas: Mapped[list["LectionQA"]] = relationship(
        back_populates="reflection",
        cascade="all, delete-orphan"
    )


class ReflectionVideo(Base, TimestampMixin):
    """Видео рефлексии."""
    
    __tablename__ = "reflection_videos"
    __table_args__ = (
        sa.UniqueConstraint("reflection_id", "order_index", name="uq_reflection_video_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reflection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lection_reflections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    file_id: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # Relationships
    reflection: Mapped["LectionReflection"] = relationship(back_populates="reflection_videos")


class LectionQA(Base, TimestampMixin):
    """Ответ студента на вопрос по лекции."""
    
    __tablename__ = "lection_qas"
    __table_args__ = (
        sa.UniqueConstraint("reflection_id", "question_id", name="uq_reflection_question"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reflection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lection_reflections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    answer_submitted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    # Relationships
    reflection: Mapped["LectionReflection"] = relationship(back_populates="lection_qas")
    question: Mapped["Question"] = relationship(back_populates="lection_qas")
    qa_videos: Mapped[list["QAVideo"]] = relationship(
        back_populates="lection_qa",
        cascade="all, delete-orphan"
    )


class QAVideo(Base, TimestampMixin):
    """Видео ответа на вопрос."""
    
    __tablename__ = "qa_videos"
    __table_args__ = (
        sa.UniqueConstraint("lection_qa_id", "order_index", name="uq_qa_video_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lection_qa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lection_qas.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    file_id: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # Relationships
    lection_qa: Mapped["LectionQA"] = relationship(back_populates="qa_videos")


class NotificationDelivery(Base, TimestampMixin):
    """Доставка уведомления студенту по лекции."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        sa.UniqueConstraint(
            "lection_session_id",
            "student_id",
            "type",
            name="uq_notification_delivery_lection_student_type",
        ),
        sa.Index("ix_notification_deliveries_type_status_scheduled_for", "type", "status", "scheduled_for"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lection_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lection_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        sa.String(64),
        default=NotificationDeliveryType.REFLECTION_PROMPT,
        nullable=False,
        index=True,
    )
    scheduled_for: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        sa.String(32),
        default=NotificationDeliveryStatus.PENDING,
        nullable=False,
        index=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    deadline_message_updated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # Relationships
    lection_session: Mapped["LectionSession"] = relationship(back_populates="notification_deliveries")
    student: Mapped["Student"] = relationship(back_populates="notification_deliveries")


class TelegramTrackedMessage(Base, TimestampMixin):
    """Отслеживаемое Telegram-сообщение для последующего автообновления."""

    __tablename__ = "telegram_tracked_messages"
    __table_args__ = (
        sa.UniqueConstraint(
            "notification_delivery_id",
            "kind",
            name="uq_telegram_tracked_messages_delivery_kind",
        ),
        sa.UniqueConstraint(
            "telegram_message_id",
            name="uq_telegram_tracked_messages_message_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, index=True)
    telegram_message_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lection_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("lection_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_delivery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("notification_deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    deadline_message_updated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )


class User(Base, TimestampMixin):
    """Пользователь для хранения контекста диалога."""
    
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    user_context: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)


class Admin(Base, TimestampMixin):
    """Администратор."""
    
    __tablename__ = "admins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    telegram_username: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    telegram_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
