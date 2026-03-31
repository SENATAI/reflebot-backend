"""
Unit tests for PaginationService.

Tests the paginate and get_pagination_buttons methods for managing
pagination of lists and generating navigation buttons.

**Validates: Requirements 8.1, 26.1, 26.2, 26.3**
"""

import pytest

from reflebot.apps.reflections.services.pagination import PaginationService
from reflebot.apps.reflections.schemas import TelegramButtonSchema


@pytest.fixture
def pagination_service():
    """Create a PaginationService instance."""
    return PaginationService()


class TestPaginate:
    """Test paginate method."""
    
    def test_paginate_empty_list(self, pagination_service):
        """Test pagination with empty list."""
        items = []
        result = pagination_service.paginate(items, page=1, page_size=5)
        
        assert result["items"] == []
        assert result["total"] == 0
        assert result["page"] == 1
        assert result["page_size"] == 5
        assert result["total_pages"] == 1
    
    def test_paginate_single_page(self, pagination_service):
        """Test pagination when all items fit on one page."""
        items = [1, 2, 3, 4, 5]
        result = pagination_service.paginate(items, page=1, page_size=5)
        
        assert result["items"] == [1, 2, 3, 4, 5]
        assert result["total"] == 5
        assert result["page"] == 1
        assert result["page_size"] == 5
        assert result["total_pages"] == 1
    
    def test_paginate_multiple_pages_first_page(self, pagination_service):
        """Test pagination with multiple pages - first page."""
        items = list(range(1, 16))  # 15 items
        result = pagination_service.paginate(items, page=1, page_size=5)
        
        assert result["items"] == [1, 2, 3, 4, 5]
        assert result["total"] == 15
        assert result["page"] == 1
        assert result["page_size"] == 5
        assert result["total_pages"] == 3
    
    def test_paginate_multiple_pages_middle_page(self, pagination_service):
        """Test pagination with multiple pages - middle page."""
        items = list(range(1, 16))  # 15 items
        result = pagination_service.paginate(items, page=2, page_size=5)
        
        assert result["items"] == [6, 7, 8, 9, 10]
        assert result["total"] == 15
        assert result["page"] == 2
        assert result["page_size"] == 5
        assert result["total_pages"] == 3
    
    def test_paginate_multiple_pages_last_page(self, pagination_service):
        """Test pagination with multiple pages - last page."""
        items = list(range(1, 16))  # 15 items
        result = pagination_service.paginate(items, page=3, page_size=5)
        
        assert result["items"] == [11, 12, 13, 14, 15]
        assert result["total"] == 15
        assert result["page"] == 3
        assert result["page_size"] == 5
        assert result["total_pages"] == 3
    
    def test_paginate_partial_last_page(self, pagination_service):
        """Test pagination when last page is not full."""
        items = list(range(1, 14))  # 13 items
        result = pagination_service.paginate(items, page=3, page_size=5)
        
        assert result["items"] == [11, 12, 13]
        assert result["total"] == 13
        assert result["page"] == 3
        assert result["page_size"] == 5
        assert result["total_pages"] == 3
    
    def test_paginate_page_less_than_one(self, pagination_service):
        """Test pagination with page number less than 1."""
        items = list(range(1, 11))
        result = pagination_service.paginate(items, page=0, page_size=5)
        
        # Should default to page 1
        assert result["items"] == [1, 2, 3, 4, 5]
        assert result["page"] == 1
    
    def test_paginate_page_greater_than_total(self, pagination_service):
        """Test pagination with page number greater than total pages."""
        items = list(range(1, 11))
        result = pagination_service.paginate(items, page=10, page_size=5)
        
        # Should default to last page
        assert result["items"] == [6, 7, 8, 9, 10]
        assert result["page"] == 2
        assert result["total_pages"] == 2
    
    def test_paginate_negative_page(self, pagination_service):
        """Test pagination with negative page number."""
        items = list(range(1, 11))
        result = pagination_service.paginate(items, page=-5, page_size=5)
        
        # Should default to page 1
        assert result["items"] == [1, 2, 3, 4, 5]
        assert result["page"] == 1
    
    def test_paginate_different_page_sizes(self, pagination_service):
        """Test pagination with different page sizes."""
        items = list(range(1, 21))  # 20 items
        
        # Page size 10
        result = pagination_service.paginate(items, page=1, page_size=10)
        assert len(result["items"]) == 10
        assert result["total_pages"] == 2
        
        # Page size 3
        result = pagination_service.paginate(items, page=1, page_size=3)
        assert len(result["items"]) == 3
        assert result["total_pages"] == 7
        
        # Page size 20
        result = pagination_service.paginate(items, page=1, page_size=20)
        assert len(result["items"]) == 20
        assert result["total_pages"] == 1
    
    def test_paginate_with_objects(self, pagination_service):
        """Test pagination with complex objects."""
        items = [
            {"id": i, "name": f"Item {i}"}
            for i in range(1, 16)
        ]
        result = pagination_service.paginate(items, page=2, page_size=5)
        
        assert len(result["items"]) == 5
        assert result["items"][0] == {"id": 6, "name": "Item 6"}
        assert result["items"][-1] == {"id": 10, "name": "Item 10"}


