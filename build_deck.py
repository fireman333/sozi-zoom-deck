#!/usr/bin/env python3
"""Build Sozi-style zoom decks from YAML config.

Modes per frame:
  - text   : full-screen text card (cover / concept / recap)
  - iframe : live webpage as background; pan + highlight box on UI region
  - image  : embedded image as background; same pan + highlight semantics

Output: self-contained HTML (base64-embed images, all CSS/JS inline).

Usage:
  build_deck.py <config.yaml> -o <output.html> [--theme dark|light] [--pdf]
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.stderr.write("Requires PyYAML: pip install pyyaml\n")
    sys.exit(1)

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "templates" / "deck.html.template"
DEFAULT_IFRAME_W = 1440
DEFAULT_IFRAME_H = 1600


def encode_image(path: Path) -> tuple[str, str]:
    """Return (mime, base64)."""
    suffix = path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    return mime, base64.b64encode(path.read_bytes()).decode("ascii")


def resolve_image_path(ref: str, config_dir: Path) -> Path:
    """Resolve image path relative to config file or as absolute."""
    p = Path(ref).expanduser()
    if not p.is_absolute():
        p = (config_dir / p).resolve()
    if not p.exists():
        raise SystemExit(f"image not found: {p}")
    return p


def prepare_deck(config: dict, config_dir: Path) -> dict:
    """Normalize config: resolve image paths, fill defaults, validate."""
    deck = {
        "id": config["id"],
        "title": config["title"],
        "subtitle": config.get("subtitle", ""),
        "iframe_ref_w": config.get("iframe_ref_w", DEFAULT_IFRAME_W),
        "iframe_ref_h": config.get("iframe_ref_h", DEFAULT_IFRAME_H),
        "pages": config.get("pages", {}),
        "frames": [],
    }
    for i, fr in enumerate(config["frames"]):
        f = {
            "id": fr.get("id", f"frame-{i+1}"),
            "mode": fr.get("mode", "text"),
            "title": fr.get("title", ""),
            "subtitle": fr.get("subtitle", ""),
            "view": fr.get("view") or [0, 0, deck["iframe_ref_w"], deck["iframe_ref_h"]],
            "dim": fr.get("dim", 0),
            "notes": fr.get("notes", ""),
            "overlay": fr.get("overlay", {}),
            "title_level": fr.get("title_level", 1),  # 1-4, sidebar outline hierarchy
        }
        if f["mode"] == "iframe":
            f["page"] = fr.get("page")
            if not f["page"] or f["page"] not in deck["pages"]:
                raise SystemExit(
                    f"frame {f['id']}: mode=iframe needs page= matching deck.pages keys"
                )
        elif f["mode"] == "image":
            img_ref = fr.get("image")
            if not img_ref:
                raise SystemExit(f"frame {f['id']}: mode=image needs image= path")
            img_path = resolve_image_path(img_ref, config_dir)
            mime, b64 = encode_image(img_path)
            f["image_data_url"] = f"data:{mime};base64,{b64}"
            f["image_natural"] = fr.get("image_natural", [deck["iframe_ref_w"], deck["iframe_ref_h"]])
        deck["frames"].append(f)
    return deck


def load_template() -> str:
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    raise SystemExit(f"template missing: {TEMPLATE_PATH}")


def render(deck: dict, theme: str) -> str:
    template = load_template()
    return (
        template.replace("__DOC_TITLE__", f"{deck['title']} — {deck['subtitle']}")
        .replace("__N__", str(len(deck["frames"])))
        .replace("__IFRAME_W__", str(deck["iframe_ref_w"]))
        .replace("__IFRAME_H__", str(deck["iframe_ref_h"]))
        .replace("__THEME__", theme)
        .replace("__DECK_JSON__", json.dumps(deck, ensure_ascii=False))
    )


def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    """Use Chrome headless to print HTML to PDF (with notes visible)."""
    chrome_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "google-chrome",
        "chromium",
    ]
    chrome = next((c for c in chrome_candidates if Path(c).exists() or _which(c)), None)
    if not chrome:
        raise SystemExit("Chrome / Chromium not found — PDF export needs one of them")
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        f"file://{html_path.resolve()}?print=1",
    ]
    print(f"running: {' '.join(cmd[:1])} ... {pdf_path.name}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"chrome PDF export failed:\n{result.stderr}")


def _which(name: str) -> bool:
    return subprocess.call(["which", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("config", type=Path, help="YAML deck config")
    ap.add_argument("-o", "--output", type=Path, default=None, help="output HTML path")
    ap.add_argument("--theme", choices=["dark", "light"], default="dark")
    ap.add_argument("--pdf", action="store_true", help="also export PDF handout")
    args = ap.parse_args()

    if not args.config.exists():
        raise SystemExit(f"config not found: {args.config}")
    with args.config.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    deck = prepare_deck(cfg, args.config.parent)
    html = render(deck, args.theme)

    out_html = args.output or args.config.with_suffix(".html")
    if args.pdf and out_html.suffix.lower() == ".pdf":
        out_html = out_html.with_suffix(".html")
    out_html.write_text(html, encoding="utf-8")
    print(f"wrote {out_html} ({len(html):,} bytes, {len(deck['frames'])} frames, theme={args.theme})")

    if args.pdf:
        pdf_path = (args.output if args.output and args.output.suffix.lower() == ".pdf"
                    else out_html.with_suffix(".pdf"))
        html_to_pdf(out_html, pdf_path)
        print(f"wrote {pdf_path}")


if __name__ == "__main__":
    main()
