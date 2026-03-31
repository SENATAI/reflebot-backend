"""
Property-based tests for PaginationService.

Feature: telegram-bot-full-workflow
Task: 8.2 - Property tests for PaginationService
"""

import pytest
from hypothesis import given, strategies as st, settings

from reflebot.apps.reflections.services.pagination import PaginationService
from reflebot.apps.reflections.schemas import TelegramButtonSchema


# Property 13: Pagination for Large Lists
# **Validates: Requirements 8.1, 26.1, 26.2, 26.3**


@given(
    items_count=st.integers(min_value=6, max_value=100),
    page_size=st.just(5),
    page=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=100)
def test_property_13_pagination_for_large_lists(
    items_count,
    page_size,
    page,
):
    """
    Property 13: Pagination for Large Lists
    
    For any списка с более чем 5 элементами, система должна применять 
    пагинацию и возвращать кнопки "Следующая страница" и "Предыдущая страница".
    
    **Validates: Requirements 8.1, 26.1, 26.2, 26.3**
    """
    # Arrange
    pagination_service = PaginationService()
    items = list(range(1, items_count + 1))
    
    # Act
    result = pagination_service.paginate(items, page=page, page_size=page_size)
    buttons = pagination_service.get_pagination_buttons(
        current_page=result["page"],
        total_pages=result["total_pages"],
        action_prefix="view_items"
    )
    
    # Assert - Total and pagination metadata
    assert result["total"] == items_count, \
        f"Total should be {items_count}, got {result['total']}"
    assert result["page_size"] == page_size
    
    # Calculate expected total pages
    expected_total_pages = (items_count + page_size - 1) // page_size
    assert result["total_pages"] == expected_total_pages, \
        f"Expected {expected_total_pages} pages, got {result['total_pages']}"
    
    # Assert - Items on page
    if page <= expected_total_pages:
        # Valid page
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, items_count)
        expected_items_count = end_idx - start_idx
        
        assert len(result["items"]) == expected_items_count, \
            f"Expected {expected_items_count} items on page {page}, got {len(result['items'])}"
        
        # Verify items are correct slice
        expected_items = items[start_idx:end_idx]
        assert result["items"] == expected_items, \
            f"Items should be {expected_items}, got {result['items']}"
    else:
        # Page beyond total pages - should return last page
        assert result["page"] == expected_total_pages
    
    # Assert - Pagination buttons
    if items_count > page_size:
        # Multiple pages exist
        if result["page"] == 1:
            # First page - only "Next" button
            assert len(buttons) == 1, \
                f"First page should have 1 button, got {len(buttons)}"
            assert buttons[0].text == "Следующая страница ▶️"
            assert buttons[0].action == "view_items_page_2"
        elif result["page"] == result["total_pages"]:
            # Last page - only "Previous" button
            assert len(buttons) == 1, \
                f"Last page should have 1 button, got {len(buttons)}"
            assert buttons[0].text == "◀️ Предыдущая страница"
            assert buttons[0].action == f"view_items_page_{result['page'] - 1}"
        else:
            # Middle page - both buttons
            assert len(buttons) == 2, \
                f"Middle page should have 2 buttons, got {len(buttons)}"
            assert buttons[0].text == "◀️ Предыдущая страница"
            assert buttons[0].action == f"view_items_page_{result['page'] - 1}"
            assert buttons[1].text == "Следующая страница ▶️"
            assert buttons[1].action == f"view_items_page_{result['page'] + 1}"
    else:
        # Single page - no pagination buttons
        assert len(buttons) == 0, \
            f"Single page should have 0 buttons, got {len(buttons)}"


@given(
    items_count=st.integers(min_value=0, max_value=5),
    page_size=st.just(5),
)
@settings(max_examples=100)
def test_property_13_no_pagination_for_small_lists(
    items_count,
    page_size,
):
    """
    Property 13.1: No Pagination for Small Lists
    
    For any списка с 5 или менее элементами, система НЕ должна возвращать 
    кнопки пагинации.
    
    **Validates: Requirements 26.1**
    """
    # Arrange
    pagination_service = PaginationService()
    items = list(range(1, items_count + 1))
    
    # Act
    result = pagination_service.paginate(items, page=1, page_size=page_size)
    buttons = pagination_service.get_pagination_buttons(
        current_page=result["page"],
        total_pages=result["total_pages"],
        action_prefix="view_items"
    )
    
    # Assert - All items on single page
    assert result["items"] == items, \
        f"All items should be on page 1, got {result['items']}"
    assert result["total"] == items_count
    assert result["total_pages"] == 1
    
    # Assert - No pagination buttons
    assert len(buttons) == 0, \
        f"Small list should have no pagination buttons, got {len(buttons)}"


