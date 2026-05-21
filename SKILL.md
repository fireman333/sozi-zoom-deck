---
name: sozi-zoom-deck
description: |
  生成 Sozi-style zoom presentations — camera 在 image 或 live webpage 上做 pan+zoom 動畫，
  搭配 highlight box spotlight + overlay annotation。用於解剖 zoom + 病灶標註 / vibe-coding 專案介紹 /
  疾病 overview slide / 任何「整頁背景 + 局部 focus」的 talk。Self-contained HTML output，無 runtime dep。
  Sister skill 跟 `anthropic-skills:pptx` 並行 — pptx 適合 slide deck，本 skill 適合 zoom canvas
  / 帶 live web 元素 / 整圖深度標註。
  Trigger 關鍵詞：`/sozi-deck`、`/zoom-deck`、`/sd`、使用者提及「Sozi 簡報」「zoom 簡報」
  「camera 滑動簡報」「live 網頁 + 標注」「解剖圖 zoom 標註」「vibe-coding 介紹簡報」「探照燈 highlight 簡報」
  等意圖時。即使使用者只說「幫我把這個解剖圖做成可以 zoom 進去標重點的簡報」「我想 demo 我的 web app 用 camera 帶觀眾走一遍」
  「給這個疾病做一個從 overview 到細節的 zoom 簡報」也應觸發。
---

# Sozi Zoom Deck — 生成 Sozi-style zoom 簡報

## 核心定位

**這跟一般 slide deck 不同**：

| | slide deck（pptx）| **Sozi zoom deck（本 skill）** |
|---|---|---|
| 切換 | 一張接一張、cut | camera 在大畫布上 pan + zoom，**空間連續** |
| 內容 | 每張獨立 | 一張底圖 / 一個 live 網頁，多個 view region 標重點 |
| 動畫 | 漸入 / 滑入 | 平滑 transform + 探照燈 spotlight |
| 適合 | 一般演講 | anatomy zoom、live demo、概念地圖、深度標註 |

## 4 種使用情境（對應 4 個 preset）

### A. Anatomy / 解剖圖 zoom 標註
- 一張 raster / SVG 圖當底
- 多個 view region 對應解剖結構
- Speaker notes 帶醫學專業內容
- preset: `presets/anatomy.yaml`

### B. Vibe-coding 專案介紹 / live web demo
- live iframe(s) 當背景（不需截圖）
- highlight box 框出關鍵 UI 區域
- overlay annotation 解釋功能
- preset: `presets/project-intro.yaml`

### C. Timeline / 時間線（水平 pan）
- 寬幅 timeline 圖（可用 Mermaid → SVG / Inkscape / PowerPoint 製作）
- frame 1 全 timeline 一覽 → frames 2-N pan 左→右、每個 milestone 一個
- 適合 project 沿革 / 病程進展 / 歷史大事年表
- 借鑒：OlivierChirouze/zef-presentation
- preset: `presets/timeline.yaml`

### D. 通用 zoom 概念地圖
- 空白模板給新 use case 起頭
- preset: `presets/generic.yaml`

## Workflow

### 1. 選 preset 起頭

```bash
cd <your-project>
cp ~/.claude/skills/sozi-zoom-deck/presets/anatomy.yaml my-deck.yaml
# 或 project-intro.yaml / generic.yaml
```

### 2. 編輯 YAML

每個 frame 定義：
- `id`、`title`、`subtitle`
- `mode`：`text` / `iframe` / `image`
- `view`：`[x, y, w, h]` camera 焦點區域（iframe natural coords 或 image coords）
- `overlay`：`position` / `bullets` / `tagline` 等
- `notes`：中文 speaker notes
- `dim`：0–1（concept slide 0.7+、live demo 0–0.2）

### 3. Build

```bash
python3 ~/.claude/skills/sozi-zoom-deck/build_deck.py my-deck.yaml -o my-deck.html
# 預設 dark theme。要 light：
python3 ~/.claude/skills/sozi-zoom-deck/build_deck.py my-deck.yaml --theme light -o my-deck.html
# 要 PDF handout（含 speaker notes）：
python3 ~/.claude/skills/sozi-zoom-deck/build_deck.py my-deck.yaml --pdf -o my-deck.pdf
```

### 4. 校正 view 座標（CRITICAL）

view 座標難用眼睛估準。用內建 **calibration mode**：

1. 開 `my-deck.html`，按 `C` 進 cal mode
2. 切到要校正的 frame，**滑鼠拖拉框出**目標 UI 區域
3. 自動存 `localStorage` + 即時套用 highlight 預覽
4. 全部校好按 `S` → 匯出 Python snippet 到剪貼簿
5. 貼進 YAML / build.py 對應 frame 的 `view` 欄、重 build

或不用 cal mode，用 Chrome DevTools：在 live URL 用 inspector 點目標 → console 打 `$0.getBoundingClientRect()` → 拿到 `{x, y, width, height}` → 填進 view。

## 操作鍵盤（生成後的 deck）

| 鍵 | 動作 |
|---|---|
| `→` `Space` | next frame |
| `←` | prev |
| `1`–`9` | jump |
| `0` | 回 cover |
| `L` | frame list sidebar |
| `N` | speaker notes panel |
| `B` | blank screen（Q&A pause） |
| `C` | calibration mode（拖拉量座標） |
| `Esc` | 關掉 overlay |

Cal mode 內額外鍵：`S` export 全部、`X` 清空、方向鍵/數字切 frame、拖滑鼠量。

## 跟其他 skill 的退讓

- 純 slide-style deck → `anthropic-skills:pptx`
- 含醫學 case discussion 結構 → `case-discussion-pptx`
- 倫理討論課 deck → `medical-ethics-discussion-pptx`
- Journal club → `journal-club-discussion-pptx`
- **anatomy zoom 標註 / live web demo / 概念地圖** → 本 skill（替代不來上面任一）

## 反例（避免）

- 別用本 skill 做 14+ frame 的長 deck — Sozi feel 在 6-10 frame 最強，太多 frame 觀眾迷失空間方位
- 別用本 skill 嵌登入後才有內容的 web app — iframe 看不到登入態，會卡 loading
- 別在 highlight box 內放超過 1 個 caption — 視覺競爭

## File layout

```
~/.claude/skills/sozi-zoom-deck/
├── SKILL.md            # this file
├── build_deck.py       # CLI generator
├── presets/
│   ├── anatomy.yaml
│   ├── project-intro.yaml
│   └── generic.yaml
└── templates/
    └── deck.html.template
```

## Build context

- Origin: 2026-05-21 myectomy + study-rpg deck experiments
- Original `build_studyrpg.py` lives at `~/coding-scratch/myectomy-sozi-2026-05-21/`
- Key design lessons baked in: iframe at native size (no CSS scale → crisp), highlight box spotlight (replace CSS zoom blur), `localStorage` calibration log per frame
