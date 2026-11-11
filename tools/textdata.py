"""讀取 data/ 的經文、注釋、自序，並套用使用者確認過的 data/corrections.json。

build.py 與 tts_edge.py 共用，確保網頁與錄音用的是同一份文字。
data/chapters.json、data/notes/、data/preface.txt 由 tools/fetch_notes.py 產生，不手改。

corrections.json 格式：
{"corrections": [
  {"ch": 9, "where": "notes", "from": "幍光養晦", "to": "韜光養晦", "count": 1, "why": "…"},
  {"ch": 52, "where": "text", "from": "…", "to": "…"},
  {"ch": 0, "where": "preface", "from": "…", "to": "…"}
]}
where：text（經文）、notes（注釋）、preface（自序，ch 填 0）。count 為預期出現次數（預設 1），不符就停止。
修改經文（where=text）可能改變該章的描寫字數，已有描寫紀錄時須另寫遷移。
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0003ffff]")
CLAUSE = re.compile(r"[^，。：；！？]+(?:[，。：；！？]」?)?")


def load():
    doc = json.load(open(os.path.join(DATA, "chapters.json"), encoding="utf-8"))
    chapters = []
    for c in doc["chapters"]:
        notes = open(os.path.join(DATA, "notes", f"{c['n']:02d}.txt"), encoding="utf-8").read().strip()
        chapters.append({"n": c["n"], "title": c["title"], "text": c["text"],
                         "inline": c["notes_inline"], "notes": notes})
    preface = open(os.path.join(DATA, "preface.txt"), encoding="utf-8").read().strip()
    applied = apply_corrections(chapters, preface)
    preface = applied.pop("preface")
    for c in chapters:
        c["notes"] = [p.strip() for p in c["notes"].split("\n\n") if p.strip()]
    return {"chapters": chapters, "preface": [p.strip() for p in preface.split("\n\n") if p.strip()],
            "corrections": applied["count"], "source": doc["source"]}


def apply_corrections(chapters, preface):
    path = os.path.join(DATA, "corrections.json")
    out = {"preface": preface, "count": 0}
    if not os.path.exists(path):
        return out
    items = json.load(open(path, encoding="utf-8")).get("corrections", [])
    for it in items:
        where, want = it["where"], it.get("count", 1)
        if where == "preface":
            target = out["preface"]
        else:
            c = chapters[it["ch"] - 1]
            target = c["text"] if where == "text" else c["notes"]
        n = target.count(it["from"])
        if n != want:
            sys.exit(f"corrections.json 不符：第 {it.get('ch')} 章 {where}「{it['from']}」出現 {n} 次，預期 {want} 次")
        new = target.replace(it["from"], it["to"])
        if where == "preface":
            out["preface"] = new
        elif where == "text":
            if c["inline"]:
                sys.exit(f"第 {c['n']} 章經文有附註位置，修改經文前須調整 notes_inline 的位置")
            c["text"] = new
        else:
            c["notes"] = new
        out["count"] += 1
    return out


def clauses(n, title, text):
    """與網頁相同：子句 0 為章名；其後以「，。：；！？」為界。"""
    return ["第" + cn_num(n) + "章　" + title] + CLAUSE.findall(text)


def sentences(cl):
    """句子到「。：！？」為止；章名自成一句。回傳 [(起, 迄)]。"""
    out, i = [(0, 0)], 1
    while i < len(cl):
        j = i
        while j < len(cl) - 1 and not re.search(r"[。：！？]」?$", cl[j]):
            j += 1
        out.append((i, j))
        i = j + 1
    return out


def cn_num(n):
    d = "〇一二三四五六七八九"
    if n < 10:
        return d[n]
    t, u = divmod(n, 10)
    return ("" if t == 1 else d[t]) + "十" + (d[u] if u else "")


def load_plain(chapters, only_ok=True):
    """讀 data/plain.json（經文白話，Claude 起草、使用者審定），並檢查與目前經文一致。

    格式：{"meta": {...}, "chapters": {"1": [{"id": "1-4", "jing": "道可道，…", "text": "…", "q": "疑點", "ok": false}]}}
    id 與預錄相同（整句的子句起迄）；jing 是起草時的經文，與目前經文（已套用校勘）不符就停止。
    回傳 {章: {id: text}}；only_ok 時只取 ok 為 true 的句子。
    """
    path = os.path.join(DATA, "plain.json")
    if not os.path.exists(path):
        return {}
    doc = json.load(open(path, encoding="utf-8"))
    by_n = {c["n"]: c for c in chapters}
    out = {}
    for n, items in doc.get("chapters", {}).items():
        c = by_n.get(int(n))
        if not c:
            sys.exit(f"plain.json：沒有第 {n} 章")
        cl = clauses(c["n"], c["title"], c["text"])
        want = {f"{i}-{j}": "".join(cl[i:j + 1]) for i, j in sentences(cl)[1:]}
        seen = set()
        for it in items:
            sid = it["id"]
            if sid not in want:
                sys.exit(f"plain.json：第 {n} 章沒有句子 {sid}（經文斷句可能改變了）")
            if it["jing"] != want[sid]:
                sys.exit(f"plain.json：第 {n} 章 {sid} 經文不符\n  白話依據：{it['jing']}\n  目前經文：{want[sid]}\n請使用者重審這一句")
            if sid in seen:
                sys.exit(f"plain.json：第 {n} 章 {sid} 重複")
            seen.add(sid)
            if it.get("ok") or not only_ok:
                if it.get("text", "").strip():
                    out.setdefault(int(n), {})[sid] = it["text"].strip()
        if seen and seen != set(want):
            print(f"注意：plain.json 第 {n} 章缺 {len(set(want) - seen)} 句白話")
    return out
