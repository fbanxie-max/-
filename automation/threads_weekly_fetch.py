#!/usr/bin/env python3
"""
Threads 週次データ取得スクリプト（GitHub Actions で実行する前提）

なぜ Actions で動かすか:
  Claude Code の実行環境は graph.threads.net への通信が遮断されている。
  GitHub Actions は GitHub 側のサーバーで動くので API を直接叩ける。
  → Actions が取得してリポジトリに保存 → AI CEO がそのファイルを読んで分析する。

取得するもの:
  1) 自分の投稿とインサイト（表示・いいね・返信・リポスト・引用・シェア）
  2) 自分のアカウント指標（表示数・フォロワー数など）
  3) キーワード検索（同ジャンルで伸びている投稿）※権限があれば

認証情報は環境変数から読む（コードにも履歴にも残さない）:
  THREADS_ACCESS_TOKEN … 長期アクセストークン（GitHub Secret）
  THREADS_USER_ID      … Threads ユーザーID（未指定なら /me から自動取得）

依存ライブラリなし（標準ライブラリのみ）。
"""
import os, sys, json, csv, datetime, urllib.request, urllib.parse, urllib.error

BASE = "https://graph.threads.net/v1.0"
TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
USER_ID = os.environ.get("THREADS_USER_ID", "").strip()
DAYS = int(os.environ.get("THREADS_LOOKBACK_DAYS", "14"))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYSIS_DIR = os.path.join(ROOT, "office", "30_分析部")
RESEARCH_DIR = os.path.join(ROOT, "office", "20_リサーチ部")
KEYWORDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "threads_watch_keywords.json")
POSTS_CSV = os.path.join(ANALYSIS_DIR, "Threads投稿インサイト.csv")

POST_FIELDS = "id,media_type,media_product_type,permalink,text,timestamp,shortcode,is_quote_post"
POST_METRICS = "views,likes,replies,reposts,quotes,shares"
USER_METRICS = "views,likes,replies,reposts,quotes,followers_count"
SEARCH_FIELDS = "id,text,permalink,timestamp,username,media_type"

notes = []          # 実行メモ（失敗も正直に残す）


def call(path, params=None):
    """GET を投げて JSON を返す。失敗は例外にせず (None, エラー文) を返す。"""
    p = dict(params or {})
    p["access_token"] = TOKEN
    url = BASE + path + "?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "asuka-company-weekly/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        return None, f"HTTP {e.code}: {body}"
    except Exception as e:  # ネットワーク等
        return None, f"{type(e).__name__}: {e}"


def iso_days_ago(days):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S+0000")


def flatten_insights(payload):
    """insights レスポンスを {metric: value} に潰す。"""
    out = {}
    for item in (payload or {}).get("data", []):
        name = item.get("name")
        val = None
        if "values" in item and item["values"]:
            val = item["values"][0].get("value")
        elif "total_value" in item:
            val = item["total_value"].get("value")
        out[name] = val
    return out