@given(
    items_count=st.integers(min_value=1, max_value=100),
    page_size=st.integers(min_value=1, max_value=20),
    page=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=100)
def test_property_pagination_consistency(
    items_count,
    page_size,
    page,
):
    """
    Property: Pagination Consistency
    
    For any списка элементов, пагинация должна быть математически корректной:
    - total_pages = ceil(total / page_size)
    - Все элементы должны быть доступны через пагинацию
    - Элементы не должны дублироваться между страницами
    
    **Validates: Requirements 26.1, 26.2**
    """
    # Arrange
    pagination_service = PaginationService()
    items = list(range(1, items_count + 1))
    
    # Act
    result = pagination_service.paginate(items, page=page, page_size=page_size)
    
    # Assert - Total pages calculation
    expected_total_pages = (items_count + page_size - 1) // page_size if items_count > 0 else 1
    assert result["total_pages"] == expected_total_pages, \
        f"Expected {expected_total_pages} pages, got {result['total_pages']}"
    
    # Assert - Page bounds
    assert result["page"] >= 1, "Page should be at least 1"
    assert result["page"] <= result["total_pages"], \
        f"Page {result['page']} should not exceed total pages {result['total_pages']}"
    
    # Assert - Items count on page
    if result["page"] < result["total_pages"]:
        # Not last page - should have full page_size items
        assert len(result["items"]) == page_size, \
            f"Non-last page should have {page_size} items, got {len(result['items'])}"
    elif result["page"] == result["total_pages"]:
        # Last page - should have remaining items
        remaining = items_count % page_size
        expected_count = remaining if remaining > 0 else page_size
        assert len(result["items"]) == expected_count, \
            f"Last page should have {expected_count} items, got {len(result['items'])}"
    
    # Assert - Items are from original list
    for item in result["items"]:
        assert item in items, f"Item {item} should be in original list"


@given(
    items_count=st.integers(min_value=1, max_value=100),
    page_size=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=100)
def test_property_pagination_completeness(
    items_count,
    page_size,
):
    """
    Property: Pagination Completeness
    
    For any списка элементов, при последовательном переборе всех страниц 
    должны быть получены все элементы ровно один раз.
    
    **Validates: Requirements 26.1, 26.2**
    """
    # Arrange
    pagination_service = PaginationService()
    items = list(range(1, items_count + 1))
    
    # Act - Collect all items from all pages
    collected_items = []
    total_pages = (items_count + page_size - 1) // page_size if items_count > 0 else 1
    
    for page in range(1, total_pages + 1):
        result = pagination_service.paginate(items, page=page, page_size=page_size)
        collected_items.extend(result["items"])
    
    # Assert - All items collected exactly once
    assert len(collected_items) == items_count, \
        f"Should collect {items_count} items, got {len(collected_items)}"
    assert sorted(collected_items) == sorted(items), \
        "Collected items should match original items"
    
    # Assert - No duplicates
    assert len(collected_items) == len(set(collected_items)), \
        "Items should not be duplicated across pages"


@given(
    current_page=st.integers(min_value=1, max_value=100),
    total_pages=st.integers(min_value=1, max_value=100),
    action_prefix=st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        min_codepoint=97,
        max_codepoint=122,
    )),
)
@settings(max_examples=100)
def test_property_pagination_buttons_correctness(
    current_page,
    total_pages,
    action_prefix,
):
    """
    Property: Pagination Buttons Correctness
    
    For any комбинации current_page и total_pages, кнопки пагинации должны 
    быть корректными:
    - "Предыдущая" только если current_page > 1
    - "Следующая" только если current_page < total_pages
    - Actions должны указывать на правильные страницы
    
    **Validates: Requirements 26.3**
    """
    # Arrange
    pagination_service = PaginationService()
    
    # Act
    buttons = pagination_service.get_pagination_buttons(
        current_page=current_page,
        total_pages=total_pages,
        action_prefix=action_prefix
    )
    
    # Assert - Button count
    if current_page == 1 and total_pages == 1:
        # Single page - no buttons
        assert len(buttons) == 0
    elif current_page == 1:
        # First page - only "Next"
        assert len(buttons) == 1
        assert buttons[0].text == "Следующая страница ▶️"
        assert buttons[0].action == f"{action_prefix}_page_{current_page + 1}"
    elif current_page == total_pages:
        # Last page - only "Previous"
        assert len(buttons) == 1
        assert buttons[0].text == "◀️ Предыдущая страница"
        assert buttons[0].action == f"{action_prefix}_page_{current_page - 1}"
    elif current_page < total_pages:
        # Middle page - both buttons
        assert len(buttons) == 2
        assert buttons[0].text == "◀️ Предыдущая страница"
        assert buttons[0].action == f"{action_prefix}_page_{current_page - 1}"
        assert buttons[1].text == "Следующая страница ▶️"
        assert buttons[1].action == f"{action_prefix}_page_{current_page + 1}"
    
    # Assert - All buttons are TelegramButtonSchema
    for button in buttons:
        assert isinstance(button, TelegramButtonSchema)
        assert hasattr(button, "text")
        assert hasattr(button, "action")
        assert isinstance(button.text, str)
        assert isinstance(button.action, str)


