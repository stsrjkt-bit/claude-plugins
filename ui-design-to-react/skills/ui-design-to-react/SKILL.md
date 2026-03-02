---
name: ui-design-to-react
description: >
  Stitch MCP + HTMLモック + Figmaキャプチャを組み合わせたUI制作ワークフロー。
  デザインモック → Stitch生成 → 比較 → Figma統合 → React実装 の5フェーズ。
  「UIを作りたい」「画面設計」「Stitchで生成」「モックからReact」等で発火。
user_invocable: true
---

# /ui-design-to-react — UI制作ワークフロー

Stitch MCP・HTMLモック・Figmaキャプチャを活用し、デザインからReact実装まで一気通貫で進めるスキル。

## 前提ツール

| ツール | 用途 | 注意 |
|--------|------|------|
| Stitch MCP | テキスト→UI生成 | `TEXT_TO_UI_PRO` タイプのプロジェクト必須。生成に1〜2分かかる |
| Playwright MCP | スクショ撮影・HTMLプレビュー | 「見るだけ」用途 |
| Figma MCP | デザイン統合・キャプチャ | `figcap` エイリアスで hash URL 生成 |
| Doppler | シークレット管理 | `doppler secrets get <KEY> --project sato-juku --config dev_studygram --plain` |

## フローの全体像

```
Phase 1: HTMLモック制作（Claude が仕様書として手書き）
    ↓
Phase 2: Stitch 生成（MCP で画面ごとに生成 ← これがデザイン本体）
    ↓
Phase 3: Stitch デザイン採用 + バグ修正（ユーザー確認後、バグのみ修正）
    ↓
Phase 4: Figma 統合（キャプチャ → デザイン確定）
    ↓
Phase 5: React 実装（Stitch デザインを忠実にコード化）
```

**Claude の役割**: Stitch 先生のデザインを現実のコードにする **黒子（実装者）**。UIデザインで対等という意識を持たない。企画されたアプリの機能がきちんと発揮される形で、Stitch のバグ含みデザインをさっと修正する裏方に徹する。

**スキップ可能**: 状況に応じて一部フェーズを省略できる。ただし **Stitch（Phase 2）は原則スキップ不可**。
- デザインが既に確定（Stitch 生成済み） → Phase 5 から
- Figma 不要 → Phase 1 → Phase 2 → Phase 3 → Phase 5
- ユーザーが明示的に「Stitch不要」と指示した場合のみ Phase 2 をスキップできる

---

## Phase 1: HTMLモック制作

**目的**: 全画面の構造・フロー・コピーを Tailwind HTML で固める。

### 手順

1. **画面フローの整理**: ユーザーと画面遷移を確認（状態遷移図をテキストで書く）
2. **HTML作成**: 1ファイルに全画面を `<div id="screenN">` で並べる
   - 幅 375px × 高さ 812px（iPhone サイズ）で固定
   - Tailwind CDN + Google Fonts でスタンドアロン
   - Figmaキャプチャ用に `capture.js` を `<head>` に入れておく:
     ```html
     <script src="https://mcp.figma.com/mcp/html-to-design/capture.js" async></script>
     ```
3. **Playwright でプレビュー確認**: `browser_navigate` → `browser_take_screenshot`
4. **出力**: `design-mock-{feature-name}.html`

### デザイン原則（CLAUDE.md準拠）

- フォント: 用途に合った個性的フォント（Arial/Inter/Roboto禁止）
- 色: メインカラー＋アクセントで攻める。CSS変数で一貫性。紫グラデ＋白背景禁止
- 動き: `@keyframes fadeIn` + `animation-delay` のスタガーが最もコスパ良い
- 背景: ベタ塗り白を避ける。グラデーション・テクスチャで奥行き
- ウェイト: 極端に振る（100/200 vs 800/900）。サイズ差3倍以上

### HTMLモックのテンプレート

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{Feature} — Design Mock</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://mcp.figma.com/mcp/html-to-design/capture.js" async></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family={Font}&display=swap" rel="stylesheet">
  <style>
    * { font-family: '{Font}', sans-serif; }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .animate-fadeIn { animation: fadeIn 0.25s ease-out both; }
    .delay-1 { animation-delay: 0.05s; }
    .delay-2 { animation-delay: 0.1s; }
    .delay-3 { animation-delay: 0.15s; }
    .delay-4 { animation-delay: 0.2s; }
  </style>
</head>
<body class="bg-gray-950">
  <!-- Screen 1 -->
  <div id="screen1" class="w-[375px] h-[812px] bg-gray-950 flex flex-col mx-auto mb-8 overflow-hidden relative">
    ...
  </div>
  <!-- Screen 2 ... -->
