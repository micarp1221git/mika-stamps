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

⭐ 2026-09-18 作り直し（みかさん「スタンプの数がかなり増えてきたので、もっと見やすい一覧ページに。
   商品一覧ページの見やすいものをリサーチして応用して」）。取り込んだのは次の5つ:
   1. **カテゴリが探し方の主役**（買い物サイトの利用者の7割はカテゴリから探す・検索やバナーではない）
      → 「そのほか」60件のごみ箱をやめ、**使う場面**で10カテゴリに分け直した（各カテゴリ5〜32件）。
        カテゴリはページ上部の**チップ**で、件数つき（「スポーツ・応援 22」）。押すとそのカテゴリだけ表示。
   2. **いちばん売れているものを先頭に**（並び順の既定は「売れている順」が最も成績がよい）
      → 先頭は「ぐぬぬちゃん・マンガの言葉」（実売1位のシリーズ）を大きく。その次に「売れてる順」。
   3. **検索とカテゴリは画面上部に貼りつく**（スマホは絞り込みボタンが常に見える状態がよい）
      → 検索バー＋チップの帯を position:sticky に。どこまでスクロールしても1タップで戻れる。
   4. **カードは「画像・名前・値段」だけ**（説明文や「見る」ボタンはカードから外す・カード全体がリンク）
   5. **スマホ2列・PC4列・画像は遅延読み込み・押せる範囲は44px以上**
   参考: suplex.design「Product Listing Page Best Practices」／Limely「UX Best Practices for PLP」／
         LINE STORE の作者ページ（カード＝画像＋作品名だけ）

⭐ コーナー運用（2026-09-01 みかさん・2026-09-18に並びを更新）:
   ・「おすすめ」＝ "recommended": true のちょうど5個（6個以上付けても先頭5個しか出ない）。
     「マンガでしか言わない言葉」は必ず置く。おすすめカードは desc も表示される。
   ・「NEW」＝ "new": true の最新5作品。新作が出たら古いものの new を外す（auto_update.py が自動でやる）。
   ・「うごく」＝ "animated": true 全部。**個数制限なし**。
   ・未承認でおすすめ予定の作品は stamps-data.json の pending_recommended に控えてある。

⭐ 検索バーとランキング（2026-09-11 みかさん「検索バーつけましょう。あとランキングも！」）:
   ・検索＝作品名・ひとこと・カテゴリ名・バッジ（うごく/着せかえ）で絞る（JS・ページ内だけ）。
   ・「🏆 売れてる順」＝上位10。順位だけ出し、売上の数字は出さない。
     元データ＝ ~/line-stickers/documents/sales_snapshot.csv（最新日の yen_cumulative>0 を並べる）。
     CSVが読めるMacでは build のたびに ranking.json（id と順位だけ）を書き直し、読めないMacは ranking.json をそのまま使う。

⭐ カテゴリの割り当て（2026-09-18）:
   ・新作の自動追加は auto_update.py の CATEGORY_RULES（このファイルと同じ10カテゴリ）。
   ・手で直すときは stamps-data.json の categories の中で作品を移すだけ。カテゴリ名を増やすときは
     auto_update.py の CATEGORY_RULES にも同じ名前を足す（片方だけ直すと新作が別の箱に落ちる）。
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
RANKING = ROOT / "ranking.json"
SALES_CSV = pathlib.Path.home() / "line-stickers" / "documents" / "sales_snapshot.csv"
RANK_TOP = 10
FOLD_AT = 8   # カテゴリ節は最初の8件だけ見せ、残りは「すべて見る」で開く（後半がだれないように・2026-09-18みかさん）
SITE_URL = "https://micarp1221git.github.io/mika-stamps/"
HERO_CAT = "😤 ぐぬぬちゃん・マンガの言葉"

