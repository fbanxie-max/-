# Threads 自動投稿（設定ガイド）

Threadsに、キュー（`threads_queue.json`）に入れた投稿を**自動で公開**する仕組み。
GitHub Actions が定期実行 → `threads_autopost.py` がキューの投稿を Threads API で公開する。
※ 自分のThreadsアカウントに投稿するだけなら、アプリは「開発モード」のまま・自分をテスターに追加すればApp Review（審査）は基本不要。

## 全体像
```
threads_queue.json（投稿の中身）
   ↓  GitHub Actions（毎日 定時に実行）
threads_autopost.py（Threads APIで公開）
   ↓
Threadsに投稿される
```

## あすかさんの作業（1回だけ）

### 手順1：Metaでアプリとトークンを用意
1. https://developers.facebook.com にログイン →「マイアプリ」→「アプリを作成」
2. アプリタイプは「その他」→ 次へ。使用ケースで **「Threads API」** を追加
3. 「Threads」設定で、投稿に必要な権限 **`threads_basic` と `threads_content_publish`** を有効化
4. 自分のThreadsアカウントを**テスターとして追加**し、承認
5. **アクセストークンを生成**（短期トークン）→ 長期トークン（60日）に交換
   - 長期トークン交換：`GET https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=（アプリのシークレット）&access_token=（短期トークン）`
6. 自分の **Threads ユーザーID** を取得：`GET https://graph.threads.net/v1.0/me?fields=id,username&access_token=（トークン）`

→ 手に入れるもの：**長期アクセストークン** と **ユーザーID**（この2つを私に渡さず、次の手順でSecretに登録）

### 手順2：GitHubにSecretとしてトークンをS登録（安全・非公開）
リポジトリの **Settings → Secrets and variables → Actions → New repository secret** で2つ登録：
- `THREADS_ACCESS_TOKEN` … 長期アクセストークン
- `THREADS_USER_ID` … ユーザーID

※ Secret はコードにも履歴にも残らず、AIからも見えません。

### 手順3：ワークフローを有効化
`.github/workflows/threads-autopost.yml`（下記）を**デフォルトブランチ(main)** に置くと、定期実行が有効になります。
まずは Actions 画面の **「Run workflow（手動実行）」でテスト投稿**して、Threadsに出るか確認。

## GitHub Actions ワークフロー（`.github/workflows/threads-autopost.yml`）
```yaml
name: Threads Auto Post
on:
  schedule:
    - cron: "0 10 * * *"   # 毎日 19:00 JST（夜が伸びやすいため）
  workflow_dispatch: {}     # 手動実行（テスト用）
permissions:
  contents: write
jobs:
  post:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Post due items
        env:
          THREADS_ACCESS_TOKEN: ${{ secrets.THREADS_ACCESS_TOKEN }}
          THREADS_USER_ID: ${{ secrets.THREADS_USER_ID }}
        run: python automation/threads_autopost.py
      - name: Commit queue updates
        run: |
          git config user.name "threads-autopost"
          git config user.email "actions@users.noreply.github.com"
          git add automation/threads_queue.json
          git commit -m "chore: update threads queue [skip ci]" || echo "no changes"
          git push
```

## 投稿の入れ方（キュー）
`threads_queue.json` の `posts` に追加するだけ：
```json
{
  "text": "投稿本文（Threadsは500文字まで）",
  "scheduled_at": "2026-07-25T10:00:00Z",   // 省略/null なら次の実行で即投稿。時刻はUTC（19:00 JST = 10:00Z）
  "posted": false
}
```
- `posted: true` になった投稿は再投稿されない
- 画像を付けたい場合は `"image_url": "https://…（公開URL）"` を追加（Threadsが取得できる公開URLが必要）
- 1回の実行で投稿する最大数は `max_per_run`（既定1）

## 注意
- **長期トークンは60日で失効**。切れる前に再生成→Secretを更新（自動更新は後で追加可能）。
- 投稿本文は**500文字**まで。
- レート制限：24時間で約250件（通常は問題なし）。
- 対外発信のガード：レーンB（同業向け）は**匿名（あすか名・店名を出さない）**を守る。
