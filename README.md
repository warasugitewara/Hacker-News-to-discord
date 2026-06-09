# Hacker News to Discord

Hacker News の最新記事を毎日自動取得し、Gemini API で日本語翻訳・要約して Discord に送信。ローカルに保存し、GitHub に自動コミットします。

## 制作理由

Hacker Newsへの関心はあってもURLにいちいち入るのも大変だし、翻訳する手間もかかるため、作成しました。

## 機能

- ✓ 過去 24 時間の Hacker News トップ 5 記事を自動取得
- ✓ Gemini 3.5 Flash で日本語翻訳・要約
- ✓ 整形済み Discord メッセージ：
  * 記事タイトルはクリック可能なマークダウンリンク
  * 日本語翻訳と要約は引用形式
  * URL 埋め込みなし（クリーンで読みやすい）
  * 記事ごとに明確に分離
- ✓ API レート制限に対応
- ✓ API 利用不可時はデモモードにフォールバック
- ✓ 毎日のダイジェストを Archive ディレクトリに保存
- ✓ 自動的に GitHub にコミット＆プッシュ
- ✓ **毎日 07:00 JST に systemd タイマーで自動実行**

## クイックスタート

### 1. セットアップ（初回のみ）

```bash
cd ~/Hacker-News-to-discord

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

### ⚠️ 事前確認：ユーザー名とパスの変更

`hacker-news.service` はデフォルトで `User=waras`、パスが `/home/waras/Hacker-news-to-Discord` にハードコードされている。
**異なるユーザー・環境で動かす場合は必ず書き換えてからコピーすること。**

```bash
# 現在のユーザーとリポジトリパスを確認
whoami
pwd
```

ユーザー名やパスがデフォルトと異なる場合は `sed` で一括置換してからインストールする：

```bash
# 例：root ユーザー、/root/Hacker-News-to-discord に配置した場合
sed \
  -e 's|User=waras|User=root|g' \
  -e 's|/home/waras/Hacker-news-to-Discord|/root/Hacker-News-to-discord|g' \
  -e 's|/home/waras/\.hacker-news-env|/root/.hacker-news-env|g' \
  hacker-news.service | sudo tee /etc/systemd/system/hacker-news.service
```

> `hacker-news.service` 内で変更が必要な箇所は以下の3点：
> - `User=` — 実行ユーザー
> - `WorkingDirectory=` — リポジトリの絶対パス
> - `EnvironmentFile=` — `.hacker-news-env` の絶対パス

変更後は必ず内容を確認する：

```bash
cat /etc/systemd/system/hacker-news.service
```

### ⚠️ 事前確認：タイムゾーン

`hacker-news.timer` の `OnCalendar=*-*-* 07:00:00` はシステムのローカル時刻で動作する。
LXC コンテナ等はデフォルトで UTC になっていることが多く、そのままでは **07:00 UTC = 16:00 JST** に実行される。

```bash
# タイムゾーン確認
timedatectl | grep "Time zone"

# UTC になっていたら JST に変更
sudo timedatectl set-timezone Asia/Tokyo
```

### サービスファイルをインストール

```bash
# hacker-news.service は上記の sed コマンドで直接インストール済みの場合はスキップ
# timer はそのままコピーで OK
sudo cp hacker-news.timer /etc/systemd/system/

# systemd デーモンをリロード
sudo systemctl daemon-reload

# タイマーを有効化＆開始
sudo systemctl enable --now hacker-news.timer
```

### ステータス確認

```bash
# 次回実行時刻を確認（NEXT が JST 07:00 になっていれば OK）
systemctl list-timers hacker-news.timer

# 最近の実行ログを確認
sudo journalctl -u hacker-news.service -n 50
```

## ファイル構成

```
Hacker-News-to-discord/
├── main.py                  # メイン Python スクリプト
├── run.sh                   # 実行スクリプト（Git 自動化含む）
├── setup.sh                 # セットアップ検証ツール
├── requirements.txt         # Python 依存パッケージ
├── README.md                # このファイル
├── hacker-news.service      # systemd サービスユニット（※パス要確認）
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

### git push が失敗する

systemd 経由での実行は SSH エージェントが使えないため、GitHub との認証に SSH 鍵を直接使う設定が必要。

```bash
# SSH 鍵を生成（未作成の場合）
ssh-keygen -t ed25519 -C "hacker-news-lxc" -f ~/.ssh/id_ed25519 -N ""

# 公開鍵を GitHub に登録（Settings > SSH and GPG keys）
cat ~/.ssh/id_ed25519.pub

# SSH 接続テスト
ssh -T git@github.com

# remote を SSH に変更
git remote set-url origin git@github.com:warasugitewara/Hacker-News-to-discord.git
```

## Todo（やらない可能性高）

- Docker 対応

## ライセンス

MIT License