def main():
    if not TOKEN:
        print("ERROR: THREADS_ACCESS_TOKEN が未設定です。GitHub Secret を確認してください。", file=sys.stderr)
        return 1

    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    os.makedirs(RESEARCH_DIR, exist_ok=True)
    today = datetime.date.today().isoformat()

    uid = USER_ID
    if not uid:
        me, err = call("/me", {"fields": "id,username"})
        if err:
            print(f"ERROR: /me 取得に失敗: {err}", file=sys.stderr)
            return 1
        uid = me.get("id", "")
        notes.append(f"ユーザーID を /me から取得: @{me.get('username','?')}")

    # ---- 1) 自分の投稿 ----
    posts, err = call(f"/{uid}/threads", {"fields": POST_FIELDS, "since": iso_days_ago(DAYS), "limit": 50})
    rows = []
    if err:
        notes.append(f"⚠️ 投稿一覧の取得に失敗: {err}")
        posts = {"data": []}
    for post in posts.get("data", []):
        pid = post.get("id")
        ins, ierr = call(f"/{pid}/insights", {"metric": POST_METRICS})
        m = flatten_insights(ins) if not ierr else {}
        if ierr:
            notes.append(f"⚠️ インサイト取得失敗(post {pid}): {ierr}")
        text = (post.get("text") or "").replace("\n", " ").strip()
        rows.append({
            "取得日": today,
            "投稿ID": pid,
            "投稿日時": post.get("timestamp", ""),
            "本文冒頭": text[:60],
            "表示": m.get("views", ""),
            "いいね": m.get("likes", ""),
            "返信": m.get("replies", ""),
            "リポスト": m.get("reposts", ""),
            "引用": m.get("quotes", ""),
            "シェア": m.get("shares", ""),
            "種別": post.get("media_type", ""),
            "URL": post.get("permalink", ""),
        })

    # ---- 2) アカウント指標 ----
    since_unix = int((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=DAYS)).timestamp())
    until_unix = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    uins, uerr = call(f"/{uid}/threads_insights", {"metric": USER_METRICS, "since": since_unix, "until": until_unix})
    user_metrics = flatten_insights(uins) if not uerr else {}
    if uerr:
        notes.append(f"⚠️ アカウント指標の取得に失敗: {uerr}")

    # ---- 3) キーワード検索（伸びてる投稿の収集）----
    keywords = []
    if os.path.exists(KEYWORDS_PATH):
        try:
            keywords = json.load(open(KEYWORDS_PATH, encoding="utf-8")).get("keywords", [])
        except Exception as e:
            notes.append(f"⚠️ キーワード設定の読込に失敗: {e}")
    search_results = {}
    for kw in keywords:
        data, serr = call("/keyword_search", {"q": kw, "search_type": "TOP", "fields": SEARCH_FIELDS, "limit": 25})
        if serr:
            notes.append(f"⚠️ キーワード検索『{kw}』失敗: {serr}")
            continue
        search_results[kw] = data.get("data", [])

    if keywords and not search_results:
        notes.append("※ キーワード検索が1件も取れていません。`threads_keyword_search` 権限が未付与の可能性があります"
                     "（Metaのアプリ設定で権限を追加、必要ならApp Reviewを申請）。取れるまでは伸びてる投稿は手動スクショで補完してください。")

    # ---- 保存 ----
    # CSV（追記・履歴を残す）
    fieldnames = ["取得日", "投稿ID", "投稿日時", "本文冒頭", "表示", "いいね", "返信", "リポスト", "引用", "シェア", "種別", "URL"]
    new_file = not os.path.exists(POSTS_CSV)
    with open(POSTS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow(r)

    # 生データ（分析用）
    snapshot = {
        "取得日": today,
        "対象期間_日数": DAYS,
        "アカウント指標": user_metrics,
        "投稿": rows,
        "キーワード検索": search_results,
        "メモ": notes,
    }
    with open(os.path.join(ANALYSIS_DIR, f"{today}_Threads自動取得.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    # 人が読むダイジェスト
    md = [f"# {today} Threads自動取得（GitHub Actions）", ""]
    md.append(f"- 対象：直近{DAYS}日／投稿 {len(rows)}件")
    if user_metrics:
        md.append("- アカウント指標：" + " ／ ".join(f"{k}={v}" for k, v in user_metrics.items() if v is not None))
    md.append("")
    if rows:
        md.append("| 投稿日時 | 本文冒頭 | 表示 | いいね | 返信 | リポスト | 引用 |")
        md.append("|---|---|---|---|---|---|---|")
        for r in sorted(rows, key=lambda x: x["投稿日時"], reverse=True):
            md.append(f"| {r['投稿日時'][:16]} | {r['本文冒頭'][:28]} | {r['表示']} | {r['いいね']} | {r['返信']} | {r['リポスト']} | {r['引用']} |")
        md.append("")
    for kw, items in search_results.items():
        md.append(f"## 検索『{kw}』上位 {len(items)}件")
        for it in items[:10]:
            t = (it.get("text") or "").replace("\n", " ")[:70]
            md.append(f"- @{it.get('username','?')} {it.get('timestamp','')[:10]}｜{t}｜{it.get('permalink','')}")
        md.append("")
    if notes:
        md.append("## 実行メモ")
        for n in notes:
            md.append(f"- {n}")
    with open(os.path.join(ANALYSIS_DIR, f"{today}_Threads自動取得.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print(f"OK: 投稿{len(rows)}件 / 検索キーワード{len(search_results)}件 を保存しました。")
    for n in notes:
        print("NOTE:", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
