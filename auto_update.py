#!/usr/bin/env python3
"""販売中になった新作スタンプを、まとめページへ自動で追加する。

みかさん2026-08-31「新しいのが承認されてたんだけど、自動で追加されないの?
言わなくても自動で追加されるようにしておいて」→ この指示が、このスクリプトの公開許可。
（対象は「みかさん自身の作品が販売中になったら、みかさんのカタログページに載せる」だけ。
  それ以外のものは何も公開しない。）

やること（毎日1回・launchd）:
  1. LINE Creators Market の管理画面から「販売中」の作品名を読む（保存済みログイン・読み取りのみ）
  2. LINEストアの作者ページから 作品名→商品ID を取る（公開ページ）
  3. stamps-data.json に無い販売中の作品があれば、カテゴリを推定して追加
  4. build.py でページを作り直し、commit + push（GitHub Pagesに反映）
  5. 何をしたかを auto_update.log に残し、追加があればDiscordのメイン部屋に1行知らせる

⚠️ ログインが切れていたら「何もせず、切れていると知らせる」（黙って0件と言わない）。
⚠️ 名前の照合は空白・改行を全部除いた形で行う（管理画面は名前が折り返されるため）。
"""

from __future__ import annotations

import datetime
import json
import pathlib
import re
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "stamps-data.json"
# 2026-09-17みかさん「国違いのスタンプは、一覧ページには載せないようにしてほしい」
SKIP_LIST = ROOT / "一覧に載せない.txt"
LOG = ROOT / "auto_update.log"
STICKERS = pathlib.Path.home() / "line-stickers"
AUTH = STICKERS / ".auth" / "line-creators-storage-state.json"
DISCORD_ENV = pathlib.Path.home() / ".claude" / "channels" / "discord" / ".env"
MAIN_ROOM = "1522158006626680923"

sys.path.insert(0, str(STICKERS / "scripts"))


def log(msg: str) -> None:
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


SAY = pathlib.Path.home() / "git/MIKA_VAULT/06_Projects/自律稼働/tools/discord-say.py"


def notify(text: str) -> None:
    """Discordのメイン部屋へ1行。失敗しても本体は止めない。

    🚨 2026-09-15 修正: 自分でBot APIを叩く形をやめて discord-say.py に寄せた。
      旧実装は urllib で /api/v10/channels/... を直接叩いており、**403 Forbidden で落ち続けていた**
      （9/13〜9/15の実測で毎回。そのあいだ「Creators Marketのログインが切れています」の警告が
      1通もみかさんに届いていなかった）。
    ⭐ 知らせ方は1つの道具に寄せる。**知らせる経路が壊れると、壊れたことも知らせられない。**
    """
    try:
        subprocess.run(["/usr/bin/python3", str(SAY), MAIN_ROOM, "-"],
                       input=text, text=True, timeout=60, check=False)
    except Exception as e:  # noqa: BLE001
        log(f"Discord通知に失敗(本体は続行): {e}")


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def selling_names() -> list[str] | None:
    """管理画面から販売中の作品名。ログイン切れならNone。"""
    from playwright.sync_api import sync_playwright

    env = {}
    for l in (STICKERS / ".auth" / "line-creators.env").read_text(encoding="utf-8").splitlines():
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1)
            env[k.strip()] = v.strip()
    mid = env["LINE_CREATOR_MYPAGE_ID"]
    names: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        c = b.new_context(storage_state=str(AUTH), locale="ja-JP")
        pg = c.new_page()
        for pageno in range(1, 11):
            pg.goto(
                f"https://creator.line.me/my/{mid}/sticker/?status=all&query=&page={pageno}",
                wait_until="networkidle", timeout=60000,
            )
            pg.wait_for_timeout(2500)
            body = pg.inner_text("body")
            if "line.me/oauth" in pg.url or "/login" in pg.url or "ログアウト" not in body:
                b.close()
                return None
            head_end = body.rfind("リジェクト")
            tail = body[head_end + len("リジェクト"):] if head_end != -1 else body
            got = []
            for chunk in tail.split("プレビュー"):
                m = re.search(r"¥[\d,]+", chunk)
                if not m:
                    continue
                name = re.sub(r"(編集|削除|P参加中\(.*?\))", "", norm(chunk[: m.start()]))
                status_zone = chunk[m.end(): m.end() + 40]
                if name and "販売中" in status_zone:
                    got.append(name)
            fresh = [n for n in got if n not in names]
            if not fresh:
                break
            names.extend(fresh)
        b.close()
    return names


