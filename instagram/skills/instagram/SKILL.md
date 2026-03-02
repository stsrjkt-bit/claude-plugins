# /instagram - Instagram投稿ワークフロー

## 説明
塾長の「今日やったこと」から、Instagram投稿の テキスト生成 → アイキャッチ選択 → 画像生成 までを一気通貫で実行する。
サブコマンドで個別ステップだけ実行することもできる。

## 使い方

| コマンド | 説明 |
|---------|------|
| `/instagram <今日やったこと>` | フルパイプライン（リサーチ確認→テキスト生成→アイキャッチ選択→画像生成） |
| `/instagram research [月番号]` | 月次リサーチだけ実行（省略時は今月） |
| `/instagram retry [パターン名orID]` | 画像テキストを別パターンで再生成（引数なしで全10パターン一覧） |
| `/instagram image` | 画像だけ生成（latest.json から） |
| `/instagram photo` | 投稿ネタ写真を正方形クロップ＋明るさ補正 |

## ディレクトリ構成

```
~/.claude/skills/instagram/
  SKILL.md        ← このファイル
  reference.md    ← 塾プロフィール・トーン指定・テンプレート設定
  patterns.md     ← 10種コピーパターン定義
  scripts/
    render.mjs    ← Puppeteer画像生成スクリプト
    template.html ← 画像HTMLテンプレート
    eyecatch.svg  ← アイキャッチSVG（投稿ごとに上書き）
    package.json  ← Node.js依存関係
```

## 共通パス

- リサーチデータ: `~/.claude/projects/-home-stsrj/memory/instagram-research/{月番号}.md`
- 最新投稿JSON: `~/.claude/projects/-home-stsrj/memory/instagram-latest.json`
- 画像納品先: `/mnt/c/Users/stsrj/Desktop/Instagram投稿/`

---

# フルパイプライン: `/instagram <今日やったこと>`

## 手順

### STEP 1: リサーチ確認
1. 現在の月を確認する
2. `~/.claude/projects/-home-stsrj/memory/instagram-research/{現在の月}.md` を Read する
3. **ファイルが存在しない場合 → 自動で「STEP R: リサーチ実行」を行ってから STEP 2 へ進む**
4. ファイルが存在する場合 → そのまま STEP 2 へ

### STEP 2: テキスト生成
1. `~/.claude/skills/instagram/reference.md` を Read して塾プロフィール・トーン指定を確認する
2. 以下の「テキスト生成仕様」に従い、投稿テキストを生成する
3. アイキャッチSVGのコンセプトを3案考える（後述「アイキャッチ提案仕様」参照）
4. 生成結果とアイキャッチ3案を画面に整形表示する（「テキスト生成 画面表示フォーマット」参照）
5. AskUserQuestion でアイキャッチの選択を求める（テキスト内容への修正指示もこの時点で受け付ける）
6. 結果を `~/.claude/projects/-home-stsrj/memory/instagram-latest.json` に保存する（選ばれたアイキャッチのコンセプトを含む。「JSON保存形式」参照）

### STEP 3: アイキャッチSVG生成
1. JSONの `eyecatch.concept` を元に、以下の流れでSVGを生成する
2. `~/.claude/skills/instagram/reference.md` から月別カラー（accentColor, highlightBg）を取得する

#### Step 3-A: 仕様書を作成する（Opusが担当）
コンセプトの説明文を元に、Sonnetへ渡す厳密な仕様書を作成する。
仕様書には以下を含める:
- 各要素の具体的な形状（circle, rect, path, polygon 等）
- 各要素の座標・サイズ
- 各要素の色（月別カラーパレットを使用）

仕様書テンプレート:

