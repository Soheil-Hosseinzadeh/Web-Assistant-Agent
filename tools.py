from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote_plus
from io import BytesIO

from playwright.sync_api import sync_playwright
from smolagents import ActionStep, tool
from PIL import Image

# One persistent thread for ALL Playwright operations
browser_executor = ThreadPoolExecutor(max_workers=1)


def _run_browser_task(func, *args, **kwargs):
    """Run a function in the dedicated Playwright thread."""
    return browser_executor.submit(func, *args, **kwargs).result()


# Browser state (accessed only from the browser thread)
playwright = None
browser = None
context = None
page = None

pending_screenshots = []
ctr = 1


def _add_visual_cursor():
    page.evaluate("""
        () => {
            if (document.getElementById('__agent_cursor')) return;

            const cursor = document.createElement('div');
            cursor.id = '__agent_cursor';

            Object.assign(cursor.style, {
                position: 'fixed',
                width: '16px',
                height: '16px',
                background: 'red',
                border: '2px solid white',
                borderRadius: '50%',
                zIndex: '2147483647',
                pointerEvents: 'none',
                transform: 'translate(-50%, -50%)',
                left: '0px',
                top: '0px'
            });

            document.documentElement.appendChild(cursor);

            document.addEventListener('mousemove', (event) => {
                cursor.style.left = event.clientX + 'px';
                cursor.style.top = event.clientY + 'px';
            });
        }
    """)


# --------------------------------------------------
# Internal browser management functions
# --------------------------------------------------


def _stop_browser():
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


def _start_browser():
    global playwright, browser, context, page

    if browser is not None and browser.is_connected():
        return "Browser is already open."

    _stop_browser()

    new_playwright = sync_playwright().start()
    new_browser = None

    try:
        new_browser = new_playwright.chromium.launch(headless=False)

        new_context = new_browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=1,
        )
        new_page = new_context.new_page()

        new_page.set_default_timeout(60000)
        new_page.set_default_navigation_timeout(60000)

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


def _search_web(query, max_results):
    _start_browser()
    current_page = page

    current_page.goto(
        f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
        wait_until="domcontentloaded",
    )
    _add_visual_cursor()

    results = current_page.locator(".result").all()
    output = []

    for result in results[:max_results]:
        title = result.locator(".result__title").inner_text()
        url = result.locator(".result__url").get_attribute("href")
        snippet = result.locator(".result__snippet").inner_text()

        output.append(f"Title: {title}\nURL: {url}\nDescription: {snippet}")

    return "\n\n".join(output) if output else "No results found."


def _open_page(url):
    page.goto(url, wait_until="domcontentloaded", timeout=120000)
    _add_visual_cursor()

    return f"Title: {page.title()}\nURL: {page.url}"


def _get_page_raw_content():
    return page.content()

def _get_page_content():
    return page.locator("body").inner_text()

def _mouse_move(x, y):
    page.mouse.move(x, y)
    return f"Mouse moved to ({x}, {y})."


def _mouse_click(x, y):
    width = page.evaluate("window.innerWidth")
    height = page.evaluate("window.innerHeight")

    if not (0 <= x < width and 0 <= y < height):
        return (
            f"Click rejected: ({x}, {y}) is outside the viewport. "
            f"Viewport dimensions: {width}x{height}."
        )

    page.mouse.click(x, y)

    return (
        f"Click dispatched at ({x}, {y}). "
        f"Viewport: {width}x{height}."
    )


def _mouse_double_click(x, y):
    page.mouse.dblclick(x, y)
    return f"Double-clicked at ({x}, {y})."


def _mouse_scroll(x, y):
    before = page.evaluate("window.scrollY")

    page.mouse.wheel(x, y)

    page.wait_for_timeout(500)

    after = page.evaluate("window.scrollY")

    return (
        f"Scroll requested: horizontal={x}, vertical={y}\n"
        f"Previous scroll position: {before}\n"
        f"Current scroll position: {after}\n"
        f"Direction: {'down' if after > before else 'up' if after < before else 'unchanged'}"
    )


