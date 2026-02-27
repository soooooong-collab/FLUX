"""
PPTX Export — Generate PowerPoint presentations from slide data.
"""
from __future__ import annotations

import io

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN


def generate_pptx(brand_name: str, slides: list[dict]) -> bytes:
    """Generate a PPTX file from slide data. Returns bytes."""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # Color scheme
    bg_dark = RGBColor(0x1A, 0x1A, 0x2E)
    accent = RGBColor(0xFF, 0x6B, 0x35)
    text_white = RGBColor(0xFF, 0xFF, 0xFF)
    text_gray = RGBColor(0xCC, 0xCC, 0xCC)

    for slide_data in slides:
        layout = slide_data.get("layout", "title_content")
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout

        # Set dark background
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = bg_dark

        title = slide_data.get("title", "")
        subtitle = slide_data.get("subtitle", "")
        body = slide_data.get("body", "")
        key_points = slide_data.get("key_points", "")
        phase = slide_data.get("phase", "")

        # Phase label (top-left)
        if phase:
            phase_label = _add_textbox(slide, Inches(0.5), Inches(0.3), Inches(2), Inches(0.4))
            _set_text(phase_label, phase.upper(), size=Pt(10), color=accent, bold=True)

        # Title
        title_box = _add_textbox(slide, Inches(0.5), Inches(0.8), Inches(12), Inches(1))
        _set_text(title_box, title, size=Pt(32), color=text_white, bold=True)

        # Subtitle
        if subtitle:
            sub_box = _add_textbox(slide, Inches(0.5), Inches(1.8), Inches(12), Inches(0.6))
            _set_text(sub_box, subtitle, size=Pt(16), color=accent)

        # Body content
        if body:
            body_top = Inches(2.6) if subtitle else Inches(2.0)
            body_box = _add_textbox(slide, Inches(0.5), body_top, Inches(12), Inches(4))
            _set_text(body_box, body[:2000], size=Pt(14), color=text_gray)

        # Key points
        if key_points:
            kp_box = _add_textbox(slide, Inches(0.5), Inches(6.0), Inches(12), Inches(1))
            _set_text(kp_box, key_points, size=Pt(12), color=text_white)

    # Save to bytes
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()


def _add_textbox(slide, left, top, width, height):
    return slide.shapes.add_textbox(left, top, width, height)


def _set_text(textbox, text, size=Pt(14), color=None, bold=False):
    tf = textbox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = size
    p.font.bold = bold
    if color:
        p.font.color.rgb = color
