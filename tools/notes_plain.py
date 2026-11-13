#!/usr/bin/env python3
"""注釋白話（data/plain_notes.json）的起草輔助工具。

注釋白話是黃元吉注釋與自序的每段大意（精簡，不逐句照翻），由 Claude 起草並自行校對。
每段記下原文（已套用校勘）的 SHA-1 前 12 碼 `sha` 與開頭幾個字 `head`；
建置時比對目前原文，不符就停止，須重寫該段大意。

用法（在專案根目錄執行）：
    python tools/notes_plain.py dump 1 10        # 印出第 1～10 章注釋，各段標上段號（起草用）
    python tools/notes_plain.py dump 0           # 印出自序
    python tools/notes_plain.py merge 草稿.json   # 把草稿併入 data/plain_notes.json
    python tools/notes_plain.py check            # 檢查與目前原文一致，列出缺漏

草稿格式：{"0": ["自序第 1 段大意", ""], "1": ["第一章注第 1 段大意", "…"]}
（鍵是章號，自序為 0；陣列依段落順序，空字串表示該段不寫，例如自序落款。）
合併時一律 ok: false；Claude 校對過後用 `merge 草稿.json --ok` 或手動把 ok 改成 true。

plain_notes.json 格式：
{"meta": {...},
 "chapters": {"0": [{"p": 0, "head": "…", "sha": "…", "text": "…", "ok": true}], "1": [...]}}
"""
import hashlib, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import textdata  # noqa: E402

PATH = os.path.join(ROOT, "data", "plain_notes.json")
META = {
    "basis": "黃元吉注釋與自序的每段大意（精簡，不逐句照翻）",
    "scope": "注釋（不含經文附註）與自序；自序落款不寫",
    "drafted_by": "Claude",
    "reviewed_by": "Claude 自行校對（使用者 2026-11-13 決定：自序一起翻、精簡成每段大意）",
    "label": "注釋白話：Claude 依黃元吉注整理大意，未經專家審訂，僅供參考",
}


def sha(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()[:12]


def paragraphs(data):
    out = {0: data["preface"]}
    for c in data["chapters"]:
        out[c["n"]] = c["notes"]
    return out


def load_doc():
    if os.path.exists(PATH):
        return json.load(open(PATH, encoding="utf-8"))
    return {"meta": META, "chapters": {}}


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    data = textdata.load()
    paras = paragraphs(data)
    if a[0] == "dump":
        lo = int(a[1]); hi = int(a[2]) if len(a) > 2 else lo
        for n in range(lo, hi + 1):
            print(f"===== 第 {n} 章 =====" if n else "===== 自序 =====")
            for i, p in enumerate(paras[n]):
                print(f"[{n}.{i}]（{len(p)} 字）{p}\n")
    elif a[0] == "merge":
        draft = json.load(open(a[1], encoding="utf-8"))
        ok = "--ok" in a
        doc = load_doc()
        doc["meta"] = META
        for n, texts in draft.items():
            src = paras[int(n)]
            if len(texts) != len(src):
                sys.exit(f"第 {n} 章：草稿 {len(texts)} 段，原文 {len(src)} 段")
            doc["chapters"][str(int(n))] = [
                {"p": i, "head": src[i][:12], "sha": sha(src[i]), "text": t.strip(), "ok": ok}
                for i, t in enumerate(texts) if t.strip()]
        doc["chapters"] = dict(sorted(doc["chapters"].items(), key=lambda kv: int(kv[0])))
        json.dump(doc, open(PATH, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
        print(f"已併入 {len(draft)} 章 → {PATH}")
    elif a[0] == "check":
        got = textdata.load_plain_notes(data, only_ok=False)
        miss = [n for n in paras if n not in got]
        nchars = sum(len(t) for v in got.values() for t in v.values())
        src = sum(len(p) for n in got for p in paras[n])
        print(f"已有 {len(got)} 章（含自序 0），{sum(len(v) for v in got.values())} 段，"
              f"白話 {nchars} 字／原文 {src} 字（{nchars / max(src, 1):.0%}）")
        if miss:
            print("還沒有：", miss)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
