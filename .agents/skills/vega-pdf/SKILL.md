---
name: vega-pdf
description: "Work with PDF files end to end: build from JSON specs, fill AcroForm forms, merge/split/rotate, watermark/stamp, encrypt/decrypt, metadata and attachments — and read/extract text, tables and form fields. Scanned/image-only PDFs route to vision review or tesseract OCR (pdf_ocr.py). Use whenever a .pdf file is an input or an output."
license: MIT
metadata:
  version: 1.1.0
  author: Nous Research
  platforms: [linux, macos, windows]
---

# PDF Skill

Respond to the user in the language they write in (e.g. Japanese); keep commands, paths, code and file names as they are.

Create PDFs from structured specs, build and fill AcroForm forms (with layout linting and visual overlays), extract text/tables/metadata, merge/split/rotate/watermark/stamp pages, export page images, manage metadata and attachments, and encrypt/decrypt — using pypdf, reportlab, and pdfplumber. Scanned/image-only PDFs are routed per the Reading scanned PDFs section below (vision review or tesseract OCR).

## When to Use

- Generate a report, invoice, or multi-page document as PDF.
- Build a fillable AcroForm (text/checkbox/radio/dropdown) from a JSON spec, linting the layout first.
- Pull text, tables (JSON/CSV), metadata, or form-field values out of a PDF.
- Merge, split, rotate, extract page subsets, watermark, stamp text/images at coordinates, bookmark, or compress PDFs.
- Export pages as PNGs for visual review or for OCR hand-off; set/clear document metadata; add/extract file attachments.
- Fill or flatten AcroForm forms; encrypt or decrypt with passwords.
- Scanned/image-only PDFs: follow the Reading scanned PDFs section below (vision review or `pdf_ocr.py`).
- NOT for pixel-perfect HTML-to-PDF rendering (use a headless browser).

## Runtime

Run every script with the Python bundled in the sibling `vega-runtime`
skill, from the user's working directory (do not `cd` into this skill):

```bash
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/<script>.py ...
```

`<skill-dir>` is the absolute "Base directory for this skill" shown when this
skill was loaded. Input/output file arguments then resolve against the
user's working directory as usual. On Windows PowerShell / cmd.exe, use
`<skill-dir>\..\vega-runtime\runtime\bin\python.bat` instead.

The runtime already contains the pinned dependencies — do not use a system
`python` or install packages. If the runtime path does not exist, stop and
follow the `vega-runtime` skill; it sets the runtime up only after the
user agrees — never build or install it on your own.

## Prerequisites

