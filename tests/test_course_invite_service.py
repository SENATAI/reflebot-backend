"""
Unit tests for course join code service.
"""

import uuid
from unittest.mock import Mock

import pytest

from reflebot.apps.reflections.services.course_invite import CourseInviteService
from reflebot.core.utils.exceptions import ValidationError


def build_service(bot_username: str | None = "reflebot") -> CourseInviteService:
    settings = Mock(secret_key="super-secret-key", telegram_bot_username=bot_username)
    return CourseInviteService(settings=settings)


def test_course_join_code_service_round_trip_code():
    service = build_service()
    course_id = uuid.uuid4()

    token = service.generate_course_join_code(course_id)

    assert service.parse_course_join_code(token) == course_id


def test_course_invite_service_builds_tg_link():
    service = build_service(bot_username="reflebot_test_bot")
    course_id = uuid.uuid4()

    link = service.build_course_invite_link(course_id)

    assert link is not None
    assert link.startswith("https://t.me/reflebot_test_bot?start=")


def test_course_join_code_service_rejects_invalid_code():
    service = build_service()

    with pytest.raises(ValidationError):
        service.parse_course_join_code("broken-token")