def _keyboard_type(text):
    page.keyboard.type(text)
    return f"Typed: {text}"


def _keyboard_press(key):
    page.keyboard.press(key)
    return f"Pressed key: {key}"


def _take_screenshot():
    global ctr

    Path("./images").mkdir(parents=True, exist_ok=True)

    screenshot_bytes = page.screenshot(
        path=f"./images/{ctr}.jpg",
        type="jpeg",
    )

    ctr += 1

    image = Image.open(BytesIO(screenshot_bytes)).convert("RGB")
    pending_screenshots.append(image.copy())

    viewport = page.evaluate("""
        () => ({
            width: window.innerWidth,
            height: window.innerHeight,
            devicePixelRatio: window.devicePixelRatio
        })
    """)

    return (
        f"Screenshot captured successfully.\n"
        f"Screenshot dimensions: {image.width}x{image.height}\n"
        f"Viewport dimensions: {viewport['width']}x{viewport['height']}\n"
        f"Device pixel ratio: {viewport['devicePixelRatio']}\n"
        f"Current URL: {page.url}"
    )


def _drain_pending_screenshots():
    screenshots = pending_screenshots.copy()
    pending_screenshots.clear()
    return screenshots

def _click(role, name):
    locator = page.get_by_role(role= role, name=name)
    count = locator.count()
    if count == 0:
        return f"No element found: {role} named {name}"
    if count > 1:
        return (
            f"Ambiguous target: found {count} matching elements. "
            "Inspect the page and narrow down the target."
        )
    locator.click()
    return f"Successfully clicked {role}: {name}"

def _fill_input(selector: str, value: str):
    locator = page.locator(selector)

    count = locator.count()

    if count == 0:
        return f"No input element found matching: {selector}"

    if count > 1:
        return (
            f"Ambiguous selector: found {count} elements. "
            "Please provide a more specific selector."
        )

    locator.fill(value)

    return f"Successfully filled '{selector}' with the provided value."

# --------------------------------------------------
# Browser tools
# --------------------------------------------------


@tool
def start_browser() -> str:
    """Launch Chromium and create a browser context and page."""
    return _run_browser_task(_start_browser)


@tool
def stop_browser() -> str:
    """Close Chromium and stop the Playwright process."""
    return _run_browser_task(_stop_browser) or "Chromium browser closed successfully."


