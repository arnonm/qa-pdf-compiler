# QA PDF Compiler

Merges multilingual IFU PDFs into one file with:

- A **cover page** rendered from a Markdown template (WeasyPrint)
- A **table of contents** with language names and **clickable links** to each language section
- **Bookmarks** for the cover, TOC, and each appended document

## Requirements

- Python 3.10+
- [WeasyPrint](https://doc.courtbouillon.org/weasyprint/) system dependencies (e.g. GTK3/Pango on Windows; see [WeasyPrint install](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html))

## Install

```bash
pip install -r requirements.txt
```

For development / tests:

```bash
pip install -r requirements-dev.txt
```

## Usage

```bash
python pdf_compiler.py --directory <dir> --sw_version <ver> --doc_version <ver> --doc_number <num> --ifu_version <ver> [options]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--directory` | `-d` | Folder containing input PDFs (default: current directory) |
| `--sw_version` | `-sv` | Software version (required); substituted into the cover template as `{{sw_version}}` |
| `--doc_version` | `-dv` | Document version (required); shown on the TOC page |
| `--doc_number` | `-dn` | Document number (required); shown on the TOC page (e.g. `IFU-1234567`) |
| `--ifu_version` | `-ifu` | IFU version (required); substituted as `{{ifu_version}}` on the cover |
| `--template` | `-t` | Cover Markdown file (default: `template.md` next to the script) |
| `--output` | `-o` | Output PDF path (default: `<directory>/merged_<doc_version>.pdf`) |

### Example

```bash
python pdf_compiler.py -d ./my_docs -sv "2.1.0" -dv "1.3" -dn "IFU-0001234" -ifu "1.3" -o ./output/package.pdf
```

## Input PDFs

### Which files are included

- All `*.pdf` files in the directory are considered, except names starting with `_` (ignored).

### Page size

Every page in every input PDF must use the **same** MediaBox size, and that size must be **US Letter** or **A4** (within a small tolerance). Portrait and landscape are treated as the same size (dimensions are normalized). If sizes differ or are not Letter/A4, the tool exits with an error.

### Language code (filename)

The compiler reads the **ISO 639 language code** from the PDF **filename**. The stem is split on spaces; the **second-to-last** segment must be the code (e.g. `en`, `de`, `eng`).

Example: `IFU StimAI 1.0 en.pdf` → language `en` → TOC shows **English** (via `iso639_names.py`).

### Optional: header-based metadata

`pdf_compiler.py` also defines `scan_pdfs()`, which can take **Document Version**, **Document Number**, and **Document Language** from the PDF text headers instead of the filename. That path is not wired in `main()` by default; switch `main()` to use `scan_pdfs(directory)` if you want header-driven discovery and stricter validation.

## Output structure

1. **Cover** – From `template.md` (or `--template`). Placeholders: `{{sw_version}}`, `{{ifu_version}}` (and any others you add in the template).
2. **Table of contents** – Lists each language (full English name) and the 1-based page where that language starts; footer includes document number and document version.
3. **Appended PDFs** – In order, sorted by **language name** (not code).

Page numbering in the TOC assumes: page 1 = cover, page 2 = TOC, page 3 = start of the first language PDF.

## Template

Edit `template.md` (Markdown) for the cover. The script injects values into the HTML before WeasyPrint renders to PDF.

## Tests

```bash
pytest
```

## License

Use as you like.
