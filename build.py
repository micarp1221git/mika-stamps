#!/usr/bin/env python3
"""stamps-data.json から index.html を組み立てる。

⭐ 正は stamps-data.json の1枚だけ。index.html は毎回ここから作り直す。
   （作品名とIDを2箇所に書くと、必ず片方が古くなるため）

使い方:
    python3 build.py          # index.html を書き出す
    python3 build.py --check  # 書き出さず、いまの index.html とズレていないか見るだけ

⚠️ 書かないもの（2026-08-31 みかさん）:
   ・「AIと一緒に作りました」系（AIを嫌がる人がいるので、わざわざ書かない）
   ・「大人気」「バズった」等の事実でない言葉
   ・コピーライトの年（© Experisent だけ）

⭐ コーナー運用（2026-09-01 みかさん・同日夜に更新）:
   ・上3コーナー（おすすめ／NEW／うごく）は**横1行のスクロール列**。PC幅では5個がちょうど収まる
     （「5個にすると列がはみ出ちゃう」対策。グリッドだと5個目が折り返して1個だけはみ出るため）。
   ・「おすすめ」＝一番上・**ちょうど5個**（"recommended": true。6個以上付けても先頭5個しか出ない）。
     「マンガでしか言わない言葉」は必ず置く。おすすめカードは desc も表示される。
   ・「NEW」＝ "new": true の最新5作品。新作が出たら古いものの new を外す。
   ・「うごく」＝ "animated": true 全部。**個数制限なし**（今後も増える前提・2026-09-01みかさん）。
   ・その下に従来どおりカテゴリ別の全作品一覧（こちらは通常グリッド）。
   ・未承認でおすすめ予定の作品は stamps-data.json の pending_recommended に控えてある
     （承認されて items に足すとき recommended を付ける）。
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
:root{
  --cream:#FFF6E9; --ink:#33323E; --coral:#FF7A59; --mint:#3FC4B0;
  --sun:#FFC93C; --grape:#8C7AE6; --line:#2A2833;
}
body{background:var(--cream);color:var(--ink);
  font-family:"Hiragino Maru Gothic ProN","ヒラギノ丸ゴ ProN","Hiragino Sans",sans-serif;
  line-height:1.6;-webkit-text-size-adjust:100%}
.wrap{max-width:1080px;margin:0 auto;padding:0 16px 72px}

/* ---- ヒーロー ---- */
header{position:relative;text-align:center;padding:44px 12px 30px;overflow:hidden}
header .dots{position:absolute;inset:0;pointer-events:none;
  background-image:radial-gradient(var(--sun) 3px,transparent 3px),radial-gradient(var(--mint) 3px,transparent 3px);
  background-size:52px 52px,52px 52px;background-position:0 0,26px 26px;opacity:.28}
header h1{position:relative;font-size:clamp(26px,6.4vw,46px);font-weight:800;letter-spacing:.02em;line-height:1.35}
header h1 em{font-style:normal;display:inline-block;position:relative;padding:0 .1em}
header h1 em::after{content:"";position:absolute;left:0;right:0;bottom:.06em;height:.34em;
  background:var(--sun);border-radius:99px;z-index:-1}
.count{position:relative;display:inline-flex;align-items:center;gap:8px;margin-top:16px;
  background:var(--line);color:#fff;border-radius:99px;padding:8px 20px;font-size:14px;font-weight:800}
.count b{color:var(--sun);font-size:19px}
.lead{position:relative;margin-top:14px;font-size:15px;font-weight:700;color:#6b6577}
.chips{position:relative;display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:20px}
.chips a{background:#fff;border:2.5px solid var(--line);border-radius:99px;padding:7px 15px;
  font-size:13.5px;font-weight:800;color:var(--ink);text-decoration:none;
  box-shadow:2px 2px 0 var(--line)}
.chips a:active{transform:translate(2px,2px);box-shadow:none}

/* ---- セクション ---- */
section{margin-top:46px;scroll-margin-top:16px}
h2{display:inline-block;font-size:clamp(19px,4vw,25px);font-weight:800;
  background:#fff;border:3px solid var(--line);border-radius:99px;padding:7px 20px;
  box-shadow:4px 4px 0 var(--line)}
.note{margin-top:12px;font-size:13.5px;font-weight:700;color:#6b6577}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-top:20px}
@media(min-width:640px){.grid{grid-template-columns:repeat(3,1fr);gap:18px}}
@media(min-width:900px){.grid{grid-template-columns:repeat(4,1fr)}}

/* ---- 横1行コーナー（おすすめ/NEW/うごく）。PC幅で5個ぴったり・あふれた分は横スクロール ---- */
.row{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(160px,44%);gap:14px;
  margin-top:20px;overflow-x:auto;padding:2px 10px 16px 2px;
  -webkit-overflow-scrolling:touch;scroll-snap-type:x proximity;scrollbar-width:thin}
.row .card{scroll-snap-align:start}
@media(min-width:640px){.row{grid-auto-columns:28%;gap:18px}}
@media(min-width:900px){.row{grid-auto-columns:calc((100% - 72px)/5)}}

/* ---- カード ---- */
.card{position:relative;min-width:0;background:#fff;border:3px solid var(--line);border-radius:20px;
  padding:12px;text-decoration:none;color:inherit;display:flex;flex-direction:column;gap:9px;
  box-shadow:5px 5px 0 var(--line);transition:transform .12s ease,box-shadow .12s ease}
.card:hover{transform:translate(-2px,-3px);box-shadow:8px 9px 0 var(--line)}
.card:active{transform:translate(3px,3px);box-shadow:1px 1px 0 var(--line)}
.thumb{position:relative;background:var(--cream);border-radius:14px;padding:10px;
  display:flex;align-items:center;justify-content:center;min-height:132px;overflow:hidden}
.thumb::before{content:"";position:absolute;inset:0;
  background-image:radial-gradient(rgba(51,50,62,.09) 2px,transparent 2px);background-size:14px 14px}
.thumb img{position:relative;max-width:100%;height:auto;border-radius:8px}
.badge{position:absolute;top:7px;font-size:10.5px;font-weight:800;padding:3px 10px;
  border-radius:99px;border:2px solid var(--line);z-index:2;letter-spacing:.02em}
.badge.new{left:7px;background:var(--coral);color:#fff;transform:rotate(-7deg)}
.badge.anim{right:7px;background:var(--mint);color:var(--line)}
.badge.kise{right:7px;background:var(--grape);color:#fff}
h3{font-size:14px;font-weight:800;line-height:1.45;flex:1;overflow-wrap:anywhere}
.desc{font-size:12px;font-weight:700;color:#6b6577;line-height:1.6}
.badge.osusume{left:7px;background:var(--sun);color:var(--line);transform:rotate(-7deg)}
.foot{display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:wrap}
.price{font-size:15px;font-weight:800;color:var(--line)}
.price small{font-size:11px;font-weight:700;color:#8a8496}
.btn{background:var(--coral);color:#fff;font-size:12.5px;font-weight:800;
  padding:7px 13px;border-radius:99px;border:2px solid var(--line);white-space:nowrap}

/* ---- フッター ---- */
footer{text-align:center;margin-top:60px;padding:32px 16px;
  background:#fff;border:3px solid var(--line);border-radius:24px;box-shadow:6px 6px 0 var(--line)}
footer p{font-size:15px;font-weight:800}
.author-btn{display:inline-block;margin-top:16px;background:var(--line);color:var(--sun);
  padding:13px 30px;border-radius:99px;font-size:15px;font-weight:800;text-decoration:none;
  border:3px solid var(--line);box-shadow:4px 4px 0 var(--coral)}
.author-btn:active{transform:translate(4px,4px);box-shadow:none}
.copy{margin-top:20px;font-size:12px;font-weight:700;color:#8a8496}"""


