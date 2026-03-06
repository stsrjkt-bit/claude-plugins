---
name: ui-design-to-react
description: >
  HTMLモック → React実装のUI制作ワークフロー。
  デザインモック制作 → ユーザー確認 → React実装 の3フェーズ。
  「UIを作りたい」「画面設計」「モックからReact」「デザインモック」等で発火。
user_invocable: true
---

# /ui-design-to-react — UI制作ワークフロー

HTMLモック制作からReact実装まで一気通貫で進めるスキル。

## ⚠️ Stitch MCP プロンプトの鉄則（2026-03-04 確認済み）

**Stitchへのプロンプトは短くシンプルな日本語で。詳細指定は絶対するな。**

### ダメなプロンプト（実際に失敗）
```
Hero section for a Japanese cram school landing page.
School name: さとう数理塾
Brand blue: #0096e0, lime accent: #d6de26...
No buttons, no navigation. Just the title and subtitle.
Make it visually stunning — think Apple or Stripe hero sections.
```
→ 色・フォント・テキスト・レイアウトを細かく指定 → Stitchの創造性が死ぬ → ゴミが出る

### 良いプロンプト（実際に成功）
```
さとう数理塾の中学生ページのヒーローセクションつくって
```
→ シンプルな日本語、デザインの自由度を与える → 高品質なデザインが出る

### ルール
1. **日本語で書け**（英語禁止）
2. **1〜2文で済ませろ**（詳細な仕様を書くな）
3. **色・フォント・レイアウトを指定するな**（Stitchに任せる）
4. **テキストもStitchに任せろ**（あとからClaudeが実データに修正する）
5. **セクション単位で依頼しろ**（ページ全体を一度に頼むな）
6. **「ボタンなし」等の制約も書くな**（デザイン要素としてStitchが生成したものは後で取捨選択する）

### セクション分割で依頼する
LPは以下のようにセクション単位でStitchに依頼:
- 「〇〇塾の中学生ページのヒーローセクションつくって」
- 「学習塾のコース紹介カード（公立中向け・私立中向けの2つ）」
- 「合格実績セクション。高校受験と大学受験の2カラム」
- 「よくあるお悩みの横スクロールカード」

Stitchが生成したテキスト・ダミーデータは**バグとして後から修正**すればよい。デザインの基盤を得ることが目的。

## 前提ツール

| ツール | 用途 | 注意 |
|--------|------|------|
| Playwright MCP | スクショ撮影・HTMLプレビュー | 「見るだけ」用途 |
| Figma MCP | デザイン統合・キャプチャ | `figcap` エイリアスで hash URL 生成 |
| Doppler | シークレット管理 | `doppler secrets get <KEY> --project sato-juku --config dev_studygram --plain` |
| Stitch MCP | **アプリUI限定** | LP・Webページには使うな。ユーザーが明示的に「Stitch使え」と言った場合のみ |

## フローの全体像

```
Phase 1: HTMLモック制作（Claude がデザイン本体として作り込む）
    ↓
Phase 2: ユーザーブラウザ確認 + フィードバック
    ↓
Phase 3: Figma 統合（任意）
    ↓
Phase 4: React 実装（HTMLモックを忠実にコード化）
```

**Claude の役割**: CLAUDE.md のデザイン原則に従い、攻めたHTMLモックを作る。ユーザー確認後、忠実にReact実装する。

## HTMLプレビューの公開方法

ユーザーにHTMLを見せる必要がある場合:
1. `gh gist create --public` でGistにアップ
2. `https://gist.githack.com/{user}/{gist_id}/raw/{filename}` でブラウザ表示可能なURLを生成
3. このURLをユーザーに渡す
- **npx serve + localhost は使えない**（ユーザーがリモートChromebookのため）
- **GitHub Pages は使えない**（privateリポジトリ、free planでは無効）
- **Netlify CLI preview** は認証・インタラクティブ問題で不安定

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

## Phase 2: ユーザーブラウザ確認

**目的**: HTMLモックをユーザーに見せてフィードバックをもらう。

### 手順

1. `gh gist create --public` でHTMLモックをGistにアップ
2. githack URLを生成してユーザーに渡す: `https://gist.githack.com/{user}/{gist_id}/raw/{filename}`
3. フィードバックを反映してHTMLモックを修正
4. 修正版を再度Gistにアップして確認
5. ユーザーOKが出たらPhase 3/4へ

---

## Phase 3: Figma 統合（任意）

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

## Phase 4: React 実装

**目的**: HTMLモックを React + TypeScript コンポーネントに **忠実に** 変換。

### HTMLモック忠実実装ルール

- HTMLモックの各セクションを **逐次対比** しながら実装する。要素の省略・簡略化は禁止
- HTMLモックにある全要素のチェックリストを作り、実装漏れがないことを確認してからコミット

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
3. **Figma capture.js**: HTMLモックの `<head>` に入っていないとキャプチャできない
4. **フォント制限**: Arial / Inter / Roboto / system fonts 禁止（CLAUDE.md）
5. **紫グラデ＋白背景禁止**（CLAUDE.md）
6. **Phase 2 ブラウザ確認必須**: HTMLモック完成後、必ずユーザーにブラウザで確認してもらい、承認を得ること。Claudeが勝手に「OK」と判定してはいけない
7. **Stitch MCP はLP・Webページに使うな**: デザインクオリティが実用レベルに達していない。アプリUI（小コンポーネント）限定。ユーザーが明示的に指示した場合のみ例外

---

## 成果物チェックリスト

Phase 完了時に以下が揃っていること:

- [ ] `design-mock-{feature}.html` — 確定デザインのHTMLモック（これがデザイン本体）
- [ ] ユーザーブラウザ確認済み（githack URL経由）
- [ ] React コンポーネント `.tsx` — 実装済み・ビルド通過
- [ ] DB migration `.sql` — Supabase で実行済み（該当する場合）
- [ ] Playwright 通しテスト — コンソールエラー0
- [ ] メモリ更新 — MEMORY.md に進捗を記録
