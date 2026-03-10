---
name: safari-test
description: >
  Playwright WebKitを使ったiOS Safari互換性テスト。
  既存テストの実行、新規テストケースの追加、iOS Safari固有の問題検証を行う。
  「Safariテスト」「iOSテスト」「WebKitテスト」「iPhoneで動くか確認」等で発火。
user_invocable: true
---

# /safari-test — iOS Safari 互換性テスト

Playwright WebKit (iPhone 14 デバイスプロファイル) でiOS Safari互換性をテストする。

## 使い方

```
/safari-test                    <- 既存テスト全実行
/safari-test run                <- 同上
/safari-test add <説明>         <- 新しいテストケースを追加して実行
/safari-test check <ファイル>   <- 指定コンポーネントのiOS互換性をチェック
```

## 前提条件

- studygramリポジトリに `@playwright/test` がインストール済み
- WebKitブラウザがインストール済み (`npx playwright install webkit`)
- テストファイル: `e2e/*.spec.ts` (複数ファイル)
- 設定: `playwright.config.ts` (project: webkit = iPhone 14)

## 実行手順

### `run` (デフォルト): 既存テスト全実行

```bash
npx playwright test e2e/ --project=webkit
```

※ studygram リポジトリのルートで実行すること。

全 `e2e/*.spec.ts` ファイルを WebKit で実行する。
結果を確認し、失敗テストがあればスクリーンショットとエラー内容を報告する。

### `add`: 新しいテストケースを追加

1. ユーザーの説明から、テストすべきiOS Safari固有の挙動を特定する
2. 適切な `e2e/*.spec.ts` に新しい `test()` を追加（既存ファイルが合わなければ新規作成）
3. テストを実行して通過を確認
4. 失敗した場合は原因を調査して修正案を提示

**テスト追加時の注意:**
- `test.describe` で論理グループにまとめる
- `page.setContent()` でインラインHTMLを使う（devサーバー不要にする）
- ポップアップは `context.waitForEvent('page')` で待つ
- タイミング依存のアサーションは `expect().toHaveText()` 等のauto-retryを使う
- タッチイベントは後述の **synthetic touch dispatch パターン** を使う

### `check`: コンポーネントのiOS互換性チェック

指定ファイルを読み、以下のiOS Safari地雷パターンを検出して報告する:

| パターン | 問題 | 修正方法 |
|----------|------|----------|
| `async` コールバック内の `window.open()` | ポップアップブロッカーにブロックされる | 同期的に `window.open('')` → await後に `location.href` 差し替え |
| `blob:` URLを `window.open` | iOS 13-14でBlobメモリ分断→白画面 | Web Share API (iOS 15+) + Base64 Data URI (iOS 13-14) の2段構え |
| `await` 後に `window.open` へフォールバック | `navigator.share()` 失敗後の `window.open` はユーザージェスチャーコンテキスト消失でブロック | `canShare` がtrueなら常にreturn、Base64フォールバックに落ちないようにする |
| React `onTouchStart` / `onTouchMove` で `e.preventDefault()` | React synthetic eventsはpassiveリスナー。preventDefaultが無効 | `useEffect` + `addEventListener({ passive: false })` でDOM直接登録 |
| `e.touches[0]` にガード無し | multi-touch等でundefinedになりランタイムエラー | `if (!touch) return;` を追加 |
| `position: fixed` + `overflow: auto` | iOS Safariでスクロールが効かない | `-webkit-overflow-scrolling: touch` を追加 |
| `100vh` | iOS Safariのアドレスバーを考慮しない | `100dvh` またはJS計算 |
| `<input>` の `focus()` | ユーザージェスチャー外だとキーボードが出ない | click/touchイベント内で呼ぶ |
| `fetch` + `ReadableStream` | iOS 14以前で未サポート | arrayBuffer() で受け取る |
| `Web Share API` | HTTPS必須、一部機能未サポート | `navigator.share` の存在チェック必須 |
| `CSS gap` (flexbox) | iOS 14.4以前で未サポート | margin で代替 |
| `backdrop-filter` | `-webkit-backdrop-filter` が必要 | 両方指定する |

検出結果を一覧で報告し、修正が必要なものはコード修正案も提示する。

## Synthetic Touch Dispatch パターン

Playwright WebKit では `new Touch()` コンストラクタが使えない（`TypeError: Illegal constructor`）。
また `page.touchscreen` は `tap()` のみで swipe/drag はサポートしない (v1.58)。

タッチイベントのテストには以下のパターンを使う:

### ページ内ヘルパー注入