```
以下の仕様に従ってSVGを1つ作成せよ。仕様に忠実に、余計な要素は加えないこと。

## サイズ・形
- viewBox: 0 0 150 150
- 背景: 透過（円枠・背景塗りなし）

## メインイラスト
{ここにOpusがコンセプトを元に各要素の形状・座標・色を具体的に記述する}

## カラーパレット
- メイン: {accentColor}（reference.md の月別テンプレートから取得）
- サブ: {highlightBg}
- ダーク: #4a4a4a
- ベース: #fefcf7

## 禁止事項
- テキスト一切不可
- 指定外の装飾要素不可（星、光線、チェックマーク等を勝手に加えない）
- filter / グラデーション不使用（フラットデザイン）

SVGコードのみを ```svg ``` で囲んで出力せよ。
```

#### Step 3-B: Task tool（model: sonnet）でSVGを生成する
Task tool を以下の設定で呼び出す:
- **subagent_type**: "general-purpose"
- **model**: "sonnet"
- **prompt**: Step 3-A で作成した仕様書をそのまま渡す。「SVGコードのみを出力せよ」と明記する。

Sonnet が返した結果から ```svg ``` ブロック内のSVGコードを抽出し、`~/.claude/skills/instagram/scripts/eyecatch.svg` に Write で保存する。

### STEP 4: 画像生成
1. Bash で Puppeteer スクリプトを実行する:
   ```
   node ~/.claude/skills/instagram/scripts/render.mjs
   ```
2. **Read ツールで生成された画像ファイルを読み込んで表示する**（ユーザーがプレビューできるようにする）
3. キャプションを .txt ファイルとして納品先に保存する
   - ファイル名: `sato-math-post-{YYYY-MM-DD}-caption.txt`
4. 生成結果を画面に表示する（「画像生成 画面表示フォーマット」参照）

---

# サブコマンド: `/instagram research [月番号]`

## 手順

1. 引数から対象月を決定する（省略時は現在の月）
2. 「STEP R: リサーチ実行」を行う

## STEP R: リサーチ実行

1. WebSearch ツールを使い、以下の情報を網羅的に収集する：
   - 静岡県東部（沼津市・三島市周辺）の中学・高校の学校行事
   - 各学年のテスト・入試スケジュール
   - 保護者が気にする教育トピック
2. **メインターゲット校（金岡中学校・第五中学校）の学校日記（swa.numazu-szo.ed.jp）を直接確認し、実データを取得すること**
3. 収集した情報を以下の形式で整理する
4. 結果を `~/.claude/projects/-home-stsrj/memory/instagram-research/{月番号}.md` に保存する
5. 保存完了を報告する

### リサーチ出力形式

以下の6学年それぞれについて、2項目を出力する：

```
■ 中1
・イベント：（この時期の学校行事・テスト・入試など、日付がわかれば明記）
・保護者の心配：（3つ程度、具体的な心の声として）

■ 中2
・イベント：
・保護者の心配：

■ 中3
・イベント：
・保護者の心配：

■ 高1
・イベント：
・保護者の心配：

■ 高2
・イベント：
・保護者の心配：

■ 高3
・イベント：
・保護者の心配：
```

### 保護者の心配の書き方ルール

抽象的ではなく、保護者の心の声として具体的に書く。

悪い例：
- 「成績に不安を感じる」

良い例：
- 「冬休み遊んでたけど、学調大丈夫かしら...」
- 「来年受験なのに全然危機感ないのよね」
- 「数学の証明が全く書けないみたい。授業についていけてる？」

### 除外する情報

- 天候・気候の話
- 送迎・交通の話
- 塾で対応できない地域行事
- 「塾でできること」（これは投稿生成フェーズで扱う）

### リサーチ用の検索クエリ例

- 「静岡県 中学 {月}月 学校行事」
- 「沼津市 中学校 定期テスト スケジュール」
- 「静岡県 高校入試 {月}月 スケジュール」
- 「中学生 {月}月 保護者 悩み」
- 「高校生 {月}月 大学受験 スケジュール」

---

# サブコマンド: `/instagram retry [パターン名orID]`

## 手順