def store_ids() -> dict[str, str]:
    """作者ページ(公開)から norm(名前)→商品ID。"""
    out: dict[str, str] = {}
    for pageno in range(1, 4):
        req = urllib.request.Request(
            f"https://store.line.me/stickershop/author/301799/ja?page={pageno}",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
        )
        try:
            h = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            log(f"作者ページp{pageno}の取得に失敗: {e}")
            break
        found = 0
        for m in re.finditer(r'href="/stickershop/product/(\d+)/ja"(.{0,900}?)</a>', h, re.S):
            t = re.search(r'alt="([^"]+)"', m.group(2))
            if t:
                out.setdefault(norm(t.group(1)), m.group(1))
                found += 1
        if not found:
            break
    return out


# ── 一覧に載せないもの（国外向け）──────────────────────────
# みかさん2026-09-17「国違いのスタンプは、一覧ページには載せないようにしてほしいです」
# ⚠️ 黙って消さない。載せなかったものは必ずログとDiscordに出す（気づかないうちに消えるのが困る）。
FOREIGN_SCRIPT = re.compile(r"[\u0E00-\u0E7F\uAC00-\uD7AF\u0400-\u04FF]")  # タイ文字・ハングル・キリル
KANA = re.compile(r"[\u3040-\u309F\u30A0-\u30FF]")                          # ひらがな・カタカナ


def skip_list() -> set:
    """作品名を1行ずつ書いたテキスト（# から後ろはメモ）。無ければ空。"""
    if not SKIP_LIST.exists():
        return set()
    out = set()
    for line in SKIP_LIST.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(norm(line))
    return out


def skip_reason(title: str, listed: set) -> str:
    """載せない理由を返す。載せてよければ空文字。"""
    if norm(title) in listed:
        return "一覧に載せない.txt に書いてある"
    if FOREIGN_SCRIPT.search(title):
        return "作品名に日本語以外の文字が入っている（タイ文字・ハングル等）"
    if not KANA.search(title):
        # 繁体字中国語は漢字だけなので、かなが1文字も無いものは保留して聞く
        return "かなが1文字も無い（繁体字などの国外向けかもしれないので保留）"
    return ""


# 2026-09-18 みかさん「もっと見やすい一覧ページに」→ 使う場面で10カテゴリに分け直した（build.py と同じ名前）。
# ⚠️ 上から順に当てる（「バレーボールくんの擬音返事」はマンガでなくスポーツ、「さびねこの関西弁」は方言でなくねこ）。
CATEGORY_RULES = [
    ("😤 ぐぬぬちゃん・マンガの言葉", r"マンガ|ぐぬぬ|効果音|まるいやつ"),
    ("🏐 スポーツ・応援",            r"バレー|サッカー|野球|テニス|バスケ|シャトル|バドミントン|運動会|赤白帽|応援"),
    ("🐈 ねこ",                      r"ねこ|ネコ|猫"),
    ("🗾 方言・ご当地",              r"弁|どすこい|浜言葉|なんくる|もみじ|えびフライ|明太子|ご当地|方言"),
    ("💼 仕事・業務連絡",            r"業務連絡|会議|シフト|回覧板|はんこ|承認|付箋|コピー機|敬語|仕事|クッション|言いにくい|既読"),
    ("🎵 声と音のなかまたち",        r"声|のど|メトロノーム|言いよどみ|早口|うるおい"),
    ("🍂 季節・行事",                r"秋|ハロウィン|お月見|焼きいも|金木犀|どんぐり|紅葉|寒暖差|てるてる|おばけ|こうもり|かぼちゃ|クリスマス|お正月|年賀|バレンタイン|さくら|春|夏|冬"),
    ("🍛 たべもの",                  r"カレー|ナス|ブロッコリー|湯のみ|だんご|栗"),
]
DEFAULT_CATEGORY = "👋 あいさつ・返事"   # 当たらなければここ（返事・あいさつが一番多い箱）


