#!/usr/bin/env python3
"""
Скрипт для создания администратора вручную.

Использование:
    uv run python scripts/create_admin.py "Иванов Иван Иванович" "ivan_telegram"
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession

from reflebot.core.db import AsyncSessionFactory
from reflebot.apps.reflections.repositories.admin import AdminRepository
from reflebot.apps.reflections.schemas import AdminCreateSchema


async def create_admin(full_name: str, telegram_username: str) -> None:
    """
    Создать администратора.
    
    Args:
        full_name: ФИО администратора
        telegram_username: Никнейм в Telegram
    """
    async with AsyncSessionFactory() as session:
        repository = AdminRepository(session=session)
        
        admin_data = AdminCreateSchema(
            full_name=full_name,
            telegram_username=telegram_username,
            telegram_id=None,
            is_active=True,
        )
        
        try:
            admin = await repository.create(admin_data)
            print(f"✅ Администратор успешно создан:")
            print(f"   ID: {admin.id}")
            print(f"   ФИО: {admin.full_name}")
            print(f"   Telegram: @{admin.telegram_username}")
            print(f"   Активен: {admin.is_active}")
        except Exception as e:
            print(f"❌ Ошибка при создании администратора: {e}")
            sys.exit(1)


def main() -> None:
    """Точка входа скрипта."""
    if len(sys.argv) != 3:
        print("Использование: uv run python scripts/create_admin.py <ФИО> <telegram_username>")
        print('Пример: uv run python scripts/create_admin.py "Иванов Иван Иванович" "ivan_telegram"')
        sys.exit(1)
    
    full_name = sys.argv[1]
    telegram_username = sys.argv[2]
    
    asyncio.run(create_admin(full_name, telegram_username))


if __name__ == "__main__":
    main()
