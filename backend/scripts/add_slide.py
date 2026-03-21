#!/usr/bin/env python3
"""
Duplicate a slide in an unpacked PPTX directory.

Usage:
    python scripts/add_slide.py unpacked/ slide5.xml

Duplicates the specified slide (with all its relationships and media),
and prints the <p:sldId> entry to add to presentation.xml.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

from defusedxml.minidom import parseString


def _read_xml(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_xml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _next_slide_number(slides_dir: Path) -> int:
    """Find the next available slide number."""
    existing = [
        int(re.search(r"slide(\d+)\.xml", f.name).group(1))
        for f in slides_dir.glob("slide*.xml")
        if re.search(r"slide(\d+)\.xml", f.name)
    ]
    return max(existing) + 1 if existing else 1


def _next_rid(rels_content: str) -> str:
    """Find the next available rId in a .rels file."""
    rids = [int(m) for m in re.findall(r'Id="rId(\d+)"', rels_content)]
    next_num = max(rids) + 1 if rids else 1
    return f"rId{next_num}"


def _next_slide_id(pres_content: str) -> int:
    """Find the next available slide id in presentation.xml."""
    ids = [int(m) for m in re.findall(r'id="(\d+)"', pres_content)]
    return max(ids) + 1 if ids else 256


def add_slide(unpacked_dir: str, source_slide: str) -> str:
    """
    Duplicate a slide and return the new slide filename.

    Returns the new slide filename (e.g., 'slide36.xml').
    """
    unpacked = Path(unpacked_dir)
    slides_dir = unpacked / "ppt" / "slides"
    rels_dir = slides_dir / "_rels"

    # Validate source
    source_path = slides_dir / source_slide
    if not source_path.exists():
        print(f"Error: {source_path} not found", file=sys.stderr)
        sys.exit(1)

    # Determine new slide number
    new_num = _next_slide_number(slides_dir)
    new_slide_name = f"slide{new_num}.xml"
    new_slide_path = slides_dir / new_slide_name

    # Copy slide XML
    shutil.copy2(source_path, new_slide_path)

    # Copy slide rels if exists
    source_rels = rels_dir / f"{source_slide}.rels"
    new_rels = rels_dir / f"{new_slide_name}.rels"
    if source_rels.exists():
        shutil.copy2(source_rels, new_rels)

    # Copy notes if exists
    notes_dir = unpacked / "ppt" / "notesSlides"
    source_num = re.search(r"slide(\d+)\.xml", source_slide)
    if source_num and notes_dir.exists():
        src_num = source_num.group(1)
        source_notes = notes_dir / f"notesSlide{src_num}.xml"
        if source_notes.exists():
            new_notes = notes_dir / f"notesSlide{new_num}.xml"
            shutil.copy2(source_notes, new_notes)

    # Update Content_Types.xml
    content_types_path = unpacked / "[Content_Types].xml"
    if content_types_path.exists():
        ct = _read_xml(content_types_path)
        # Add override for new slide if not present
        new_override = f'<Override PartName="/ppt/slides/{new_slide_name}" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        if f"/ppt/slides/{new_slide_name}" not in ct:
            ct = ct.replace("</Types>", f"  {new_override}\n</Types>")
            _write_xml(content_types_path, ct)

    # Add relationship in presentation.xml.rels
    pres_rels_path = unpacked / "ppt" / "_rels" / "presentation.xml.rels"
    if pres_rels_path.exists():
        pres_rels = _read_xml(pres_rels_path)
        new_rid = _next_rid(pres_rels)
        new_rel = f'<Relationship Id="{new_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/{new_slide_name}"/>'
        pres_rels = pres_rels.replace("</Relationships>", f"  {new_rel}\n</Relationships>")
        _write_xml(pres_rels_path, pres_rels)
    else:
        new_rid = "rId1"

    # Generate sldId entry for presentation.xml
    pres_path = unpacked / "ppt" / "presentation.xml"
    if pres_path.exists():
        pres = _read_xml(pres_path)
        new_id = _next_slide_id(pres)
    else:
        new_id = 256

    sld_id_entry = f'<p:sldId id="{new_id}" r:id="{new_rid}"/>'

    print(f"Created: {new_slide_name}")
    print(f"Add to <p:sldIdLst> in presentation.xml:")
    print(f"  {sld_id_entry}")

    return new_slide_name


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <unpacked_dir/> <slideN.xml>")
        sys.exit(1)
    add_slide(sys.argv[1], sys.argv[2])