</body>
</html>
```

---

## Phase 2: Stitch 生成

**目的**: Stitch MCP で各画面のデザインを生成する。**これがデザインの本体**であり、Phase 5 で忠実にコード化する対象。

### 前提

- Stitch MCP が `~/.claude/mcp.json` に登録済みであること
- `TEXT_TO_UI_PRO` タイプのプロジェクトを使うこと（`PROJECT_DESIGN` だとエラー）
- 既存プロジェクトID: `6578710306801403070`

### 手順

1. **ToolSearch で Stitch ツールを読み込み**:
   ```
   ToolSearch: "+stitch generate"
   ```

2. **画面ごとに `generate_screen_from_text` を呼ぶ**:
   - 1画面ずつ生成（バッチ不可）
   - プロンプトにはHTMLモックの構造を要約して渡す
   - ダークテーマ、配色、フォント等の指定を含める
   - 生成に1〜2分かかる。タイムアウトに注意

3. **生成結果を取得**:
   - `get_screen_image` でスクショ PNG を保存: `stitch-screen{N}.png`
   - `get_screen_code` でHTML を保存: `stitch-html-screen{N}.html`
   - Playwright で HTML をレンダリングしてスクショも撮る: `stitch-render-screen{N}.png`

### Stitch プロンプトのコツ

```
Mobile screen (375x812). Dark theme (gray-950 background).
Amber-500/600 accent color. Font: Space Grotesk + Noto Sans JP.

Screen: [画面名]
- [要素1の説明]
- [要素2の説明]
- ...

Style: rounded-2xl cards, subtle borders (gray-700/800),
stagger fade-in animations, Material Symbols Outlined icons.
```

- **具体的に書く**: 「4択カード」ではなく「2x2 grid of cards, each showing element symbol (Li, Ca, Si, Cu) in 2xl font-black」
- **既存モックを参照**: 「similar to the attached HTML structure but with different layout」

---

## Phase 3: Stitch デザイン採用 + バグ修正

**目的**: Stitch 生成デザインを **そのまま採用** し、バグのみを修正する。

### ⚠️ 最重要原則: Claude はデザインの黒子

**Claude は Stitch 先生のデザインしたUIを現実のコードにする実装者。UIデザインで対等という意識を持たないこと。**

- Stitch のデザインは原則 **全採用**。Claude の HTMLモックは Stitch へのインプット（仕様書）でしかない
- Claude が「こっちの方がいい」と判断して Stitch の要素を省略・変更することは **絶対禁止**
- 修正して良いのは **バグのみ**:
  - 英語テキスト → 日本語化
  - ワークフロー不整合（ボタン遷移先が実装と合わない等）
  - データ構造との齟齬（ダミーデータ→実データ対応）
- **Stitch にあるが現在のデータ型にない要素** → 型拡張を提案（省略は禁止）
- デザイン判断が必要な場合は **必ずユーザーに聞く**（AskUserQuestion）

### ⚠️ Hard Gate: ユーザーブラウザ確認必須

1. Stitch 生成 HTML を `chrome` でユーザーのブラウザに表示し、**実物を確認してもらう**
2. バグ一覧を提示し、修正方針の承認を得る
3. ユーザーの指示なしに Phase 4/5 に進んではいけない

### 手順

1. **Stitch 生成結果をユーザーに見せる**:
   - `npx serve` でローカルサーバー起動
   - `chrome http://localhost:{PORT}/stitch-html-screen{N}.html` で各画面を開く
   - HTMLモックとの比較が必要なら `stitch-comparison.html` も用意

2. **バグ一覧を作成**: Stitch HTML を読み、以下を洗い出す
   - 英語テキスト（日本語に修正必要）
   - ダミーデータ（実データ構造と異なる）
   - ワークフローの不整合（ボタン遷移先が実装と合わない等）
   - **Stitch にあるが現在のデータ型にない要素**（hint フィールド等）→ 型拡張を提案

3. **ユーザーに報告**: バグ一覧 + 修正方針を提示し承認を得る

4. **Stitch HTML をそのまま最終デザインとして確定**: HTMLモックは参考資料に格下げ

---

## Phase 4: Figma 統合

**目的**: 確定デザインを Figma にキャプチャし、デザインシステムとして保存。

### 手順

1. **Figma キャプチャ**: `figcap` エイリアスでブラウザを開く
   ```bash
   figcap "file:///path/to/design-mock-{feature}.html" {captureId}
   ```

2. **Figma MCP で確認**: `get_screenshot` で取り込み結果を確認

3. **デザイントークンの抽出**: 色・フォント・スペーシングをメモ
   - React実装時に CSS変数 or Tailwind config として使う

### 注意

- Figma キャプチャは HTMLモックの `capture.js` が必要
- キャプチャは画面単位（screenN の div ごと）
- Figma ファイルの fileKey をメモリに記録しておくこと

---

## Phase 5: React 実装

**目的**: Stitch デザインを React + TypeScript コンポーネントに **忠実に** 変換。

### ⚠️ Stitch 忠実実装ルール

- Stitch HTML の各画面を **逐次対比** しながら実装する。要素の省略・簡略化は禁止
- Stitch HTML にある UI 要素が現在のデータ型にない場合 → **型を拡張** して対応（省略するな）
- テーマカラーのアダプテーション（例: Stitch の emerald → プロジェクトの amber）は OK
- Stitch HTML にある全要素のチェックリストを作り、実装漏れがないことを確認してからコミット

### 実装計画の立て方

