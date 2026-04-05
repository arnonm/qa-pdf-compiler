# QA PDF Compiler

Merges versioned multi-language PDFs into a single package with a cover page (from a Markdown template) and a table of contents. Output PDF includes bookmarks for the cover, TOC, and each document.

## Requirements

- Python 3.10+
- [WeasyPrint](https://doc.courtbouillon.org/weasyprint/) system dependencies (e.g. GTK3/Pango on Windows; see [WeasyPrint install](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html))

## Install

```bash
pip install -r requirements.txt
```

For running tests:

```bash
pip install -r requirements-dev.txt
```

## Usage

```bash
python pdf_compiler.py <directory> <version> [--template path] [--output path]
```

- **directory** – Folder containing the PDF files.
- **version** – Version string substituted for `{{version}}` in the template (e.g. `1.0`, `2.1.3`).
- **--template**, **-t** – Path to the cover template (Markdown). Default: `template.md` next to the script.
- **--output**, **-o** – Output PDF path. Default: `<directory>/merged_<version>.pdf`.

### Example

```bash
python pdf_compiler.py ./my_docs 1.0 -o ./output/package_1.0.pdf
```

## Filename convention

PDFs in the directory should include both a **version** and a **language** so the compiler can sort and label them:

- Version: digits, optionally prefixed with `v` (e.g. `1.0`, `v1.2.3`).
- Language: letters immediately before `.pdf` (e.g. `en`, `de`, `German`, `FR`).

Examples of valid names:

- `Manual_v1.0_en.pdf`
- `Guide_1.2_German.pdf`
- `Doc-2.0-FR.pdf`

Files whose names cannot be parsed (or that start with `_`) are skipped with a warning.

## Tests

```bash
pytest
```

## License

Use as you like.
