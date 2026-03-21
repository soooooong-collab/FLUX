"""
Slide Injector — Inject content into template slide XML while preserving formatting.

Strategy:
- Parse slide XML with xml.etree.ElementTree (namespace-aware)
- Find text shapes (<p:sp> with <p:txBody>)
- Replace <a:t> text content while preserving all <a:rPr> formatting
- Support **highlight** markers: text in ** gets the accent color, rest keeps primary color
"""
from __future__ import annotations

import re
import logging
from pathlib import Path
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# OpenXML namespaces
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

# Register namespaces so ET preserves them on write
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)
# Additional namespaces found in template
ET.register_namespace("p14", "http://schemas.microsoft.com/office/powerpoint/2010/main")
ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")
ET.register_namespace("a14", "http://schemas.microsoft.com/office/drawing/2010/main")


def _read_xml(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_xml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _get_text_shapes(tree: ET.Element) -> list[ET.Element]:
    """Get all <p:sp> elements that contain <p:txBody>."""
    shapes = []
    for sp in tree.iter(f"{{{NS['p']}}}sp"):
        txBody = sp.find(f"{{{NS['p']}}}txBody")
        if txBody is not None:
            shapes.append(sp)
    return shapes


def _get_paragraphs(txBody: ET.Element) -> list[ET.Element]:
    """Get all <a:p> elements from a txBody."""
    return txBody.findall(f"{{{NS['a']}}}p")


def _get_runs(paragraph: ET.Element) -> list[ET.Element]:
    """Get all <a:r> elements from a paragraph."""
    return paragraph.findall(f"{{{NS['a']}}}r")


def _get_run_text(run: ET.Element) -> str:
    """Get text from an <a:r> element."""
    t = run.find(f"{{{NS['a']}}}t")
    return t.text if t is not None and t.text else ""


def _set_run_text(run: ET.Element, text: str) -> None:
    """Set text on an <a:r> element."""
    t = run.find(f"{{{NS['a']}}}t")
    if t is not None:
        t.text = text


def _clone_run(run: ET.Element) -> ET.Element:
    """Deep-clone an <a:r> element."""
    import copy
    return copy.deepcopy(run)


def _extract_colors_from_shape(txBody: ET.Element) -> tuple[str | None, str | None]:
    """Extract primary and accent colors from existing runs.

    Returns (primary_color_xml, accent_color_xml) as serialized XML strings
    of the <a:solidFill> elements. Primary = most common, accent = different one.
    """
    color_counts: dict[str, tuple[int, ET.Element]] = {}

    for run in txBody.iter(f"{{{NS['a']}}}r"):
        rPr = run.find(f"{{{NS['a']}}}rPr")
        if rPr is None:
            continue
        fill = rPr.find(f"{{{NS['a']}}}solidFill")
        if fill is None:
            continue

        # Serialize for comparison
        fill_str = ET.tostring(fill, encoding="unicode")
        if fill_str not in color_counts:
            color_counts[fill_str] = (0, fill)
        count, elem = color_counts[fill_str]
        color_counts[fill_str] = (count + 1, elem)

    if not color_counts:
        return None, None

    sorted_colors = sorted(color_counts.items(), key=lambda x: -x[1][0])
    primary = sorted_colors[0][1][1]
    accent = sorted_colors[1][1][1] if len(sorted_colors) > 1 else None

    return primary, accent


def _parse_highlight_text(text: str) -> list[tuple[str, bool]]:
    """Parse text with **highlight** markers into segments.

    Returns list of (text, is_highlighted) tuples.
    """
    if "**" not in text:
        return [(text, False)]

    segments = []
    parts = re.split(r"\*\*", text)
    for i, part in enumerate(parts):
        if part:
            segments.append((part, i % 2 == 1))
    return segments


def _rebuild_paragraph_with_highlights(
    paragraph: ET.Element,
    text: str,
    template_run: ET.Element,
    primary_fill: ET.Element | None,
    accent_fill: ET.Element | None,
) -> None:
    """Replace paragraph content with highlighted text, preserving formatting.

    Removes existing runs, creates new runs based on highlight markers.
    """
    import copy

    # Remove existing runs
    runs_to_remove = paragraph.findall(f"{{{NS['a']}}}r")
    for run in runs_to_remove:
        paragraph.remove(run)

    # Parse highlights
    segments = _parse_highlight_text(text)

    # Find insertion point (after <a:pPr> if it exists)
    pPr = paragraph.find(f"{{{NS['a']}}}pPr")
    insert_idx = 0
    if pPr is not None:
        insert_idx = list(paragraph).index(pPr) + 1

    for seg_text, is_highlight in segments:
        new_run = copy.deepcopy(template_run)
        _set_run_text(new_run, seg_text)

        # Set color
        rPr = new_run.find(f"{{{NS['a']}}}rPr")
        if rPr is not None:
            old_fill = rPr.find(f"{{{NS['a']}}}solidFill")
            if old_fill is not None:
                rPr.remove(old_fill)

            fill_to_use = accent_fill if (is_highlight and accent_fill is not None) else primary_fill
            if fill_to_use is not None:
                rPr.insert(0, copy.deepcopy(fill_to_use))

        paragraph.insert(insert_idx, new_run)
        insert_idx += 1


def _simple_text_replace(txBody: ET.Element, lines: list[str]) -> None:
    """Simple text replacement: put each line into corresponding paragraph.

    If fewer lines than paragraphs, empty the extra paragraphs.
    If more lines than paragraphs, concatenate extras into last paragraph.
    Supports **highlight** markers.
    """
    paragraphs = _get_paragraphs(txBody)
    if not paragraphs:
        return

    # Extract template formatting from first run of first paragraph
    first_para = paragraphs[0]
    first_runs = _get_runs(first_para)
    if not first_runs:
        return

    template_run = first_runs[0]
    primary_fill, accent_fill = _extract_colors_from_shape(txBody)

    for i, para in enumerate(paragraphs):
        if i < len(lines):
            text = lines[i]
        elif i >= len(lines):
            text = ""
        else:
            text = ""

        # For last paragraph, join any remaining lines
        if i == len(paragraphs) - 1 and i < len(lines) - 1:
            text = "\n".join(lines[i:])

        # Get template run from this paragraph if available
        para_runs = _get_runs(para)
        para_template = para_runs[0] if para_runs else template_run

        _rebuild_paragraph_with_highlights(para, text, para_template, primary_fill, accent_fill)


# ──────────────────────────────────────────────
# Pattern-specific injectors
# ──────────────────────────────────────────────

def inject_cover(slide_path: Path, content: dict) -> None:
    """Cover slide: 1 shape, 2 paragraphs (brand name, campaign title)."""
    tree = ET.parse(slide_path)
    root = tree.getroot()
    shapes = _get_text_shapes(root)
    if not shapes:
        return

    txBody = shapes[0].find(f"{{{NS['p']}}}txBody")
    lines = [
        content.get("title", ""),
        content.get("subtitle", ""),
    ]
    _simple_text_replace(txBody, [l for l in lines if l] or [""])
    tree.write(slide_path, encoding="unicode", xml_declaration=True)


def inject_statement(slide_path: Path, content: dict) -> None:
    """Statement slide: 1 shape with impact text. Supports highlights."""
    tree = ET.parse(slide_path)
    root = tree.getroot()
    shapes = _get_text_shapes(root)
    if not shapes:
        return

    txBody = shapes[0].find(f"{{{NS['p']}}}txBody")
    text = content.get("title", "") or content.get("body", "")
    lines = text.split("\n") if "\n" in text else [text]
    _simple_text_replace(txBody, lines)
    tree.write(slide_path, encoding="unicode", xml_declaration=True)


def inject_title_body(slide_path: Path, content: dict) -> None:
    """Title+body slide: shape 0 = title, shape 1 = body."""
    tree = ET.parse(slide_path)
    root = tree.getroot()
    shapes = _get_text_shapes(root)

    if len(shapes) >= 2:
        # Title shape
        title_body = shapes[0].find(f"{{{NS['p']}}}txBody")
        _simple_text_replace(title_body, [content.get("title", "")])

        # Body shape
        body_txBody = shapes[1].find(f"{{{NS['p']}}}txBody")
        body_text = content.get("body", "")
        body_lines = body_text.split("\n") if "\n" in body_text else [body_text]
        _simple_text_replace(body_txBody, body_lines)
    elif shapes:
        # Single shape fallback
        txBody = shapes[0].find(f"{{{NS['p']}}}txBody")
        title = content.get("title", "")
        body = content.get("body", "")
        lines = [title]
        if body:
            lines.extend(body.split("\n") if "\n" in body else [body])
        _simple_text_replace(txBody, lines)

    tree.write(slide_path, encoding="unicode", xml_declaration=True)


def inject_quote(slide_path: Path, content: dict) -> None:
    """Quote slide: may have image + text shape. Find the text shape and inject."""
    tree = ET.parse(slide_path)
    root = tree.getroot()
    shapes = _get_text_shapes(root)
    if not shapes:
        return

    # Use the last text shape (in quote slides, image comes first)
    txBody = shapes[-1].find(f"{{{NS['p']}}}txBody")
    quote_text = content.get("quote", "") or content.get("body", "")
    lines = quote_text.split("\n") if "\n" in quote_text else [quote_text]
    _simple_text_replace(txBody, lines)
    tree.write(slide_path, encoding="unicode", xml_declaration=True)


def inject_narrative(slide_path: Path, content: dict) -> None:
    """Narrative slide: 1 shape, multiple paragraphs of poetic text."""
    tree = ET.parse(slide_path)
    root = tree.getroot()
    shapes = _get_text_shapes(root)
    if not shapes:
        return

    txBody = shapes[0].find(f"{{{NS['p']}}}txBody")
    body = content.get("body", "") or content.get("title", "")
    lines = body.split("\n") if "\n" in body else [body]
    _simple_text_replace(txBody, lines)
    tree.write(slide_path, encoding="unicode", xml_declaration=True)


def inject_reveal(slide_path: Path, content: dict) -> None:
    """Reveal slide: 1 main shape with large concept word."""
    tree = ET.parse(slide_path)
    root = tree.getroot()
    shapes = _get_text_shapes(root)
    if not shapes:
        return

    # First shape is the main concept text
    txBody = shapes[0].find(f"{{{NS['p']}}}txBody")
    concept = content.get("concept_word", "") or content.get("title", "")
    _simple_text_replace(txBody, [concept])
    tree.write(slide_path, encoding="unicode", xml_declaration=True)


def inject_reveal_kr(slide_path: Path, content: dict) -> None:
    """Korean reveal slide: first shape = main text, others are decorative."""
    tree = ET.parse(slide_path)
    root = tree.getroot()
    shapes = _get_text_shapes(root)
    if not shapes:
        return

    # Only inject into first shape (main concept text)
    txBody = shapes[0].find(f"{{{NS['p']}}}txBody")
    concept = content.get("concept_word", "") or content.get("title", "")
    _simple_text_replace(txBody, [concept])
    tree.write(slide_path, encoding="unicode", xml_declaration=True)


def inject_comparison(slide_path: Path, content: dict) -> None:
    """Comparison/diagram slide: multiple shapes with labels.

    For comparison patterns, we inject title into first text shape
    and leave structural elements intact (they're positional).
    """
    tree = ET.parse(slide_path)
    root = tree.getroot()
    shapes = _get_text_shapes(root)

    if not shapes:
        return

    # Inject title into first shape
    txBody = shapes[0].find(f"{{{NS['p']}}}txBody")
    title = content.get("title", "")
    body = content.get("body", "")

    if title:
        _simple_text_replace(txBody, [title])

    # If there are comparison items, try to inject into remaining shapes
    compare = content.get("compare", {})
    if isinstance(compare, dict) and shapes:
        before = compare.get("before", [])
        after = compare.get("after", [])
        all_items = before + after

        # Inject into subsequent shapes (skip first = title)
        for i, shape in enumerate(shapes[1:], 1):
            if i - 1 < len(all_items):
                shape_txBody = shape.find(f"{{{NS['p']}}}txBody")
                _simple_text_replace(shape_txBody, [all_items[i - 1]])

    tree.write(slide_path, encoding="unicode", xml_declaration=True)


def inject_diagram(slide_path: Path, content: dict) -> None:
    """Diagram slide: multiple shapes forming a flow diagram.

    Inject title into first shape, flow items into subsequent shapes.
    """
    tree = ET.parse(slide_path)
    root = tree.getroot()
    shapes = _get_text_shapes(root)

    if not shapes:
        return

    # Inject title into first shape
    txBody = shapes[0].find(f"{{{NS['p']}}}txBody")
    title = content.get("title", "")
    if title:
        _simple_text_replace(txBody, [title])

    # Inject flow items into subsequent shapes
    flow_items = content.get("flow_items", [])
    if flow_items:
        for i, shape in enumerate(shapes[1:], 0):
            if i < len(flow_items):
                shape_txBody = shape.find(f"{{{NS['p']}}}txBody")
                _simple_text_replace(shape_txBody, [flow_items[i]])

    tree.write(slide_path, encoding="unicode", xml_declaration=True)


# ──────────────────────────────────────────────
# Main dispatch
# ──────────────────────────────────────────────

_PATTERN_INJECTORS = {
    "cover": inject_cover,
    "statement": inject_statement,
    "title_body": inject_title_body,
    "quote": inject_quote,
    "narrative": inject_narrative,
    "reveal": inject_reveal,
    "reveal_kr": inject_reveal_kr,
    "comparison": inject_comparison,
    "diagram": inject_diagram,
}


def inject_content(slide_path: str | Path, pattern: str, content: dict) -> None:
    """Inject content into a template slide XML based on the pattern type.

    Args:
        slide_path: Path to the slide XML file
        pattern: Slide pattern name (cover, statement, title_body, etc.)
        content: Dict with keys like title, body, concept_word, etc.
    """
    slide_path = Path(slide_path)
    if not slide_path.exists():
        logger.warning("Slide XML not found: %s", slide_path)
        return

    injector = _PATTERN_INJECTORS.get(pattern)
    if injector is None:
        logger.warning("Unknown pattern '%s', falling back to statement", pattern)
        injector = inject_statement

    try:
        injector(slide_path, content)
        logger.info("Injected content into %s (pattern=%s)", slide_path.name, pattern)
    except Exception:
        logger.exception("Failed to inject content into %s", slide_path.name)