1. **データ型の確認**: 既存の `types/` や `data/` を読み、Props の型を決める
2. **既存コンポーネントのパターンを踏襲**: 同モジュールの既存コンポーネントを読み、以下を合わせる:
   - Props インターフェース（`{ themeData: ThemeData; onBack: () => void }` 等）
   - 状態管理パターン（`useState` のステートマシン）
   - Supabase 保存パターン（fire-and-forget upsert + RLS リトライ）
   - Gemini API 呼び出しパターン（`getGeminiFlashModel()` — ハードコード厳禁）
3. **ファイル構成を決める**:
   - メインコンポーネント: `components/{module}/{ComponentName}.tsx`
   - API/ロジック: `lib/{module}/{featureName}.ts`
   - DB migration: `supabase/migrations/{date}_{feature}.sql`
   - 型定義: `types/{module}.ts` に追加

### 実装の進め方

1. **`index.html`**: フォント・アニメーション等のグローバルリソースを追加
2. **ロジック層**: API呼び出し・データ処理（Gemini採点等）
3. **DB migration**: テーブル作成SQL + RLSポリシー
   - **Doppler経由でMigration実行**:
     ```bash
     ACCESS_TOKEN=$(doppler secrets get SUPABASE_ACCESS_TOKEN --project sato-juku --config dev_studygram --plain)
     curl -X POST "https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query" \
       -H "Authorization: Bearer ${ACCESS_TOKEN}" \
       -H "Content-Type: application/json" \
       -d '{"query": "<SQL>"}'
     ```
4. **メインコンポーネント**: HTMLモックをReact JSXに変換
   - サブコンポーネントは同ファイル内に書く（ファイル分割は後でリファクタ）
   - ステートマシンで画面遷移管理
   - Material Symbols Outlined の `<span>` ヘルパーを作ると楽:
     ```tsx
     const MIcon: React.FC<{ name: string; className?: string; size?: number }> = ({ name, className = '', size = 20 }) => (
       <span className={`material-symbols-outlined ${className}`} style={{ fontSize: size }}>{name}</span>
     );
     ```
5. **親コンポーネントに接続**: プレースホルダーを実コンポーネントに置換

### HTMLモック → JSX 変換のコツ

| HTMLモック | React JSX |
|-----------|-----------|
| `class=` | `className=` |
| `<button onclick=...>` | `<button onClick={handler}>` |
| `style="..."` 固定値 | `style={{ ... }}` オブジェクト |
| `<input disabled>` | `<input disabled />` |
| インラインSVGアイコン | `<MIcon name="..." />` or lucide-react |
| `animate-fadeIn delay-1` | そのまま使える（index.html にCSS追加済み前提） |

### 検証

1. `npm run build` — コンパイルエラーがないこと
2. `npm run dev` — 開発サーバー起動
3. Playwright MCP で全画面フローを通しテスト:
   - 各画面の表示を `browser_take_screenshot` で確認
   - `browser_evaluate` で DOM 操作してフロー進行
4. コンソールエラー0を確認（`Console: 0 errors`）
5. Supabase保存がある場合: Doppler → Management API で `SELECT` して確認

---

## Hard Gates

1. **モデル名ハードコード禁止**: Gemini モデル名は `getGeminiFlashModel()` / `getGeminiModel()` で環境変数から取得
2. **Doppler 必須**: service_role key / access token は `.env` にない。必ず Doppler から取得
3. **Stitch プロジェクトタイプ**: `TEXT_TO_UI_PRO` 必須（`PROJECT_DESIGN` はエラー）
4. **Figma capture.js**: HTMLモックの `<head>` に入っていないとキャプチャできない
5. **フォント制限**: Arial / Inter / Roboto / system fonts 禁止（CLAUDE.md）
6. **紫グラデ＋白背景禁止**（CLAUDE.md）
7. **Phase 3 ブラウザ確認必須**: Stitch生成後、Claudeが勝手にデザイン判定してはいけない。必ずユーザーにブラウザで確認してもらい、承認を得ること
8. **Stitch デザイン全採用**: Claude が「こっちの方がいい」と判断して Stitch の要素を省略・変更することは絶対禁止。修正して良いのはバグ（英語テキスト、ワークフロー不整合）のみ
9. **Stitch 要素の省略禁止**: Stitch にある UI 要素が現在のデータ型にない場合、型を拡張して対応する。「データがないから省略」は禁止
10. **Claude はデザインの黒子**: UIデザインで Stitch と対等という意識を持たない。Stitch 先生のデザインを忠実にコード化する実装者に徹する

---

## 成果物チェックリスト

Phase 完了時に以下が揃っていること:

- [ ] `design-mock-{feature}.html` — 確定デザインのHTMLモック
- [ ] `stitch-html-screen{N}.html` — Stitch 生成物（参考保存）
- [ ] `stitch-comparison.html` — 比較ページ
- [ ] React コンポーネント `.tsx` — 実装済み・ビルド通過
- [ ] DB migration `.sql` — Supabase で実行済み
- [ ] Playwright 通しテスト — コンソールエラー0
- [ ] メモリ更新 — MEMORY.md に進捗を記録
