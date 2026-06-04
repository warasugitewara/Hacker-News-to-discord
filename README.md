# Hacker News to Discord

Hacker News の最新記事を毎日自動取得し、Gemini API で日本語翻訳・要約して Discord に送信。ローカルに保存し、GitHub に自動コミットします。

## 機能

- ✓ 過去 24 時間の Hacker News トップ 5 記事を自動取得
- ✓ Gemini 3.5 Flash で日本語翻訳・要約
- ✓ 整形済み Discord メッセージ：
  - 記事タイトルはクリック可能なマークダウンリンク
  - 日本語翻訳と要約は引用形式
  - URL 埋め込みなし（クリーンで読みやすい）
  - 記事ごとに明確に分離
- ✓ API レート制限に対応
- ✓ API 利用不可時はデモモードにフォールバック
- ✓ 毎日のダイジェストを Archive ディレクトリに保存
- ✓ 自動的に GitHub にコミット＆プッシュ
- ✓ **毎日 07:00 JST に systemd タイマーで自動実行**

## クイックスタート

### 1. セットアップ（初回のみ）

```bash
cd ~/Hacker-news-to-Discord

# 仮想環境を作成
python3 -m venv venv

# 依存パッケージをインストール
venv/bin/pip install --no-user -r requirements.txt
```

### 2. API キーを設定

```bash
# 環境変数ファイルを作成
cat > ~/.hacker-news-env << 'EOF'
GEMINI_API_KEY=your-api-key-here
DISCORD_WEBHOOK_URL=your-webhook-url-here
EOF

# ファイルをセキュアに
chmod 600 ~/.hacker-news-env
```

**API キーを取得：**
- **Gemini API:** https://aistudio.google.com/app/api-keys
- **Discord Webhook:** Discord サーバー > 設定 > 連携 > Webhook

### 3. 設定を確認

```bash
./setup.sh
```

以下をチェックします：
- ✓ 仮想環境が存在
- ✓ API キーが設定されている
- ✓ Python 依存パッケージがインストール済み

### 4. 手動実行してテスト

```bash
./run.sh
```

## 自動実行の設定（systemd）

### サービスファイルをインストール

```bash
# systemd ファイルをコピー（sudo が必要）
sudo cp hacker-news.service /etc/systemd/system/
sudo cp hacker-news.timer /etc/systemd/system/

# systemd デーモンをリロード
sudo systemctl daemon-reload

# タイマーを有効化＆開始
sudo systemctl enable --now hacker-news.timer
```

### ステータス確認

```bash
# タイマーのステータスを確認
sudo systemctl status hacker-news.timer

# スケジュール済みタイマーを表示
sudo systemctl list-timers

# 最近の実行ログを確認
sudo journalctl -u hacker-news.service -n 50
```

## ファイル構成

```
Hacker-news-to-Discord/
├── main.py                  # メイン Python スクリプト
├── run.sh                   # 実行スクリプト（Git 自動化含む）
├── setup.sh                 # セットアップ検証ツール
├── requirements.txt         # Python 依存パッケージ
├── README.md                # このファイル
├── hacker-news.service      # systemd サービスユニット
├── hacker-news.timer        # systemd タイマーユニット
├── .env.example             # 環境変数テンプレート例
└── Archive/                 # 毎日のダイジェスト保存先（自動作成）
    └── YYYY-MM-DD.md        # 日付ごとのダイジェスト
```

## 動作フロー

1. **毎日 07:00 JST** - 自動実行開始
2. Hacker News API から過去 24 時間のトップ 5 記事を取得
3. Gemini API で日本語に翻訳・要約
4. Discord Webhook 経由でメッセージを送信 📨
5. Archive ディレクトリに Markdown ファイルで保存
6. 変更を GitHub にコミット＆プッシュ 🚀

## トラブルシューティング

### API キーが無効とエラーが出る

- `~/.hacker-news-env` の API キーが正しいか確認
- ファイルのパーミッションが `600` か確認：`ls -l ~/.hacker-news-env`

### Discord にメッセージが届かない

- Webhook URL が有効か確認
- Discord サーバーの権限を確認（Webhook の投稿権限）

### systemd タイマーが実行されない

```bash
# タイマーが有効か確認
systemctl is-enabled hacker-news.timer

# 次の実行予定を確認
systemctl list-timers hacker-news.timer

# 実行ログを確認
sudo journalctl -u hacker-news.service -xe
```

## ライセンス

MIT License