def price_tag(item: dict) -> str:
    p = item.get("price")
    return f'<span class="price">¥{p}<small>〜</small></span>' if p else ""


def card(item: dict, d: dict, with_desc: bool = False) -> str:
    title = html.escape(item["title"])
    if item.get("kisekae"):
        url, img = item["theme_url"], item["img"]
    else:
        url = d["url_pattern"].replace("<id>", str(item["id"]))
        img = d["img_pattern"].replace("<id>", str(item["id"]))
    badges = ""
    if item.get("recommended"):
        badges += '<span class="badge osusume">おすすめ</span>'
    elif item.get("new"):
        badges += '<span class="badge new">NEW</span>'
    if item.get("animated"):
        badges += '<span class="badge anim">うごく</span>'
    if item.get("kisekae"):
        badges += '<span class="badge kise">着せかえ</span>'
    desc = ""
    if with_desc and item.get("desc"):
        desc = f'      <p class="desc">{html.escape(item["desc"])}</p>\n'
    return (
        f'<a class="card" href="{url}" target="_blank" rel="noopener">\n'
        f'      <div class="thumb">{badges}<img src="{img}" alt="{title}" loading="lazy"></div>\n'
        f"      <h3>{title}</h3>\n" + desc +
        f'      <div class="foot">{price_tag(item)}<span class="btn">見てみる →</span></div>\n'
        f"    </a>"
    )