STYLE = """*{margin:0;padding:0;box-sizing:border-box}
:root{
  --cream:#FFF6E9; --ink:#33323E; --coral:#FF7A59; --mint:#3FC4B0;
  --sun:#FFC93C; --grape:#8C7AE6; --line:#2A2833; --mute:#6b6577;
}
html{scroll-behavior:smooth}
body{background:var(--cream);color:var(--ink);
  font-family:"Hiragino Maru Gothic ProN","ヒラギノ丸ゴ ProN","Hiragino Sans",sans-serif;
  line-height:1.6;-webkit-text-size-adjust:100%}
.wrap{max-width:1080px;margin:0 auto;padding:0 14px 72px}
a{color:inherit}

/* ---- ヒーロー（短く。すぐ一覧に入れるように） ---- */
header{position:relative;text-align:center;padding:30px 12px 8px;overflow:hidden}
header .dots{position:absolute;inset:0;pointer-events:none;
  background-image:radial-gradient(var(--sun) 3px,transparent 3px),radial-gradient(var(--mint) 3px,transparent 3px);
  background-size:52px 52px,52px 52px;background-position:0 0,26px 26px;opacity:.22}
header h1{position:relative;font-size:clamp(24px,6vw,40px);font-weight:800;letter-spacing:.02em;line-height:1.3}
header h1 em{font-style:normal;display:inline-block;position:relative;padding:0 .1em}
header h1 em::after{content:"";position:absolute;left:0;right:0;bottom:.06em;height:.34em;
  background:var(--sun);border-radius:99px;z-index:-1}
.lead{position:relative;margin-top:10px;font-size:14px;font-weight:700;color:var(--mute)}
.lead b{color:var(--ink)}

/* ---- 貼りつく帯（検索＋カテゴリ） ---- */
.bar{position:sticky;top:0;z-index:30;background:var(--cream);padding:6px 0 4px;margin:0 -14px;
  border-bottom:2px solid rgba(42,40,51,.08)}
.bar.stuck{box-shadow:0 6px 16px rgba(42,40,51,.10)}
.bar .in{max-width:1080px;margin:0 auto;padding:0 14px}
.search{display:flex;align-items:center;gap:8px;max-width:560px;margin:0 auto;
  background:#fff;border:2px solid #d9d2c6;border-radius:12px;padding:4px 6px 4px 12px}
.search:focus-within{border-color:var(--line)}
.search::before{content:"";flex:none;width:18px;height:18px;opacity:.55;
  background:no-repeat center/contain url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2333323E' stroke-width='2.6' stroke-linecap='round'><circle cx='10.5' cy='10.5' r='6.5'/><path d='M15.5 15.5 21 21'/></svg>")}
.search input{flex:1;min-width:0;border:0;outline:0;background:transparent;font:inherit;font-size:16px;font-weight:700;color:var(--ink);height:36px}
.search input::placeholder{color:#a39db0;font-weight:700}
.search input::-webkit-search-cancel-button{-webkit-appearance:none;display:none}
.search .qn{font-size:12.5px;font-weight:800;color:#fff;background:var(--line);border-radius:99px;padding:6px 12px;white-space:nowrap}
.search .qx{border:0;background:var(--sun);color:var(--line);font-weight:800;font-size:16px;width:36px;height:36px;border-radius:99px;cursor:pointer;display:none;flex:none}
.search.on .qx{display:inline-block}
.chips{display:flex;gap:8px;overflow-x:auto;padding:8px 2px 6px;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.chips::-webkit-scrollbar{display:none}
.chip{flex:none;min-height:42px;display:inline-flex;align-items:center;gap:6px;background:#fff;border:2.5px solid var(--line);
  border-radius:99px;padding:0 15px;font:inherit;font-size:14px;font-weight:800;color:var(--ink);cursor:pointer;
  box-shadow:2px 2px 0 var(--line);white-space:nowrap}
.chip small{font-size:11.5px;font-weight:800;color:var(--mute);background:var(--cream);border-radius:99px;padding:1px 7px}
.chip.on{background:var(--line);color:#fff;box-shadow:none;transform:translate(2px,2px)}
.chip.on small{background:rgba(255,255,255,.18);color:#fff}
@media(min-width:900px){.chips{flex-wrap:wrap;justify-content:center;overflow:visible}}

/* ---- セクション ---- */
section{margin-top:38px;scroll-margin-top:130px}
.sec-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
h2{display:inline-block;position:relative;font-size:clamp(19px,4.4vw,24px);font-weight:800;padding:0 .1em;line-height:1.35}
h2::after{content:"";position:absolute;left:0;right:0;bottom:.08em;height:.36em;background:var(--sun);border-radius:99px;z-index:-1;opacity:.9}
h2 small{font-size:13px;font-weight:800;color:var(--mute);margin-left:8px}
.sec-h{margin-top:4px}
section.cat.alt{background:#fff;border-radius:22px;padding:18px 14px 20px;margin-top:34px}
section.cat.alt .thumb{background:var(--cream)}
.note{margin-top:10px;font-size:13.5px;font-weight:700;color:var(--mute)}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:16px}
@media(min-width:640px){.grid{grid-template-columns:repeat(3,1fr);gap:16px}}
@media(min-width:900px){.grid{grid-template-columns:repeat(4,1fr)}}

/* ---- 横1行コーナー（売れてる順/おすすめ/NEW/うごく） ---- */
.row{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(150px,42%);gap:12px;
  margin-top:16px;overflow-x:auto;padding:2px 10px 14px 2px;
  -webkit-overflow-scrolling:touch;scroll-snap-type:x proximity;scrollbar-width:thin}
.row .card{scroll-snap-align:start}
@media(min-width:640px){.row{grid-auto-columns:28%;gap:16px}}
@media(min-width:900px){.row{grid-auto-columns:calc((100% - 64px)/5)}}

/* ---- 先頭の目玉（ぐぬぬちゃん） ---- */
.hero{margin-top:16px;display:grid;gap:12px;grid-template-columns:1fr}
.hero .card.big .thumb{min-height:160px}
.hero .card.big h3{font-size:16px}
@media(max-width:639px){.hero .card.big{flex-direction:row;flex-wrap:wrap;align-items:center}.hero .card.big .thumb{flex:0 0 46%;min-height:0}.hero .card.big h3{flex:1 1 40%;font-size:15px}.hero .card.big .desc{flex:1 1 100%}.hero .card.big .foot{flex:1 1 100%}}
.hero .sub{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
@media(min-width:640px){.hero{grid-template-columns:1.1fr 2fr;gap:16px}.hero .sub{grid-template-columns:repeat(3,1fr);gap:16px}}
@media(min-width:900px){.hero .sub{grid-template-columns:repeat(4,1fr)}}

/* ---- カード（画像・名前・値段だけ。カード全体がリンク） ---- */
.card{position:relative;min-width:0;background:#fff;border:2.5px solid var(--line);border-radius:18px;
  padding:10px;text-decoration:none;color:inherit;display:flex;flex-direction:column;gap:8px;
  box-shadow:4px 4px 0 var(--line);transition:transform .12s ease,box-shadow .12s ease}
.card:hover{transform:translate(-2px,-3px);box-shadow:7px 8px 0 var(--line)}
.card:active{transform:translate(3px,3px);box-shadow:1px 1px 0 var(--line)}
.thumb{position:relative;background:var(--cream);border-radius:12px;padding:10px;
  display:flex;align-items:center;justify-content:center;min-height:128px;overflow:hidden}
.thumb::before{content:"";position:absolute;inset:0;
  background-image:radial-gradient(rgba(51,50,62,.09) 2px,transparent 2px);background-size:14px 14px}
.thumb img{position:relative;max-width:100%;height:auto;border-radius:8px}
.badge{position:absolute;top:7px;font-size:10.5px;font-weight:800;padding:3px 10px;
  border-radius:99px;border:2px solid var(--line);z-index:2;letter-spacing:.02em}
.badge.new{left:7px;background:var(--coral);color:#fff;transform:rotate(-7deg)}
.badge.osusume{left:7px;background:var(--sun);color:var(--line);transform:rotate(-7deg)}
.badge.anim{right:7px;background:var(--mint);color:var(--line)}
.badge.kise{right:7px;background:var(--grape);color:#fff}
.badge.rank{left:7px;background:var(--line);color:var(--sun);transform:rotate(-7deg);font-size:12px}
.badge.rank.r1{background:var(--sun);color:var(--line)}
h3{font-size:13.5px;font-weight:800;line-height:1.45;flex:1;overflow-wrap:anywhere}
.desc{font-size:12px;font-weight:700;color:var(--mute);line-height:1.6}
.foot{display:flex;align-items:center;justify-content:space-between;gap:6px}
.price{font-size:14px;font-weight:800;color:var(--line)}
.price small{font-size:11px;font-weight:700;color:#8a8496}
.go{display:none;font-size:12px;font-weight:800;color:var(--coral);white-space:nowrap}
.card.big .go{display:inline}

.card.more{display:none}
section.open .card.more,body.searching .card.more{display:flex}
.morebtn{display:inline-flex;align-items:center;min-height:44px;margin-top:14px;padding:0 18px;background:#fff;border:2.5px solid var(--line);
  border-radius:99px;font:inherit;font-size:14px;font-weight:800;color:var(--ink);cursor:pointer;box-shadow:2px 2px 0 var(--line)}
.morebtn:active{transform:translate(2px,2px);box-shadow:none}
section.open .morebtn,body.searching .morebtn{display:none}
.card.hide,section.hide{display:none!important}
.noresult{display:none;margin-top:28px;text-align:center;font-weight:800;color:var(--mute)}
.noresult.on{display:block}
.totop{position:fixed;right:14px;bottom:18px;z-index:20;width:46px;height:46px;border-radius:99px;border:2.5px solid var(--line);
  background:#fff;box-shadow:3px 3px 0 var(--line);font-weight:800;font-size:18px;cursor:pointer;display:none}
.totop.on{display:block}

/* ---- フッター ---- */
footer{text-align:center;margin-top:60px;padding:30px 16px;
  background:#fff;border:3px solid var(--line);border-radius:24px;box-shadow:6px 6px 0 var(--line)}
footer p{font-size:15px;font-weight:800}
.author-btn{display:inline-block;margin-top:14px;background:var(--line);color:var(--sun);
  padding:13px 30px;border-radius:99px;font-size:15px;font-weight:800;text-decoration:none;
  border:3px solid var(--line);box-shadow:4px 4px 0 var(--coral)}
.author-btn:active{transform:translate(4px,4px);box-shadow:none}
.copy{margin-top:18px;font-size:12px;font-weight:700;color:#8a8496}"""


