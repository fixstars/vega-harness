"""Japanese-capable fonts for the reportlab-based scripts.

reportlab's built-in fonts (Helvetica etc.) only cover Latin-1, so Japanese
text comes out as black boxes. This module registers the bundled
BIZ UDPGothic (SIL OFL 1.1, see assets/fonts/OFL.txt), which covers Latin
and Japanese, and is used for all text drawn by pdf_create.py,
pdf_make_form.py, pdf_stamp.py and the pdf_form_layout.py overlay.
reportlab embeds only the glyphs actually used, so output PDFs stay small.
"""
from __future__ import annotations

from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
REGULAR_FILE = FONT_DIR / "BIZUDPGothic-Regular.ttf"
BOLD_FILE = FONT_DIR / "BIZUDPGothic-Bold.ttf"

REGULAR = "BIZUDPGothic"
BOLD = "BIZUDPGothic-Bold"


def register() -> tuple[str, str]:
    """Register the bundled fonts with reportlab; return (regular, bold) names.

    Also maps <b>/<i> in Paragraph markup onto the family (there is no italic
    face, so italic falls back to upright).
    """
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if REGULAR not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(REGULAR, str(REGULAR_FILE)))
        pdfmetrics.registerFont(TTFont(BOLD, str(BOLD_FILE)))
        for italic in (0, 1):
            addMapping(REGULAR, 0, italic, REGULAR)
            addMapping(REGULAR, 1, italic, BOLD)
    return REGULAR, BOLD
