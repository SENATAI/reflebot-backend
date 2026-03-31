# Files Module

Модуль для работы с файлами через MinIO S3 и PostgreSQL.

## Возможности

- Загрузка файлов в MinIO
- Сохранение метаданных в PostgreSQL
- Генерация presigned URLs для доступа к файлам
- Удаление файлов из MinIO и БД

## Использование

### В use case или сервисе

```python
from pinch.apps.files.depends import FileServiceDep
from fastapi import UploadFile
import uuid

# Загрузка файла
async def handle_upload(file: UploadFile, file_service: FileServiceDep):
    result = await file_service.upload_file(file)
    # result: FileUploadResponseSchema с полями:
    # - file_id, path, filename, url, size
    return result

# Получение URL
async def get_url(file_id: uuid.UUID, file_service: FileServiceDep):
    url = await file_service.get_file_url(file_id, expires_in=3600)
    return url

# Удаление файла
async def remove_file(file_id: uuid.UUID, file_service: FileServiceDep):
    success = await file_service.delete_file(file_id)
    return success
```

## Архитектура

- `models.py` - SQLAlchemy модель File
- `schemas.py` - Pydantic схемы для валидации
- `repositories/file.py` - Репозиторий для работы с БД
- `services/minio_service.py` - Низкоуровневая работа с MinIO
- `services/file_service.py` - Высокоуровневый сервис (MinIO + БД)
- `depends.py` - Dependency injection

## Настройка

См. `SETUP_FILES_MODULE.md` в корне проекта.