@given(
    items_count=st.integers(min_value=1, max_value=100),
    page_size=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=100)
def test_property_pagination_navigation_sequence(
    items_count,
    page_size,
):
    """
    Property: Pagination Navigation Sequence
    
    For any списка элементов, последовательная навигация по кнопкам 
    "Следующая" и "Предыдущая" должна позволять перемещаться между всеми 
    страницами.
    
    **Validates: Requirements 26.3**
    """
    # Arrange
    pagination_service = PaginationService()
    items = list(range(1, items_count + 1))
    total_pages = (items_count + page_size - 1) // page_size if items_count > 0 else 1
    
    # Act & Assert - Navigate forward through all pages
    current_page = 1
    while current_page < total_pages:
        result = pagination_service.paginate(items, page=current_page, page_size=page_size)
        buttons = pagination_service.get_pagination_buttons(
            current_page=result["page"],
            total_pages=result["total_pages"],
            action_prefix="nav"
        )
        
        # Should have "Next" button
        next_button = next((btn for btn in buttons if "Следующая" in btn.text), None)
        assert next_button is not None, \
            f"Page {current_page} should have 'Next' button"
        
        # Extract next page from action
        expected_action = f"nav_page_{current_page + 1}"
        assert next_button.action == expected_action, \
            f"Next button should navigate to page {current_page + 1}"
        
        current_page += 1
    
    # Act & Assert - Navigate backward through all pages
    current_page = total_pages
    while current_page > 1:
        result = pagination_service.paginate(items, page=current_page, page_size=page_size)
        buttons = pagination_service.get_pagination_buttons(
            current_page=result["page"],
            total_pages=result["total_pages"],
            action_prefix="nav"
        )
        
        # Should have "Previous" button
        prev_button = next((btn for btn in buttons if "Предыдущая" in btn.text), None)
        assert prev_button is not None, \
            f"Page {current_page} should have 'Previous' button"
        
        # Extract previous page from action
        expected_action = f"nav_page_{current_page - 1}"
        assert prev_button.action == expected_action, \
            f"Previous button should navigate to page {current_page - 1}"
        
        current_page -= 1


# Edge cases


def test_property_pagination_empty_list():
    """
    Property Edge Case: Empty List Pagination
    
    For any пустого списка, пагинация должна возвращать корректные метаданные.
    
    **Validates: Requirements 26.1**
    """
    # Arrange
    pagination_service = PaginationService()
    items = []
    
    # Act
    result = pagination_service.paginate(items, page=1, page_size=5)
    buttons = pagination_service.get_pagination_buttons(
        current_page=result["page"],
        total_pages=result["total_pages"],
        action_prefix="view"
    )
    
    # Assert
    assert result["items"] == []
    assert result["total"] == 0
    assert result["page"] == 1
    assert result["page_size"] == 5
    assert result["total_pages"] == 1
    assert len(buttons) == 0


def test_property_pagination_single_item():
    """
    Property Edge Case: Single Item Pagination
    
    For any списка с одним элементом, пагинация должна работать корректно.
    
    **Validates: Requirements 26.1**
    """
    # Arrange
    pagination_service = PaginationService()
    items = [1]
    
    # Act
    result = pagination_service.paginate(items, page=1, page_size=5)
    buttons = pagination_service.get_pagination_buttons(
        current_page=result["page"],
        total_pages=result["total_pages"],
        action_prefix="view"
    )
    
    # Assert
    assert result["items"] == [1]
    assert result["total"] == 1
    assert result["page"] == 1
    assert result["total_pages"] == 1
    assert len(buttons) == 0


def test_property_pagination_exact_page_size():
    """
    Property Edge Case: Exact Page Size
    
    For any списка, размер которого кратен page_size, последняя страница 
    должна быть полной.
    
    **Validates: Requirements 26.1, 26.2**
    """
    # Arrange
    pagination_service = PaginationService()
    page_size = 5
    items = list(range(1, page_size * 3 + 1))  # Exactly 3 full pages
    
    # Act - Get last page
    result = pagination_service.paginate(items, page=3, page_size=page_size)
    
    # Assert - Last page is full
    assert len(result["items"]) == page_size
    assert result["items"] == [11, 12, 13, 14, 15]
    assert result["total_pages"] == 3