SEARCH_JS = r"""(function(){
var q=document.getElementById('q'),qn=document.getElementById('qn'),qx=document.getElementById('qx'),box=document.getElementById('search');
var nores=document.getElementById('noresult'),bar=document.getElementById('bar'),totop=document.getElementById('totop');
var chips=[].slice.call(document.querySelectorAll('.chip'));
var cards=[].slice.call(document.querySelectorAll('.card')),secs=[].slice.call(document.querySelectorAll('section'));
var cat='all';
function norm(t){return (t||'').toLowerCase().replace(/[ァ-ヶ]/g,function(c){return String.fromCharCode(c.charCodeAt(0)-0x60)}).replace(/\s+/g,'')}
function run(){
  var w=norm(q.value);box.classList.toggle('on',!!w);document.body.classList.toggle('searching',!!w);
  var seen={},n=0;
  secs.forEach(function(s){
    var show=(cat==='all')?!s.hasAttribute('data-only'):(s.id===cat);
    s.classList.toggle('hide',!show);
  });
  cards.forEach(function(c){var ok=!w||norm(c.getAttribute('data-s')).indexOf(w)>-1;c.classList.toggle('hide',!ok);
    if(ok&&!c.closest('section').classList.contains('hide')){var id=c.querySelector('img')&&c.querySelector('img').getAttribute('src');if(!seen[id]){seen[id]=1;n++}}});
  if(w){secs.forEach(function(s){if(!s.classList.contains('hide')&&!s.querySelector('.card:not(.hide)'))s.classList.add('hide')});}
  qn.textContent=n+'件';qn.hidden=!(w||cat!=='all');nores.classList.toggle('on',n===0);
}
chips.forEach(function(ch){ch.addEventListener('click',function(){
  cat=ch.getAttribute('data-cat');chips.forEach(function(x){x.classList.toggle('on',x===ch)});
  var sec=document.getElementById(cat);if(sec)sec.classList.add('open');run();
  var y=bar.getBoundingClientRect().top;if(y<0){window.scrollTo({top:window.scrollY+y,behavior:'smooth'})}
  ch.scrollIntoView({block:'nearest',inline:'center',behavior:'smooth'});
})});
[].slice.call(document.querySelectorAll('.morebtn')).forEach(function(b){b.addEventListener('click',function(){var s=document.getElementById(b.getAttribute('data-open'));if(s)s.classList.add('open')})});
q.addEventListener('input',run);qx.addEventListener('click',function(){q.value='';run();q.focus()});
window.addEventListener('scroll',function(){var s=window.scrollY>240;bar.classList.toggle('stuck',window.scrollY>80);totop.classList.toggle('on',s)},{passive:true});
totop.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'})});
})();"""


