#!/usr/bin/env python3
"""OCR PDF pages with tesseract (for scanned/image-only PDFs).

Renders each page via the shared rasterizer (pypdfium2 -> pdftoppm
fallback) and runs tesseract on it. Prints JSON to stdout.

Exit codes: 0 = done, 2 = missing dependency (pypdf / tesseract),
3 = encrypted or wrong password, 4 = bad arguments.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_pages(spec: str, page_count: int) -> list[int]:
    """'1-3,5,9-' (1-based, inclusive) -> sorted page list."""
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, _, end_s = part.partition("-")
            start = int(start_s) if start_s else 1
            end = int(end_s) if end_s else page_count
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    bad = [p for p in pages if not 1 <= p <= page_count]
    if bad:
        raise ValueError(f"pages out of range 1-{page_count}: {sorted(bad)}")
    return sorted(pages)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="OCR PDF pages with tesseract.")
    parser.add_argument("pdf", help="Input PDF path")
    parser.add_argument("--lang", default="jpn+eng",
                        help="tesseract language(s), +-separated (default: jpn+eng)")
    parser.add_argument("--pages", default="1-", help="1-based ranges, e.g. '1-3,5' (default: all)")
    parser.add_argument("--dpi", type=int, default=300, help="Render DPI (default 300)")
    parser.add_argument("-o", "--out", help="Also write plain text to this file")
    parser.add_argument("--keep-images", metavar="DIR",
                        help="Keep rendered page PNGs in this directory")
    parser.add_argument("--password", help="Password for encrypted PDFs")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _raster

    if not shutil.which("tesseract"):
        print("tesseract is not available (optional OCR engine). Use the vision "
              "route (render pages and read the images) instead.", file=sys.stderr)
        return 2
    if not _raster.available_backends():
        print('Missing rasterizer: {"missing": ' + json.dumps(_raster.missing_hints()) + "}",
              file=sys.stderr)
        return 2
    try:
        from pypdf import PdfReader
    except ImportError:
        print("Missing dependency: pypdf (the bundled vega-runtime is incomplete; rebuild it as described in the vega-runtime skill)", file=sys.stderr)
        return 2

    reader = PdfReader(args.pdf)
    if reader.is_encrypted:
        if args.password is None or not reader.decrypt(args.password):
            print("File is encrypted; pass --password.", file=sys.stderr)
            return 3
    page_count = len(reader.pages)

    try:
        pages = parse_pages(args.pages, page_count)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 4

    image_dir = Path(args.keep_images) if args.keep_images else None
    if image_dir:
        image_dir.mkdir(parents=True, exist_ok=True)

    results = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        for pageno in pages:
            img = _raster.rasterize_page(args.pdf, pageno, dpi=args.dpi, password=args.password)
            if img is None:
                print('Rasterizer unavailable: {"missing": '
                      + json.dumps(_raster.missing_hints()) + "}", file=sys.stderr)
                return 2
            if image_dir:
                image_path = image_dir / f"page{pageno:03d}.png"
            else:
                image_path = Path(tmp) / f"page{pageno:03d}.png"
            img.save(image_path)
            proc = subprocess.run(
                ["tesseract", str(image_path), "stdout", "-l", args.lang],
                capture_output=True, text=True, encoding="utf-8",
            )
            if proc.returncode != 0:
                print(f"tesseract failed on page {pageno}: {proc.stderr.strip()}",
                      file=sys.stderr)
                return 4
            results.append({"page": pageno, "chars": len(proc.stdout), "text": proc.stdout})

    body = "\n".join(entry["text"] for entry in results)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(body)

    json.dump({"ok": True, "lang": args.lang, "dpi": args.dpi,
               "pages": [{"page": e["page"], "chars": e["chars"]} for e in results],
               "total_chars": sum(e["chars"] for e in results),
               "output": args.out or None, "text": body if not args.out else None},
              sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
