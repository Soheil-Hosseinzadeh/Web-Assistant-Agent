from playwright.sync_api import sync_playwright
from smolagents import ActionStep, tool
from urllib.parse import quote_plus
from PIL import Image
from io import BytesIO


playwright = None
browser = None
context = None
page = None
pending_screenshots = []
ctr = 1


def _require_page():
    if browser is None or not browser.is_connected() or page is None:
        raise RuntimeError("Browser is not open. Call start_browser first.")
    return page


def _stop_browser() -> None:
    global playwright, browser, context, page

    if playwright is None and browser is None:
        return

    try:
        if browser is not None:
            browser.close()
    finally:
        try:
            if playwright is not None:
                playwright.stop()
        finally:
            playwright = None
            browser = None
            context = None
            page = None
            pending_screenshots.clear()


@tool
def start_browser() -> str:
    """Launch Chromium and create a browser context and page.

    Call this before using other browser tools.
    """
    global playwright, browser, context, page

    if browser is not None and browser.is_connected():
        return "Browser is already open."

    _stop_browser()
    new_playwright = sync_playwright().start()
    new_browser = None

    try:
        new_browser = new_playwright.chromium.launch(headless=False)
        new_context = new_browser.new_context()
        new_page = new_context.new_page()
        new_page.set_default_timeout(15000)
    except Exception:
        try:
            if new_browser is not None:
                new_browser.close()
        finally:
            new_playwright.stop()
        raise

    playwright = new_playwright
    browser = new_browser
    context = new_context
    page = new_page
    return "Chromium browser opened successfully."


@tool
def stop_browser() -> str:
    """Close the Chromium browser and stop its Playwright process."""
    if playwright is None and browser is None:
        return "Browser is not open."

    _stop_browser()
    return "Chromium browser closed successfully."


@tool
def search_web(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo and return search results.
    Call start_browser first; this tool does not launch the browser.

    Args:
        query: The search query.
        max_results: Maximum number of search results to return.

    Returns:
        Search result titles, URLs, and descriptions.
    """

    current_page = _require_page()
    current_page.goto(
        f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
        wait_until="domcontentloaded",
    )

    results = current_page.locator(".result").all()
    output = []

    for result in results[:max_results]:
        title = result.locator(".result__title").inner_text()
        url = result.locator(".result__url").get_attribute("href")
        snippet = result.locator(".result__snippet").inner_text()

        output.append(f"Title: {title}\nURL: {url}\nDescription: {snippet}")

    return "\n\n".join(output) if output else "No results found."


@tool
def open_page(url: str) -> str:
    """
    Open a website in the browser.

    Args:
        url: The URL of the website to open.

    Returns:
        The page title and current URL.
    """
    if not url.startswith(("https://", "http://")):
        return "Invalid URL. Only HTTP and HTTPS URLs are allowed."

    current_page = _require_page()
    current_page.goto(url, wait_until="domcontentloaded")

    return f"Title: {current_page.title()}\nURL: {current_page.url}"


@tool
def get_page_content() -> str:
    """
    Extract the readable text content of the currently open website.

    Returns:
        The website's visible text content.
    """
    content = _require_page().locator("body").inner_text()

    # Avoid returning excessively large content to the LLM.
    return content


@tool
def mouse_move(x: int, y: int) -> str:
    """
    Move the mouse to the specified screen coordinates.

    Args:
        x: Horizontal coordinate.
        y: Vertical coordinate.

    Returns:
        a text that says: 'Mouse moved to ({x}, {y}).
    """
    _require_page().mouse.move(x, y)
    return f"Mouse moved to ({x}, {y})."


@tool
def mouse_click(x: int, y: int) -> str:
    """
    Click at the specified browser viewport coordinates.

    Args:
        x: Horizontal coordinate.
        y: Vertical coordinate.

    Returns:
        a text that says: 'Clicked at ({x}, {y}).
    """
    _require_page().mouse.click(x, y)
    return f"Clicked at ({x}, {y})."


@tool
def mouse_double_click(x: int, y: int) -> str:
    """
    Double-click at specified coordinates.

    Args:
        x: Horizontal coordinate.
        y: Vertical coordinate.

    Returns:
        a text that says Double-clicked at ({x}, {y}).
    """
    _require_page().mouse.dblclick(x, y)
    return f"Double-clicked at ({x}, {y})."


@tool
def mouse_scroll(x: int, y: int, delta_y: int) -> str:
    """
    Scroll the page at the specified coordinates.

    Args:
        x: Horizontal coordinate.
        y: Vertical coordinate.
        delta_y: Vertical scroll amount.

    Returns:
        a text that says Scrolled by {delta_y}.
    """
    _require_page().mouse.wheel(x, y, delta_y)
    return f"Scrolled by {delta_y}."


@tool
def keyboard_type(text: str) -> str:
    """
    Type the provided text using the browser keyboard.

    Args:
        text: The text to type.
    """
    _require_page().keyboard.type(text)
    return f"Typed: {text}"


@tool
def keyboard_press(key: str) -> str:
    """
    Press a keyboard key or key combination.

    Args:
        key: Key to press, such as Enter, Tab, Escape, ArrowDown,
             Control+A, or Shift+Tab.
    """
    _require_page().keyboard.press(key)
    return f"Pressed key: {key}"


@tool
def take_screenshot() -> str:
    """
    Capture the current browser page.
    The screenshot will be provided to the model as a visual observation.

    Returns:
        a text that confirms Screenshot captured.
    """

    current_page = _require_page()
    global ctr
    screenshot_bytes = current_page.screenshot(f"./images/{ctr}.jpg")
    ctr += 1

    image = Image.open(BytesIO(screenshot_bytes)).convert("RGB")

    pending_screenshots.append(image.copy())

    return f"Screenshot captured successfully. Current URL: {current_page.url}"


def attach_requested_screenshots(
    step_log: ActionStep,
) -> None:

    if not pending_screenshots:
        return

    step_log.observations_images = [
        *(step_log.observations_images or []),
        *pending_screenshots,
    ]

    pending_screenshots.clear()
