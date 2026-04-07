"""
API route tests for simplified Telegram workflow endpoints.
"""

import io

import pytest
from fastapi import UploadFile

from reflebot.apps.reflections.routers.actions import (
    MessageDeliveredSchema,
    TextInputSchema,
    handle_button_action,
    handle_file_upload,
    handle_message_delivered,
    handle_text_input,
)
from reflebot.apps.reflections.routers.auth import user_login
from reflebot.apps.reflections.schemas import ActionResponseSchema, UserLoginResponseSchema, AdminLoginSchema


class DummyButtonHandler:
    async def handle(self, action: str, telegram_id: int) -> ActionResponseSchema:
        return ActionResponseSchema(message="ok", buttons=[], awaiting_input=False)


class DummyTextHandler:
    async def handle(self, text: str, telegram_id: int) -> ActionResponseSchema:
        return ActionResponseSchema(message="ok", buttons=[], awaiting_input=False)


class DummyFileHandler:
    async def handle(self, file, telegram_id: int, telegram_file_id: str | None = None) -> ActionResponseSchema:
        return ActionResponseSchema(message="ok", buttons=[], awaiting_input=False)


class DummyLoginUseCase:
    async def __call__(self, telegram_username: str, login_data) -> UserLoginResponseSchema:
        return UserLoginResponseSchema(
            full_name="User",
            telegram_username=telegram_username,
            telegram_id=login_data.telegram_id,
            is_active=True,
            is_admin=True,
            is_teacher=False,
            is_student=False,
            message="ok",
            parse_mode="HTML",
            buttons=[],
            awaiting_input=False,
        )


class DummyTrackedMessageService:
    async def track_message_delivery(
        self,
        telegram_id: int,
        tracking_key: str,
        telegram_message_id: int,
    ) -> None:
        self.payload = (telegram_id, tracking_key, telegram_message_id)


@pytest.mark.asyncio
async def test_actions_endpoints_return_standard_response_structure():
    button_response = await handle_button_action("test", DummyButtonHandler(), 1)
    text_response = await handle_text_input(TextInputSchema(text="hello"), DummyTextHandler(), 1)
    file_response = await handle_file_upload(
        DummyFileHandler(),
        UploadFile(filename="test.txt", file=io.BytesIO(b"hello")),
        1,
    )

    for response in [button_response, text_response, file_response]:
        payload = response.model_dump()
        assert set(payload.keys()) == {
            "message",
            "parse_mode",
            "buttons",
            "files",
            "dialog_messages",
            "awaiting_input",
            "message_tracking",
        }


@pytest.mark.asyncio
async def test_auth_endpoint_returns_login_payload():
    response = await user_login("test_user", AdminLoginSchema(telegram_id=42), DummyLoginUseCase())

    payload = response.model_dump()
    assert payload["telegram_username"] == "test_user"
    assert payload["telegram_id"] == 42
    assert payload["message"] == "ok"


@pytest.mark.asyncio
async def test_message_delivered_endpoint_tracks_bot_message():
    service = DummyTrackedMessageService()

    await handle_message_delivered(
        MessageDeliveredSchema(tracking_key="reflection_status:test", telegram_message_id=77),
        service,
        42,
    )

    assert service.payload == (42, "reflection_status:test", 77)