def price_tag(item: dict) -> str:
    p = item.get("price")
    return f'<span class="price">¥{p}<small>〜</small></span>' if p else ""


def card(item: dict, d: dict, with_desc: bool = False, cat: str = "", rank: int = 0, big: bool = False, more: bool = False) -> str:
    title = html.escape(item["title"])
    stext = " ".join(x for x in [item["title"], item.get("desc", ""), cat,
                                  "うごく" if item.get("animated") else "",
                                  "着せかえ" if item.get("kisekae") else "",
                                  "新作 NEW" if item.get("new") else ""] if x)
    stext = html.escape(stext.replace("\n", " "))
    if item.get("kisekae"):
        url, img = item["theme_url"], item["img"]
    else:
        url = d["url_pattern"].replace("<id>", str(item["id"]))
        img = d["img_pattern"].replace("<id>", str(item["id"]))
    badges = ""
    if rank:
        badges += f'<span class="badge rank r{rank}">{rank}位</span>'
    elif item.get("recommended"):
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
    cls = "card big" if big else ("card more" if more else "card")
    return (
        f'<a class="{cls}" href="{url}" target="_blank" rel="noopener" data-s="{stext}">\n'
        f'      <div class="thumb">{badges}<img src="{img}" alt="{title}" loading="lazy"></div>\n'
        f"      <h3>{title}</h3>\n" + desc +
        f'      <div class="foot">{price_tag(item)}<span class="go">LINEストアで見る →</span></div>\n'
        f"    </a>"
    )


