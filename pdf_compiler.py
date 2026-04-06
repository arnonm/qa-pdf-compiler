#!/usr/bin/env python3
"""
QA PDF Compiler: Merges PDFs with a template and TOC.
Accepts PDFs with Document Version, Document Number, and Document Language (ISO 639) in the header.
Names in TOC are shown without the .pdf extension; language column shows full English name.

Usage:
    python pdf_compiler.py [--directory path] [--version X.X] [--template path] [--output path]
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Literal

from pypdf import PdfWriter, PdfReader
from pypdf.constants import PagesAttributes
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, RectangleObject
from markdown import markdown
from weasyprint import HTML, CSS

from iso639_names import language_code_to_full_name

# TOC table layout for link rects (PDF points: 72 pt = 1 inch, origin bottom-left)
# Approximate: body margin 2em ~ 48pt, h1 + margin ~ 80pt, row height ~ 24pt
# Rects span full body width so clicking anywhere on the row activates the link
TOC_TABLE_TOP = 660
TOC_ROW_HEIGHT = 24
TOC_LEFT = 72  # 1 inch margin
TOC_RIGHT = 72 * 7.5  # ~7.5 inch (A4 width 595pt - margin)
LETTER_W, LETTER_H = 612, 792
A4_W, A4_H = 595.28, 841.89
TOL = 2.0  # points


# Header patterns on each page
DOC_VERSION_RE = re.compile(r"Document Version:\s+(\d+(?:\.\d+)*)", re.IGNORECASE)
DOC_NUMBER_RE = re.compile(r"Document Number:\s+(IFU-[A-Z0-9-]+)", re.IGNORECASE)
# ISO 639-1 (2 letters) or common ISO 639-2 (3 letters)
DOC_LANGUAGE_RE = re.compile(r"Document Language:\s+([a-zA-Z]{2,3})\b", re.IGNORECASE)


def page_size_label(page) -> str:
    mb = page.mediabox
    w, h = float(mb.width), float(mb.height)
    # Normalize orientation: treat "tall" vs "wide" consistently
    a, b = sorted((w, h))
    def near(want_w, want_h):
        return abs(a - min(want_w, want_h)) < TOL and abs(b - max(want_w, want_h)) < TOL
    if near(LETTER_W, LETTER_H):
        return "Letter"
    if near(A4_W, A4_H):
        return "A4"
    return f"{w:.1f}×{h:.1f} pt"


def _normalized_mediabox_dims_pt(page) -> tuple[float, float]:
    """Return (shorter_side, longer_side) in points for orientation-independent comparison."""
    mb = page.mediabox
    w, h = float(mb.width), float(mb.height)
    a, b = sorted((w, h))
    return (a, b)


def _paper_kind_from_normalized_dims(
    dims: tuple[float, float], *, tolerance: float = TOL
) -> Literal["letter", "a4"] | None:
    """Return ``letter`` or ``a4`` if normalized dims match a standard size, else ``None``."""
    a, b = dims

    def near(want_w: float, want_h: float) -> bool:
        return (
            abs(a - min(want_w, want_h)) < tolerance
            and abs(b - max(want_w, want_h)) < tolerance
        )

    if near(LETTER_W, LETTER_H):
        return "letter"
    if near(A4_W, A4_H):
        return "a4"
    return None


def verify_uniform_page_size(
    paths: list[Path], *, tolerance: float = TOL
) -> Literal["letter", "a4"]:
    """Check that every page in every PDF uses the same Letter or A4 MediaBox size.

    Compares dimensions in points with orientation normalized (portrait vs landscape
    does not matter: 612×792 matches 792×612).

    Returns:
        The string ``"letter"`` or ``"a4"`` for the uniform page size.

    Raises:
        ValueError: If ``paths`` is empty, any page differs from the reference,
            or the uniform size is not Letter or A4 within ``tolerance``.
    """
    if not paths:
        raise ValueError("No PDF paths to check.")
    ref_dims: tuple[float, float] | None = None
    ref_desc: str = ""
    for path in paths:
        reader = PdfReader(path)
        if len(reader.pages) == 0:
            raise ValueError(f"{path.name} has no pages.")
        for i, page in enumerate(reader.pages):
            dims = _normalized_mediabox_dims_pt(page)
            if ref_dims is None:
                ref_dims = dims
                ref_desc = f"{page_size_label(page)} ({dims[0]:.1f}×{dims[1]:.1f} pt, from {path.name} page 1)"
                continue
            if (
                abs(dims[0] - ref_dims[0]) > tolerance
                or abs(dims[1] - ref_dims[1]) > tolerance
            ):
                w, h = float(page.mediabox.width), float(page.mediabox.height)
                got = f"{page_size_label(page)} ({w:.1f}×{h:.1f} pt)"
                raise ValueError(
                    f"Page size mismatch in {path.name} page {i + 1}: {got}. "
                    f"Expected {ref_desc}."
                )
    assert ref_dims is not None
    kind = _paper_kind_from_normalized_dims(ref_dims, tolerance=tolerance)
    if kind is None:
        raise ValueError(
            f"All pages share the same size ({ref_dims[0]:.1f}×{ref_dims[1]:.1f} pt), "
            "but it is not Letter or A4 within tolerance."
        )
    return kind


def extract_version_from_pdf(path: Path) -> str | None:
    """Extract document version from PDF page headers ('Document Version: XX.XX')."""
    reader = PdfReader(path)
    for page in reader.pages:
        text = page.extract_text() or ""
        m = DOC_VERSION_RE.search(text)
        if m:
            return m.group(1)
    return None


def extract_doc_number_from_pdf(path: Path) -> str | None:
    """Extract document number from PDF page headers ('Document Number: IFU-XXXXXXX')."""
    reader = PdfReader(path)
    for page in reader.pages:
        text = page.extract_text() or ""
        m = DOC_NUMBER_RE.search(text)
        if m:
            return m.group(1)
    return None


def extract_document_language_from_pdf(path: Path) -> str | None:
    """Extract ISO 639 language code from PDF headers ('Document Language: XX')."""
    reader = PdfReader(path)
    for page in reader.pages:
        text = page.extract_text() or ""
        m = DOC_LANGUAGE_RE.search(text)
        if m:
            return m.group(1).lower()
    return None


def scan_pdfs(directory: Path) -> list[tuple[Path, str, str, str]]:
    """Scan directory for PDFs; return (path, version, lang_code, doc_number). Language from header.
    Ignore documents starting with an underscore. 
    Ignore documents with no Document Language in the header. 
    Language code is ISO 639-1 (2 letters) or common ISO 639-2 (3 letters).
    Ignore documents with no Document Version in the header.
    Ignore documents with no Document Number in the header.
    """
    results = []
    for path in sorted(directory.glob("*.pdf")):
        if path.name.startswith("_"):
            continue
        version = extract_version_from_pdf(path)
        if version is None:
            print(f"Warning: Skipping {path.name} (no 'Document Version: XX.XX' in header)", file=sys.stderr)
            continue
        doc_number = extract_doc_number_from_pdf(path)
        if doc_number is None:
            print(f"Warning: Skipping {path.name} (no 'Document Number: IFU-XXXXXXX' in header)", file=sys.stderr)
            continue
        lang_code = extract_document_language_from_pdf(path)
        if lang_code is None:
            print(f"Warning: Skipping {path.name} (no 'Document Language: XX' in header)", file=sys.stderr)
            continue
        results.append((path, version, lang_code, doc_number))
    return results


def template_md_to_pdf(template_path: Path, sw_version: str, doc_version: str, ifu_version: str, doc_number: str, output_path: Path) -> None:
    """Render template Markdown to PDF with {{sw_version}} and {{doc_version}} replaced.
    Used to generate the cover page.
    """
    text = template_path.read_text(encoding="utf-8")
    text = text.replace("{{sw_version}}", sw_version)
    text = text.replace("{{doc_version}}", doc_version)
    text = text.replace("{{ifu_version}}", ifu_version)
    html_content = markdown(
        text,
        extensions=["extra", "nl2br"],
        extension_configs={"extra": {"linkify": True}},
    )
    full_html = f"""
    <!DOCTYPE html>
    <style>
        @page {{
            size: letter;
        }}
    </style>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: sans-serif; margin: 2em; line-height: 1.5; }}
            h1 {{ font-size: 1.8em; }}
        </style>
    </head>
    <body>{html_content}</body>
    </html>
    """
    HTML(string=full_html, base_url=str(template_path.parent)).write_pdf(output_path)


def toc_to_pdf(
    toc_entries: list[tuple[str, str, int]],
    toc_template_path: Path,
    sw_version: str,
    doc_version: str,
    ifu_version: str,
    doc_number: str,
    output_path: Path,
) -> None:
    """Generate a TOC PDF from ``toc.md`` (HTML + placeholders) via WeasyPrint.

    ``toc_entries``: (document_name, lang_iso_code, page_number) per row.
    Template placeholders: ``{{table_rows}}``, ``{{doc_number}}``, ``{{doc_version}}``,
    ``{{sw_version}}``, ``{{ifu_version}}``.
    """
    rows = []
    for _doc_name, lang_code, page_num in toc_entries:
        lang_display = language_code_to_full_name(lang_code)
        rows.append(
            f"<tr><td>{lang_display}</td><td class=\"page-num\"><span class=\"page-link\">{page_num}</span></td></tr>"
        )
    table_rows = "\n".join(rows)
    text = toc_template_path.read_text(encoding="utf-8")
    text = text.replace("{{table_rows}}", table_rows)
    text = text.replace("{{doc_number}}", doc_number)
    text = text.replace("{{doc_version}}", doc_version)
    text = text.replace("{{sw_version}}", sw_version)
    text = text.replace("{{ifu_version}}", ifu_version)
    HTML(string=text, base_url=str(toc_template_path.parent)).write_pdf(output_path)

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge versioned multi-language PDFs with a template and TOC."
    )
    parser.add_argument(
        "--directory", "-d",
        type=Path,
        default=Path("."),
        help="Directory containing the PDF files",
    )
    parser.add_argument(
        "--sw_version", "-sv",
        type=str,
        default=None,
        help="Software Version for template {{sw_version}} (default: empty)",
    )
    parser.add_argument(
        "--doc_version", "-dv",
        type=str,
        default=None,
        help="Document Version for template {{doc_version}} (default: empty)",
    )
    parser.add_argument(
        "--doc_number", "-dn",
        type=str,
        default=None,
        help="Document Number for template {{doc_number}} (default: empty)",
    )
    parser.add_argument(
        "--ifu_version", "-ifu",
        type=str,
        default=None,
        help="IFU Version for template {{ifu_version}} (default: empty)",
    )
    parser.add_argument(
        "--template", "-t",
        type=Path,
        default=None,
        help="Path to cover template .md file (default: template.md in script directory)",
    )
    parser.add_argument(
        "--toc",
        "-T",
        type=Path,
        default=None,
        dest="toc_template",
        help="Path to TOC template .md file (default: toc.md in script directory)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output PDF path (default: <directory>/merged_<version>.pdf)",
    )
    return parser.parse_args()

def scan_pdfs_by_filename(directory: Path) -> list[tuple[Path, str, str, str]]:
    """Scan directory for PDFs; return (path, version, lang_code, doc_number). Language from filename.
    Ignore documents starting with an underscore. 
    Ignore documents with no Document Language in the filename. 
    Language code is ISO 639-1 (2 letters) or common ISO 639-2 (3 letters).
    Ignore documents with no Document Version in the filename.
    Ignore documents with no Document Number in the filename.
    """

    results = []
    for path in sorted(directory.glob("*.pdf")):
        if path.name.startswith("_"):
            continue
        lang_code = path.stem.split(" ")[-2]
        # print(path.stem, lang_code)
        results.append((path, lang_code))
    return results

def main() -> None:
    args = parse_arguments()

    # Exit if directory is not a directory
    directory: Path = args.directory.resolve()
    if not directory.is_dir():
        print(f"Error: Not a directory: {directory}", file=sys.stderr)
        sys.exit(1)

    # Exit if template is not a file
    script_dir = Path(__file__).resolve().parent
    template_path = (args.template or script_dir / "template.md").resolve()
    if not template_path.is_file():
        print(f"Error: Template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    toc_template_path = (args.toc_template or script_dir / "toc.md").resolve()
    if not toc_template_path.is_file():
        print(f"Error: TOC template not found: {toc_template_path}", file=sys.stderr)
        sys.exit(1)

    # Scan PDFs and extract version from header, language from filename
    # Exit if no valid PDFs are found
    # Retired = scanning the pdf file name instead for the langage
    # entries = scan_pdfs(directory)
    # if not entries:
    #     print("Error: No valid PDF files found in directory.", file=sys.stderr)
    #     sys.exit(1)

    entries = scan_pdfs_by_filename(directory)
    if not entries:
        print("Error: No valid PDF files found in directory.", file=sys.stderr)
        sys.exit(1)

    try:
        input_paper_size = verify_uniform_page_size([p for p, _ in entries])
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Input PDFs: uniform {'Letter' if input_paper_size == 'letter' else 'A4'} page size."
    )

    # Version for template: CLI or first document's extracted version
    # Exit if version is not a string
    sw_version = args.sw_version if args.sw_version is not None else None
    if sw_version is None:
        print("Error: Software Version is required.", file=sys.stderr)
        sys.exit(1)

    doc_version = args.doc_version if args.doc_version is not None else None
    if doc_version is None:
        print("Error: Document Version is required.", file=sys.stderr)
        sys.exit(1)

    doc_number = args.doc_number if args.doc_number is not None else None
    if doc_number is None:
        print("Error: Document Number is required.", file=sys.stderr)
        sys.exit(1)


    ifu_version = args.ifu_version if args.ifu_version is not None else None
    if ifu_version is None:
        print("Error: IFU Version is required.", file=sys.stderr)
        sys.exit(1)
        
    output_path = args.output or directory / f"merged_{doc_version.replace('.', '_')}.pdf"
    output_path = output_path.resolve()

    # Sort by full language name for stable TOC order
    entries.sort(key=lambda x: language_code_to_full_name(x[1]).lower())

    # Page counts: cover=1, TOC=1, then each doc (1-based: page 1=cover, 2=TOC, 3=first doc)
    doc_page_counts = [len(PdfReader(p).pages) for p, _ in entries]
    start_pages_1based = []
    acc = 3  # first doc starts on page 3 (after cover and TOC)
    for n in doc_page_counts:
        start_pages_1based.append(acc)
        acc += n

    # Build TOC entries with start page numbers
    toc_entries = [
        (p.stem, lang_code, start_pages_1based[i])
        # (p.stem, doc_number, lang_code, ver, start_pages_1based[i])
        for i, (p, lang_code) in enumerate(entries)
    ]

    # Temporary files for template and TOC PDFs
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cover_pdf = tmp_path / "cover.pdf"
        toc_pdf_path = tmp_path / "toc.pdf"

        print("Generating cover from template...")
        template_md_to_pdf(template_path, sw_version, doc_version, ifu_version, doc_number, cover_pdf)

        print("Generating TOC...")
        toc_to_pdf(
            toc_entries,
            toc_template_path,
            sw_version,
            doc_version,
            ifu_version,
            doc_number,
            toc_pdf_path,
        )

        print("Merging PDFs...")
        writer = PdfWriter()

        # 1. Cover (template)
        for page in PdfReader(cover_pdf).pages:
            writer.add_page(page)

        # 2. TOC
        toc_start = len(writer.pages)
        for page in PdfReader(toc_pdf_path).pages:
            writer.add_page(page)

        # 3. Bookmark for cover and TOC
        writer.add_outline_item("Cover", 0)
        writer.add_outline_item("Table of Contents", toc_start)

        # 4. Append each document and add outline entry
        for i, (path, lang_code) in enumerate(entries):
            start = len(writer.pages)
            reader = PdfReader(path)
            for page in reader.pages:
                writer.add_page(page)
            lang_name = language_code_to_full_name(lang_code)
            title = f"{path.stem} ({lang_name})"
            writer.add_outline_item(title, start)

        # 5. Add internal links on TOC page: each row links to that document's start page.
        # Use a GoTo action (/A) with explicit page reference so PDF viewers resolve the link.
        toc_page_index = 1  # 0-based
        for i, page_1based in enumerate(start_pages_1based):
            target_page_index = page_1based - 1  # 0-based
            bottom = TOC_TABLE_TOP - (i + 1) * TOC_ROW_HEIGHT
            top = TOC_TABLE_TOP - i * TOC_ROW_HEIGHT
            rect = (TOC_LEFT, bottom, TOC_RIGHT, top)
            # Page ref from page tree (flat) or from the page object
            page_tree = writer.get_object(writer._pages)
            kids = page_tree[PagesAttributes.KIDS]
            if target_page_index < len(kids):
                page_ref = kids[target_page_index]
            else:
                page_ref = getattr(writer.pages[target_page_index], "indirect_reference", None)
            if page_ref is None:
                continue
            action = DictionaryObject({
                NameObject("/S"): NameObject("/GoTo"),
                NameObject("/D"): ArrayObject([page_ref, NameObject("/Fit")]),
            })
            link_annotation = DictionaryObject({
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Link"),
                NameObject("/Rect"): RectangleObject(rect),
                NameObject("/Border"): ArrayObject([NumberObject(0), NumberObject(0), NumberObject(0)]),
                NameObject("/A"): action,
            })
            writer.add_annotation(page_number=toc_page_index, annotation=link_annotation)

        try:
            writer.write(output_path)
        except OSError as e:
            if e.errno in (13, 32) or "Permission denied" in str(e) or "being used" in str(e).lower():
                print(f"Error: Cannot write to {output_path}", file=sys.stderr)
                print("The file may be open in another program. Close it and try again.", file=sys.stderr)
            else:
                print(f"Error writing PDF: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Done. Output: {output_path}")


if __name__ == "__main__":
    main()
