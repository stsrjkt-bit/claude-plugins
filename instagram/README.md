# Instagram投稿プラグイン

塾長の「今日やったこと」から、Instagram投稿のテキスト生成→アイキャッチSVG→画像生成までを一気通貫で実行するスキル。

## 前提条件

- Puppeteer（`scripts/` 内に `npm install` 済み）
- ImageMagick（写真加工用）
- poppler-utils（PDF→画像変換用）

## スキル

- `/instagram <今日やったこと>` — フルパイプライン
- `/instagram research [月]` — 月次リサーチ
- `/instagram retry [パターン]` — コピーパターン別再生成
- `/instagram image` — 画像のみ再生成
- `/instagram photo` — 写真クロップ＋補正

## コマンド

- `/instagram-research` — 月次リサーチ単体
- `/instagram-retry` — パターン再生成単体
