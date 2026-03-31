"""
Роутер для обработки действий, текста и файлов.
"""

from fastapi import APIRouter, File, Form, Header, UploadFile
from pydantic import BaseModel, Field

from ..depends import ButtonActionHandlerDep, FileUploadHandlerDep, TextInputHandlerDep
from ..schemas import ActionResponseSchema


router = APIRouter(prefix="/actions", tags=["Actions"])


class TextInputSchema(BaseModel):
    """Схема текстового ввода пользователя."""

    text: str = Field(..., description="Текст, отправленный пользователем")


@router.post("/button/{action}", response_model=ActionResponseSchema)
async def handle_button_action(
    action: str,
    button_handler: ButtonActionHandlerDep,
    x_telegram_id: int = Header(..., alias="X-Telegram-Id"),
) -> ActionResponseSchema:
    """Обработать нажатие inline-кнопки."""
    return await button_handler.handle(action, x_telegram_id)


@router.post("/text", response_model=ActionResponseSchema)
async def handle_text_input(
    data: TextInputSchema,
    text_handler: TextInputHandlerDep,
    x_telegram_id: int = Header(..., alias="X-Telegram-Id"),
) -> ActionResponseSchema:
    """Обработать текстовый ввод в рамках текущего контекста."""
    return await text_handler.handle(data.text, x_telegram_id)


@router.post("/file", response_model=ActionResponseSchema)
async def handle_file_upload(
    file_handler: FileUploadHandlerDep,
    file: UploadFile | None = File(default=None, description="Файл от пользователя"),
    telegram_file_id: str | None = Form(default=None, description="Telegram file_id для медиа"),
    x_telegram_id: int = Header(..., alias="X-Telegram-Id"),
) -> ActionResponseSchema:
    """Обработать загруженный файл через единый endpoint."""
    return await file_handler.handle(file, x_telegram_id, telegram_file_id=telegram_file_id)
