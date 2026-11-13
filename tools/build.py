#!/usr/bin/env python3
"""建置 index.html：內嵌經文與注釋資料、子集化字體、圖示與預錄音檔。

用法（在專案根目錄執行）：
    pip install fonttools brotli pillow
    python tools/build.py [字體檔路徑]

預設字體檔：fonts/LXGWWenKaiTC-Regular.ttf（完整字體，約 13 MB）。
找不到完整字體時改用 fonts/WenKai-subset.woff2，並列出缺字。
字體只保留範本與 data/（經文、注釋、自序、已校對的經文白話與注釋白話）用到的字元。
"""
import base64, json, os, subprocess, sys, tempfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import textdata  # noqa: E402

TEMPLATE = os.path.join(ROOT, "src", "daodejing.template.html")
OUT = os.path.join(ROOT, "index.html")
FULL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "fonts", "LXGWWenKaiTC-Regular.ttf")
SUBSET = os.path.join(ROOT, "fonts", "WenKai-subset.woff2")
EXTRA = "0123456789〇一二三四五六七八九十第章民國年月日敬書"  # 章名、匯出圖片落款會用到的字
LIMIT = 16 * 1024 * 1024

html = open(TEMPLATE, encoding="utf-8").read()
for ph in ("__FONT_B64__", "__ICON_B64__", "/*__DATA__*/null", "/*__AUDIO__*/null"):
    if ph not in html:
        sys.exit(f"範本缺少 {ph} 預留位置")

# ---- 經文、注釋、自序 ----
data = textdata.load()
payload = {"chapters": [{"n": c["n"], "title": c["title"], "text": c["text"], "inline": c["inline"],
                         "notes": c["notes"]} for c in data["chapters"]],
           "preface": data["preface"]}
plain = textdata.load_plain(data["chapters"])  # 只放已校對（ok）的白話
if plain:
    payload["plain"] = {str(n): v for n, v in plain.items()}
nplain = textdata.load_plain_notes(data)  # 注釋與自序的每段大意（章 0 為自序），只放已校對（ok）的段落
if nplain:
    payload["nplain"] = {str(n): {str(p): t for p, t in v.items()} for n, v in nplain.items()}
pjson = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
print(f"資料：81 章，已套用校勘 {data['corrections']} 條，已校對白話 {sum(len(v) for v in plain.values())} 句、注釋白話 {sum(len(v) for v in nplain.values())} 段，{len(pjson.encode('utf-8')) // 1024} KB")

# ---- 字體 ----
text_all = html + pjson
chars = set(c for c in text_all if ord(c) > 127) | set(EXTRA) | set(chr(c) for c in range(32, 127))
if os.path.exists(FULL):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("".join(sorted(chars)))
        txt = f.name
    subprocess.run(["pyftsubset", FULL, f"--text-file={txt}", "--flavor=woff2",
                    f"--output-file={SUBSET}", "--layout-features=*"], check=True)
    os.unlink(txt)
    src_font = FULL
    print(f"已從完整字體子集化 {len(chars)} 個字元 → {SUBSET}（{os.path.getsize(SUBSET) // 1024} KB）")
else:
    src_font = SUBSET
    print(f"找不到 {FULL}，改用現有子集字體 {SUBSET}")
try:
    from fontTools.ttLib import TTFont
    cmap = TTFont(src_font).getBestCmap()
    missing = sorted(c for c in chars if ord(c) not in cmap and not c.isspace() and ord(c) > 127)
    if missing:
        print("注意：字體沒有這些字，會以手機的備用字體顯示：", "".join(missing))
except Exception as e:
    print("（無法檢查缺字：", e, "）")
html = html.replace("__FONT_B64__", base64.b64encode(open(SUBSET, "rb").read()).decode())

# ---- 主畫面圖示：磁青底、泥金「道」字 ----
ICON = os.path.join(ROOT, "icons", "icon-512.png")
def make_icon():
    from PIL import Image, ImageDraw, ImageFont
    S = 512
    img = Image.new("RGB", (S, S), "#16203A")
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(src_font, int(S * 0.62))
    l, t, r, b = d.textbbox((0, 0), "道", font=font)
    d.text(((S - (r - l)) / 2 - l, (S - (b - t)) / 2 - t), "道", font=font, fill="#D3B169")
    os.makedirs(os.path.dirname(ICON), exist_ok=True)
    img.save(ICON, optimize=True)
try:
    make_icon()
    print(f"已產生圖示 {ICON}（{os.path.getsize(ICON) // 1024} KB）")
except Exception as e:
    if not os.path.exists(ICON):
        sys.exit(f"無法產生圖示（需要 pip install pillow）：{e}")
    print("（無法重新產生圖示，沿用現有檔案：", e, "）")
html = html.replace("__ICON_B64__", base64.b64encode(open(ICON, "rb").read()).decode())
html = html.replace("/*__DATA__*/null", pjson.replace("</", "<\\/"))

# ---- 預錄朗讀：audio/manifest.json 存在時，各章各句音檔以 base64 內嵌（由 tools/tts_edge.py 產生）----
AUDIO = os.path.join(ROOT, "audio")
MANIFEST = os.path.join(AUDIO, "manifest.json")
if os.path.exists(MANIFEST):
    man = json.load(open(MANIFEST, encoding="utf-8"))
    mimes = {".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".webm": "audio/webm", ".m4a": "audio/mp4"}
    chs, total = {}, 0
    for n, items in man["chapters"].items():
        out = []
        for it in items:
            p = os.path.join(AUDIO, it["file"])
            if not os.path.exists(p):
                sys.exit(f"缺少音檔 {p}，請重新執行 tools/tts_edge.py")
            raw = open(p, "rb").read()
            total += len(raw)
            out.append({"id": it["id"], "type": mimes.get(os.path.splitext(p)[1], "audio/mpeg"),
                        "b64": base64.b64encode(raw).decode()})
        chs[n] = out
    rec = {"voice": man.get("voice", ""), "chapters": chs}
    html = html.replace("/*__AUDIO__*/null", json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
    print(f"已內嵌預錄朗讀 {len(chs)} 章（{man.get('voice', '')}，音檔 {total / 1048576:.1f} MB）")
else:
    print("沒有 audio/manifest.json，略過預錄朗讀")

open(OUT, "w", encoding="utf-8", newline="\n").write(html)
size = os.path.getsize(OUT)
print(f"完成：{OUT}（{size / 1048576:.2f} MB）")
if size > LIMIT:
    print("警告：超過 Artifact 16 MB 上限，無法發布")
