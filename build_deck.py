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
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.stderr.write("Requires PyYAML: pip install pyyaml\n")
    sys.exit(1)

try:
    import websocket  # type: ignore
    HAS_WS = True
except ImportError:
    HAS_WS = False

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


# ============================================================
# Auto-calibration: resolve target: {selector / svg_id} → view via Chrome CDP
# ============================================================

def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _find_chrome() -> str | None:
    for path in [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]:
        if Path(path).exists():
            return path
    for name in ["google-chrome", "chromium"]:
        found = shutil.which(name)
        if found:
            return found
    return None


class CDPSession:
    """Minimal Chrome DevTools Protocol client via websocket-client + raw Chrome subprocess."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.profile: Path | None = None
        self.ws = None
        self.msg_id = 0
        self.port = 0
        self.viewport_w = 1440
        self.viewport_h = 900

    def start(self, viewport_w: int = 1440, viewport_h: int = 900) -> None:
        if not HAS_WS:
            raise SystemExit("auto-calibration requires `pip install websocket-client`")
        chrome = _find_chrome()
        if not chrome:
            raise SystemExit("auto-calibration requires Chrome / Chromium installed")
        self.viewport_w = viewport_w
        self.viewport_h = viewport_h
        self.profile = Path(tempfile.mkdtemp(prefix="sozi-cal-"))
        self.port = _find_free_port()
        self.proc = subprocess.Popen(
            [
                chrome, "--headless=new", "--disable-gpu",
                f"--remote-debugging-port={self.port}",
                "--remote-allow-origins=*",   # required by Chrome ≥111 for local WS clients
                f"--user-data-dir={self.profile}",
                f"--window-size={viewport_w},{viewport_h}",
                "--no-first-run", "--no-default-browser-check",
                "--hide-scrollbars",
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # Wait for CDP HTTP endpoint (use 127.0.0.1 explicitly, longer warmup)
        time.sleep(1.0)
        ws_url = None
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/version", timeout=3) as r:
                    ws_url = json.loads(r.read())["webSocketDebuggerUrl"]
                break
            except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError, ConnectionError):
                time.sleep(0.3)
                continue
        if not ws_url:
            self.stop()
            raise SystemExit("Chrome CDP failed to start within ~12s")
        # Find a page tab (might take an extra moment after browser endpoint is up)
        tab = None
        for _ in range(20):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json", timeout=3) as r:
                    tabs = json.loads(r.read())
                tab = next((t for t in tabs if t.get("type") == "page"), None)
                if tab:
                    break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                pass
            time.sleep(0.3)
        if not tab:
            self.stop()
            raise SystemExit("Chrome CDP: no page tab found")
        self.ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=15)
        self._send("Page.enable")

    def stop(self) -> None:
        if self.ws:
            try: self.ws.close()
            except Exception: pass
            self.ws = None
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try: self.proc.kill()
                except Exception: pass
            self.proc = None
        if self.profile:
            shutil.rmtree(self.profile, ignore_errors=True)
            self.profile = None

    def _send(self, method: str, params: dict | None = None) -> dict:
        if not self.ws:
            raise RuntimeError("CDP session not started")
        self.msg_id += 1
        my_id = self.msg_id
        self.ws.send(json.dumps({"id": my_id, "method": method, "params": params or {}}))
        # Read until we get response with matching id (skip events)
        end = time.time() + 20
        while time.time() < end:
            raw = self.ws.recv()
            msg = json.loads(raw)
            if msg.get("id") == my_id:
                if "error" in msg:
                    raise RuntimeError(f"CDP {method}: {msg['error']}")
                return msg.get("result", {})
        raise RuntimeError(f"CDP {method}: timeout waiting for response")

    def navigate(self, url: str, wait_after_load_ms: int = 1500) -> None:
        self._send("Page.navigate", {"url": url})
        # Wait for loadEventFired event
        end = time.time() + 20
        while time.time() < end:
            try:
                raw = self.ws.recv()
            except Exception:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("method") == "Page.loadEventFired":
                break
        # SPA hydration grace period
        time.sleep(wait_after_load_ms / 1000)

    def query_rect(self, selector: str) -> dict | None:
        expr = (
            "(() => {"
            f"  const el = document.querySelector({json.dumps(selector)});"
            "  if (!el) return null;"
            "  const r = el.getBoundingClientRect();"
            "  return {x: Math.round(r.x), y: Math.round(r.y),"
            "          w: Math.round(r.width), h: Math.round(r.height)};"
            "})()"
        )
        result = self._send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        val = result.get("result", {}).get("value")
        return val


def calibrate_views(config: dict, config_dir: Path) -> None:
    """For each frame with `target:` and no `view:`, resolve to view coords via Chrome CDP.

    target schema:
      target:
        selector: ".some-class"        # CSS selector (any mode)
        svg_id: "my-svg-cluster-1"     # SVG element ID (image mode, shorthand for selector=#id)
        padding: 8                     # optional, expand box by N px each side
    """
    needs_cal = [(i, fr) for i, fr in enumerate(config["frames"])
                 if isinstance(fr.get("target"), dict) and not fr.get("view")]
    if not needs_cal:
        return

    cache_path = config_dir / f".{config['id']}.calibrated.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        cache = {}

    vp_w = config.get("iframe_ref_w", DEFAULT_IFRAME_W)
    vp_h = 900

    print(f"\n[calibrate] {len(needs_cal)} frame(s) need view resolution")
    sess: CDPSession | None = None
    cache_dirty = False
    try:
        for i, fr in needs_cal:
            target = fr["target"]
            mode = fr.get("mode", "text")
            url = None
            selector = target.get("selector")
            if not selector and target.get("svg_id"):
                # Use attribute selector to handle IDs with special chars (., :, etc.)
                selector = f"[id={json.dumps(target['svg_id'])}]"

            if mode == "iframe":
                page_key = fr.get("page")
                pages = config.get("pages", {})
                if not page_key or page_key not in pages:
                    print(f"  ⚠ frame {fr.get('id', i+1)}: iframe target needs page= in pages")
                    continue
                url = pages[page_key]
            elif mode == "image":
                img_ref = fr.get("image")
                if not img_ref:
                    print(f"  ⚠ frame {fr.get('id', i+1)}: image target needs image=")
                    continue
                img_path = resolve_image_path(img_ref, config_dir)
                url = f"file://{img_path}"
            else:
                print(f"  ⚠ frame {fr.get('id', i+1)}: target ignored for mode={mode}")
                continue

            if not selector:
                print(f"  ⚠ frame {fr.get('id', i+1)}: target needs selector or svg_id")
                continue

            key = hashlib.md5(f"{url}|{selector}|{vp_w}".encode()).hexdigest()[:16]
            if key in cache:
                fr["view"] = cache[key]
                print(f"  ✓ {fr.get('id', i+1):<20} cached  → view={fr['view']}")
                continue

            if sess is None:
                print(f"  spawning Chrome headless ({vp_w}x{vp_h})...")
                sess = CDPSession()
                sess.start(vp_w, vp_h)

            print(f"  • {fr.get('id', i+1):<20} {url[:50]}...  {selector}")
            sess.navigate(url)
            rect = sess.query_rect(selector)
            if not rect:
                print(f"    ⚠ selector not found, frame keeps default full-canvas view")
                continue
            padding = int(target.get("padding", 0))
            view = [
                max(0, rect["x"] - padding),
                max(0, rect["y"] - padding),
                max(1, rect["w"] + 2 * padding),
                max(1, rect["h"] + 2 * padding),
            ]
            fr["view"] = view
            cache[key] = view
            cache_dirty = True
            print(f"    ✓ → view={view}")
    finally:
        if sess:
            sess.stop()
        if cache_dirty:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  cache → {cache_path.name}")


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
    ap.add_argument("--no-calibrate", action="store_true",
                    help="skip auto-calibration of frames with target: field")
    args = ap.parse_args()

    if not args.config.exists():
        raise SystemExit(f"config not found: {args.config}")
    with args.config.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    # Auto-calibrate any frame with target: but no view: (resolves to view via Chrome CDP)
    if not args.no_calibrate:
        calibrate_views(cfg, args.config.parent)
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
