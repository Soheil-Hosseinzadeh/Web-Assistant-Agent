"""Visual assets for the web GUI: fonts, logo and the stylesheet."""

from pathlib import Path

CSS = (Path(__file__).parent / "theme.css").read_text(encoding="utf-8")

FONTS_HTML = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
"""

LOGO_HTML = (
    '<div class="brand-mark"><svg viewBox="0 0 64 64" aria-hidden="true">'
    '<path d="M32 5 39 23 58 32 39 41 32 59 25 41 6 32 25 23Z" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linejoin="round"/>'
    '<circle cx="32" cy="32" r="7" fill="currentColor"/>'
    '<path d="M32 1v9M63 32h-9M32 63v-9M1 32h9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'
    "</svg></div>"
)
