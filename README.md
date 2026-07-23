<div align="center">

# 🔗 Hacker News → Discord

**毎朝、Hacker News の話題の記事を日本語の翻訳・要約つきで Discord に届ける自動ボット**

<img alt="Python" src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white">
<img alt="Gemini" src="https://img.shields.io/badge/AI-Gemini-8E75B2?logo=googlegemini&logoColor=white">
<img alt="Discord" src="https://img.shields.io/badge/Discord-Webhook-5865F2?logo=discord&logoColor=white">
<img alt="systemd" src="https://img.shields.io/badge/Schedule-systemd_timer-333">
<img alt="License" src="https://img.shields.io/badge/License-MIT-green">

</div>

---

## なぜ作ったか

Hacker News は面白いけれど、いちいち英語のページを開いて読むのは手間。
そこで **「話題の記事を、翻訳・要約した状態で毎朝 Discord に流し込む」** ことにしました。
起きてスマホを見れば、その日読むべき技術ニュースが日本語で並んでいます。

## 仕組み

```
Hacker News API ──▶ points 順で上位を抽出 ──▶ Gemini で翻訳・要約(JSON)
        │                                              │
        └──────────────▶ Python で決定論的に整形 ◀──────┘
                                   │
                                   ▼
                          Discord Webhook 📨
```

> [!NOTE]
> **設計方針** — AI(Gemini)には「翻訳・要約テキストを JSON で返す」ことだけを任せ、
> 見出し・URL・レイアウトは **すべて Python 側で確定データから組み立てます**。
> AI の出力書式に依存しないため、見出し抜け・URL 抜け・フォーマット崩れが構造的に起こりません。

## 特長

| | |
|---|---|
| 🏆 **本当の「トップ」記事** | 直近 24h の候補を最大 100 件取得し、**points 順**で上位を厳選 |
| 🇯🇵 **日本語で翻訳・要約** | Gemini が各記事のタイトル訳と 1〜3 行の要約を生成 |
| 🔗 **URL が抜けない** | Show HN / Ask HN などの投稿も **HN 議論ページへのリンク**に自動フォールバック |
| 🧱 **崩れないレイアウト** | タイトルはクリック可能なリンク、要約は引用形式。記事はメッセージ境界で分割され途中で切れない |
| ♻️ **堅牢なリトライ** | HN・Gemini・Discord の各通信を指数バックオフで再試行。Discord のレート制限(429)も自動待機 |
| 🛟 **グレースフルな劣化** | 翻訳が失敗しても、タイトルと URL は必ず投稿される |
| ⏰ **完全自動** | systemd タイマーで毎朝 07:00 JST に自動実行 |

## クイックスタート

### 1. セットアップ（初回のみ）

```bash
cd ~/Hacker-News-to-discord
python3 -m venv venv
venv/bin/pip install --no-user -r requirements.txt
```

### 2. API キーを設定

```bash
cat > ~/.hacker-news-env << 'EOF'
GEMINI_API_KEY=your-api-key-here
DISCORD_WEBHOOK_URL=your-webhook-url-here
EOF
chmod 600 ~/.hacker-news-env
```

- **Gemini API キー:** https://aistudio.google.com/app/apikeys
- **Discord Webhook:** サーバー設定 → 連携 → Webhook

### 3. 設定を検証

```bash
./setup.sh     # venv・API キー・依存パッケージをチェック
```

### 4. 手動実行してテスト

```bash
./run.sh
```

## 設定（環境変数）

必須は 2 つだけ。残りは既定値で動きます。

| 変数 | 既定値 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | — | **必須。** Gemini API キー |
| `DISCORD_WEBHOOK_URL` | — | **必須。** 送信先の Discord Webhook |
| `GEMINI_MODEL` | `gemini-3.5-flash` | 使用する Gemini モデル |
| `HN_MAX_ARTICLES` | `5` | ダイジェストに載せる記事数 |
| `HN_CANDIDATE_POOL` | `100` | points 順の選抜前に取得する候補数 |
| `HN_LOOKBACK_HOURS` | `24` | 遡る時間の範囲 |

## 自動実行（systemd）

> [!IMPORTANT]
> `hacker-news.service` は既定で `User=waras` とパスがハードコードされています。
> **別ユーザー・別環境で動かす場合は必ず書き換えてから配置してください。**

```bash
# 例：root ユーザー、/root/Hacker-News-to-discord に配置した場合
sed \
  -e 's|User=waras|User=root|g' \
  -e 's|/home/waras/Hacker-news-to-Discord|/root/Hacker-News-to-discord|g' \
  -e 's|/home/waras/\.hacker-news-env|/root/.hacker-news-env|g' \
  hacker-news.service | sudo tee /etc/systemd/system/hacker-news.service

sudo cp hacker-news.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hacker-news.timer
```

書き換えが必要なのは `User=` / `WorkingDirectory=` / `EnvironmentFile=` の 3 箇所です。

> [!WARNING]
> **タイムゾーンに注意。** `hacker-news.timer` は `OnCalendar=... Asia/Tokyo` を明示していますが、
> システムのタイムゾーン設定次第でズレることがあります。UTC のコンテナ等では確認を。
> ```bash
> timedatectl | grep "Time zone"
> sudo timedatectl set-timezone Asia/Tokyo   # 必要なら
> ```

### ステータス確認

```bash
systemctl list-timers hacker-news.timer          # 次回実行時刻
sudo journalctl -u hacker-news.service -n 50      # 実行ログ
```

## ファイル構成

```
Hacker-News-to-discord/
├── main.py               # メインスクリプト（取得・翻訳・整形・送信・保存）
├── run.sh                # 実行ラッパー（venv + env 読み込み）
├── setup.sh              # セットアップ検証ツール
├── requirements.txt      # Python 依存パッケージ
├── hacker-news.service   # systemd サービス（※ User/パス要確認）
├── hacker-news.timer     # systemd タイマー（毎朝 07:00 JST）
└── .env.example          # 環境変数テンプレート
```

## トラブルシューティング

<details>
<summary><b>Discord にメッセージが届かない</b></summary>

- Webhook URL が有効か、Discord サーバーの Webhook 投稿権限があるか確認
- ログに `429` が出ていればレート制限。コードは自動で待機・再試行します
</details>

<details>
<summary><b>API キーが無効というエラー</b></summary>

- `~/.hacker-news-env` の `GEMINI_API_KEY` が正しいか確認
- パーミッションが `600` か確認：`ls -l ~/.hacker-news-env`
</details>

<details>
<summary><b>翻訳が空になる／要約が付かない</b></summary>

- Gemini の一時的な失敗時でも、タイトルと URL は投稿されます（グレースフル劣化）
- 継続する場合は `GEMINI_MODEL` を有効なモデル名に変更してください
</details>

<details>
<summary><b>systemd タイマーが動かない</b></summary>

```bash
systemctl is-enabled hacker-news.timer
systemctl list-timers hacker-news.timer
sudo journalctl -u hacker-news.service -xe
```
</details>

## ライセンス

MIT License