```javascript
// page.setContent() のスクリプト内に以下を追加
// canvas や div 等、タッチ対象の要素を指定する
const target = document.getElementById('canvas');
window._dispatchTouch = (type, x, y) => {
  const evt = new Event(type, { bubbles: true, cancelable: true });
  const fakeTouch = { clientX: x, clientY: y, target, identifier: 0 };
  evt.touches = type === 'touchend' ? [] : [fakeTouch];
  evt.changedTouches = [fakeTouch];
  target.dispatchEvent(evt);
  return evt.defaultPrevented;
};
```

### テストコードからの呼び出し

```typescript
const result = await page.evaluate(async () => {
  const dispatch = (window as any)._dispatchTouch;
  dispatch('touchstart', 50, 50);
  for (let i = 1; i <= 5; i++) {
    await new Promise(r => setTimeout(r, 16));
    dispatch('touchmove', 50 + i * 30, 50 + i * 30);
  }
  const wasPrevented = dispatch('touchend', 200, 200);
  return wasPrevented;
});
```

### passive vs non-passive の検証

```typescript
// passive listener では defaultPrevented が false になることを検証
const target = document.getElementById('my-element')!;
const evt = new Event('touchstart', { bubbles: true, cancelable: true });
evt.touches = [{ clientX: 100, clientY: 100, target, identifier: 0 }];
evt.changedTouches = evt.touches;
target.dispatchEvent(evt);
// passive: evt.defaultPrevented === false
// non-passive: evt.defaultPrevented === true
```

## iOS Safari 既知の地雷集（テスト作成時の参考）

### ポップアップ・ナビゲーション
- `window.open()` は同期的なユーザージェスチャーコンテキスト内でのみ許可
- `async/await` を挟むとコンテキストが切れてブロックされる
- `blob:` URLの共有シートは制限される（プリンターアプリが表示されない等）
- iOS 13-14: `blob:` URL を `window.open` で開くと、別タブからは blob メモリにアクセスできず白画面になる
- 推奨パターン: Web Share API (iOS 15+) + Base64 Data URI (iOS 13-14) の2段構え
- `navigator.share()` 失敗後の `window.open` フォールバックはユーザージェスチャー消失でブロックされるため、`canShare` が true なら常に return

### タッチイベント・Canvas
- React synthetic touch events (`onTouchStart` 等) は **passive** リスナー。`preventDefault()` が無効
- Canvas描画にはDOM直接 `addEventListener('touchstart', fn, { passive: false })` が必要
- `touch-action: none` CSS だけでは不十分なケースがある（モーダル内バウンス等）
- `e.touches[0]` は常に存在が保証されないため guard clause 必須
- Canvas メモリ制限: iOS Safari は Canvas のピクセル数に上限あり（16MP）。大きな PDF ページのレンダリングで `dpr` を掛けすぎるとクラッシュ → `Math.min(dpr, 2)` でキャップ

### レイアウト・スクロール
- `100vh` がアドレスバーを含むため実際の表示領域と一致しない
- `position: fixed` の要素内スクロールに `-webkit-overflow-scrolling: touch` が必要
- セーフエリア: `env(safe-area-inset-*)` の考慮が必要

### フォーム・入力
- `<input type="date">` のUIが独自
- `autofocus` が効かない（ユーザージェスチャー必須）
- 仮想キーボード表示時の `visualViewport` リサイズが `window.innerHeight` と異なる挙動になる
- `visualViewport` API でキーボード高さを検出する必要がある（iOS 13+対応）

### メディア・ファイル
- `<video>` の自動再生にはmutedが必須
- Web Audio APIの再生開始にはユーザージェスチャーが必須
- PDF表示がiOS独自ビューアになる
- `FileReader.readAsDataURL()` は大きなファイル（10MB超）でメモリ圧迫→iOS低メモリ端末でクラッシュの可能性

### ナビゲーション・キャッシュ
- bfcache（Back/Forward Cache）: `pageshow` イベントの `event.persisted` を確認し、キャッシュ復帰時にステート再初期化が必要
- Safari は他ブラウザより積極的に bfcache を使うため、SPA でも `pagehide`/`pageshow` を監視すべき

## Playwright WebKit の制約

Playwright WebKitは **WebKitエンジン (GTKポート)** を使っている。
iOS Safariと同一エンジンだが、以下は再現しない:

- iOSのポップアップブロッカーの厳密な判定ロジック
- セーフエリア (`env(safe-area-inset-*)`)
- iOS固有のスクロールバウンス
- AirPrintダイアログ
- 共有シートのアクティビティ一覧

**API制約:**
- `new Touch()` コンストラクタは `TypeError: Illegal constructor` で失敗する → `new Event()` + プロパティ付与で代替
- `page.touchscreen` は `tap()` のみ。`swipe()` は未実装 (v1.58)
- マウスイベントとタッチイベントは別パスなので、`page.mouse` はタッチハンドラを検証できない

**つまり**: エンジンレベルのバグ（CSS、JS API）は検出できるが、
OS統合レベルの問題は検出できない。後者は実機テストが必要。