1. `~/.claude/projects/-home-stsrj/memory/instagram-latest.json` を Read して直前の生成結果を読み込む
   - ファイルが存在しない場合はエラー: 「先に /instagram で投稿を生成してください」
2. `~/.claude/skills/instagram/patterns.md` を Read してパターン定義を確認する
3. `~/.claude/skills/instagram/reference.md` を Read して塾プロフィール・トーン指定を確認する
4. 引数に応じて処理を分岐する

### A. 特定パターン指定時

指定されたパターンで headline/subhead/body を再生成する。キャプションはそのまま維持。

生成仕様：

あなたは学習塾のSNS担当です。以下のキャプションに合う「画像用テキスト」を作成してください。

- 塾情報: reference.md の塾プロフィール
- 今日やったこと: instagram-latest.json の input
- 生成済みキャプション: instagram-latest.json の caption
- 指定パターン: patterns.md から該当パターンの名前と説明

制約：
- headline は8文字程度（伝わるなら超えてOK）
- subhead は10文字程度
- body は40文字程度、改行で3行程度に
- 画像テキストだけで何の話かわかるようにする（キャプションは読まれない前提）
- 必ず指定パターンの特徴を活かすこと
- キャプションの内容・トーンと整合性を保つこと

結果を画面表示し、instagram-latest.json の imageText を更新する。

### B. 引数なし（全パターン一覧）

10パターン全てについて headline/subhead/body を生成する。

結果を一覧表示する。ユーザーが番号を選んだら instagram-latest.json を更新する。

---

# サブコマンド: `/instagram image`

## 手順

1. `~/.claude/projects/-home-stsrj/memory/instagram-latest.json` を Read して投稿データを読み込む
   - ファイルが存在しない場合はエラー: 「先に /instagram で投稿を生成してください」
   - `eyecatch.concept` が含まれていなければエラー: 「JSONにeyecatch情報がありません。/instagram を再実行してください」
2. フルパイプラインの「STEP 3: アイキャッチSVG生成」→「STEP 4: 画像生成」と同じ手順を実行する

---

# テキスト生成仕様

あなたは学習塾のSNS担当です。塾長の「今日やったこと」を、保護者向けのInstagram投稿に変換してください。

### コンテキスト情報
- リサーチデータがある場合はその内容を活用する
- なければ現在の月の一般的な教育事情を考慮する

### 塾情報
reference.md の塾プロフィールをそのまま使用する。

### 生成ルール
1. 塾長の入力を、該当月の文脈と結びつける
2. 保護者が「なるほど、この時期にこれをやるのは意味があるな」と思える投稿にする
3. 画像テキスト（headline/subhead/body）だけで「何の話か」「いつの話か」がわかるようにする（キャプションは読まれない前提）
4. 文字数は目安。伝わりやすさを優先し、必要なら超えてよい

### トーン（★重要★）
reference.md のトーン指定に厳密に従うこと。

### 出力形式
reference.md の出力JSON形式に従う。

---

# アイキャッチ提案仕様

投稿テキスト生成後、アイキャッチSVGのコンセプトを3案考える。

### 発想の基準
- 投稿内容（headline/subhead/body）と月の雰囲気から発想する
- 画像タイトル横の小さなスペース（300x300px相当）に入るバッジ型アイコンとして成立するもの
- シンプルな図案（フラットデザイン、1〜3個のモチーフ）

### 各案の記述
- 「何を描くか」を具体的に1〜2行で説明する
- モチーフの意味や投稿内容との関連を明記する
- 例: 「開いた手のひらから蝶が飛び立つ。手＝手放す、蝶＝不安が希望に変わる」

---

# 画面表示フォーマット

## テキスト生成（アイキャッチ候補含む）

```
📸 Instagram投稿を生成しました

━━━ 画像テキスト ━━━
🔤 headline: {headline}
🔤 subhead: {subhead}
📝 body:
{body}

━━━ キャプション ━━━
{caption}

━━━ アイキャッチ候補 ━━━
1️⃣ {概要1}
2️⃣ {概要2}
3️⃣ {概要3}
```

