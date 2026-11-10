# AGENTS.md

給接手這個專案的 AI 代理的工作說明。功能細節以 `SPEC.md` 為準，資料來源與校勘以 `SOURCES.md` 為準。架構與規則沿用《心經》專案（chungyilin2005-sys/xinjing）。

## 專案概要

《道德經》讀誦與描寫網頁，附黃元吉《道德經注釋》。單一 HTML 檔，主要在 Android 手機的 Chrome 上使用，發布為 claude.ai Artifact 與 GitHub Pages。

## 檔案結構

```
daodejing/
├── index.html                      建置產物（勿手改）
├── src/daodejing.template.html     原始碼：HTML + CSS + JS
├── tools/fetch_notes.py            下載維基文庫原始碼（固定 oldid）→ 解析 → 簡轉繁 → data/
├── tools/textdata.py               讀 data/ 並套用 data/corrections.json（build 與 tts 共用）
├── tools/build.py                  子集化字體、內嵌資料／圖示／錄音 → index.html
├── tools/tts_edge.py               edge-tts 逐章逐句產生經文錄音 → audio/
├── data/chapters.json              81 章：章序、章名、經文、經文附註位置（fetch 產生，勿手改）
├── data/notes/01.txt～81.txt       各章注釋（段落以空行分隔；fetch 產生，勿手改）
├── data/preface.txt                黃元吉自序（fetch 產生，勿手改）
├── data/convert_rules.json         簡轉繁一對多字的上下文規則
├── data/corrections.json           使用者確認過的錄入錯字修正（建置時套用；尚未建立）
├── data/corrections.proposed.json  校勘建議（未套用）
├── data/raw/source.json            來源網址、oldid、SHA-1、取得日期
├── data/raw/*.wiki                 下載的原始碼（含蕭天石例言，不進 git）
├── audio/                          錄音與 manifest.json（產生後才有）
├── fonts/                          霞鶩文楷 TC 完整字體、子集、授權說明
├── icons/icon-512.png              「道」字圖示（建置時產生）
└── samples/                        錄音格式試聽樣本（不進 git）
```

## 修改流程

1. 介面與功能只改 `src/daodejing.template.html`。
2. 文字只能經由以下途徑改變：
   - 轉換問題 → `data/convert_rules.json`，再執行 `python tools/fetch_notes.py --offline`。
   - 錄入錯字 → 使用者確認後加進 `data/corrections.json`。**不可直接改 `data/` 下 fetch 產生的檔案，也不可自行修字。**
3. 建置：
   ```bash
   pip install fonttools brotli pillow opencc
   python tools/build.py
   ```
4. 依 `SPEC.md` 第 7 節驗收；有功能變更時同步更新 `SPEC.md`。

## 必須遵守的規則

### 不可違反

- **注釋全文只來自維基文庫 oldid 2315999**，不可憑記憶生成、補寫或改寫。更換版本號須經使用者同意，並更新 `SOURCES.md`。
- **不收錄蕭天石例言**；`data/raw/*.wiki` 不可提交到 git。
- **單一檔案、零外部資源**：不可引用 CDN、外部圖片、外部字體或任何網路請求。
- **不可修改顯示用的經文來修正讀音**，讀音問題只改 `SAY`（見 `SPEC.md` 3.3）。
- **儲存格式向後相容**：`dd.*` 鍵與筆畫格式裡有使用者的描寫紀錄。改經文（校勘）會使某章字序改變，已有紀錄時必須寫遷移程式。不可使用 `xj.*` 鍵。
- **夜間配色兩處同步**：`@media (prefers-color-scheme: dark)` 與 `:root[data-theme="dark"]`。
- 推上 GitHub 前先問使用者。

### 慣例

- 介面文字繁體中文、台灣用語，引號「」。
- JS 維持 ES5 風格（`var`、`function`），不引入框架。
- `localStorage`、`indexedDB`、`claude.use()` 都包 try/catch 或 `.catch()`。
- canvas 顏色用 `css("--變數")` 讀取（匯出圖片除外）；畫字前先 `document.fonts.load()`。
- 觸控區至少 44 × 44 px。
- **注意**：在某些代理工具中輸入 `\uXXXX` 會被直接轉成字元。範本裡的正規表示式範圍（如 `\u3400-\u9fff`）必須保持跳脫寫法，否則字體子集會混入不需要的字。

## 朗讀相關注意事項

同《心經》，不要回退：

- 手機語音：逐句送出（長文字約 15 秒會中斷）；暫停 = `cancel()` 後記住位置；用遞增的 `token` 讓舊回呼失效；監聽 `voiceschanged`。
- Claude 語音：整句一行送出，可用平台 `pause()`／`resume()`；`not_granted` 時不可自動改用手機語音。開了「朗讀注釋」時經文與注釋要放在同一次 `speak()`，避免沒有使用者手勢。
- 注釋沒有預錄；預錄引擎時注釋改用 Claude 語音或手機語音。
- 預錄只錄經文。改了經文（含校勘）或 `SAY` 就要重新產生錄音再建置。edge-tts 是非公開介面，出現 403 先升級套件；不要用偽造標頭繞過。
- 錄音格式（`tts_edge.py --format`）會影響檔案大小，Artifact 上限 16 MB，見 `SPEC.md` 第 5 節。

## 測試

用 Playwright 在 360 × 740、`device_scale_factor=2`、`has_touch=True` 檢查。可用 `add_init_script` 換成假的 `speechSynthesis`（`speak()` 後立即呼叫 `onend`）來驗證經文→注釋的接續、暫停、停止與「從某段開始」。

Playwright 無法驗證實際聲音、Claude 語音、Android 檔案選擇器與 `downloads` 能力；回報時要明確列出哪些只在模擬環境測過。

## 發布

- Artifact 能力：`{"downloads": true, "tts": {}}`，圖示用「道」字對應的通用詞（如 `book`）。
- 更新既有頁面時帶原本的 Artifact 網址；描寫紀錄依網址存在瀏覽器，換網址等於紀錄消失。
- 小幅修改可直接改已發布頁面，但之後要套回範本。

## 授權

經文與黃元吉注釋為公有領域。霞鶩文楷 TC 採 SIL OFL 1.1，見 `fonts/FONT-LICENSE.md`。