- The bundled runtime provides `pypdf`, `reportlab`, `pdfplumber`, `pypdfium2`.
- Optional, for page rasterization (`pdf_page_image.py`, overlay rendering): poppler's `pdftoppm` on PATH. Scripts fall back pypdfium2 → pdftoppm and report `{"rendered": false, "missing": [...]}` (exit 0) when neither exists.
- Optional (only when available; not a requirement): tesseract for OCR of scanned PDFs (`pdf_ocr.py`), with the language pack for `--lang`.
- Each helper script checks imports lazily and, if a dependency is missing, says so and points to the `vega-runtime` skill (setting the runtime up needs the user's consent).
- Japanese text: all text the scripts draw (`pdf_create.py`, form labels, `pdf_stamp.py --text`) uses the bundled BIZ UDPGothic in `assets/fonts/` (SIL OFL 1.1), so Japanese and Latin both render. For bold stamps pass `--font BIZUDPGothic-Bold`; standard fonts such as `Helvetica` are Latin-only.

## How to Run

All helpers live in `scripts/` and are argparse CLIs — run them with the `bash` tool; every one supports `--help`. They read/write JSON strictly as UTF-8, print JSON results to stdout, and exit non-zero on failure.

```bash
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_create.py spec.json -o out.pdf         # build PDF from JSON spec
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_make_form.py formspec.json -o form.pdf # build fillable AcroForm from JSON spec
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_form_layout.py formspec.json           # lint form layout BEFORE building
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_form_layout.py formspec.json --render-overlay boxes.png [--pdf form.pdf]
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_read.py doc.pdf --text                 # per-page text (JSON)
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_read.py doc.pdf --tables --csv-dir t/  # tables to JSON + CSV files
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_read.py doc.pdf --meta                 # metadata, page sizes, encrypted/scanned flags
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_read.py form.pdf --fields              # form fields: name, type, value
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_merge.py a.pdf b.pdf -o merged.pdf [--bookmarks]
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_split.py doc.pdf --pages 1-3,7 -o part.pdf [--rotate 90]
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_fill_form.py form.pdf --fields-json values.json -o filled.pdf [--flatten]
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_secure.py doc.pdf --encrypt -o enc.pdf --user-password your-password
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_secure.py enc.pdf --decrypt -o dec.pdf --password your-password
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_watermark.py doc.pdf --stamp mark.pdf -o stamped.pdf [--under]
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_stamp.py doc.pdf -o out.pdf --text "DRAFT" --x 150 --y 400 \
    --font-size 60 --rotation 45 --opacity 0.3 --color "#cc0000" [--pages 1-3]
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_stamp.py doc.pdf -o out.pdf --image sig.png --x 400 --y 60 --width 120
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_page_image.py doc.pdf --pages 1-3 --dpi 150 --out-dir imgs/
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_ocr.py scan.pdf --lang jpn+eng -o ocr.txt   # OCR scanned pages
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_meta.py doc.pdf --set-meta --title "T" --author "A" -o out.pdf
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_meta.py doc.pdf --attach data.csv -o out.pdf
<skill-dir>/../vega-runtime/runtime/bin/python <skill-dir>/scripts/pdf_meta.py doc.pdf --list-attachments | --extract-attachments dir/
```

## Quick Reference

| Task | Tool | Command / API |
|---|---|---|
| Create doc (headings, tables, images) | reportlab platypus | `pdf_create.py spec.json -o out.pdf` |
| Build fillable form | reportlab acroForm | `pdf_make_form.py formspec.json -o form.pdf` |
| Lint form layout / overlay image | pure python + PIL | `pdf_form_layout.py formspec.json [--render-overlay o.png]` |
| Per-page text | pdfplumber | `pdf_read.py f.pdf --text` |
| Tables → JSON/CSV | pdfplumber | `pdf_read.py f.pdf --tables` |
| Metadata / sizes / encrypted / scanned | pypdf + pdfplumber | `pdf_read.py f.pdf --meta` |
| Merge (+ outline) | pypdf | `pdf_merge.py a.pdf b.pdf -o m.pdf` |
| Split / extract / rotate | pypdf | `pdf_split.py f.pdf --pages 2-5 --rotate 90` |
| List / fill / flatten form | pypdf | `pdf_read.py --fields`, `pdf_fill_form.py` |
| Encrypt / decrypt (AES-256) | pypdf | `pdf_secure.py --encrypt/--decrypt` |
| Watermark / stamp PDF page | pypdf | `pdf_watermark.py f.pdf --stamp w.pdf` |
| Stamp text/image at coordinates | reportlab + pypdf | `pdf_stamp.py f.pdf --text "Sign here" --x 400 --y 60` |
| Pages → PNG (review / OCR hand-off) | pypdfium2 or pdftoppm | `pdf_page_image.py f.pdf --pages 1-3 --out-dir imgs/` |
| OCR scanned pages | tesseract (via rasterizer) | `pdf_ocr.py f.pdf --lang jpn+eng -o out.txt` |
| Set/clear metadata, attachments | pypdf | `pdf_meta.py --set-meta / --attach / --extract-attachments` |
| Compress content streams | pypdf | `pdf_split.py f.pdf --pages 1-N --compress` |

## Procedure

1. **Inspect first.** Run `pdf_read.py file.pdf --meta`. Check `encrypted` (if true, decrypt first with `pdf_secure.py --decrypt`) and `likely_scanned_pages`. If pages are image-only, follow the Reading scanned PDFs routing (vision review or `pdf_ocr.py`) — do not report empty text as "no content".
2. **Create.** Write a JSON spec with the `write` tool (elements: `heading`, `paragraph`, `table`, `image`, `pagebreak`; optional `title`/`author` metadata; page numbers are added automatically), then run `pdf_create.py`. Verify visually on a rendered page image (`pdf_page_image.py`) if layout matters.
3. **Extract.** `--text` gives a JSON list of per-page strings; `--tables` gives row arrays per page and can also emit CSV files. Read results with the `read` tool; never eyeball a binary PDF directly.
4. **Manipulate.** `pdf_merge.py` concatenates and can add one bookmark per source file; `pdf_split.py` handles page ranges (1-based, e.g. `1-3,5,9-`), rotation in 90° steps, and `--compress`. Watermark by preparing a single-page stamp PDF (e.g. via `pdf_create.py`) and overlaying it with `pdf_watermark.py`; for one-liner stamps ("sign here", diagonal DRAFT, corner labels) use `pdf_stamp.py` with text or an image at explicit coordinates.
5. **Build forms.** Write one form-spec JSON (fields with `label_box`/`entry_box` in PDF points — see `references/forms.md`), lint it with `pdf_form_layout.py` and fix every reported problem, optionally review the `--render-overlay` PNG, then build with `pdf_make_form.py` and confirm with `pdf_read.py --fields`.
6. **Fill forms.** List fields (`--fields`) to learn exact names and types, write a UTF-8 JSON of `{"FieldName": "value"}` with the `write` tool (checkboxes accept `true`/`false`; radio/choice values must match the field's export options), then `pdf_fill_form.py`. Re-read with `--fields` to confirm values landed.
7. **Metadata & attachments.** `pdf_meta.py --set-meta` writes Title/Author/Subject/Keywords (DocInfo); `--clear-meta` drops them; `--attach`/`--list-attachments`/`--extract-attachments` round-trip embedded files.
8. **Secure.** Encrypt with distinct user/owner passwords and AES-256. To remove a password you know, `--decrypt` writes an unencrypted copy.
9. **Verify** (see below) before reporting success.

## Reading scanned PDFs (vision / OCR routing)

For scanned or image-only PDFs the text layer is empty; pick a route in this order:

1. **Text layer first, always.** `pdf_read.py file.pdf --text` (and `--meta`'s
   `likely_scanned_pages`). Text-layer extraction is lossless, cheap, and
   deterministic — never start with OCR or vision on a PDF that has one.
2. **Vision route** (when a vision-capable model is available): render the
   pages with `pdf_page_image.py --dpi 300 --out-dir imgs/` and read the
   images directly.
3. **OCR route** (no vision model, or bulk text needed): get the user's
   consent first — OCR misreads are possible and accuracy is not guaranteed;
   state this explicitly. Then run `pdf_ocr.py file.pdf --lang jpn+eng -o out.txt`.
4. **Tooling absent (airgapped installs)**: the Python libraries come from
   the bundled `vega-runtime`; if they are missing, follow the `vega-runtime`
   skill (never `pip install`). No OS-level tools are required: when
   tesseract is unavailable, use the vision route or report the limitation.

Reporting rule: always state which method (text-layer / OCR / vision) and
which pages were used. Content derived from OCR or vision is an estimate —
mark it as such.

## Pitfalls

- **Scanned PDFs**: empty `extract_text()` plus page images means there is no text layer. Route to vision review or `pdf_ocr.py` per the Reading scanned PDFs section; do not fabricate text.
- **Flattening limits**: `pdf_fill_form.py --flatten` uses pypdf's flatten support, which converts widget appearances into page content. It is reliable for plain text fields and checkboxes but can drop or misrender exotic widgets (rich text, custom appearance streams, some radio groups). Verify the flattened output visually on a rendered page image; for bulletproof flattening use an external renderer (e.g. Ghostscript or `pdftoppm`+reassembly) as a fallback.
- **NeedAppearances**: after filling, viewers only render values if appearance streams exist. The fill script sets the AcroForm `NeedAppearances` flag so conforming viewers regenerate them; some minimal viewers ignore it — flatten if display fidelity matters.
- **Japanese in forms**: field names, labels, radio options and dropdown options may be Japanese. Only the text reportlab draws in the field itself must be Latin-1 — a text field's default `value` and a dropdown's selected value (reportlab limitation; `pdf_form_layout.py` flags it and `pdf_make_form.py` exits 5 naming the field). Build text fields empty and fill them with `pdf_fill_form.py`; for Japanese dropdowns put a placeholder such as `"-"` first and select it.
- **Non-Latin form values**: filled values are stored correctly (UTF-16), but the field's default font may lack glyphs, so a viewer can show blanks even though the data round-trips. Verify with `--fields`, not just visually.
- **Compression expectations**: `--compress` only deflates content streams. Typical savings are 0–20%; it does nothing for PDFs dominated by images or already-compressed streams. It is not a substitute for image downsampling (Ghostscript territory).
- **Permission flags don't enforce**: owner-password permission bits (no-print, no-copy) are polite requests that viewers may honor; any library (including pypdf) can read and strip them. Only the user password actually gates content via encryption. Never present permission flags as security.
- **Table extraction is heuristic**: pdfplumber detects tables from ruling lines/word alignment; borderless or merged-cell tables may need `table_settings` tuning or manual cleanup.
- **Page indexing**: helper CLIs take 1-based pages; pypdf APIs are 0-based. The scripts convert — don't double-convert.
- **Rotated stamp text extraction**: pdfplumber's line grouping scrambles rotated glyphs (a 45° "DRAFT" extracts as stray letters); verify rotated stamps with `pypdf`'s `extract_text()` or a rendered image instead.
- **Radio groups**: reportlab needs ≥2 `radio()` widgets per group, fills need the slashed export value (`"/red"`), and flatten fidelity is worst for radios — see `references/forms.md`.
- **Metadata scope**: `pdf_meta.py` writes the classic DocInfo dictionary only; embedded XMP metadata (if any) is left untouched and may show different values in some viewers.
- **PDF/A is out of scope**: pypdf/reportlab cannot produce or validate conformant PDF/A. If archival conformance is required, run Ghostscript via the `bash` tool (e.g. `gs -dPDFA=2 -dPDFACompatibilityPolicy=1 -sColorConversionStrategy=UseDeviceIndependentColor -sDEVICE=pdfwrite -o out.pdf in.pdf` with a suitable ICC profile) and validate with veraPDF — both are external installs, and the result still needs validation, not assumption.
- Rotation must be a multiple of 90; encrypted inputs must be decrypted before any other operation.

## Verification

- After create/merge/split: `pdf_read.py out.pdf --meta` — confirm `page_count`, and per-page `rotation` when you rotated.
- After extraction: check the JSON is non-empty and spot-check a known string or cell.
- Form design loop: `pdf_form_layout.py spec.json` must exit 0; then `--render-overlay boxes.png --pdf form.pdf` and review the PNG (red = entry boxes with field names, blue = label boxes) asking about overlaps, misalignment, and labels detached from their fields. Iterate spec → lint → overlay until clean.
- After building a form: `pdf_read.py form.pdf --fields` lists every spec field with the right type and options.
- After form fill: `pdf_read.py filled.pdf --fields` and compare values (exact match, including non-ASCII).
- After stamping: re-extract text (pypdf for rotated stamps) or render the page with `pdf_page_image.py` and inspect the image.
- After metadata/attachment edits: `pdf_read.py --meta` / `pdf_meta.py --list-attachments`, and re-extract an attachment to byte-compare.
- After encrypt: `--meta` shows `"encrypted": true` and opening without a password fails; after decrypt, text extraction matches the original.
- For anything visual (watermarks, flattened forms), render with `pdf_page_image.py` and inspect the image.
