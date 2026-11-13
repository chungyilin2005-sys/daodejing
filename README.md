# 道德經

《道德經》讀誦與描寫網頁，附黃元吉《道德經注釋》。單一 HTML 檔，主要在 Android 手機的 Chrome 上使用。

- **讀誦**：81 章，直排或橫排，逐句標亮朗讀；可選預錄、Claude 語音或手機語音。每章可展開黃元吉注釋，也可接著朗讀注釋。另有黃元吉自序。
- **白話**：經文逐句白話（依黃元吉注意譯，由 Claude 撰寫，未經專家審訂，僅供參考），可選逐句對照或放在章末，也可以接在經文後朗讀。
- **注釋白話**：黃元吉注釋與自序每段的大意（由 Claude 整理，未經專家審訂，僅供參考），可與原文對照，或只看白話。
- **描寫**：用手指一字一字描寫經文（共 5,304 字），紀錄存在瀏覽器；整篇依章分組，可把每章存成朱絲欄圖片。
- **外觀**：日間（宣紙與墨）、夜間（磁青紙配泥金字）。

直接用瀏覽器開啟 `index.html` 就能使用。每次更新了什麼見 [CHANGELOG.md](CHANGELOG.md)，待確認的事見 [TODO.md](TODO.md)。

## 開發

只改 `src/daodejing.template.html`，再建置：

```bash
pip install fonttools brotli pillow opencc
python tools/build.py
```

重新取得注釋資料：`python tools/fetch_notes.py`（固定維基文庫 oldid 2315999）。

規格見 [SPEC.md](SPEC.md)，資料來源、簡繁轉換與校勘見 [SOURCES.md](SOURCES.md)，修改規則見 [AGENTS.md](AGENTS.md)。

## 授權

經文與黃元吉注釋（清光緒十年刊）為公有領域，取自維基文庫。字體為霞鶩文楷 TC，採 SIL Open Font License 1.1，見 [fonts/FONT-LICENSE.md](fonts/FONT-LICENSE.md)。
