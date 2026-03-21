#!/usr/bin/env python3
"""
Pack an unpacked PPTX directory back into a .pptx file.

Usage:
    python scripts/office/pack.py unpacked_dir/ output.pptx [--original input.pptx]
"""
from __future__ import annotations

import os
import re
import sys
import zipfile
from pathlib import Path

SMART_QUOTES_RESTORE = {
    "___LQUOT___": "\u201c",
    "___RQUOT___": "\u201d",
    "___LSQUOT___": "\u2018",
    "___RSQUOT___": "\u2019",
}


def _restore_smart_quotes(text: str) -> str:
    for placeholder, char in SMART_QUOTES_RESTORE.items():
        text = text.replace(placeholder, char)
    return text


def _condense_xml(text: str) -> str:
    """Remove pretty-print whitespace to condense XML back."""
    # Remove the XML declaration added by toprettyxml (we'll use the original)
    text = re.sub(r'<\?xml[^?]*\?>\s*', '', text, count=1)
    # Remove indentation whitespace between tags
    text = re.sub(r'>\s+<', '><', text)
    # Restore smart quotes
    text = _restore_smart_quotes(text)
    # Add XML declaration back
    text = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + text.strip()
    return text


def pack(input_dir: str, output_path: str, original_path: str | None = None) -> None:
    """Pack directory back into PPTX."""
    input_dir = Path(input_dir)
    output_path = Path(output_path)

    if not input_dir.exists():
        print(f"Error: {input_dir} not found", file=sys.stderr)
        sys.exit(1)

    # Collect all files
    all_files = []
    for root, dirs, files in os.walk(input_dir):
        for fname in files:
            full_path = Path(root) / fname
            rel_path = full_path.relative_to(input_dir)
            all_files.append((str(rel_path), full_path))

    # If original provided, use its compression settings
    compression = zipfile.ZIP_DEFLATED

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", compression=compression) as zf:
        for rel_path, full_path in sorted(all_files):
            if full_path.suffix in (".xml", ".rels"):
                content = full_path.read_text(encoding="utf-8")
                content = _condense_xml(content)
                zf.writestr(rel_path, content.encode("utf-8"))
            else:
                zf.write(full_path, rel_path)

    print(f"Packed {input_dir} -> {output_path}")
    print(f"Size: {output_path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <unpacked_dir/> <output.pptx> [--original input.pptx]")
        sys.exit(1)

    input_dir = sys.argv[1]
    output_path = sys.argv[2]
    original = None
    if "--original" in sys.argv:
        idx = sys.argv.index("--original")
        if idx + 1 < len(sys.argv):
            original = sys.argv[idx + 1]

    pack(input_dir, output_path, original)
