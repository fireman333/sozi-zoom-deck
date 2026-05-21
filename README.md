# sozi-zoom-deck

> Self-contained HTML zoom presentations — camera pans + zooms over a single image or live webpage, with spotlight highlight boxes and overlay annotations. Single-file output, no runtime deps.

[繁體中文 README ↓](#中文版-readme)

A Claude Code skill that generates [Sozi](https://sozi.baierouge.fr/)-style zoom decks from YAML config. Different from traditional slide decks — instead of one-slide-at-a-time, the camera moves spatially over a continuous canvas (a diagram, a live web page, a timeline) with smooth pan + zoom transitions.

## Why this exists

Traditional slide tools (PowerPoint, Keynote, reveal.js) put every idea on a separate slide. For some content types — **anatomical diagrams, state machines, vibe-coding live demos, project timelines** — spatial continuity matters more than slide-by-slide chunking. Sozi pioneered the "zoomable canvas" model in 2009 but its ecosystem has no programmable / config-driven generator.

This skill fills that gap:

- **YAML config in, self-contained HTML out** — no Inkscape/Sozi editor required
- **Live webpage as background** — embed your actual web app as iframe, annotate live UI
- **Crisp text** — iframe at native size + highlight box spotlight (no CSS scale blur)
- **In-deck calibration mode** — press `C`, drag-measure UI regions, auto-save coords
- **Presenter mode** — `P` toggles prev/cur/next strip + auto-open notes + clock/timer
- **Dark + light themes** — `--theme light` for academic/print use
- **PDF export** — `--pdf` for handouts with speaker notes

## Use cases

| Preset | Best for |
|---|---|
| `anatomy.yaml` | Anatomical diagrams, surgical landmarks, X-ray annotations |
| `project-intro.yaml` | Vibe-coding project intro, live web demo with UI walkthrough |
| `timeline.yaml` | Project milestones, disease progression, life timeline |
| `state-machine.yaml` | HSM, decision tree, clinical DDx algorithm, UI flow |
| `generic.yaml` | Empty template for any new use case |

## Install

This skill lives at `~/.claude/skills/sozi-zoom-deck/`. To use it standalone (outside Claude Code):

```bash
git clone <this repo>
cd sozi-zoom-deck
pip install pyyaml
```

## Quick start

```bash
# 1. Pick a preset
cp ~/.claude/skills/sozi-zoom-deck/presets/anatomy.yaml my-deck.yaml

# 2. Edit my-deck.yaml — replace IMAGE_PATH, customize frames, write notes

# 3. Build
python3 ~/.claude/skills/sozi-zoom-deck/build_deck.py my-deck.yaml -o my-deck.html

# 4. Open
open my-deck.html
```

In the deck:
- `→` / `Space` — next frame
- `←` — prev
- `1`–`9` — jump
- `L` — frame list sidebar
- `N` — speaker notes
- `B` — blank screen (for Q&A pause)
- `C` — **calibration mode** (drag to measure UI region coords)
- `P` — **presenter mode** (prev/cur/next strip + clock + auto notes)
- `Esc` — close overlays

## Calibration mode (the killer feature)

Sozi-style decks require `view: [x, y, w, h]` coords for each frame's zoom target. Eyeballing pixel coords from a screenshot is error-prone. This skill ships a built-in calibration tool:

1. Open your deck, press `C` — banner appears, cursor becomes crosshair
2. Navigate to any frame with arrow keys
3. **Drag a rectangle** over the UI element / image region you want to highlight
4. Coords auto-saved to `localStorage` + copied to clipboard
5. Highlight box instantly applies the new coords (live preview, no rebuild needed)
6. Repeat for all frames you want to recalibrate
7. Press `S` — exports all calibrations as a paste-ready snippet
8. Paste back into your YAML, rebuild, ship

## Architecture

```
sozi-zoom-deck/
├── SKILL.md                  # Claude Code skill metadata + triggers
├── build_deck.py             # CLI generator (YAML → HTML/PDF)
├── presets/
│   ├── anatomy.yaml          # static image + zoom regions
│   ├── project-intro.yaml    # live iframe + highlight boxes
│   ├── timeline.yaml         # horizontal pan along wide image
│   ├── state-machine.yaml    # HSM / decision tree zoom
│   └── generic.yaml          # blank template
└── templates/
    └── deck.html.template    # CSS + JS + HTML scaffold
```

**Design choices** (lessons from iteration):

1. **No CSS scale on iframes** — scaling iframes rasterizes content then blurs. Instead, iframe stays at native size + highlight box draws attention via `box-shadow: 0 0 0 9999px rgba(0,0,0,0.65)` (outer dim).
2. **Width-fit + top-anchor** — iframes always fill viewport width, no horizontal letterbox. Vertical can overflow (clipped).
3. **Cross-origin safe** — works with any third-party URL (GitHub Pages, your live web app, etc.). No need to scrape DOM.
4. **localStorage persistence** — calibration log keyed by `cal:<deck-id>:<frame-id>`. Survives reload, deck rebuild, browser restart.

## Theming

```bash
# Default dark theme (good for live talks)
python3 build_deck.py my-deck.yaml

# Light theme (academic, print, conservative audience)
python3 build_deck.py my-deck.yaml --theme light

# PDF handout (speaker notes inline, page-per-frame)
python3 build_deck.py my-deck.yaml --pdf
```

Custom themes: edit CSS variables in `templates/deck.html.template`. Look for `:root { --bg: ... }` and `:root[data-theme="light"] { ... }`.

## Frame schema

```yaml
- id: my-frame              # unique identifier
  mode: image|iframe|text   # background type
  title: "Frame Title"      # shown in sidebar / overlay
  subtitle: "..."           # smaller subtitle
  title_level: 1            # 1-4, sidebar outline indent (optional)
  view: [x, y, w, h]        # camera focus region in image/iframe coords
  dim: 0.0                  # 0=clear, 1=fully dark overlay
  page: home                # (iframe mode) URL key from deck.pages
  image: ./img.png          # (image mode) image path
  overlay:
    position: full|right|left|caption-top|caption-bottom|none
    title: "Visible Title"  # different from frame.title (frame.title is internal)
    subtitle: "..."
    bullets:
      - "Bullet 1"
      - "Bullet 2"
    tagline: "..."          # for cover-style frames
    footer: "..."           # for cover-style frames
  notes: |
    Speaker notes here (Chinese / English).
    Shown when N is pressed or in presenter mode.
    Also exported to PDF when --pdf flag is used.
```

## Contributing

PRs welcome for:
- New presets (life-decision-style, scientific-paper-walkthrough, code-walkthrough, …)
- Theme variants (academic, playful, brand-aligned)
- Bug fixes in calibration math (especially for non-1440 viewports)
- Translation of SKILL.md / README to other languages

Not in scope:
- Auto-play / kiosk mode (use existing static-site generators)
- Mobile touch swipe (deck is for desktop presentation)
- Multi-presenter sync (out of scope for self-contained HTML)

## License

MIT. Original Sozi project is by Guillaume Savaton (BSD-2-Clause); we share design DNA but no code.

## Credits

- [Sozi](https://github.com/sozi-projects/Sozi) — the original zoomable canvas concept
- Inspired by real-world Sozi decks in the wild: aleph2c/miros (state machines), DEMCON/libstored (outline hierarchy), OlivierChirouze/zef-presentation (timeline pan), INF554/a5-tripley (presenter mode)

---

## 中文版 README

`sozi-zoom-deck` 是一個 Claude Code skill，用 YAML config 生成 [Sozi](https://sozi.baierouge.fr/)-style zoom 簡報。Camera 在大畫布上 pan + zoom，而不是傳統「一張接一張」的 slide。

### 適合什麼場景

跟一般 slide deck（PowerPoint / reveal.js）相比，這套適合「空間連續性 > 切片重要」的內容：
- 解剖圖標註 / 影像 zoom 細節
- Vibe-coding 專案 live demo（嵌 iframe 自己的 web app）
- Project timeline / 病程進展
- HSM / decision tree / clinical algorithm
- 任何需要「整圖 overview → 局部 zoom → 帶觀眾巡走」的 talk

### 核心特色

- **YAML 驅動** — 不用 Inkscape / Sozi editor
- **Live iframe 當背景** — 可嵌真實 web app，文字 crisp 不模糊
- **In-deck calibration mode** — 按 `C` 拖拉框 UI，座標自動存
- **Presenter mode** — 按 `P` 切 prev/cur/next strip + 時鐘 + 自動展開 notes
- **Dark / light theme** + **PDF export with speaker notes**

### 快速開始

```bash
# 1. 用 preset 起頭
cp ~/.claude/skills/sozi-zoom-deck/presets/anatomy.yaml my-deck.yaml

# 2. 編輯 YAML（換 image、改 frame、寫 notes）

# 3. Build
python3 ~/.claude/skills/sozi-zoom-deck/build_deck.py my-deck.yaml -o my-deck.html

# 4. 開檔 → 按 C 校 view 座標 → S 匯出 → 貼回 YAML → 重 build
```

### 鍵盤操作

| 鍵 | 動作 |
|---|---|
| `→` / `Space` | 下一張 |
| `←` | 上一張 |
| `1`–`9` | 跳張 |
| `L` | frame list 側欄 |
| `N` | speaker notes |
| `B` | 黑屏（Q&A） |
| `C` | **calibration mode**（拖拉量座標） |
| `P` | **presenter mode**（prev/cur/next + 時鐘） |
| `Esc` | 關掉所有 overlay |

### 5 個 preset

| Preset | 用途 |
|---|---|
| `anatomy.yaml` | 解剖圖 / 影像標註 |
| `project-intro.yaml` | Vibe-coding 專案介紹 / live demo |
| `timeline.yaml` | 水平 pan 時間線（milestone 巡走） |
| `state-machine.yaml` | HSM / decision tree / clinical algorithm |
| `generic.yaml` | 空殼起手式 |

### 設計決策（從多次迭代學到的）

1. **iframe 不做 CSS scale** — scaling iframe 會 rasterize 內容然後模糊。改成 iframe 原生尺寸 + highlight box spotlight 強調局部
2. **width-fit + top-anchor** — iframe 永遠橫向滿版、上對齊；垂直可溢位（被 overflow:hidden clip）
3. **Cross-origin safe** — 可嵌任何第三方 URL，不用爬 DOM
4. **localStorage 持久化** — calibration log 按 `cal:<deck-id>:<frame-id>` 存，重 build 不丟

### 雙語對照

- 英文 primary（國際使用、Claude Code skills 生態大宗）
- 中文 secondary（中文使用者快速上手）
- 兩邊核心資訊相同，中文部分更精簡

### 授權

MIT。原始 Sozi 是 Guillaume Savaton (BSD-2-Clause)，本 skill 借鑒概念但 zero code reuse。
