# atama+ COACH 自動化プラグイン

Chromium + chrome-devtools MCP 経由で atama+ COACH を操作し、生徒のつまずき分析→補習プリント作成→PDF出力を一気通貫で実行するスキル。

## 前提条件

- Google Chrome がインストール済み
- chrome-devtools MCP が設定済み
- `~/.env.atama` に認証情報（Doppler 経由で生成）
- Puppeteer（`scripts/` 内に `npm install` 済み）

## スキル

- `/atama <生徒名> <教科>` — フルパイプライン
- `/atama login` — Chrome起動＆ログインのみ

## コマンド

- `/atama` — SKILL.md の Phase 1〜12 を実行
