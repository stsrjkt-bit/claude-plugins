---
name: test
description: >
  実アプリのビジュアルE2Eテスト。Playwright MCPで操作→スクショ→HTMLレポート→Gist公開。
  「テストして」「動作確認」「スクショ付きテスト」「テスト報告」等で発火。
user_invocable: true
---

# /test — ビジュアルE2Eテスト & レポート

実アプリを Playwright MCP で操作し、スクショ付きテストレポートを生成して Gist 経由で共有する。

## 使い方

```
/test <テスト対象の説明>
/test AddBookWizard の DnD 並べ替え
/test ナレッジカードのフリック操作
```

## 全体フロー

```
Phase 1: 準備 → Phase 2: テスト実行 → Phase 3: レポート生成 → Phase 4: 公開
```

---

## Phase 1: 準備

### 1-1. dev サーバー確認

```bash
lsof -i :5173 2>/dev/null | grep LISTEN
```

- 起動済み → そのまま進む
- 未起動 → `npm run dev` をバックグラウンドで起動し、応答するまで待つ

### 1-2. Playwright MCP でブラウザ起動

`browser_navigate` で `http://localhost:5173` を開く。

### 1-3. テスト対象の特定

ユーザーの説明から、テスト対象の画面・機能を特定する。
直近の変更内容（git diff / git log）も参考にする。

### 1-4. テスト計画

テストステップを箇条書きで作成（5〜15ステップ）。
各ステップに「操作」と「期待結果」を明記する。

---

## Phase 2: テスト実行

### 各ステップで必ず行うこと

1. **Playwright MCP で操作**（`browser_click`, `browser_fill_form`, `browser_snapshot` 等）
2. **スクショ撮影**: `browser_take_screenshot` で PNG 取得
3. **結果記録**: PASS / FAIL / WARN + 短いメモ

### スクショ保存

```bash
mkdir -p test-results
# ファイル名: test-{NN}-{slug}.png
# 例: test-01-home.png, test-02-shelf-tab.png
```

### ボトムナビに隠れるボタンの対処

画面下部の fixed ナビがボタンを覆って `click` がタイムアウトする場合:

```
# evaluate で直接クリック
browser_evaluate(ref=対象ref, function="(el) => el.click()")
```

### ドラッグ&ドロップのテスト（dnd-kit等）

`browser_drag` は HTML5 drag プロトコルを使うため、**PointerSensor ベースの dnd-kit では動作しない**。
代わりに `browser_run_code` で `page.mouse` API を使う:

```js
async (page) => {
  // ドラッグ元・先の座標を取得
  const coords = await page.evaluate(() => {
    // セレクタでハンドル要素を特定し、getBoundingClientRect()
  });

  const src = coords[fromIndex];
  const dst = coords[toIndex];

  // page.mouse でポインタドラッグ
  await page.mouse.move(src.cx, src.cy);
  await page.mouse.down();

  const steps = 20;
  for (let i = 1; i <= steps; i++) {
    const t = i / steps;
    await page.mouse.move(
      src.cx + (dst.cx - src.cx) * t,
      src.cy + (dst.cy - src.cy) * t
    );
    await page.waitForTimeout(30);
  }

  await page.mouse.up();
  await page.waitForTimeout(500);

  // 結果を検証
  const newOrder = await page.evaluate(() => { /* DOM確認 */ });
  return { before, after: newOrder };
}
```

**重要**: `browser_run_code` 内では `setTimeout` が使えない。`page.waitForTimeout()` を使うこと。

### 状態の一括構築

テスト対象画面までのナビゲーションが長い場合、`browser_run_code` で一気にセットアップ:

```js
async (page) => {
  await page.waitForTimeout(3000); // アプリ読み込み待ち
  // ナビ → タブ → ボタン → フォーム入力 を一気に実行
  await page.locator('...').click();
  // ...
  return { ready: true };
}
```

### FAIL 時の対応

- スクショは必ず撮る（失敗状態を記録）
- コンソールエラーがあれば `browser_console_messages` で取得
- テストは続行する（1つの FAIL で全停止しない）

### モバイルテスト

1. `browser_resize` で iPhone 14 サイズ (390×844) にリサイズ
2. レイアウト崩れがないか確認
3. スクショファイル名に `-mobile` サフィックスを付ける

---

## Phase 3: レポート生成

### テストレポート HTML

全スクショを Base64 埋め込みした自己完結型 HTML を Python スクリプトで生成する。

```python
python3 << 'PYEOF'
import base64, os
from datetime import datetime

steps = [
    {"file": "test-results/test-01-xxx.png", "title": "...", "desc": "...", "result": "pass"},
    # ...
]

pass_count = sum(1 for s in steps if s["result"] == "pass")
fail_count = sum(1 for s in steps if s["result"] == "fail")

steps_html = ""
for i, s in enumerate(steps, 1):
    with open(s["file"], "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    steps_html += f'''
  <div class="step">
    <div class="step-header">
      <div class="step-num {s["result"]}">{i}</div>
      <div class="step-title">{s["title"]}</div>
    </div>
    <p class="step-desc">{s["desc"]}</p>
    <img class="step-img" src="data:image/png;base64,{b64}" loading="lazy" />
  </div>'''

# ... HTML テンプレートに埋め込み、ファイル保存
PYEOF
```

### HTMLテンプレートのデザイン

- フォント: IBM Plex Sans JP + JetBrains Mono
- 背景: #0a0f1a（ダークテーマ）
- アクセント: #39FF85（PASS）/ #ef4444（FAIL）/ #f59e0b（WARN）
- ヘッダー: テスト名 + 日時 + ブランチ + コミットhash
- サマリーバッジ: PASS/FAIL件数
- 各ステップ: 番号バッジ + タイトル + 説明 + スクショ

### レポートファイル

```bash
# ファイル名: test-report-{slug}-{YYYYMMDD}.html
# 保存先: プロジェクトルート
```

---

## Phase 4: 公開

### Gist にアップロード

```bash
GIST_URL=$(gh gist create --public test-report-*.html --desc "Test Report: {テスト対象}" 2>&1)
GIST_ID=$(echo "$GIST_URL" | awk -F/ '{print $NF}')
```

### githack.com URL 生成

```
https://gist.githack.com/{GitHubユーザー名}/{GIST_ID}/raw/{filename}
```

### ユーザーへ報告

```
## テスト結果: {テスト対象}

| # | ステップ | 結果 |
|---|---------|------|
| 1 | ... | PASS |
| 2 | ... | FAIL |

**全体: {pass}/{total} PASS**

レポート: {githack URL}
```

---

## 注意事項

- **認証が必要な場合**: テスト用アカウントでログイン状態を作ってからテスト開始
- **破壊的操作**: 本番データに影響する操作（削除等）は実行前に確認
- **タイムアウト**: Playwright MCP の操作は各 30 秒以内。長い場合は waitFor を使う
- **既存の test-*.png**: テスト実行前に古い test-*.png を削除しない（別テストのものかもしれない）
