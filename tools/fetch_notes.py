#!/usr/bin/env python3
"""下載維基文庫《道德經注釋 (黃元吉)》的原始碼（wikitext），解析成 data/。

用法（在專案根目錄執行）：
    pip install opencc
    python tools/fetch_notes.py            # 下載固定版本（OLDID），解析並輸出
    python tools/fetch_notes.py --offline  # 不連網，直接用 data/raw/ 裡已下載的原始碼

來源固定為 OLDID 這一版，確保每次結果相同。原始碼原封不動存在 data/raw/，不修改。

處理步驟：
1. 以 index.php?oldid=…&action=raw 下載原始碼（不抓網頁 HTML），並以 API 確認版本號與頁名。
2. 依「==標題==」分節。第一個標題（自序）之前的蕭天石「例言」不收錄。
3. 每章標題下第一段是 {{Yw|經文}}，其後各段是注釋。
4. 原始碼是簡體字，以 OpenCC s2tw（繁體、台灣字形）轉換，再套用 data/convert_rules.json
   （一對多字依簡體上下文逐字決定，例如「古云」不可轉成「古雲」）。引號 “” ‘’ 改為 「」『』。
5. 經文區塊中的括號附註（如第十七章的版本異文說明）從經文抽出，另存於 notes_inline，
   經文本身只留正文；注釋全文不刪任何字。
6. 檢查：剛好 81 章、章序連續、每章都有經文與注釋、經文總字數合理。不符即停止。

錄入錯字不在這裡改。經使用者確認的錯字放在 data/corrections.json，由 build.py 套用。
"""
import argparse, datetime, hashlib, json, os, re, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAWDIR = os.path.join(DATA, "raw")
TITLE = "道德經注釋 (黃元吉)"
OLDID = 2315999
API = "https://zh.wikisource.org/w/api.php"
RAW_URL = f"https://zh.wikisource.org/w/index.php?oldid={OLDID}&action=raw"
PAGE_URL = "https://zh.wikisource.org/zh-hant/" + urllib.parse.quote(TITLE.replace(" ", "_"))
UA = "daodejing-notes-fetch/1.0 (personal study project; https://github.com/chungyilin2005-sys/daodejing)"
RAWFILE = os.path.join(RAWDIR, f"wikisource-{OLDID}.wiki")

CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn2int(s):
    """一～八十一。"""
    if s == "十":
        return 10
    if "十" in s:
        a, b = s.split("十")
        return (CN[a] if a else 1) * 10 + (CN[b] if b else 0)
    return CN[s]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def download():
    q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "revids": OLDID,
                                "rvprop": "ids|timestamp|size|sha1", "format": "json", "formatversion": 2})
    info = json.loads(get(API + "?" + q))
    page = info["query"]["pages"][0]
    rev = page["revisions"][0]
    if page["title"] != TITLE or rev["revid"] != OLDID:
        sys.exit(f"版本資訊不符：{page['title']} / {rev['revid']}")
    raw = get(RAW_URL)
    if len(raw) != rev["size"]:
        sys.exit(f"下載大小 {len(raw)} 與版本大小 {rev['size']} 不符")
    if hashlib.sha1(raw).hexdigest() != rev["sha1"]:
        sys.exit("下載內容的 SHA-1 與維基文庫紀錄不符")
    os.makedirs(RAWDIR, exist_ok=True)
    open(RAWFILE, "wb").write(raw)
    meta = {"title": TITLE, "page_url": PAGE_URL, "raw_url": RAW_URL, "oldid": OLDID,
            "rev_timestamp": rev["timestamp"], "size": rev["size"], "sha1": rev["sha1"],
            "fetched": datetime.date.today().isoformat()}
    json.dump(meta, open(os.path.join(RAWDIR, "source.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"已下載 oldid={OLDID}（{rev['timestamp']}，{len(raw)} 位元組，SHA-1 相符）")


def converter():
    """簡轉繁：OpenCC s2tw，再依 data/convert_rules.json 按簡體原文上下文逐字修正。"""
    try:
        import opencc
    except ImportError:
        sys.exit("請先安裝：pip install opencc")
    cc = opencc.OpenCC("s2tw")
    rules = json.load(open(os.path.join(DATA, "convert_rules.json"), encoding="utf-8"))["rules"]
    hits = {(r["s"], ctx): 0 for r in rules for ctx in r.get("cases", {})}

    def conv(s):
        t = list(cc.convert(s))
        if len(t) != len(s):
            sys.exit("OpenCC 轉換改變了字數，無法逐字套用規則")
        for r in rules:
            ch = r["s"]
            if "default" in r:
                for i, c in enumerate(s):
                    if c == ch:
                        t[i] = r["default"]
            for ctx, to in r.get("cases", {}).items():
                for m in re.finditer(re.escape(ctx), s):
                    hits[(ch, ctx)] += 1
                    for j in range(m.start(), m.end()):
                        if s[j] == ch:
                            t[j] = to
        out = re.sub(r'"([^"]*)"', r'「\1」', "".join(t))  # 原文少數半形引號
        return out.replace("“", "「").replace("”", "」").replace("‘", "『").replace("’", "』")

    def check():
        unused = [f"{ch}：{ctx}" for (ch, ctx), n in hits.items() if n == 0]
        if unused:
            sys.exit("convert_rules.json 有對不到原文的規則：" + "、".join(unused))
    return conv, check, len(rules)


def paragraphs(block):
    return [p.strip() for p in re.split(r"\n\s*\n", block) if p.strip()]


def parse(src):
    parts = re.split(r"^==([^=\n]+)==\s*$", src, flags=re.M)
    # parts[0] = 第一個標題前（頁首模板與蕭天石例言，不收錄）
    secs = [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]
    preface, chapters = None, []
    for head, body in secs:
        if head.endswith("自序"):
            preface = paragraphs(body)
            continue
        m = re.match(r"^第(.+?)章\s+(.+)$", head)
        if not m:
            sys.exit(f"無法辨認的標題：{head}")
        paras = paragraphs(body)
        if not paras or not paras[0].startswith("{{Yw|") or not paras[0].endswith("}}"):
            sys.exit(f"{head}：第一段不是經文（{{{{Yw|…}}}}）")
        chapters.append({"n": cn2int(m.group(1)), "title": m.group(2).strip(),
                         "jing": paras[0][5:-2], "notes": paras[1:]})
    return preface, chapters


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    if not a.offline or not os.path.exists(RAWFILE):
        download()
    src = open(RAWFILE, encoding="utf-8").read()
    preface, chs = parse(src)

    # ---- 檢查（簡體原文階段）----
    errs = []
    if preface is None:
        errs.append("找不到自序")
    if len(chs) != 81:
        errs.append(f"章數 {len(chs)}，不是 81")
    if [c["n"] for c in chs] != list(range(1, len(chs) + 1)):
        errs.append("章序不連續")
    for c in chs:
        if not c["jing"].strip():
            errs.append(f"第 {c['n']} 章沒有經文")
        if not c["notes"]:
            errs.append(f"第 {c['n']} 章沒有注釋")
        if "{{" in "".join(c["notes"]) or "{{" in c["jing"]:
            errs.append(f"第 {c['n']} 章有未處理的模板")
    if errs:
        sys.exit("解析檢查未通過：\n" + "\n".join(errs))

    conv, check, nrules = converter()
    out = {"preface": conv("\n\n".join(preface))}
    for c in chs:
        k = f"{c['n']:02d}"
        out[k + ".title"] = conv(c["title"])
        out[k + ".jing"] = conv(c["jing"])
        out[k + ".notes"] = conv("\n\n".join(c["notes"]))
    check()

    chapters, total = [], 0
    os.makedirs(os.path.join(DATA, "notes"), exist_ok=True)
    for c in chs:
        k = f"{c['n']:02d}"
        jing_full = out[k + ".jing"]
        # 抽出經文中的括號附註，記下它原本接在經文第幾個字元之後
        inline, text, last = [], "", 0
        for m in re.finditer(r"（[^（）]*）", jing_full):
            text += jing_full[last:m.start()]
            inline.append({"after": len(text), "text": m.group(0)[1:-1]})
            last = m.end()
        text += jing_full[last:]
        chars = len(re.findall(r"[\u3400-\u9fff\U00020000-\U0003ffff]", text))
        total += chars
        chapters.append({"n": c["n"], "title": out[k + ".title"], "text": text,
                         "notes_inline": inline, "chars": chars})
        with open(os.path.join(DATA, "notes", k + ".txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(out[k + ".notes"] + "\n")
    with open(os.path.join(DATA, "preface.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(out["preface"] + "\n")

    if not 4800 <= total <= 5800:
        sys.exit(f"經文總字數 {total} 不在合理範圍（約五千字）")
    for bad in ("肖天石", "蕭天石", "例言"):
        if bad in out["preface"]:
            sys.exit(f"自序中出現「{bad}」，可能誤收例言")

    import opencc
    meta = json.load(open(os.path.join(RAWDIR, "source.json"), encoding="utf-8"))
    doc = {"source": meta, "convert": {"tool": "OpenCC s2tw", "opencc_version": getattr(opencc, "__version__", "?"),
                                       "rules": nrules},
           "total_chars": total, "chapters": chapters}
    with open(os.path.join(DATA, "chapters.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    nchars = sum(len(out[f"{c['n']:02d}.notes"]) for c in chs)
    print(f"完成：81 章，經文 {total} 字，注釋 {nchars} 字元，自序 {len(out['preface'])} 字元 → {DATA}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
