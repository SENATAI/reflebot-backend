from contextlib import asynccontextmanager

from fastapi import FastAPI

from reflebot.apps.reflections.repositories.default_question import DefaultQuestionRepository
from reflebot.apps.reflections.services.default_question import DefaultQuestionService
from .core.db import AsyncSessionFactory
from .core.loggers import set_logging
from .middleware import apply_middleware
from .exceptions import apply_exceptions_handlers
from .router import apply_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Предварительная инициализация приложения.

    - устанавливаем настройки логгирования
    - устанавливаем настройки кеширования
    - устанавливаем настройки стриминга
    """
    set_logging()

    default_question_service = DefaultQuestionService(
        repository=DefaultQuestionRepository(session=AsyncSessionFactory()),
    )
    await default_question_service.ensure_seeded()

    # stream_repository = await get_streaming_repository_type()
    # await stream_repository.start(settings.kafka)

    yield

    # await stream_repository.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
        docs_url='/docs',
        openapi_url='/docs.json',
    )

    app = apply_routes(apply_exceptions_handlers(apply_middleware(app)))

    return app
