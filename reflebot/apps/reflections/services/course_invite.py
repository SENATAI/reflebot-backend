"""
Сервис для генерации и проверки пригласительных ссылок на курс.
"""

import base64
import hashlib
import hmac
import uuid
from typing import Protocol

from reflebot.core.utils.exceptions import ValidationError
from reflebot.settings import Settings


class CourseInviteServiceProtocol(Protocol):
    """Протокол сервиса кодов курса."""

    def generate_course_join_code(self, course_id: uuid.UUID) -> str:
        """Сгенерировать код для записи на курс."""
        ...

    def parse_course_join_code(self, code: str) -> uuid.UUID:
        """Проверить код и вернуть идентификатор курса."""
        ...

    def build_course_invite_link(self, course_id: uuid.UUID) -> str | None:
        """Построить deep link на Telegram-бота."""
        ...


class CourseInviteService(CourseInviteServiceProtocol):
    """Сервис для генерации непрозрачных кодов курса."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_course_join_code(self, course_id: uuid.UUID) -> str:
        """Сгенерировать HMAC-подписанный код курса."""
        payload = course_id.hex.encode("ascii")
        signature = hmac.new(
            self.settings.secret_key.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).digest()[:16]
        raw_token = payload + b"." + signature
        return base64.urlsafe_b64encode(raw_token).decode("ascii").rstrip("=")

    def parse_course_join_code(self, code: str) -> uuid.UUID:
        """Проверить код курса и извлечь идентификатор курса."""
        try:
            padded_token = code + "=" * (-len(code) % 4)
            decoded = base64.urlsafe_b64decode(padded_token.encode("ascii"))
            payload, signature = decoded.split(b".", maxsplit=1)
            expected_signature = hmac.new(
                self.settings.secret_key.encode("utf-8"),
                payload,
                hashlib.sha256,
            ).digest()[:16]
            if not hmac.compare_digest(signature, expected_signature):
                raise ValidationError("course_code", "Недействительный код курса.")
            return uuid.UUID(payload.decode("ascii"))
        except (ValueError, TypeError, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError("course_code", "Недействительный код курса.") from exc

    def generate_course_invite_token(self, course_id: uuid.UUID) -> str:
        """Обратная совместимость со старым названием токена."""
        return self.generate_course_join_code(course_id)

    def parse_course_invite_token(self, token: str) -> uuid.UUID:
        """Обратная совместимость со старым названием токена."""
        return self.parse_course_join_code(token)

    def build_course_invite_link(self, course_id: uuid.UUID) -> str | None:
        """Построить deep link на Telegram-бота для записи на курс."""
        bot_username = self.settings.telegram_bot_username
        if not bot_username:
            return None
        token = self.generate_course_join_code(course_id)
        return f"https://t.me/{bot_username}?start={token}"
