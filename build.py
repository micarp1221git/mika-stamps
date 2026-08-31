#!/usr/bin/env python3
"""stamps-data.json から index.html を組み立てる。

⭐ 正は stamps-data.json の1枚だけ。index.html は毎回ここから作り直す。
   （作品名とIDを2箇所に書くと、必ず片方が古くなるため）

使い方:
    python3 build.py          # index.html を書き出す
    python3 build.py --check  # 書き出さず、いまの index.html とズレていないか見るだけ
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "stamps-data.json"
OUT = ROOT / "index.html"

STYLE = """*{margin:0;padding:0;box-sizing:border-box}
body{background:#F7F1E6;color:#22314F;font-family:"Hiragino Sans","Hiragino Kaku Gothic ProN",sans-serif;line-height:1.6}
.wrap{max-width:1040px;margin:0 auto;padding:24px 16px 64px}
header{text-align:center;padding:40px 12px 28px}
header h1{font-size:clamp(24px,5vw,38px);font-weight:800;letter-spacing:.04em}
header h1 span{display:inline-block;border-bottom:6px solid #D9824F;padding-bottom:6px}
header p{margin-top:14px;color:rgba(34,49,79,.75);font-size:15px}
.author-btn{display:inline-block;margin-top:18px;background:#22314F;color:#F7F1E6;padding:10px 22px;border-radius:999px;font-size:14px;font-weight:700;text-decoration:none}
section{margin-top:44px}
h2{font-size:clamp(19px,3.6vw,24px);font-weight:800;display:inline-block;border-bottom:5px solid #D9824F;padding-bottom:4px}
.note{margin-top:8px;font-size:13px;color:rgba(34,49,79,.65)}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-top:18px}
@media(min-width:640px){.grid{grid-template-columns:repeat(3,1fr)}}
@media(min-width:900px){.grid{grid-template-columns:repeat(4,1fr)}}
.card{background:#fff;border-radius:18px;padding:14px;box-shadow:0 2px 10px rgba(34,49,79,.08);text-decoration:none;color:inherit;display:flex;flex-direction:column;gap:10px;transition:transform .15s}
.card:hover{transform:translateY(-3px)}
.thumb{position:relative;background:#F7F1E6;border-radius:12px;padding:10px;display:flex;align-items:center;justify-content:center;min-height:120px}
.thumb img{max-width:100%;height:auto;border-radius:6px}
.badge{position:absolute;top:8px;left:8px;font-size:11px;font-weight:800;padding:3px 9px;border-radius:999px;color:#fff;z-index:1}
.badge.new{background:#D9824F}
.badge.anim{background:#22314F;top:8px;left:auto;right:8px}
.badge.kise{background:#7A9B76}
h3{font-size:14px;font-weight:700;line-height:1.45;flex:1}
.btn{display:block;text-align:center;background:#D9824F;color:#fff;font-size:13px;font-weight:800;padding:9px 0;border-radius:999px}
footer{text-align:center;margin-top:56px;padding-top:28px;border-top:2px solid rgba(34,49,79,.12)}
footer p{font-size:14px;color:rgba(34,49,79,.7)}
footer .author-btn{margin-top:14px}
.copy{margin-top:22px;font-size:12px;color:rgba(34,49,79,.5)}"""


def card(item: dict, d: dict) -> str:
    title = html.escape(item["title"])
    if item.get("kisekae"):
        url, img = item["theme_url"], item["img"]
    else:
        url = d["url_pattern"].replace("<id>", str(item["id"]))
        img = d["img_pattern"].replace("<id>", str(item["id"]))
    badges = ""
    if item.get("new"):
        badges += '<span class="badge new">NEW</span>'
    if item.get("animated"):
        badges += '<span class="badge anim">動くスタンプ</span>'
    if item.get("kisekae"):
        badges += '<span class="badge kise">着せかえ</span>'
    return (
        f'<a class="card" href="{url}" target="_blank" rel="noopener">\n'
        f'      <div class="thumb">{badges}<img src="{img}" alt="{title}" loading="lazy"></div>\n'
        f"      <h3>{title}</h3>\n"
        f'      <span class="btn">LINEストアで見る</span>\n'
        f"    </a>"
    )


def build() -> str:
    d = json.loads(DATA.read_text(encoding="utf-8"))
    total = sum(len(c["items"]) for c in d["categories"])
    secs = []
    for c in d["categories"]:
        note = f'<p class="note">{html.escape(c["note"])}</p>' if c.get("note") else ""
        cards = "\n".join(card(i, d) for i in c["items"])
        secs.append(
            f'<section><h2>{html.escape(c["name"])}</h2>{note}<div class="grid">{cards}</div></section>'
        )
    author = d["author_page"]
    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<title>{html.escape(d["author"])}のLINEスタンプ</title>\n'
        f"<style>\n{STYLE}\n</style></head><body><div class=\"wrap\">\n"
        "<header>\n"
        f'<h1><span>{html.escape(d["author"])}の<br>LINEスタンプ</span></h1>\n'
        f"<p>ぜんぶAIと一緒に作りました。全{total}作品</p>\n"
        f'<a class="author-btn" href="{author}" target="_blank" rel="noopener">作者ページで全部見る</a>\n'
        "</header>\n" + "\n".join(secs) + "\n\n<footer>\n"
        "<p>新作はときどき増えます。</p>\n"
        f'<a class="author-btn" href="{author}" target="_blank" rel="noopener">最新の一覧はこちら</a>\n'
        f'<p class="copy">© 2026 {html.escape(d["author"])}</p>\n'
        "</footer>\n</div></body></html>\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    out = build()
    if args.check:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur == out:
            print("✅ index.html は stamps-data.json と一致しています")
            return 0
        print("⚠️ index.html が stamps-data.json とズレています。`python3 build.py` で作り直してください")
        return 1
    OUT.write_text(out, encoding="utf-8")
    d = json.loads(DATA.read_text(encoding="utf-8"))
    print(f"✅ index.html を書き出しました（{sum(len(c['items']) for c in d['categories'])}作品）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