@tool
def search_web(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Search query.
        max_results: Maximum number of results.
    """
    return _run_browser_task(_search_web, query, max_results)


@tool
def open_page(url: str) -> str:
    """
    Open a website in the browser.

    Args:
        url: HTTP or HTTPS URL.
    """
    if not url.startswith(("https://", "http://")):
        return "Invalid URL. Only HTTP and HTTPS URLs are allowed."

    return _run_browser_task(_open_page, url)


@tool
def get_page_raw_content() -> str:
    """
    get the whole raw HTML page as text.
    This tool is useful when you need to know more about the HTML elements in a page besides its text information.
    """
    return _run_browser_task(_get_page_raw_content)

@tool
def get_page_text_content() -> str:
    """Get readable text from the current webpage. Without HTML syntax."""
    return _run_browser_task(_get_page_content)

# Mouse tools should be used with a high quality VML model that can correctly underestand the coordinate of the elements in an image

@tool
def mouse_move(x: int, y: int) -> str:
    """
    Move the mouse to the specified screen coordinates.
    The coordinate origin begins at the top-left corner of the webpage. 
    On the horizontal axis, positive values are to the right, and negative values are to the left. 
    On the vertical axis, positive values are downward, and negative values are upward.

    Args:
        x: Horizontal coordinate relative to the main frame's viewport in CSS pixels.
        y: Vertical coordinate relative to the main frame's viewport in CSS pixels.

    Returns:
        a text that says: 'Mouse moved to ({x}, {y}).
    """
    return _run_browser_task(_mouse_move, x, y)


@tool
def mouse_click(x: int, y: int) -> str:
    """
    Click at the specified browser viewport coordinates.
    The coordinate origin begins at the top-left corner of the webpage. 
    On the horizontal axis, positive values are to the right, and negative values are to the left. 
    On the vertical axis, positive values are downward, and negative values are upward.
    
    Args:
        x: horizontal coordinate relative to the main frame's viewport in CSS pixels.
        y: vertical coordinate relative to the main frame's viewport in CSS pixels.

    Returns:
        a text that says: 'Clicked at ({x}, {y}).
    """
    return _run_browser_task(_mouse_click, x, y)


@tool
def mouse_double_click(x: int, y: int) -> str:
    """
    Double-click at specified coordinates.
    The coordinate origin begins at the top-left corner of the webpage. 
    On the horizontal axis, positive values are to the right, and negative values are to the left. 
    On the vertical axis, positive values are downward, and negative values are upward.
    
    Args:
        x: Horizontal coordinate relative to the main frame's viewport in CSS pixels.
        y: Vertical coordinate relative to the main frame's viewport in CSS pixels.

    Returns:
        a text that says Double-clicked at ({x}, {y}).
    """
    return _run_browser_task(_mouse_double_click, x, y)


@tool
def mouse_scroll(delta_x: int, delta_y: int) -> str:
    """
    Scroll the page at horizonal or vertical directions.
    
    Args:
        delta_x: horizontal scroll. Use positive value to scroll right and negative value to scorll left.
        delta_y: vertical scroll. Use positive value to scroll down and negative value to scorll up.

    Returns:
        A string like the below one:
        
        Scroll requested: horizontal={x}, vertical={y}
        Previous scroll position: {before}
        Current scroll position: {after}
        Direction: {'down' if after > before else 'up' if after < before else 'unchanged'}
    """
    return _run_browser_task(_mouse_scroll, delta_x, delta_y)


@tool
def keyboard_type(text: str) -> str:
    """
    Type the provided text using the browser keyboard.

    Args:
        text: The text to type.
    """
    return _run_browser_task(_keyboard_type, text)


@tool
def keyboard_press(key: str) -> str:
    """
    Press a keyboard key or key combination.

    Args:
        key: Key to press, such as Enter, Tab, Escape, ArrowDown,
             Control+A, or Shift+Tab.
    """
    return _run_browser_task(_keyboard_press, key)


@tool
def take_screenshot() -> str:
    """
    Capture the current page and save it as a visual observation.

    Returns:
        a text that confirms Screenshot captured.
    """
    return _run_browser_task(_take_screenshot)


@tool
def click_element(role: str, name: str) -> str:
    """
    Click a webpage element using its accessibility role and name.

    Args:
        role: The accessibility role of the target element.
              Examples: "button", "link", "textbox", "checkbox".

        name: The accessible name of the target element.
              Examples: "Sign in", "Forgot password?", "Email".

    Returns:
        A string describing the result.
    """

    try:
        return _run_browser_task(_click, role, name)
    except Exception as e:
        return f"Failed to click {role} named '{name}': {str(e)}"

@tool
def fill_input(selector: str, value: str) -> str:
    """
    Fill an input field with the provided value.

    Args:
        selector: CSS selector identifying the input element.
                  Examples:
                  - input[name="email"]
                  - input#username
                  - textarea
                  - input[placeholder="Search"]
                  - [contenteditable="true"]

        value: The text to enter into the input field.
    """

    try:
        return _run_browser_task(_fill_input, selector, value)

    except Exception as e:
        return f"Failed to fill input '{selector}': {str(e)}"

# --------------------------------------------------
# Screenshot observation management
# --------------------------------------------------


def attach_requested_screenshots(step_log: ActionStep) -> None:
    screenshots = _run_browser_task(_drain_pending_screenshots)

    if not screenshots:
        return

    step_log.observations_images = [
        *(step_log.observations_images or []),
        *screenshots,
    ]
