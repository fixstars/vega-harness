#!/usr/bin/env python3
"""Create a fillable AcroForm PDF from a JSON spec (reportlab canvas.acroForm).

Spec format (UTF-8 JSON; coordinates in PDF points, origin bottom-left):
{
  "title": "Example Intake Form",
  "page_size": "A4",                  // or "letter" or [width, height]
  "page_count": 1,
  "fields": [
    {"name": "surname", "type": "text", "page": 1,
     "label": "Surname", "label_box": [72, 700, 150, 714],
     "entry_box": [160, 696, 400, 716], "value": "", "tooltip": "Family name"},
    {"name": "agree", "type": "checkbox", "page": 1,
     "label": "I agree", "label_box": [72, 660, 150, 674],
     "entry_box": [160, 658, 176, 674], "checked": false},
    {"name": "color", "type": "radio", "page": 1,
     "label": "Color", "label_box": [72, 620, 150, 634],
     "entry_box": [160, 616, 400, 636], "options": ["red", "blue"],
     "value": "red"},
    {"name": "size", "type": "dropdown", "page": 1,
     "label": "Size", "label_box": [72, 580, 150, 594],
     "entry_box": [160, 576, 300, 596], "options": ["small", "large"],
     "value": "small"}
  ]
}
The same spec (label_box/entry_box/page) is what pdf_form_layout.py validates,
so lint the layout first, then build.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fonts  # noqa: E402


def _reconfigure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _page_size(spec: dict):
    from reportlab.lib.pagesizes import A4, letter
    ps = spec.get("page_size", "A4")
    if isinstance(ps, (list, tuple)) and len(ps) == 2:
        return float(ps[0]), float(ps[1])
    return letter if str(ps).lower() == "letter" else A4


def _is_latin1(text: str) -> bool:
    try:
        text.encode("latin-1")
        return True
    except UnicodeEncodeError:
        return False


def field_text_problem(f: dict) -> str | None:
    """Why reportlab cannot build this field, or None.

    reportlab draws the value shown in a field's own appearance (a text
    field's value, a dropdown's selected value) with a standard Latin-1 font
    and crashes on anything else, e.g. Japanese. Everything else may be
    Japanese: names, labels, radio options and captions, other dropdown
    options. Also used by pdf_form_layout.py so the lint catches it first.
    """
    ftype = f.get("type", "text")
    if ftype == "text" and not _is_latin1(str(f.get("value", ""))):
        return ("text 'value' must be Latin-1: leave it empty and set it with "
                "pdf_fill_form.py instead")
    if ftype == "dropdown":
        options = [str(o) for o in f.get("options", [])]
        selected = str(f.get("value", options[0] if options else ""))
        if not _is_latin1(selected):
            return ("dropdown's selected value (\"value\", or the first option) must be "
                    "Latin-1: put a placeholder such as \"-\" first and select it")
    return None


def _pdf_name(value: str) -> str:
    """Radio export value as reportlab should see it.

    reportlab escapes a non-ASCII character in a PDF name as '#<code point>',
    which is not valid PDF (names escape bytes), so '赤' would read back as
    garbage. Passing the UTF-8 bytes makes it write '/#E8#B5#A4', which reads
    back as '/赤'. ASCII values are unchanged.
    """
    return value.encode("utf-8").decode("latin-1")


def build_form(spec: dict, out_path: str) -> int:
    try:
        from reportlab.lib import colors
        from reportlab.pdfgen import canvas
    except ImportError:
        print("Missing dependency: reportlab (the bundled vega-runtime is incomplete; rebuild it as described in the vega-runtime skill)", file=sys.stderr)
        return 2

    font, _bold = _fonts.register()  # labels and radio captions (Japanese OK)
    width, height = _page_size(spec)
    page_count = int(spec.get("page_count", 1))
    fields = spec.get("fields", [])
    problems = [(f.get("name", "?"), field_text_problem(f)) for f in fields]
    problems = [(name, p) for name, p in problems if p]
    if problems:
        for name, p in problems:
            print(f"Error: {name}: {p}", file=sys.stderr)
        return 5
    by_page: dict[int, list[dict]] = {}
    for f in fields:
        by_page.setdefault(int(f.get("page", 1)), []).append(f)
    page_count = max([page_count, *by_page.keys()]) if by_page else page_count

    c = canvas.Canvas(out_path, pagesize=(width, height))
    if spec.get("title"):
        c.setTitle(str(spec["title"]))
    if spec.get("author"):
        c.setAuthor(str(spec["author"]))
    form = c.acroForm
    created = []

    for pageno in range(1, page_count + 1):
        for f in by_page.get(pageno, []):
            name = f["name"]
            ftype = f.get("type", "text")
            ex0, ey0, ex1, ey1 = (float(v) for v in f["entry_box"])
            ew, eh = ex1 - ex0, ey1 - ey0
            if f.get("label"):
                lx, ly = (float(f["label_box"][0]), float(f["label_box"][1])) \
                    if f.get("label_box") else (ex0 - 90, ey0 + 4)
                c.setFont(font, float(f.get("label_size", 10)))
                c.setFillColor(colors.black)
                c.drawString(lx, ly + 2, str(f["label"]))
            tooltip = f.get("tooltip", "")
            if ftype == "text":
                form.textfield(name=name, x=ex0, y=ey0, width=ew, height=eh,
                               value=str(f.get("value", "")), tooltip=tooltip,
                               borderWidth=0.5, forceBorder=True)
            elif ftype == "checkbox":
                size = min(ew, eh)
                form.checkbox(name=name, x=ex0, y=ey0, size=size,
                              checked=bool(f.get("checked", False)),
                              buttonStyle="check", tooltip=tooltip,
                              borderWidth=0.5, forceBorder=True)
            elif ftype == "radio":
                options = f.get("options", [])
                if not options:
                    print(f"Warning: radio {name!r} has no options, skipped", file=sys.stderr)
                    continue
                size = min(eh, ew / max(len(options), 1) * 0.5, 16)
                slot = ew / len(options)
                sel = f.get("value")
                c.setFont(font, 8)
                for i, opt in enumerate(options):
                    ox = ex0 + i * slot
                    form.radio(name=name, value=_pdf_name(str(opt)), x=ox, y=ey0, size=size,
                               selected=(str(opt) == str(sel)), buttonStyle="circle",
                               borderWidth=0.5, forceBorder=True)
                    c.drawString(ox + size + 2, ey0 + size / 3, str(opt))
            elif ftype == "dropdown":
                options = [str(o) for o in f.get("options", [])]
                value = str(f.get("value", options[0] if options else ""))
                form.choice(name=name, x=ex0, y=ey0, width=ew, height=eh,
                            options=options, value=value, tooltip=tooltip,
                            borderWidth=0.5, forceBorder=True)
            else:
                print(f"Warning: unknown field type {ftype!r} for {name!r}, skipped",
                      file=sys.stderr)
                continue
            created.append({"name": name, "type": ftype, "page": pageno})
        c.showPage()
    c.save()
    print(json.dumps({"output": out_path, "pages": page_count, "fields": created},
                     ensure_ascii=False))
    return 0


def main() -> int:
    _reconfigure_stdio()
    parser = argparse.ArgumentParser(
        description="Create a fillable AcroForm PDF from a JSON spec (reportlab).")
    parser.add_argument("spec", help="Path to UTF-8 JSON form spec")
    parser.add_argument("-o", "--output", required=True, help="Output PDF path")
    args = parser.parse_args()
    with open(args.spec, encoding="utf-8") as fh:
        spec = json.load(fh)
    return build_form(spec, args.output)


if __name__ == "__main__":
    sys.exit(main())
