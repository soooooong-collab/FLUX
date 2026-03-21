#!/usr/bin/env python3
"""
Clean an unpacked PPTX directory by removing orphaned slides, media, and rels.

Usage:
    python scripts/clean.py unpacked/
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def _read_xml(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_xml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _get_referenced_slides(unpacked: Path) -> set[str]:
    """Get slide filenames referenced in presentation.xml's sldIdLst."""
    pres_path = unpacked / "ppt" / "presentation.xml"
    if not pres_path.exists():
        return set()

    pres = _read_xml(pres_path)

    # Find all r:id references in sldIdLst
    pres_rels_path = unpacked / "ppt" / "_rels" / "presentation.xml.rels"
    if not pres_rels_path.exists():
        return set()

    pres_rels = _read_xml(pres_rels_path)

    # Get rIds from sldIdLst
    sld_rids = set(re.findall(r'<p:sldId[^>]*r:id="(rId\d+)"', pres))

    # Map rIds to slide filenames
    referenced = set()
    for rid in sld_rids:
        match = re.search(
            rf'<Relationship Id="{rid}"[^>]*Target="slides/(slide\d+\.xml)"',
            pres_rels,
        )
        if match:
            referenced.add(match.group(1))

    return referenced


def _get_referenced_media(unpacked: Path) -> set[str]:
    """Get media filenames referenced by any slide rels."""
    media_refs = set()
    rels_dir = unpacked / "ppt" / "slides" / "_rels"
    if not rels_dir.exists():
        return media_refs

    for rels_file in rels_dir.glob("*.xml.rels"):
        content = _read_xml(rels_file)
        for match in re.finditer(r'Target="\.\./(media/[^"]+)"', content):
            media_refs.add(match.group(1))

    return media_refs


def clean(unpacked_dir: str) -> None:
    """Remove orphaned slides, media, and relationship files."""
    unpacked = Path(unpacked_dir)

    if not unpacked.exists():
        print(f"Error: {unpacked} not found", file=sys.stderr)
        sys.exit(1)

    slides_dir = unpacked / "ppt" / "slides"
    rels_dir = slides_dir / "_rels"
    media_dir = unpacked / "ppt" / "media"

    referenced_slides = _get_referenced_slides(unpacked)
    removed_count = 0

    # Remove unreferenced slides
    if slides_dir.exists():
        for slide_file in sorted(slides_dir.glob("slide*.xml")):
            if slide_file.name not in referenced_slides:
                slide_file.unlink()
                print(f"Removed slide: {slide_file.name}")
                removed_count += 1

                # Remove corresponding rels
                rels_file = rels_dir / f"{slide_file.name}.rels"
                if rels_file.exists():
                    rels_file.unlink()
                    print(f"Removed rels: {rels_file.name}")

    # Remove orphaned rels (rels for slides that don't exist)
    if rels_dir.exists():
        for rels_file in sorted(rels_dir.glob("slide*.xml.rels")):
            slide_name = rels_file.name.replace(".rels", "")
            slide_path = slides_dir / slide_name
            if not slide_path.exists():
                rels_file.unlink()
                print(f"Removed orphan rels: {rels_file.name}")
                removed_count += 1

    # Remove unreferenced media
    referenced_media = _get_referenced_media(unpacked)
    if media_dir.exists():
        for media_file in sorted(media_dir.iterdir()):
            rel_path = f"media/{media_file.name}"
            if rel_path not in referenced_media:
                media_file.unlink()
                print(f"Removed media: {media_file.name}")
                removed_count += 1

    # Clean Content_Types.xml — remove entries for deleted slides
    content_types_path = unpacked / "[Content_Types].xml"
    if content_types_path.exists():
        ct = _read_xml(content_types_path)
        original_ct = ct
        for slide_name in set(
            f.name for f in slides_dir.glob("slide*.xml")
        ) if slides_dir.exists() else set():
            pass  # Keep existing slides

        # Remove overrides for slides that no longer exist
        for match in re.finditer(
            r'<Override PartName="/ppt/slides/(slide\d+\.xml)"[^/]*/>', ct
        ):
            slide_name = match.group(1)
            if not (slides_dir / slide_name).exists():
                ct = ct.replace(match.group(0), "")
                removed_count += 1

        if ct != original_ct:
            _write_xml(content_types_path, ct)

    # Clean presentation.xml.rels — remove rels for deleted slides
    pres_rels_path = unpacked / "ppt" / "_rels" / "presentation.xml.rels"
    if pres_rels_path.exists():
        pres_rels = _read_xml(pres_rels_path)
        original_rels = pres_rels
        for match in re.finditer(
            r'<Relationship[^>]*Target="slides/(slide\d+\.xml)"[^/]*/>', pres_rels
        ):
            slide_name = match.group(1)
            if not (slides_dir / slide_name).exists():
                pres_rels = pres_rels.replace(match.group(0), "")

        if pres_rels != original_rels:
            _write_xml(pres_rels_path, pres_rels)

    if removed_count == 0:
        print("Nothing to clean.")
    else:
        print(f"\nCleaned {removed_count} orphaned items.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <unpacked_dir/>")
        sys.exit(1)
    clean(sys.argv[1])