class TestGetPaginationButtons:
    """Test get_pagination_buttons method."""
    
    def test_get_pagination_buttons_first_page(self, pagination_service):
        """Test pagination buttons on first page."""
        buttons = pagination_service.get_pagination_buttons(
            current_page=1,
            total_pages=3,
            action_prefix="view_lections"
        )
        
        # Should only have "Next" button
        assert len(buttons) == 1
        assert buttons[0].text == "Следующая страница ▶️"
        assert buttons[0].action == "view_lections_page_2"
    
    def test_get_pagination_buttons_middle_page(self, pagination_service):
        """Test pagination buttons on middle page."""
        buttons = pagination_service.get_pagination_buttons(
            current_page=2,
            total_pages=3,
            action_prefix="view_lections"
        )
        
        # Should have both "Previous" and "Next" buttons
        assert len(buttons) == 2
        assert buttons[0].text == "◀️ Предыдущая страница"
        assert buttons[0].action == "view_lections_page_1"
        assert buttons[1].text == "Следующая страница ▶️"
        assert buttons[1].action == "view_lections_page_3"
    
    def test_get_pagination_buttons_last_page(self, pagination_service):
        """Test pagination buttons on last page."""
        buttons = pagination_service.get_pagination_buttons(
            current_page=3,
            total_pages=3,
            action_prefix="view_lections"
        )
        
        # Should only have "Previous" button
        assert len(buttons) == 1
        assert buttons[0].text == "◀️ Предыдущая страница"
        assert buttons[0].action == "view_lections_page_2"
    
    def test_get_pagination_buttons_single_page(self, pagination_service):
        """Test pagination buttons when only one page exists."""
        buttons = pagination_service.get_pagination_buttons(
            current_page=1,
            total_pages=1,
            action_prefix="view_lections"
        )
        
        # Should have no pagination buttons
        assert len(buttons) == 0
    
    def test_get_pagination_buttons_different_action_prefix(self, pagination_service):
        """Test pagination buttons with different action prefixes."""
        buttons = pagination_service.get_pagination_buttons(
            current_page=2,
            total_pages=5,
            action_prefix="view_students"
        )
        
        assert len(buttons) == 2
        assert buttons[0].action == "view_students_page_1"
        assert buttons[1].action == "view_students_page_3"
    
    def test_get_pagination_buttons_returns_telegram_button_schema(
        self, pagination_service
    ):
        """Test that pagination buttons are TelegramButtonSchema instances."""
        buttons = pagination_service.get_pagination_buttons(
            current_page=2,
            total_pages=3,
            action_prefix="view_courses"
        )
        
        assert all(isinstance(btn, TelegramButtonSchema) for btn in buttons)
        assert all(hasattr(btn, "text") for btn in buttons)
        assert all(hasattr(btn, "action") for btn in buttons)


