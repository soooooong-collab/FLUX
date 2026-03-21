#!/usr/bin/env python3
"""
Unpack a PPTX file into a directory with pretty-printed XML.

Usage:
    python scripts/office/unpack.py input.pptx output_dir/
"""
from __future__ import annotations

import os
import re
import sys
import zipfile
from pathlib import Path

from defusedxml.minidom import parseString


SMART_QUOTES = {
    "\u201c": "___LQUOT___",
    "\u201d": "___RQUOT___",
    "\u2018": "___LSQUOT___",
    "\u2019": "___RSQUOT___",
}


def _escape_smart_quotes(text: str) -> str:
    for char, placeholder in SMART_QUOTES.items():
        text = text.replace(char, placeholder)
    return text


def _pretty_print_xml(raw_bytes: bytes) -> str:
    """Parse and pretty-print XML, escaping smart quotes for safe editing."""
    try:
        text = raw_bytes.decode("utf-8")
        text = _escape_smart_quotes(text)
        dom = parseString(text.encode("utf-8"))
        pretty = dom.toprettyxml(indent="  ", encoding="UTF-8")
        result = pretty.decode("utf-8")
        # Remove extra blank lines from toprettyxml
        result = re.sub(r"\n\s*\n", "\n", result)
        return result
    except Exception:
        # If XML parsing fails, return raw text
        return raw_bytes.decode("utf-8", errors="replace")


def unpack(pptx_path: str, output_dir: str) -> None:
    """Extract PPTX and pretty-print all XML files."""
    pptx_path = Path(pptx_path)
    output_dir = Path(output_dir)

    if not pptx_path.exists():
        print(f"Error: {pptx_path} not found", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(pptx_path, "r") as zf:
        for info in zf.infolist():
            data = zf.read(info.filename)
            out_path = output_dir / info.filename

            out_path.parent.mkdir(parents=True, exist_ok=True)

            if info.filename.endswith(".xml") or info.filename.endswith(".rels"):
                content = _pretty_print_xml(data)
                out_path.write_text(content, encoding="utf-8")
            else:
                out_path.write_bytes(data)

    print(f"Unpacked {pptx_path.name} -> {output_dir}")
    # List slide files
    slides_dir = output_dir / "ppt" / "slides"
    if slides_dir.exists():
        slide_files = sorted(slides_dir.glob("slide*.xml"))
        print(f"Found {len(slide_files)} slides:")
        for sf in slide_files:
            print(f"  {sf.name}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.pptx> <output_dir/>")
        sys.exit(1)
    unpack(sys.argv[1], sys.argv[2])