表示後、AskUserQuestion でアイキャッチの番号選択を求める。選択肢は「1」「2」「3」の3つ。テキスト内容に問題があればこの時点で指摘してもらう旨を question テキストに含める。

## 画像生成

```
🖼️ Instagram画像を生成しました

🎨 アイキャッチ: {eyecatch.concept の要約}

📁 保存先: /mnt/c/Users/stsrj/Desktop/Instagram投稿/
   - sato-math-post-{日付}.png
   - sato-math-post-{日付}-caption.txt
```

## リトライ（特定パターン）

```
🔄 パターン「{パターン名}」で再生成しました

━━━ 画像テキスト ━━━
🔤 headline: {headline}
🔤 subhead: {subhead}
📝 body:
{body}

━━━ キャプション（変更なし）━━━
{caption}

💾 instagram-latest.json を更新しました
⏳ 画像を生成しています...
```

## リトライ（全パターン一覧）

```
🔄 10パターンを生成しました

1. ❓ 問いかけ型
   headline: {headline}
   subhead: {subhead}
   body: {body}

2. 🔀 意外な組み合わせ型
   ...

👉 使いたい番号を教えてください（選択後、画像も生成します）
```

---

# JSON保存形式

```json
{
  "generatedAt": "ISO日時",
  "month": 月番号,
  "input": "塾長の入力テキスト",
  "imageText": {
    "headline": "...",
    "subhead": "...",
    "body": "..."
  },
  "caption": "...",
  "eyecatch": {
    "concept": "選ばれたコンセプトの説明文"
  }
}
```

---

# サブコマンド: `/instagram photo`

投稿ネタの写真やPDFをInstagram用に加工する（正方形クロップ＋明るさ補正）。

## 手順

1. `デスクトップ/Instagram投稿/` フォルダ内のファイルを Bash の `ls` で一覧する
2. 加工対象のファイルが1つなら自動選択、複数あればAskUserQuestionで選択を求める
   - 既に `_square` がついたファイル（加工済み）は候補から除外する
3. ファイル形式に応じて前処理を行う:
   - **画像（jpg/png等）**: そのまま次のステップへ
   - **PDF**: `pdftoppm` で1ページ目を300dpiのPNG画像に変換してから次のステップへ
     ```
     pdftoppm -png -r 300 -f 1 -l 1 '{入力PDF}' /tmp/pdf_preview
     ```
     変換後の画像: `/tmp/pdf_preview-1.png`
4. Read ツールで元画像を表示し、現状を確認する
5. ImageMagick（`convert`）で以下の加工を行う:
   - **写真（横長）**: `-gravity Center` で正方形クロップ（短辺に合わせる）
   - **PDF（縦長）**: `-gravity North` で正方形クロップ（上部基準、タイトルが見切れないように）
   - 明るさ補正: `-brightness-contrast 8x5`（自然な明るさアップ）
   - 1080x1080 にリサイズ
   - 出力ファイル名: `{元のファイル名（拡張子なし）}_square.jpg`
6. Read ツールで加工後の画像を表示し、ユーザーに確認する
7. ユーザーが調整を求めた場合は値を変えて再生成する
   - 「明るすぎ」→ brightness を下げる（例: 5x3）
   - 「暗い」→ brightness を上げる（例: 12x8）
   - 「左寄せ」→ `-gravity West` に変更
   - 「もっと下を見せて」→ gravity を調整
   - 等

## パス

- 入力元・出力先: `/mnt/c/Users/stsrj/Desktop/Instagram投稿/`

---

# 前提条件
- Node.js と puppeteer がインストール済みであること（`~/.claude/skills/instagram/scripts/node_modules/` にローカルインストール済み）
- ImageMagick がインストール済みであること（写真加工で使用）
- poppler-utils がインストール済みであること（PDF→画像変換で使用）
