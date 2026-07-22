#!/usr/bin/env python3
"""
Threads 自動投稿スクリプト
- automation/threads_queue.json の投稿キューを読み、
  「まだ投稿してない & 予定時刻を過ぎた」投稿を Threads API で公開する。
- 認証情報は環境変数から読む（コードには一切書かない）:
    THREADS_ACCESS_TOKEN  … 長期アクセストークン（GitHub Secret 等で渡す）
    THREADS_USER_ID       … Threads ユーザーID（未指定なら /me から自動取得）
- 依存ライブラリなし（標準ライブラリのみ）。
"""
import os, sys, json, time, datetime, urllib.request, urllib.parse, urllib.error

BASE = "https://graph.threads.net/v1.0"
QUEUE_PATH = os.path.join(os.path.dirname(__file__), "threads_queue.json")
TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
USER_ID = os.environ.get("THREADS_USER_ID", "").strip()


def _call(method, path, params):
    params = dict(params)
    params["access_token"] = TOKEN
    if method == "GET":
        url = BASE + path + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method="GET")
    else:
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(BASE + path, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Threads API {method} {path} failed: {e.code} {body}")


def resolve_user_id():
    if USER_ID:
        return USER_ID
    me = _call("GET", "/me", {"fields": "id,username"})
    return me["id"]


def publish(uid, text, image_url=None):
    # 1) メディアコンテナ作成
    params = {"text": text}
    if image_url:
        params["media_type"] = "IMAGE"
        params["image_url"] = image_url
    else:
        params["media_type"] = "TEXT"
    created = _call("POST", f"/{uid}/threads", params)
    creation_id = created["id"]
    # 画像はサーバー取得に少し時間がかかるため待つ
    if image_url:
        time.sleep(5)
    # 2) 公開
    result = _call("POST", f"/{uid}/threads_publish", {"creation_id": creation_id})
    return result.get("id")


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_iso(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    dt = datetime.datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def main():
    if not TOKEN:
        print("ERROR: THREADS_ACCESS_TOKEN が未設定です。", file=sys.stderr)
        sys.exit(1)
    with open(QUEUE_PATH, encoding="utf-8") as f:
        queue = json.load(f)
    posts = queue.get("posts", [])
    now = now_utc()

    due = [p for p in posts
           if not p.get("posted")
           and (not p.get("scheduled_at") or parse_iso(p["scheduled_at"]) <= now)]
    if not due:
        print("投稿予定の投稿はありません（due=0）。")
        return

    # 予定時刻の早い順に、1回の実行で最大 max_per_run 件まで
    due.sort(key=lambda p: parse_iso(p.get("scheduled_at")) or now)
    max_per_run = int(queue.get("max_per_run", 1))
    uid = resolve_user_id()

    posted = 0
    for p in due[:max_per_run]:
        pid = publish(uid, p["text"], p.get("image_url"))
        p["posted"] = True
        p["posted_at"] = now.isoformat()
        p["post_id"] = pid
        posted += 1
        print(f"投稿しました: id={pid} / {p['text'][:24]}...")

    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
    print(f"完了：{posted}件投稿しました。")


if __name__ == "__main__":
    main()
