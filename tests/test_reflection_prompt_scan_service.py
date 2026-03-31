"""
Unit tests для ReflectionPromptScanService.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import uuid

import pytest

from reflebot.apps.reflections.services.reflection_prompt_scan import ReflectionPromptScanService


def configure_session(session: AsyncMock) -> None:
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None


@pytest.mark.asyncio
async def test_reflection_prompt_scan_service_maps_due_candidates():
    repository = AsyncMock()
    session = AsyncMock()
    configure_session(session)
    repository.session = session
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(
        lection_session_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        telegram_id=777,
        ended_at=now,
    )
    execute_result = Mock()
    execute_result.all.return_value = [row]
    session.execute.return_value = execute_result
    service = ReflectionPromptScanService(repository, lookback_hours=48)

    result = await service.find_due_candidates(now=now, limit=10)

    assert len(result) == 1
    assert result[0].telegram_id == 777
    assert result[0].scheduled_for == now


@pytest.mark.asyncio
async def test_reflection_prompt_scan_service_builds_bounded_query():
    repository = AsyncMock()
    session = AsyncMock()
    configure_session(session)
    repository.session = session
    execute_result = Mock()
    execute_result.all.return_value = []
    session.execute.return_value = execute_result
    service = ReflectionPromptScanService(repository, lookback_hours=24)
    now = datetime.now(timezone.utc)

    await service.find_due_candidates(now=now, limit=25)

    statement = session.execute.call_args[0][0]
    statement_sql = str(statement)
    assert "notification_deliveries" in statement_sql
    assert "NOT (EXISTS" in statement_sql
    assert "lection_sessions.ended_at" in statement_sql
    assert "LIMIT" in statement_sql.upper()


@pytest.mark.asyncio
async def test_reflection_prompt_scan_service_uses_updated_ended_at_value():
    repository = AsyncMock()
    session = AsyncMock()
    configure_session(session)
    repository.session = session
    now = datetime.now(timezone.utc)
    new_ended_at = now - timedelta(minutes=5)
    row = SimpleNamespace(
        lection_session_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        telegram_id=999,
        ended_at=new_ended_at,
    )
    execute_result = Mock()
    execute_result.all.return_value = [row]
    session.execute.return_value = execute_result
    service = ReflectionPromptScanService(repository, lookback_hours=24)

    result = await service.find_due_candidates(now=now, limit=1)

    assert result[0].scheduled_for == new_ended_at
