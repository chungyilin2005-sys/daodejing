#!/usr/bin/env python3
"""產生「待確認事項」頁面 review/daodejing-review.html（發布為 claude.ai Artifact 供使用者勾選）。

資料直接取自專案檔案，與文件一致：
- 校勘建議：data/corrections.proposed.json（並從 data/ 擷取前後文）
- 讀音校正表：SPEC.md 3.3 的表格
- 簡繁轉換規則：data/convert_rules.json
- 與王弼本的出入：SOURCES.md 最後一節的表格
- 錄音格式方案：SPEC.md 第 5 節的表格
"""
import json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "tools", "review.template.html")
OUT = os.path.join(ROOT, "review", "daodejing-review.html")


def rd(p):
    return open(os.path.join(ROOT, p), encoding="utf-8").read()


def rows(md, start, stop=None):
    """取出 md 中 start 標記之後（到 stop 之前）第一個表格的資料列。"""
    s = md[md.index(start):]
    if stop:
        s = s[:s.index(stop)]
    out = []
    for line in s.splitlines():
        if line.startswith("|") and not re.match(r"^\|[-| ]+\|$", line):
            out.append([c.strip() for c in line.strip().strip("|").split("|")])
    return out[1:]  # 去掉表頭


chapters = json.load(open(os.path.join(ROOT, "data", "chapters.json"), encoding="utf-8"))["chapters"]
titles = {c["n"]: c["title"] for c in chapters}


def context(ch, where, frm, width=14):
    t = chapters[ch - 1]["text"] if where == "text" else rd(f"data/notes/{ch:02d}.txt")
    i = t.index(frm)
    a, b = max(0, i - width), min(len(t), i + len(frm) + width)
    return [("…" if a else "") + t[a:i].replace("\n", ""), frm, t[i + len(frm):b].replace("\n", "") + ("…" if b < len(t) else "")]


prop = json.load(open(os.path.join(ROOT, "data", "corrections.proposed.json"), encoding="utf-8"))["corrections"]
corr = []
for k, x in enumerate(prop):
    corr.append({"id": f"c{k:02d}", "ch": x["ch"], "title": titles[x["ch"]], "where": x["where"], "from": x["from"],
                 "to": x["to"], "conf": x["conf"], "why": x["why"], "ctx": context(x["ch"], x["where"], x["from"])})

spec = rd("SPEC.md")
say = [{"id": f"s{k:02d}", "orig": r[0], "say": r[1], "read": r[2], "note": r[3]}
       for k, r in enumerate(rows(spec, "#### 讀音校正表", "未經實機試聽"))]
fmt = [{"id": r[0].split("．")[0].split("：")[0].split(".")[0].strip(), "name": r[0], "audio": r[1], "b64": r[2], "total": r[3]}
       for r in rows(spec, "| 方案 | 錄音大小", "試聽樣本")]

rules = json.load(open(os.path.join(ROOT, "data", "convert_rules.json"), encoding="utf-8"))["rules"]
conv = [{"id": f"v{k:02d}", "s": r["s"], "default": r.get("default", ""),
         "cases": [[a, b] for a, b in r.get("cases", {}).items()], "why": r.get("why", "")}
        for k, r in enumerate(rules)]

src = rd("SOURCES.md")
wb = [{"ch": int(r[0]), "ours": r[1], "wb": r[2], "pos": r[3]} for r in rows(src, "## 與王弼本的出入")]

data = {"corr": corr, "say": say, "fmt": fmt, "conv": conv, "wb": wb,
        "source": json.load(open(os.path.join(ROOT, "data", "raw", "source.json"), encoding="utf-8"))}
html = open(TPL, encoding="utf-8").read().replace("/*__DATA__*/null",
                                                   json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8", newline="\n").write(html)
print(f"校勘 {len(corr)}、讀音 {len(say)}、錄音方案 {len(fmt)}、轉換規則 {len(conv)}、王弼本出入 {len(wb)} → {OUT}（{os.path.getsize(OUT)//1024} KB）")