def slug(i: int) -> str:
    return f"cat{i}"


def build() -> str:
    d = json.loads(DATA.read_text(encoding="utf-8"))
    cats = d["categories"]
    total = sum(len(c["items"]) for c in cats)
    author = d["author_page"]

    chips = '<a href="#osusume">⭐ おすすめ</a><a href="#shinsaku">🆕 NEW</a><a href="#ugoku">🏃 うごく</a>' + "".join(
        f'<a href="#{slug(i)}">{html.escape(c["name"])}</a>' for i, c in enumerate(cats)
    )
    secs = []

    # ⭐ おすすめ（ちょうど5個・一番上・横1行）
    reco = [it for c in cats for it in c["items"] if it.get("recommended")][:5]
    if reco:
        cards = "\n".join(card(it, d, with_desc=True) for it in reco)
        secs.append(
            '<section id="osusume"><h2>⭐ おすすめ</h2>'
            f'<div class="row">{cards}</div></section>'
        )

    # 🆕 NEW（最新5作品・横1行）
    news = [it for c in cats for it in c["items"] if it.get("new") and not it.get("recommended")][:5]
    if news:
        cards = "\n".join(card(it, d) for it in news)
        secs.append(
            '<section id="shinsaku"><h2>🆕 NEW</h2>'
            f'<div class="row">{cards}</div></section>'
        )

    # 🏃 うごくスタンプ（NEWの次・個数制限なし・横1行スクロール）
    anims = [it for c in cats for it in c["items"] if it.get("animated")]
    if anims:
        cards = "\n".join(card(it, d) for it in anims)
        secs.append(
            '<section id="ugoku"><h2>🏃 うごくスタンプ</h2>'
            f'<div class="row">{cards}</div></section>'
        )
    for i, c in enumerate(cats):
        note = f'<p class="note">{html.escape(c["note"])}</p>' if c.get("note") else ""
        cards = "\n".join(card(it, d) for it in c["items"])
        secs.append(
            f'<section id="{slug(i)}"><h2>{html.escape(c["name"])}</h2>{note}'
            f'<div class="grid">{cards}</div></section>'
        )

    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<title>{html.escape(d["author"])}のLINEスタンプ</title>\n'
        f"<style>\n{STYLE}\n</style></head><body><div class=\"wrap\">\n"
        '<header><div class="dots"></div>\n'
        f'<h1>{html.escape(d["author"])}の<br><em>LINEスタンプ</em></h1>\n'
        f'<div class="count">ぜんぶで <b>{total}</b> 作品</div>\n'
        '<p class="lead">ねこも、方言も、言いにくいひとことも。</p>\n'
        f'<div class="chips">{chips}</div>\n'
        "</header>\n" + "\n".join(secs) + "\n\n<footer>\n"
        "<p>新作はときどき増えます 🐾</p>\n"
        f'<a class="author-btn" href="{author}" target="_blank" rel="noopener">ぜんぶ見る</a>\n'
        '<p class="copy">© Experisent</p>\n'
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
