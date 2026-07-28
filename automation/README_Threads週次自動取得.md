# Threads 週次データ自動取得（設定ガイド）

**やりたいこと**：毎週、自分の投稿インサイトと「伸びている投稿」を**自動で取得**し、AI CEOが分析する。

## なぜこの形なのか（重要）
Claude Code の実行環境は `graph.threads.net` への通信が**遮断**されている（ゲートウェイが403）。
一方 **GitHub Actions は GitHub 側のサーバーで動く**ので、Threads API を直接叩ける。

```
GitHub Actions（毎週月曜10:00 JST）
   ↓ Threads API を叩く
自分の投稿インサイト ＋ キーワード検索の結果
   ↓ リポジトリに保存（office/30_分析部/ 配下）
AI CEO がそのファイルを読んで分析・改善案・投稿案を作る
```

## あすかさんの作業（1回だけ・15〜20分）

### 手順1：Metaでアプリを作る
1. https://developers.facebook.com にログイン →「マイアプリ」→**アプリを作成**
2. ユースケースで **「Threads API へのアクセス」** を選ぶ
3. 追加する権限（Permissions）：
   - `threads_basic` … 必須
   - `threads_manage_insights` … **インサイト取得に必須**
   - `threads_content_publish` … （将来の自動投稿用。今は無くても可）
   - `threads_keyword_search` … **キーワード検索用**（※付与できない/審査が要る場合あり。後述）

### 手順2：自分のアカウントをテスターに追加
1. アプリの「アプリロール」→ **Threadsテスターを追加** → 自分のThreadsユーザー名を入力
2. **Threadsアプリ側で承認**：設定 → ウェブサイトの許可 → 招待 → 承認
   ※ 自分のアカウントのデータを見るだけなら、アプリは**開発モードのまま**でOK（App Review不要）

### 手順3：アクセストークンを発行 → 長期トークンに交換
1. アプリ管理画面の Threads API 設定に **「アクセストークンを生成」** ボタンがある → 押して**短期トークン**（約1時間）を取得
2. 長期トークン（60日）に交換：ブラウザで下記URLを開く（`{}`は自分の値に置き換え）
   ```
   https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret={アプリのシークレット}&access_token={短期トークン}
   ```
   → 返ってきた `access_token` が**長期トークン**。
3. 自分のユーザーIDを取得：
   ```
   https://graph.threads.net/v1.0/me?fields=id,username&access_token={長期トークン}
   ```
   → `id` の値をメモ。

> ⚠️ **トークンは絶対にチャットに貼らない・コードに書かない。** 次の手順でGitHubのSecretに入れる（AIからも他人からも見えません）。

### 手順4：GitHubにSecretとして登録
リポジトリ → **Settings → Secrets and variables → Actions → New repository secret** で2つ登録：
| 名前 | 中身 |
|---|---|
| `THREADS_ACCESS_TOKEN` | 手順3の**長期トークン** |
| `THREADS_USER_ID` | 手順3の**id** |

### 手順5：ワークフローを有効化してテスト
1. `.github/workflows/threads-weekly-fetch.yml` を**デフォルトブランチ**に置く（scheduleはデフォルトブランチでしか動かない）。
   - このリポジトリの現在のデフォルトブランチは `claude/salon-management-app-tf40o2`。**作業ブランチ `claude/missing-file-el9ite` をマージするか、デフォルトブランチを切り替える**必要がある（CEOに言えばやります）。
2. GitHubの **Actions** タブ → 「Threads Weekly Fetch」→ **Run workflow** で手動実行してテスト。
3. 成功すると `office/30_分析部/YYYY-MM-DD_Threads自動取得.md`（人が読む用）と `.json`（分析用）、`Threads投稿インサイト.csv`（履歴）が自動コミットされる。

## 取得できるもの
| 種類 | 中身 | 必要な権限 |
|---|---|---|
| 自分の投稿 | 本文・投稿日時・URL・種別 | `threads_basic` |
| 投稿インサイト | 表示・いいね・返信・リポスト・引用・シェア | `threads_manage_insights` |
| アカウント指標 | 表示数・フォロワー数 など | `threads_manage_insights` |
| 伸びてる投稿の検索 | キーワード上位の投稿（本文・URL・投稿者） | `threads_keyword_search` |

**検索キーワードの編集**：`automation/threads_watch_keywords.json`（現在＝美容室 経営／サロン 集客／美容師 独立／客単価／ホットペッパー 集客／個人事業 AI）

## 正直な注意点
- **キーワード検索は取れない可能性がある**：`threads_keyword_search` は権限付与やApp Reviewが要る場合がある。取れない時はスクリプトが**落ちずにメモを残す**設計なので、その週は「伸びてる投稿だけ手動スクショ」で補完すればOK（自分のインサイトは取れる）。
- **プロフィール流入・保存数はAPIに無い**可能性が高い：APIで取れるのは主に 表示/いいね/返信/リポスト/引用/シェア。**保存・プロフィール流入はアプリのインサイト画面のスクショ**で補う。
- **トークンは60日で切れる**。切れる前に更新（下記URLを開くだけ・新しいトークンをSecretに入れ直す）：
  ```
  https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token&access_token={現在の長期トークン}
  ```
  → **2ヶ月に1回の更新をカレンダーに入れておくと安全**。取得が失敗し始めたらまずここを疑う。

## 週次の流れ（設定後）
1. 月曜10:00 … Actionsが自動でデータ取得＆コミット
2. あすかさん … Claude Codeで **`/threads-weekly`** を実行（＋保存/プロフィール流入のスクショだけ渡す）
3. AI CEO … 自動取得データ＋スクショを突き合わせて、分析・改善3点・今週の投稿案を納品