class TestPaginationIntegration:
    """Test paginate and get_pagination_buttons together."""
    
    def test_pagination_workflow_first_page(self, pagination_service):
        """Test complete pagination workflow for first page."""
        items = list(range(1, 16))  # 15 items
        
        # Paginate first page
        result = pagination_service.paginate(items, page=1, page_size=5)
        
        # Get pagination buttons
        buttons = pagination_service.get_pagination_buttons(
            current_page=result["page"],
            total_pages=result["total_pages"],
            action_prefix="view_items"
        )
        
        # Verify
        assert result["items"] == [1, 2, 3, 4, 5]
        assert len(buttons) == 1
        assert buttons[0].text == "Следующая страница ▶️"
    
    def test_pagination_workflow_middle_page(self, pagination_service):
        """Test complete pagination workflow for middle page."""
        items = list(range(1, 16))  # 15 items
        
        # Paginate middle page
        result = pagination_service.paginate(items, page=2, page_size=5)
        
        # Get pagination buttons
        buttons = pagination_service.get_pagination_buttons(
            current_page=result["page"],
            total_pages=result["total_pages"],
            action_prefix="view_items"
        )
        
        # Verify
        assert result["items"] == [6, 7, 8, 9, 10]
        assert len(buttons) == 2
        assert buttons[0].text == "◀️ Предыдущая страница"
        assert buttons[1].text == "Следующая страница ▶️"
    
    def test_pagination_workflow_last_page(self, pagination_service):
        """Test complete pagination workflow for last page."""
        items = list(range(1, 16))  # 15 items
        
        # Paginate last page
        result = pagination_service.paginate(items, page=3, page_size=5)
        
        # Get pagination buttons
        buttons = pagination_service.get_pagination_buttons(
            current_page=result["page"],
            total_pages=result["total_pages"],
            action_prefix="view_items"
        )
        
        # Verify
        assert result["items"] == [11, 12, 13, 14, 15]
        assert len(buttons) == 1
        assert buttons[0].text == "◀️ Предыдущая страница"
    
    def test_pagination_workflow_single_page(self, pagination_service):
        """Test complete pagination workflow when all items fit on one page."""
        items = list(range(1, 6))  # 5 items
        
        # Paginate
        result = pagination_service.paginate(items, page=1, page_size=5)
        
        # Get pagination buttons
        buttons = pagination_service.get_pagination_buttons(
            current_page=result["page"],
            total_pages=result["total_pages"],
            action_prefix="view_items"
        )
        
        # Verify
        assert result["items"] == [1, 2, 3, 4, 5]
        assert len(buttons) == 0  # No pagination needed
    
    def test_pagination_navigation_sequence(self, pagination_service):
        """Test navigating through multiple pages."""
        items = list(range(1, 21))  # 20 items
        
        # Page 1
        result = pagination_service.paginate(items, page=1, page_size=5)
        assert result["items"] == [1, 2, 3, 4, 5]
        buttons = pagination_service.get_pagination_buttons(
            result["page"], result["total_pages"], "nav"
        )
        assert len(buttons) == 1
        assert buttons[0].action == "nav_page_2"
        
        # Page 2
        result = pagination_service.paginate(items, page=2, page_size=5)
        assert result["items"] == [6, 7, 8, 9, 10]
        buttons = pagination_service.get_pagination_buttons(
            result["page"], result["total_pages"], "nav"
        )
        assert len(buttons) == 2
        assert buttons[0].action == "nav_page_1"
        assert buttons[1].action == "nav_page_3"
        
        # Page 3
        result = pagination_service.paginate(items, page=3, page_size=5)
        assert result["items"] == [11, 12, 13, 14, 15]
        buttons = pagination_service.get_pagination_buttons(
            result["page"], result["total_pages"], "nav"
        )
        assert len(buttons) == 2
        assert buttons[0].action == "nav_page_2"
        assert buttons[1].action == "nav_page_4"
        
        # Page 4 (last)
        result = pagination_service.paginate(items, page=4, page_size=5)
        assert result["items"] == [16, 17, 18, 19, 20]
        buttons = pagination_service.get_pagination_buttons(
            result["page"], result["total_pages"], "nav"
        )
        assert len(buttons) == 1
        assert buttons[0].action == "nav_page_3"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_paginate_one_item(self, pagination_service):
        """Test pagination with single item."""
        items = [1]
        result = pagination_service.paginate(items, page=1, page_size=5)
        
        assert result["items"] == [1]
        assert result["total"] == 1
        assert result["total_pages"] == 1
    
    def test_paginate_exact_page_size(self, pagination_service):
        """Test pagination when total items equals page size."""
        items = list(range(1, 6))  # Exactly 5 items
        result = pagination_service.paginate(items, page=1, page_size=5)
        
        assert result["items"] == [1, 2, 3, 4, 5]
        assert result["total_pages"] == 1
    
    def test_paginate_one_more_than_page_size(self, pagination_service):
        """Test pagination when total items is one more than page size."""
        items = list(range(1, 7))  # 6 items
        result = pagination_service.paginate(items, page=2, page_size=5)
        
        assert result["items"] == [6]
        assert result["total_pages"] == 2
    
    def test_paginate_large_page_size(self, pagination_service):
        """Test pagination with very large page size."""
        items = list(range(1, 11))
        result = pagination_service.paginate(items, page=1, page_size=1000)
        
        assert result["items"] == items
        assert result["total_pages"] == 1
    
    def test_paginate_page_size_one(self, pagination_service):
        """Test pagination with page size of 1."""
        items = list(range(1, 6))
        result = pagination_service.paginate(items, page=3, page_size=1)
        
        assert result["items"] == [3]
        assert result["total_pages"] == 5
    
    def test_get_pagination_buttons_many_pages(self, pagination_service):
        """Test pagination buttons with many pages."""
        buttons = pagination_service.get_pagination_buttons(
            current_page=50,
            total_pages=100,
            action_prefix="view"
        )
        
        assert len(buttons) == 2
        assert buttons[0].action == "view_page_49"
        assert buttons[1].action == "view_page_51"
