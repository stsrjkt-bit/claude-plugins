---
name: browser
description: WSL2環境でChrome headless + Playwright connectOverCDP によるブラウザ自動化。重いサイト（Ionic/SPA）でもタイムアウトしない。
args:
  - name: command
    description: "'start' でChrome起動、'stop' で停止、'status' で状態確認、引数なしで起動+接続テンプレート出力"
---

# /browser — WSL2 ブラウザ自動化スキル

## 背景

WSL2 環境で Playwright の `chromium.launch()` を使うと、重いサイト（atama+ COACH 等の Ionic/SPA）で
タイムアウトする。解決策: **Chrome headless を事前起動し、`connectOverCDP` で接続する**。

## 使い方

```
/browser          # Chrome起動 + 接続テンプレート出力
/browser start    # Chrome headless 起動のみ
/browser stop     # Chrome 停止
/browser status   # 起動状態確認
```

## 引数判定

- **引数なし** → Chrome起動確認 + スクリプトテンプレート出力
- **`start`** → Chrome起動のみ
- **`stop`** → Chrome停止のみ
- **`status`** → `curl http://127.0.0.1:9222/json/version` で確認

## Chrome 起動

```bash
# 既に起動中ならスキップ
if curl -s http://127.0.0.1:9222/json/version > /dev/null 2>&1; then
  echo "Already running"
else
  google-chrome \
    --headless=new \
    --no-sandbox \
    --disable-setuid-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    --no-first-run \
    --remote-debugging-port=9222 \
    --remote-allow-origins=* \
    --user-data-dir="$HOME/.config/chrome-headless" \
    about:blank > /tmp/chrome-headless.log 2>&1 &

  echo $! > /tmp/chrome-headless.pid

  # 起動待ち（最大10秒）
  started=false
  for i in $(seq 1 10); do
    sleep 1
    if curl -s http://127.0.0.1:9222/json/version > /dev/null 2>&1; then
      echo "Chrome started (port 9222, PID=$(cat /tmp/chrome-headless.pid))"
      started=true
      break
    fi
  done
  if [ "$started" = false ]; then
    echo "Chrome failed to start. Check /tmp/chrome-headless.log"
  fi
fi
```

### 重要事項
- `--user-data-dir` は `"$HOME/..."` のようにダブルクォートで囲む（シェルが `$HOME` を正しく展開する）
- `--headless=new` は Chrome 112+ の新しいヘッドレスモード（旧 `--headless` より互換性が高い）
- ポートは **9222 固定**（chrome-devtools MCP と共有可能）
- PID は `/tmp/chrome-headless.pid` に保存される

## Playwright 接続テンプレート

引数なしで呼ばれた場合、以下のテンプレートを出力する:

```javascript
import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  const context = browser.contexts()[0] || await browser.newContext();
  const page = context.pages()[0] || await context.newPage();

  // ネットワーク傍受（goto の前に登録しないとリクエストを取りこぼす）
  page.on('response', async resp => {
    if (resp.url().includes('api.example.com')) {
      console.log(resp.url(), resp.status());
    }
  });

  // --- ここから自由に使う ---
  await page.goto('https://example.com', { waitUntil: 'domcontentloaded', timeout: 60000 });
  // スクショ
  await page.screenshot({ path: '/tmp/screenshot.png' });

  await browser.close();
})();
```

### スクリプト配置ルール
- `import { chromium } from 'playwright'` を使うスクリプトは **プロジェクト内**（`node_modules/playwright` がある場所）に配置する
- `/tmp/` に置くと `ERR_MODULE_NOT_FOUND` になる

## Chrome 停止

```bash
PID_FILE="/tmp/chrome-headless.pid"
if [ -f "$PID_FILE" ]; then
  kill "$(cat "$PID_FILE")" 2>/dev/null && rm -f "$PID_FILE"
  echo "Chrome stopped."
else
  echo "PID file not found. Falling back to pkill."
  pkill -f "chrome.*--remote-debugging-port=9222" 2>/dev/null
fi
```

## よくあるトラブル

| 症状 | 原因 | 対処 |
|------|------|------|
| `curl: (7) Failed to connect` | Chrome未起動 or 起動失敗 | `/tmp/chrome-headless.log` を確認。`--user-data-dir` が絶対パスか確認 |
| `ERR_MODULE_NOT_FOUND: playwright` | スクリプトが `node_modules` 外にある | プロジェクトディレクトリ内にスクリプトを配置 |
| `Target closed` | ページが閉じた/Chrome再起動された | `browser.contexts()` を再取得 |
| COACHログインでモーダルがブロック | 「Google Chromeをお使いください」モーダル | `page.keyboard.press('Escape')` + `force: true` でクリック |

## 他スキルとの連携

- **/atama**: Phase 1 のログインで `connectOverCDP` を使える（`launch-chrome.sh` の代替）
- **/test**: Playwright MCP の代わりに直接 CDP 接続でテスト実行可能
- **ネットワーク傍受**: `page.on('response', ...)` で API リクエストをキャプチャ（MCP不要）
