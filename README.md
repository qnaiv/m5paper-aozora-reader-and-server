# M5Paper 日替わり青空文庫リーダー

M5Stack社の電子ペーパー端末「M5Paper」で、毎日ランダムに選ばれた青空文庫の作品を読めるシステムです。

## システムアーキテクチャ

M5Paperのリソース制約（メモリ・Shift_JIS処理等）を回避するため、処理をサーバーサイドとクライアントサイドに分離しています。

```
[GitHub Actions (毎日定時)]
    │
    ├─ scripts/fetch_aozora.py を実行
    ├─ 青空文庫からランダムに1作品取得・クリーニング
    └─ data/todays_book.json をリポジトリにコミット
                │
                │ GitHub Raw URL
                ▼
[M5Paper (MicroPython)]
    │
    ├─ 起動時 or 日付変更時に todays_book.json を取得
    ├─ テキストをページに分割
    └─ E-Inkに表示・タッチでページめくり
```

## リポジトリ構成

```
.
├── .github/
│   └── workflows/
│       ├── claude.yml          # Claude Code GitHub Actions
│       └── daily_update.yml    # 毎日定時実行ワークフロー（Issue 2で作成）
├── scripts/
│   └── fetch_aozora.py         # 青空文庫スクレイピングスクリプト（Issue 1で作成）
├── data/
│   └── todays_book.json        # 毎日更新される今日の作品データ
├── m5paper/
│   ├── main.py                 # M5Paperメインアプリ（Issue 3/4で作成）
│   ├── config.py               # Wi-FI・URL等の設定
│   └── lib/
│       ├── wifi.py             # Wi-Fi接続
│       ├── time_sync.py        # NTP時刻同期
│       ├── fetcher.py          # JSON取得
│       ├── font_loader.py      # 日本語フォント読み込み
│       ├── paginator.py        # テキスト折り返し・ページ分割
│       ├── renderer.py         # E-Ink描画
│       └── touch.py            # タッチ入力処理
├── requirements.txt            # Pythonスクリプトの依存ライブラリ
└── README.md
```

## データ仕様

### data/todays_book.json

GitHub Actions が毎日更新するファイル。M5Paper はこのファイルを GitHub Raw URL から取得します。

```json
{
  "title": "作品タイトル",
  "author": "著者名",
  "text": "本文テキスト（プレーンUTF-8、ルビ・注記・HTMLタグなし）"
}
```

**GitHub Raw URL:**
```
https://raw.githubusercontent.com/qnaiv/m5paper-aozora-reader-and-server/main/data/todays_book.json
```

## マイルストーン

| Issue | 内容 | 依存 | 状態 |
|-------|------|------|------|
| [#2](https://github.com/qnaiv/m5paper-aozora-reader-and-server/issues/2) | 青空文庫スクレイピングPythonスクリプト | なし | 未着手 |
| [#3](https://github.com/qnaiv/m5paper-aozora-reader-and-server/issues/3) | GitHub Actions 定時実行ワークフロー | Issue #2 | 未着手 |
| [#4](https://github.com/qnaiv/m5paper-aozora-reader-and-server/issues/4) | M5Paper 基盤機能（Wi-Fi/NTP/JSON取得） | なし | 未着手 |
| [#5](https://github.com/qnaiv/m5paper-aozora-reader-and-server/issues/5) | M5Paper UI・ページネーション | Issue #4 | 未着手 |

## ハードウェア仕様（M5Paper）

- **ディスプレイ:** 960×540 E-Ink（4グレースケール）
- **プロセッサ:** ESP32-D0WDQ6-V3
- **メモリ:** 8MB PSRAM / 16MB Flash
- **タッチ:** 静電容量式タッチパネル（全面）
- **接続:** Wi-Fi 802.11 b/g/n

## 技術的制約と設計方針

### Python スクリプト（GitHub Actions側）

- 実行環境: Python 3.11 on Ubuntu（GitHub Actions）
- 青空文庫のテキストは **Shift_JIS** エンコード → UTF-8に変換して保存
- クリーニング対象: ルビ `《》｜`、注記 `［＃...］`、HTMLタグ
- 短すぎる作品（本文500文字未満）はスキップして再選択

### MicroPython スクリプト（M5Paper側）

- 実行環境: MicroPython（UIFlow2 または M5Stack MicroPython）
- `import requests` ではなく `import urequests as requests` を使用
- 標準ライブラリ: `network`, `ntptime`, `ujson`, `gc`, `time`
- メモリ節約のため `gc.collect()` をページ遷移ごとに呼ぶ
- 大作品（10万文字超）は冒頭3万文字に切り詰めて処理

### フォント

- 日本語TTFフォントをM5PaperのFlashまたはSDカードに配置する
- 推奨パス: `/flash/fonts/unifont.ttf`
- フォントサイズ: タイトル 20px、本文 24px、ページ番号 18px

## 開発フロー

このリポジトリではIssueコメントに `@claude` をメンションするとClaude Code GitHub Actionsが起動します。

Claude Codeは以下のフェーズで段階的に開発を進めます：

1. **要件定義フェーズ** (`phase:requirements`) — Issue内容の分析・不明点の確認
2. **設計フェーズ** (`phase:design`) — アーキテクチャ設計・ファイル構成の決定
3. **設計確認フェーズ** (`phase:design-review`) — 設計内容の最終確認・実装承認
4. **実装フェーズ** (`phase:implementation`) — コード実装・PR作成

各フェーズでユーザーの承認を得てから次のフェーズに進みます。

## セットアップ

### GitHub Actions の設定

`CLAUDE_CODE_OAUTH_TOKEN` シークレットをリポジトリに設定してください。

### M5Paper へのデプロイ

1. `m5paper/config.py` の `WIFI_SSID` と `WIFI_PASSWORD` を書き換える
2. 日本語フォントファイルを `/flash/fonts/unifont.ttf` に配置する
3. `m5paper/` 以下のファイルをM5PaperのFlashにコピーする
