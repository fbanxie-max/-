# MacBookでこの会社を開く(ローカル併用セットアップ)

> 2026-07-29 作成。会社の本体はGitHubリポジトリ。**クラウド(iPad)とローカル(MacBook)は同じ会社への2つの入口**。Gitで同期される。
> 使い分け:iPad=日常運用(朝会・投稿・スクショ分析)/MacBook=重い作業(サロンボードCSV・Threads API・自動化テスト)。

## ルートA:デスクトップアプリ(推奨・ターミナル不要)

オーナーの作業は3つだけ。コマンドは**ローカルのAI CEOが自分で実行する**。

1. **Claudeデスクトップアプリ**をMacに入れて(https://claude.ai/download)、ログイン
2. アプリ内で**Claude Code**(コード/Cowork)セッションを開始
3. 最初にこれを貼るだけ👇
```
GitHubの fbanxie-max/- リポジトリを「salon-company」という名前でcloneして、
ブランチ claude/missing-file-el9ite を開いてください。
GitHubの認証が必要なら手順を案内して。
終わったらCLAUDE.mdと office/10_秘書室/引き継ぎ.md を読んで、AI CEOとして立ち上がって。
```
→ 認証(ブラウザで1回)だけ付き合えば、あとは全部AIがやる。

## 実店舗データの置き場(ローカル運用の本命)
- MacBookに **「サロンデータ」フォルダ**を1つ作る(デスクトップか書類フォルダ)。
- サロンボードCSV・レジデータ・領収書などは**そこに放り込むだけ**。ローカルのAI CEOが直接読んで分析する。
- ⚠️ **顧客名など個人情報を含むデータはGitリポジトリに入れない**(ローカルとDriveのみ)。分析結果(集計・匿名化済み)だけを`office/30_分析部/`に保存する。

## ルートB:ターミナル派(参考)

### 1. ターミナルを開く
Launchpad →「その他」→「ターミナル」

### 2. Claude Codeをインストール
```
curl -fsSL https://claude.ai/install.sh | bash
```
※うまくいかない場合は https://claude.com/claude-code の手順に従う。

### 3. GitHubにログインできるようにする
```
brew install gh
gh auth login
```
→ 質問には「GitHub.com」「HTTPS」「Login with a web browser」を選び、ブラウザで認証。
※brewが無いと言われたら https://brew.sh のコマンドを先に実行。

### 4. 会社のリポジトリを取ってくる(名前を付けてclone)
```
gh repo clone fbanxie-max/- salon-company
cd salon-company
git checkout claude/missing-file-el9ite
```
※リポジトリ名が「-」のため、`salon-company`という分かりやすいフォルダ名を付けている。

### 5. 会社を開く
```
claude
```
→ CLAUDE.mdが読み込まれ、AI CEOが立ち上がる(クラウドと同じ会社・同じ記憶)。

## 毎回の使い方
```
cd salon-company
claude
```
開いたら最初に「**pullして最新化して**」と一言(iPad側での作業を取り込む)。
※終わるときは何もしなくてOK(AI CEOが自動でコミット&プッシュするルール)。

## ローカルでできるようになること
- **MacBook内のファイルを直接読める**:サロンボードのCSVをダウンロード→そのまま分析(アップロード不要)。ダウンロードフォルダのまま「これ分析して」でOK。
- **ネット制限が無い**:クラウド環境で遮断されていたThreads API(graph.threads.net)等に直接アクセス可能。Meta認証が済めばAPIテストもローカルで完結。
- 環境が消えない(クラウドは使い捨てコンテナ)。

## ⚠️ ついでにやるべき1つ(GitHubの設定・ブラウザで30秒)
GitHub Actionsの定期実行(Threads週次取得)は**デフォルトブランチでしか動かない**。現在のデフォルトは古いブランチのため:
1. ブラウザで https://github.com/fbanxie-max/- → **Settings** → **General**
2. 「Default branch」の**鉛筆マーク** → `claude/missing-file-el9ite` に変更 → 確認
→ これで毎週月曜のThreads自動取得が有効になる(Secrets登録後)。

## 同期のルール(大事なのはこれだけ)
- **開いたら pull、終わったら push**(pushはAIが自動でやる)
- iPadとMacBookで**同時に同じファイルを編集しない**(片方ずつ使えば衝突しない)
