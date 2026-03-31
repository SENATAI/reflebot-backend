"""
Роутер для аутентификации.
"""

from fastapi import APIRouter, Path, status

from ..schemas import AdminLoginSchema, UserLoginResponseSchema
from ..depends import AdminLoginUseCaseDep


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/{telegram_username}/login",
    response_model=UserLoginResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Вход пользователя",
    description="Универсальный вход для админа/студента/преподавателя. Обновляет telegram_id во всех таблицах, где найден username.",
)
async def user_login(
    telegram_username: str = Path(..., description="Никнейм пользователя в Telegram"),
    login_data: AdminLoginSchema = ...,
    use_case: AdminLoginUseCaseDep = ...,
) -> UserLoginResponseSchema:
    """Вход пользователя. Проверяет все таблицы (Admin, Student, Teacher)."""
    return await use_case(telegram_username, login_data)
