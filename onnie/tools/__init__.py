"""Browser tools available to the agent."""

from onnie.tools import browser
from onnie.tools.browser import attach_requested_screenshots

# Tools that work with any model.
BASE_TOOLS = [
    browser.start_browser,
    browser.stop_browser,
    browser.search_web,
    browser.open_page,
    browser.get_page_text_content,
    browser.get_page_raw_content,
    browser.click_element,
    browser.mouse_scroll,
    browser.keyboard_type,
    browser.keyboard_press,
    browser.fill_input,
    browser.take_screenshot,
]

# Coordinate-based tools: only useful with a capable vision-language model that correctly determines the coordinates of the elements.
# (enable with ENABLE_VISION_TOOLS: true in conf.yml).
VISION_TOOLS = [
    browser.mouse_move,
    browser.mouse_click,
    browser.mouse_double_click,
]


def default_tools(include_vision: bool = False) -> list:
    return [*BASE_TOOLS, *(VISION_TOOLS if include_vision else [])]


__all__ = ["attach_requested_screenshots", "default_tools", "BASE_TOOLS", "VISION_TOOLS"]
