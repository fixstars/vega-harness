# Attribution

Vendored from https://github.com/NousResearch/hermes-agent (`skills/productivity/pdf`, MIT License — see LICENSE).
Upstream commit: `d6ee48799369e63364fcd58071414843f9019fd5` (2026-09-17).

## Changes for this preset (OpenCode)

- Excluded `scripts/extract_pymupdf.py` and `references/ocr-extraction.md`:
  PyMuPDF / pymupdf4llm are AGPL-3.0 (dual-licensed with a commercial
  option), outside this preset's permissive-only runtime policy.
- Excluded `scripts/extract_marker.py` for environment reasons, not license:
  marker-pdf is Apache-2.0, but it pulls PyTorch and downloads ~3-5GB of
  models on first use, which does not fit airgapped customer environments
  (and the GPU is reserved for LLM inference).
- Excluded `references/nano-pdf-editing.md` (external `nano-pdf` CLI).
- Tool names `terminal`→`bash`, `write_file`→`write`, `read_file`→`read`;
  `vision_analyze`→rendered page image review.
- Frontmatter restructured for the Agent Skills schema (`version`/`author`/
  `platforms` moved under `metadata`, Hermes-specific `metadata.hermes`
  block removed).
- Excluded upstream `tests/`.
- SKILL.md: added a line telling the agent to respond in the user's language.
- `pdf_stamp.py`: `--opacity` was ignored for text stamps (the fill color
  was set after the alpha, which resets it to opaque); set the color first.
- Japanese text: `pdf_create.py`, `pdf_make_form.py` (labels, radio
  captions), `pdf_stamp.py` (default `--font`) and the `pdf_form_layout.py`
  overlay use the bundled font (see Additions) instead of Latin-only
  Helvetica. `pdf_make_form.py` also stores non-ASCII radio export values
  as valid PDF names and rejects fields whose drawn value is not Latin-1
  (text-field value, dropdown selection) up front instead of crashing
  inside reportlab; `pdf_form_layout.py` lints the same.

## Additions by Fixstars Corporation (Vega harness)

- `scripts/_fonts.py`: registers the bundled font with reportlab.
- `assets/fonts/BIZUDPGothic-{Regular,Bold}.ttf`: BIZ UDPGothic from
  https://github.com/googlefonts/morisawa-biz-ud-gothic (tag `v1.051`,
  commit `18934af56b9c`), SIL Open Font License 1.1 — see
  `assets/fonts/OFL.txt`. Unmodified.

- `scripts/pdf_ocr.py`: original tesseract OCR wrapper (reuses the skill's
  `_raster.py` fallback chain). Covers the OCR capability dropped with the
  AGPL/marker scripts, offline and lightweight.
- SKILL.md: "Reading scanned PDFs (vision / OCR routing)" section —
  text-layer first, vision route, OCR with explicit consent, airgap install
  guidance, and the method/page reporting rule. This merges the former
  `read-pdf` skill (now removed); extraction and rendering are covered by
  upstream `pdf_read.py` / `pdf_page_image.py`.
