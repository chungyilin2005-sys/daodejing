#!/usr/bin/env python3
"""產生白話審閱頁 review/plain-review.html（發布為 claude.ai Artifact，capabilities {db:{}}）。

資料取自 data/plain.json（已起草的章）與 data/ 的經文、黃元吉注（已套用校勘）。
使用者在頁面上逐句選「通過」或「要改」（可寫意見或直接改寫），決定存在 Artifact 的 db：
    文件 plain/review = {s: {"章:句id": {v: "ok"|"edit", note}}, note, updated}
Claude 用 ArtifactData 讀取後，把通過的句子在 plain.json 標 ok: true，要改的依意見修改後重新產生此頁。
"""
import json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import textdata  # noqa: E402

TPL = os.path.join(ROOT, "tools", "plain_review.template.html")
OUT = os.path.join(ROOT, "review", "plain-review.html")

data = textdata.load()
textdata.load_plain(data["chapters"], only_ok=False)  # 先檢查 plain.json 與經文一致
doc = json.load(open(os.path.join(ROOT, "data", "plain.json"), encoding="utf-8"))
by_n = {c["n"]: c for c in data["chapters"]}
chs = []
for n, items in doc["chapters"].items():
    c = by_n[int(n)]
    chs.append({"n": c["n"], "title": c["title"], "notes": c["notes"],
                "s": [{"id": it["id"], "jing": it["jing"], "text": it["text"], "q": it.get("q", ""),
                       "ok": bool(it.get("ok"))} for it in items]})
payload = {"meta": doc.get("meta", {}), "chapters": chs}
html = open(TPL, encoding="utf-8").read().replace(
    "/*__DATA__*/null", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8", newline="\n").write(html)
total = sum(len(c["s"]) for c in chs)
done = sum(1 for c in chs for s in c["s"] if s["ok"])
print(f"{len(chs)} 章、{total} 句（已審定 {done}）→ {OUT}（{os.path.getsize(OUT) // 1024} KB）")