def pick_category(title: str) -> str:
    for cat, pat in CATEGORY_RULES:
        if re.search(pat, title):
            return cat
    return DEFAULT_CATEGORY


def main() -> int:
    d = json.loads(DATA.read_text(encoding="utf-8"))
    have = {norm(i["title"]) for c in d["categories"] for i in c["items"]}

    names = selling_names()
    if not names:  # None＝ログイン切れ／[]＝ログイン切れで一覧が空に見えている（9/20 10:17・15:17に「販売中0」で黙って通っていた）
        log("🚨 Creators Marketのログインが切れています。追加チェックできていません")
        # 同じ知らせは1日1回だけ（9/20 みかさん「なぜなおさないの？」＝直せない件を何度も知らせない）
        stamp = pathlib.Path(__file__).with_name(".login-expired-notified")
        today = datetime.date.today().isoformat()
        if not (stamp.exists() and stamp.read_text().strip() == today):
            notify("🎨 スタンプ自動追加: LINE Creators Marketのログインが切れていて確認できませんでした。`~/line-stickers` のログインを1回お願いします（きょうはこの1回だけ知らせます）")
            stamp.write_text(today)
        return 0  # 知らせは自分で出したので、拾う役（終了コード見張り）には拾わせない

    new_names = [n for n in names if n not in have]
    if not new_names:
        log(f"新作なし（販売中{len(names)}・掲載{len(have)}）")
        return 0

    listed = skip_list()
    skipped = [(n, r) for n in new_names for r in [skip_reason(n, listed)] if r]
    if skipped:
        new_names = [n for n in new_names if n not in {x[0] for x in skipped}]
        log("一覧に載せませんでした: " + "、".join(f"{n}（{r}）" for n, r in skipped))
        notify("🌏 **一覧ページに載せなかった作品があります**（国違いは載せない設定）\n"
               + "\n".join(f"・{n}\n　理由: {r}" for n, r in skipped)
               + "\n\n載せたいものがあれば言ってください（`一覧に載せない.txt` から外します）")
    if not new_names:
        return 0

    ids = store_ids()
    added, waiting = [], []
    for n in new_names:
        pid = ids.get(n)
        if not pid:
            waiting.append(n)  # 販売中になったがストアにまだ出ていない（時差）→次回また見る
            continue
        animated = "動く" in n
        item = {"title": n, "id": int(pid), "new": True, "price": 250 if animated else 190}
        if animated:
            item["animated"] = True
        cat_name = pick_category(n)
        cat = next((c for c in d["categories"] if c["name"] == cat_name), None)
        if cat is None:
            cat = {"name": cat_name, "items": []}
            d["categories"].append(cat)
        cat["items"].insert(0, item)
        added.append((n, cat_name, pid))

    if waiting:
        log(f"販売中だがストア未掲載（次回まで待つ）: {waiting}")
    if not added:
        return 0

    # 前回までのNEWを外して、今回の追加だけNEWにする
    for c in d["categories"]:
        for i in c["items"]:
            if i.get("new") and norm(i["title"]) not in {a[0] for a in added}:
                i.pop("new", None)

    DATA.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "build.py")], check=True, cwd=ROOT)
    subprocess.run(["git", "add", "-A"], check=True, cwd=ROOT)
    msg = "自動追加: " + "、".join(a[0] for a in added)
    subprocess.run(["git", "commit", "-q", "-m", msg], check=True, cwd=ROOT)
    subprocess.run(["git", "push", "-q"], check=True, cwd=ROOT)
    log(f"追加してpushしました: {added}")
    lines = "\n".join(f"・{a[0]}（{a[1]}）" for a in added)
    # 2026-09-19 みかさん「この通知も不要です」→ 成功の知らせはDiscordに出さない（ログにだけ残す）。ログイン切れ・載せなかった作品の知らせは残す
    log(f"（Discord通知なし）新作を追加: {lines.replace(chr(10), ' / ')}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log(f"🚨 想定外のエラー: {e}")
        notify(f"🎨 スタンプ自動追加が失敗しました: {str(e)[:150]}")
        sys.exit(1)