def slug(i: int) -> str:
    return f"cat{i}"


def _norm_title(t: str) -> str:
    return "".join(str(t or "").split()).replace("　", "")


def load_ranking(cats: list) -> list[str]:
    """売れてる順の商品ID（上位10）。CSVが読めればranking.jsonを書き直し、読めなければranking.jsonを使う。"""
    known = {str(it["id"]) for c in cats for it in c["items"] if it.get("id")}
    by_title = {_norm_title(it["title"]): str(it["id"]) for c in cats for it in c["items"] if it.get("id")}
    ids: list[str] = []
    if SALES_CSV.exists():
        import csv
        rows = list(csv.DictReader(SALES_CSV.open(encoding="utf-8")))
        if rows:
            last = max(r["date"] for r in rows)
            day = [r for r in rows if r["date"] == last and _norm_title(r.get("title")) in by_title]
            day.sort(key=lambda r: (-int(r.get("yen_cumulative") or 0), r.get("release", "")))
            ids = [by_title[_norm_title(r["title"])] for r in day if int(r.get("yen_cumulative") or 0) > 0][:RANK_TOP]
            RANKING.write_text(json.dumps({"as_of": last, "ids": ids}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if not ids and RANKING.exists():
        ids = [str(x) for x in json.loads(RANKING.read_text(encoding="utf-8")).get("ids", []) if str(x) in known][:RANK_TOP]
    return ids


def chip(cat_id: str, label: str, n: int, on: bool = False) -> str:
    cls = "chip on" if on else "chip"
    return f'<button type="button" class="{cls}" data-cat="{cat_id}">{html.escape(label)}<small>{n}</small></button>'


def build() -> str:
    d = json.loads(DATA.read_text(encoding="utf-8"))
    cats = d["categories"]
    total = sum(len(c["items"]) for c in cats)
    author = d["author_page"]
    all_items = [it for c in cats for it in c["items"]]

    rank_ids = load_ranking(cats)
    by_id = {str(it["id"]): it for it in all_items if not it.get("kisekae")}
    ranked = [by_id[i] for i in rank_ids if i in by_id]
    reco = [it for it in all_items if it.get("recommended")][:5]
    news = [it for it in all_items if it.get("new")][:5]
    anims = [it for it in all_items if it.get("animated")]

    # ── チップ（件数つき）。順番＝ページの並びと同じ ──
    chips = [chip("all", "すべて", total, on=True)]
    if ranked:
        chips.append(chip("ranking", "🏆 売れてる順", len(ranked)))
    if reco:
        chips.append(chip("osusume", "⭐ おすすめ", len(reco)))
    if news:
        chips.append(chip("shinsaku", "🆕 NEW", len(news)))
    if anims:
        chips.append(chip("ugoku", "🏃 うごく", len(anims)))
    for i, c in enumerate(cats):
        chips.append(chip(slug(i), c["name"], len(c["items"])))

    secs = []

    # ── 先頭の目玉: ぐぬぬちゃん（実売1位のシリーズ）。1つ目を大きく、残りをグリッド ──
    hero_idx = next((i for i, c in enumerate(cats) if c["name"] == HERO_CAT), None)
    if hero_idx is not None and cats[hero_idx]["items"]:
        hc = cats[hero_idx]
        order = {i: n for n, i in enumerate(rank_ids)}
        items = sorted(hc["items"], key=lambda it: order.get(str(it.get("id")), 999))
        first, rest = items[0], items[1:]
        note = f'<p class="note">{html.escape(hc["note"])}</p>' if hc.get("note") else ""
        secs.append(
            f'<section id="{slug(hero_idx)}"><div class="sec-h"><h2>{html.escape(hc["name"])}<small>{len(hc["items"])}</small></h2></div>{note}'
            f'<div class="hero">{card(first, d, with_desc=True, cat=hc["name"], big=True)}'
            f'<div class="sub">{"".join(card(it, d, cat=hc["name"]) for it in rest)}</div></div></section>'
        )

    # ── 🏆 売れてる順（上位10・横1行・順位だけ） ──
    if ranked:
        cards = "\n".join(card(it, d, rank=n + 1) for n, it in enumerate(ranked))
        secs.append('<section id="ranking" data-only="1"><div class="sec-h"><h2>🏆 売れてる順<small>10</small></h2></div>'
                    f'<div class="row">{cards}</div></section>')

    # ── ⭐ おすすめ（ちょうど5個・横1行） ──
    if reco:
        cards = "\n".join(card(it, d, with_desc=True) for it in reco)
        secs.append('<section id="osusume" data-only="1"><div class="sec-h"><h2>⭐ おすすめ</h2></div>'
                    f'<div class="row">{cards}</div></section>')

    # ── 🆕 NEW（最新5作品・横1行） ──
    if news:
        cards = "\n".join(card(it, d) for it in news)
        secs.append('<section id="shinsaku" data-only="1"><div class="sec-h"><h2>🆕 NEW</h2></div>'
                    f'<div class="row">{cards}</div></section>')

    # ── 🏃 うごく（個数制限なし・横1行） ──
    if anims:
        cards = "\n".join(card(it, d) for it in anims)
        secs.append('<section id="ugoku" data-only="1"><div class="sec-h"><h2>🏃 うごくスタンプ<small>' + str(len(anims)) + '</small></h2></div>'
                    f'<div class="row">{cards}</div></section>')

    # ── カテゴリ別の全作品（目玉カテゴリは上で出したので飛ばす） ──
    alt_i = 0
    for i, c in enumerate(cats):
        if i == hero_idx:
            continue
        note = f'<p class="note">{html.escape(c["note"])}</p>' if c.get("note") else ""
        cards = "\n".join(card(it, d, cat=c["name"], more=(n >= FOLD_AT)) for n, it in enumerate(c["items"]))
        rest = len(c["items"]) - FOLD_AT
        morebtn = f'<button type="button" class="morebtn" data-open="{slug(i)}">すべて見る（あと{rest}件）</button>' if rest > 0 else ""
        alt_i += 1
        cls = "cat alt" if alt_i % 2 == 0 else "cat"
        secs.append(
            f'<section id="{slug(i)}" class="{cls}"><div class="sec-h"><h2>{html.escape(c["name"])}<small>{len(c["items"])}</small></h2></div>{note}'
            f'<div class="grid">{cards}</div>{morebtn}</section>'
        )

    og_img = d["img_pattern"].replace("<id>", str(first["id"])) if hero_idx is not None else ""
    title = f'{d["author"]}のLINEスタンプ'
    return (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f'<title>{html.escape(title)}</title>\n'
        f'<meta name="description" content="{html.escape(d["author"])}のLINEスタンプ、ぜんぶで{total}作品。ねこ、方言、スポーツの応援、仕事の返事まで。">\n'
        f'<meta property="og:title" content="{html.escape(title)}">\n'
        f'<meta property="og:description" content="ぜんぶで{total}作品。ねこも、方言も、言いにくいひとことも。">\n'
        f'<meta property="og:image" content="{og_img}">\n'
        f'<meta property="og:url" content="{SITE_URL}">\n'
        '<meta name="twitter:card" content="summary">\n'
        f"<style>\n{STYLE}\n</style></head><body><div class=\"wrap\">\n"
        '<header><div class="dots"></div>\n'
        f'<h1>{html.escape(d["author"])}の<br><em>LINEスタンプ</em></h1>\n'
        f'<p class="lead">ぜんぶで <b>{total}</b> 作品<br>ねこも、方言も、言いにくいひとことも。</p>\n'
        "</header>\n"
        '<div class="bar" id="bar"><div class="in">'
        '<form class="search" id="search" role="search" onsubmit="return false">'
        '<input id="q" type="search" placeholder="スタンプをさがす（ねこ・広島弁・おはよう…）" autocomplete="off" aria-label="スタンプをさがす">'
        '<span class="qn" id="qn" hidden></span><button type="button" class="qx" id="qx" aria-label="検索をクリア">×</button></form>\n'
        f'<div class="chips" id="chips">{"".join(chips)}</div>'
        "</div></div>\n" + "\n".join(secs) + "\n"
        '<p class="noresult" id="noresult">見つかりませんでした。別の言葉でどうぞ 🐾</p>'
        "\n\n<footer>\n"
        "<p>新作はときどき増えます 🐾</p>\n"
        f'<a class="author-btn" href="{author}" target="_blank" rel="noopener">LINEストアの作者ページ</a>\n'
        '<p class="copy">© Experisent</p>\n'
        "</footer>\n</div>\n"
        '<button type="button" class="totop" id="totop" aria-label="いちばん上へ">↑</button>\n'
        "<script>\n" + SEARCH_JS + "\n</script></body></html>\n"
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
