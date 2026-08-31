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


def notify(text: str) -> None:
    """Discordのメイン部屋へ1行（intake.shと同じ経路）。失敗しても本体は止めない。"""
    try:
        token = ""
        for l in DISCORD_ENV.read_text(encoding="utf-8").splitlines():
            if l.startswith("DISCORD_BOT_TOKEN="):
                token = l.split("=", 1)[1].strip()
        if not token:
            return
        req = urllib.request.Request(
            f"https://discord.com/api/v10/channels/{MAIN_ROOM}/messages",
            data=json.dumps({"content": text}).encode(),
            headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=15)
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


CATEGORY_RULES = [
    ("🏐 スポーツ", r"バレー|サッカー|野球|テニス|スポーツ|部活"),
    ("🐈 ねこシリーズ", r"ねこ|ネコ|猫"),
    ("🗾 方言・ご当地", r"弁|どすこい|カモメ|もみじ|ご当地|なまり|方言|浜言葉"),
    ("🦦 カワウソ", r"カワウソ"),
    ("🎵 声と音のなかまたち", r"声|のど|メトロノーム|ヘビ|音"),
    ("💬 ことば・英語", r"言葉|言わない|英語|返事|クッション"),
]


def pick_category(title: str) -> str:
    for cat, pat in CATEGORY_RULES:
        if re.search(pat, title):
            return cat
    return "🆕 そのほか"


def main() -> int:
    d = json.loads(DATA.read_text(encoding="utf-8"))
    have = {norm(i["title"]) for c in d["categories"] for i in c["items"]}

    names = selling_names()
    if names is None:
        log("🚨 Creators Marketのログインが切れています。追加チェックできていません")
        notify("🎨 スタンプ自動追加: LINE Creators Marketのログインが切れていて確認できませんでした。`~/line-stickers` のログインを1回お願いします")
        return 1

    new_names = [n for n in names if n not in have]
    if not new_names:
        log(f"新作なし（販売中{len(names)}・掲載{len(have)}）")
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
    notify(f"🎨 スタンプまとめページに新作を自動追加しました（販売開始を検知）:\n{lines}\nhttps://micarp1221git.github.io/mika-stamps/")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log(f"🚨 想定外のエラー: {e}")
        notify(f"🎨 スタンプ自動追加が失敗しました: {str(e)[:150]}")
        sys.exit(1)
