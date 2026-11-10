#!/usr/bin/env python3
"""用 edge-tts（Edge「大聲朗讀」的微軟語音）把經文逐章逐句合成，存到 audio/，
供 build.py 內嵌成「預錄朗讀」。只錄經文，不錄注釋。不需要金鑰。

用法（在專案根目錄執行）：
    pip install edge-tts
    python tools/tts_edge.py --format opus-24k
    其他選項：
        --voice zh-TW-HsiaoYuNeural   聲音（預設曉雨；另有 zh-TW-HsiaoChenNeural 曉臻、zh-TW-YunJheNeural 雲哲）
        --rate -10%                   語速（預設 -10%）
        --pitch +0Hz                  音高
        --format mp3-48k              mp3-48k（edge-tts 原檔，不轉檔）、mp3-32k、mp3-24k、opus-24k、opus-16k
                                      除 mp3-48k 外都需要 ffmpeg
        --only 20                     只重做第 20 章（可重複指定）

注意：edge-tts 使用的是 Edge 的非公開介面，不是微軟正式授權的服務，可能隨時改變或失效。
若出現 403，先升級 edge-tts；不要用偽造標頭等方式繞過。

經文（已套用 data/corrections.json）、句子切法與讀音校正表（SAY，從範本讀出）都與網頁一致。
產生後執行 python tools/build.py 重建 index.html。
"""
import argparse, asyncio, json, os, re, shutil, subprocess, sys, tempfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import textdata  # noqa: E402

TEMPLATE = os.path.join(ROOT, "src", "daodejing.template.html")
OUTDIR = os.path.join(ROOT, "audio")
FORMATS = {  # 名稱: (副檔名, ffmpeg 參數；None 表示保留原檔)
    "mp3-48k": (".mp3", None),
    "mp3-32k": (".mp3", ["-ac", "1", "-ar", "24000", "-b:a", "32k"]),
    "mp3-24k": (".mp3", ["-ac", "1", "-ar", "22050", "-b:a", "24k"]),
    "opus-24k": (".webm", ["-ac", "1", "-c:a", "libopus", "-b:a", "24k", "-application", "voip"]),
    "opus-16k": (".webm", ["-ac", "1", "-c:a", "libopus", "-b:a", "16k", "-application", "voip"]),
}


def read_say():
    html = open(TEMPLATE, encoding="utf-8").read()
    src = re.search(r"var SAY=\[(.*?)\n\];", html, re.S).group(1)
    return re.findall(r'\[/(.+?)/g,"(.*?)"\]', src)


def spoken(text, say):
    for pat, rep in say:
        text = re.sub(pat, rep, text)
    return text


async def synth(text, path, voice, rate, pitch):
    import edge_tts
    err = "音檔是空的"
    for attempt in range(4):
        try:
            await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(path)
            if os.path.getsize(path) > 0:
                return
        except Exception as e:
            err = e
        await asyncio.sleep(2 * (attempt + 1))
    sys.exit(f"產生失敗：{path}（{err}）")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="zh-TW-HsiaoYuNeural")
    ap.add_argument("--rate", default="-10%")
    ap.add_argument("--pitch", default="+0Hz")
    ap.add_argument("--format", default="mp3-48k", choices=sorted(FORMATS))
    ap.add_argument("--only", type=int, action="append")
    a = ap.parse_args()
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        sys.exit("請先安裝：pip install edge-tts")
    ext, ff = FORMATS[a.format]
    if ff and not shutil.which("ffmpeg"):
        sys.exit("這個格式需要 ffmpeg")

    say = read_say()
    data = textdata.load()
    os.makedirs(OUTDIR, exist_ok=True)
    man_path = os.path.join(OUTDIR, "manifest.json")
    old = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else {}
    if a.only and old.get("format") not in (None, a.format):
        sys.exit(f"現有錄音是 {old.get('format')}，--only 時格式要相同")
    chapters = dict(old.get("chapters", {})) if a.only else {}
    tmp = tempfile.mkdtemp()
    for c in data["chapters"]:
        n = c["n"]
        cl = textdata.clauses(n, c["title"], c["text"])
        items = []
        for k, (i, j) in enumerate(textdata.sentences(cl)):
            fname = f"{n:02d}/{k:02d}_{i}-{j}{ext}"
            items.append({"id": f"{i}-{j}", "file": fname})
            if a.only and n not in a.only:
                continue
            text = f"第{textdata.cn_num(n)}章，{c['title']}。" if i == 0 else "".join(cl[i:j + 1])
            text = spoken(text, say)
            path = os.path.join(OUTDIR, fname)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if ff:
                raw = os.path.join(tmp, "raw.mp3")
                await synth(text, raw, a.voice, a.rate, a.pitch)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw] + ff + [path], check=True)
            else:
                await synth(text, path, a.voice, a.rate, a.pitch)
        chapters[str(n)] = items
        if not a.only or n in a.only:
            print(f"第 {n} 章：{len(items)} 句")
    manifest = {"voice": a.voice, "rate": a.rate, "pitch": a.pitch, "format": a.format,
                "source": "edge-tts", "chapters": chapters}
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"完成 → {OUTDIR}。接著執行 python tools/build.py")


if __name__ == "__main__":
    asyncio.run(main())
