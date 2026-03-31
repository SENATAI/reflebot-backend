"""
Unit tests for ContextService navigation methods.

Tests the push_navigation and pop_navigation methods for managing
navigation history in user context.

**Validates: Requirements 27.2, 27.3**
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from reflebot.apps.reflections.services.context import ContextService
from reflebot.apps.reflections.schemas import UserReadSchema


def create_user_read_schema(telegram_id: int, user_context: dict | None) -> UserReadSchema:
    """Helper to create UserReadSchema with required timestamp fields."""
    now = datetime.now(timezone.utc)
    return UserReadSchema(
        telegram_id=telegram_id,
        user_context=user_context,
        created_at=now,
        updated_at=now
    )


@pytest.fixture
def mock_user_repository():
    """Create a mock user repository."""
    return AsyncMock()


@pytest.fixture
def context_service(mock_user_repository):
    """Create a ContextService instance with mocked repository."""
    return ContextService(user_repository=mock_user_repository)


class TestPushNavigation:
    """Test push_navigation method."""
    
    @pytest.mark.asyncio
    async def test_push_navigation_to_empty_context(
        self, context_service, mock_user_repository
    ):
        """Test pushing navigation when no context exists."""
        telegram_id = 123456789
        screen = "main_menu"
        
        # Mock get_context to return None (no existing context)
        mock_user_repository.get_by_telegram_id.return_value = None
        
        # Mock upsert_context to return a user
        expected_user = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={
                "action": None,
                "step": None,
                "data": {},
                "navigation_history": [screen]
            }
        )
        mock_user_repository.upsert_context.return_value = expected_user
        
        # Execute
        result = await context_service.push_navigation(telegram_id, screen)
        
        # Verify
        assert result.telegram_id == telegram_id
        assert result.user_context["navigation_history"] == [screen]
        
        # Verify upsert was called with correct context
        mock_user_repository.upsert_context.assert_called_once()
        call_args = mock_user_repository.upsert_context.call_args
        assert call_args[0][0] == telegram_id
        assert call_args[0][1]["navigation_history"] == [screen]
    
    @pytest.mark.asyncio
    async def test_push_navigation_to_existing_context(
        self, context_service, mock_user_repository
    ):
        """Test pushing navigation when context already exists."""
        telegram_id = 123456789
        existing_context = {
            "action": "create_admin",
            "step": "awaiting_fullname",
            "data": {},
            "navigation_history": ["main_menu"]
        }
        
        # Mock get_context to return existing context
        mock_user = Mock()
        mock_user.user_context = existing_context
        mock_user_repository.get_by_telegram_id.return_value = mock_user
        
        # Mock upsert_context
        expected_user = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={
                "action": "create_admin",
                "step": "awaiting_fullname",
                "data": {},
                "navigation_history": ["main_menu", "admin_menu"]
            }
        )
        mock_user_repository.upsert_context.return_value = expected_user
        
        # Execute
        result = await context_service.push_navigation(telegram_id, "admin_menu")
        
        # Verify
        assert result.user_context["navigation_history"] == ["main_menu", "admin_menu"]
        
        # Verify upsert was called
        mock_user_repository.upsert_context.assert_called_once()
        call_args = mock_user_repository.upsert_context.call_args
        assert call_args[0][1]["navigation_history"] == ["main_menu", "admin_menu"]
    
    @pytest.mark.asyncio
    async def test_push_navigation_without_history_field(
        self, context_service, mock_user_repository
    ):
        """Test pushing navigation when context exists but has no navigation_history."""
        telegram_id = 123456789
        existing_context = {
            "action": "create_course",
            "step": "awaiting_file",
            "data": {"course_name": "Test Course"}
        }
        
        # Mock get_context to return context without navigation_history
        mock_user = Mock()
        mock_user.user_context = existing_context
        mock_user_repository.get_by_telegram_id.return_value = mock_user
        
        # Mock upsert_context
        expected_user = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={
                "action": "create_course",
                "step": "awaiting_file",
                "data": {"course_name": "Test Course"},
                "navigation_history": ["course_menu"]
            }
        )
        mock_user_repository.upsert_context.return_value = expected_user
        
        # Execute
        result = await context_service.push_navigation(telegram_id, "course_menu")
        
        # Verify
        assert result.user_context["navigation_history"] == ["course_menu"]
    
    @pytest.mark.asyncio
    async def test_push_navigation_multiple_screens(
        self, context_service, mock_user_repository
    ):
        """Test pushing multiple screens in sequence."""
        telegram_id = 123456789
        
        # First push
        mock_user_repository.get_by_telegram_id.return_value = None
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": ["main_menu"]}
        )
        await context_service.push_navigation(telegram_id, "main_menu")
        
        # Second push
        mock_user = Mock()
        mock_user.user_context = {"navigation_history": ["main_menu"]}
        mock_user_repository.get_by_telegram_id.return_value = mock_user
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": ["main_menu", "admin_menu"]}
        )
        await context_service.push_navigation(telegram_id, "admin_menu")
        
        # Third push
        mock_user.user_context = {"navigation_history": ["main_menu", "admin_menu"]}
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": ["main_menu", "admin_menu", "course_list"]}
        )
        result = await context_service.push_navigation(telegram_id, "course_list")
        
        # Verify final state
        assert result.user_context["navigation_history"] == [
            "main_menu", "admin_menu", "course_list"
        ]


class TestPopNavigation:
    """Test pop_navigation method."""
    
    @pytest.mark.asyncio
    async def test_pop_navigation_with_history(
        self, context_service, mock_user_repository
    ):
        """Test popping navigation when history exists."""
        telegram_id = 123456789
        existing_context = {
            "action": "view_analytics",
            "step": None,
            "data": {},
            "navigation_history": ["main_menu", "admin_menu", "course_list"]
        }
        
        # Mock get_context
        mock_user = Mock()
        mock_user.user_context = existing_context
        mock_user_repository.get_by_telegram_id.return_value = mock_user
        
        # Mock upsert_context
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={
                "action": "view_analytics",
                "step": None,
                "data": {},
                "navigation_history": ["main_menu", "admin_menu"]
            }
        )
        
        # Execute
        result = await context_service.pop_navigation(telegram_id)
        
        # Verify - should return the previous screen (admin_menu)
        assert result == "admin_menu"
        
        # Verify upsert was called with updated history
        mock_user_repository.upsert_context.assert_called_once()
        call_args = mock_user_repository.upsert_context.call_args
        assert call_args[0][1]["navigation_history"] == ["main_menu", "admin_menu"]
    
    @pytest.mark.asyncio
    async def test_pop_navigation_to_main_menu(
        self, context_service, mock_user_repository
    ):
        """Test popping navigation when only main menu remains."""
        telegram_id = 123456789
        existing_context = {
            "action": None,
            "step": None,
            "data": {},
            "navigation_history": ["main_menu"]
        }
        
        # Mock get_context
        mock_user = Mock()
        mock_user.user_context = existing_context
        mock_user_repository.get_by_telegram_id.return_value = mock_user
        
        # Mock upsert_context
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={
                "action": None,
                "step": None,
                "data": {},
                "navigation_history": []
            }
        )
        
        # Execute
        result = await context_service.pop_navigation(telegram_id)
        
        # Verify - should return None when history becomes empty
        assert result is None
    
    @pytest.mark.asyncio
    async def test_pop_navigation_empty_history(
        self, context_service, mock_user_repository
    ):
        """Test popping navigation when history is already empty."""
        telegram_id = 123456789
        existing_context = {
            "action": None,
            "step": None,
            "data": {},
            "navigation_history": []
        }
        
        # Mock get_context
        mock_user = Mock()
        mock_user.user_context = existing_context
        mock_user_repository.get_by_telegram_id.return_value = mock_user
        
        # Execute
        result = await context_service.pop_navigation(telegram_id)
        
        # Verify - should return None
        assert result is None
        
        # Verify upsert was NOT called (no changes needed)
        mock_user_repository.upsert_context.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_pop_navigation_no_context(
        self, context_service, mock_user_repository
    ):
        """Test popping navigation when no context exists."""
        telegram_id = 123456789
        
        # Mock get_context to return None
        mock_user_repository.get_by_telegram_id.return_value = None
        
        # Execute
        result = await context_service.pop_navigation(telegram_id)
        
        # Verify - should return None
        assert result is None
        
        # Verify upsert was NOT called
        mock_user_repository.upsert_context.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_pop_navigation_no_history_field(
        self, context_service, mock_user_repository
    ):
        """Test popping navigation when context exists but has no navigation_history."""
        telegram_id = 123456789
        existing_context = {
            "action": "create_admin",
            "step": "awaiting_fullname",
            "data": {}
        }
        
        # Mock get_context
        mock_user = Mock()
        mock_user.user_context = existing_context
        mock_user_repository.get_by_telegram_id.return_value = mock_user
        
        # Execute
        result = await context_service.pop_navigation(telegram_id)
        
        # Verify - should return None
        assert result is None
        
        # Verify upsert was NOT called
        mock_user_repository.upsert_context.assert_not_called()


class TestNavigationIntegration:
    """Test push and pop navigation together."""
    
    @pytest.mark.asyncio
    async def test_push_and_pop_sequence(
        self, context_service, mock_user_repository
    ):
        """Test a sequence of push and pop operations."""
        telegram_id = 123456789
        
        # Start with no context
        mock_user_repository.get_by_telegram_id.return_value = None
        
        # Push main_menu
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": ["main_menu"]}
        )
        await context_service.push_navigation(telegram_id, "main_menu")
        
        # Push admin_menu
        mock_user = Mock()
        mock_user.user_context = {"navigation_history": ["main_menu"]}
        mock_user_repository.get_by_telegram_id.return_value = mock_user
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": ["main_menu", "admin_menu"]}
        )
        await context_service.push_navigation(telegram_id, "admin_menu")
        
        # Push course_list
        mock_user.user_context = {"navigation_history": ["main_menu", "admin_menu"]}
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": ["main_menu", "admin_menu", "course_list"]}
        )
        await context_service.push_navigation(telegram_id, "course_list")
        
        # Pop back to admin_menu
        mock_user.user_context = {"navigation_history": ["main_menu", "admin_menu", "course_list"]}
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": ["main_menu", "admin_menu"]}
        )
        result = await context_service.pop_navigation(telegram_id)
        assert result == "admin_menu"
        
        # Pop back to main_menu
        mock_user.user_context = {"navigation_history": ["main_menu", "admin_menu"]}
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": ["main_menu"]}
        )
        result = await context_service.pop_navigation(telegram_id)
        assert result == "main_menu"
        
        # Pop from main_menu (should return None)
        mock_user.user_context = {"navigation_history": ["main_menu"]}
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": []}
        )
        result = await context_service.pop_navigation(telegram_id)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_return_to_main_menu_clears_history(
        self, context_service, mock_user_repository
    ):
        """Test that returning to main menu clears navigation history."""
        telegram_id = 123456789
        
        # Setup context with deep navigation
        existing_context = {
            "action": "view_analytics",
            "step": None,
            "data": {},
            "navigation_history": ["main_menu", "admin_menu", "course_list", "lection_details"]
        }
        
        mock_user = Mock()
        mock_user.user_context = existing_context
        mock_user_repository.get_by_telegram_id.return_value = mock_user
        
        # Pop multiple times until we reach main menu
        # Pop 1: lection_details -> course_list
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": ["main_menu", "admin_menu", "course_list"]}
        )
        result = await context_service.pop_navigation(telegram_id)
        assert result == "course_list"
        
        # Pop 2: course_list -> admin_menu
        mock_user.user_context = {"navigation_history": ["main_menu", "admin_menu", "course_list"]}
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": ["main_menu", "admin_menu"]}
        )
        result = await context_service.pop_navigation(telegram_id)
        assert result == "admin_menu"
        
        # Pop 3: admin_menu -> main_menu
        mock_user.user_context = {"navigation_history": ["main_menu", "admin_menu"]}
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": ["main_menu"]}
        )
        result = await context_service.pop_navigation(telegram_id)
        assert result == "main_menu"
        
        # Pop 4: main_menu -> None (history cleared)
        mock_user.user_context = {"navigation_history": ["main_menu"]}
        mock_user_repository.upsert_context.return_value = create_user_read_schema(
            telegram_id=telegram_id,
            user_context={"navigation_history": []}
        )
        result = await context_service.pop_navigation(telegram_id)
        assert result is None
