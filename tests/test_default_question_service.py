"""
Unit tests for DefaultQuestionService.
"""

from unittest.mock import AsyncMock

import pytest

from reflebot.apps.reflections.services.default_question import (
    DEFAULT_QUESTION_TEMPLATES,
    DefaultQuestionService,
)


@pytest.mark.asyncio
async def test_default_question_service_seeds_missing_templates():
    repository = AsyncMock()
    repository.get_all_question_texts.return_value = [DEFAULT_QUESTION_TEMPLATES[0]]
    service = DefaultQuestionService(repository)

    await service.ensure_seeded()

    assert repository.create.await_count == len(DEFAULT_QUESTION_TEMPLATES) - 1


@pytest.mark.asyncio
async def test_default_question_service_returns_random_question_from_seeded_set():
    repository = AsyncMock()
    repository.get_all_question_texts.return_value = DEFAULT_QUESTION_TEMPLATES
    service = DefaultQuestionService(repository)

    question = await service.get_random_question_text()

    assert question in DEFAULT_QUESTION_TEMPLATES
