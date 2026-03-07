---
name: instagram
description: Instagram投稿ワークフロー（リサーチ→テキスト生成→アイキャッチ→ベース画像→NB2ブラッシュアップ）
user_invocable: true
arguments:
  - name: input
    description: "今日やったこと、またはサブコマンド（research, retry, image, photo）"
    required: true
---

# /instagram - Instagram投稿ワークフロー

## 説明
塾長の「今日やったこと」から、Instagram投稿の テキスト生成 → アイキャッチ → ベース画像 → Nano Banana 2 ブラッシュアップ までを一気通貫で実行する。
サブコマンドで個別ステップだけ実行することもできる。

## 使い方

| コマンド | 説明 |
|---------|------|
| `/instagram <今日やったこと>` | フルパイプライン |
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
- 画像納品先（ローカル）: `/mnt/c/Users/stsrj/Desktop/Instagram投稿/`
- 画像納品先（Surface）: `scp` で Surface に転送する
  - `scp <ファイル> stsrj@surface:"/mnt/c/Users/stsrj/Desktop/Instagram投稿/"`
  - ファイル名はシンプルに `YYYY-MM-DD.png` と `YYYY-MM-DD.md`（キャプション）
  - Tailscale SSH認証を求められたらURLをユーザーに提示して待つ

## プレビュー方式（全ステップ共通）

画像をユーザーに見せるときは **必ず tmpfiles.org** を使う。ワンクリックでブラウザ表示できること。

```bash
curl -s -F "file=@<画像パス>" https://tmpfiles.org/api/v1/upload
```

レスポンスの URL の `tmpfiles.org/` の後に `dl/` を挿入して直リンクにする。

**以下は使うな:**
- gist + githack（不安定）
- base64 埋め込み HTML（表示されないことがある）
- Read ツールでの画像表示（ユーザーのブラウザで見れない）

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
3. 生成結果を画面に整形表示する（「テキスト生成 画面表示フォーマット」参照）
4. AskUserQuestion でテキスト内容の確認を求める
5. 結果を `~/.claude/projects/-home-stsrj/memory/instagram-latest.json` に保存する（「JSON保存形式」参照）

**※ このステップではアイキャッチの話はしない。原稿に集中する。**

### STEP 3: アイキャッチ
1. 投稿内容と月の雰囲気から、アイキャッチSVGのコンセプトを3案考える（「アイキャッチ提案仕様」参照）
2. 3案を画面に表示し、AskUserQuestion で選択を求める
3. 選択されたコンセプトを元に、`reference.md` から月別カラーを取得する
4. Opus が直接 SVG コードを書き、`~/.claude/skills/instagram/scripts/eyecatch.svg` に Write で保存する
5. instagram-latest.json の `eyecatch.concept` を更新する

SVG仕様:
- viewBox: 0 0 150 150
- 背景: 透過
- カラーは月別パレット（accentColor, highlightBg）を使用
- テキスト不可、filter/グラデーション不使用（フラットデザイン）

### STEP 4: ベース画像生成
1. Bash で Puppeteer スクリプトを実行する:
   ```
   node ~/.claude/skills/instagram/scripts/render.mjs
   ```
2. 生成された PNG を tmpfiles.org にアップし、直リンクをユーザーに渡す

### STEP 5: ユーザー確認（ゴーサイン）

ユーザーにベース画像を確認してもらう。

- テキストの修正 → instagram-latest.json を更新して STEP 4 からやり直し
- アイキャッチの修正 → STEP 3 からやり直し
- **OK（ゴーサイン）→ STEP 6 へ進む**

### STEP 6: Nano Banana 2 ブラッシュアップ

ベース PNG を Gemini の画像編集 API に渡してデザインを改善する。

```python
import os
from google import genai
from google.genai import types
from PIL import Image as PILImage
from dotenv import dotenv_values

env = dotenv_values(os.path.expanduser('~/studygram/.env'))
api_key = env.get('GEMINI_API_KEY')
model_name = env.get('GEMINI_IMAGE_MODEL') or env.get('VITE_GEMINI_IMAGE_MODEL')
if not api_key:
    raise RuntimeError('GEMINI_API_KEY が ~/studygram/.env に未設定')
if not model_name:
    raise RuntimeError('GEMINI_IMAGE_MODEL or VITE_GEMINI_IMAGE_MODEL が ~/studygram/.env に未設定')

client = genai.Client(api_key=api_key)
image = PILImage.open('<ベース画像パス>')

response = client.models.generate_content(
    model=model_name,
    contents=[
        'この画像のデザインをブラッシュアップしてください。'
        '文字の内容・配置・フォントサイズは絶対に変えないでください。文字は一文字も変更禁止です。'
        '背景や装飾、色使い、イラストをより洗練されたものに改善してください。'
        '1080x1080pxの正方形画像として出力してください。',
        image
    ],
    config=types.GenerateContentConfig(
        response_modalities=['TEXT', 'IMAGE'],
    )
)

for part in response.parts:
    if part.inline_data is not None:
        img = part.as_image().resize((1080, 1080), PILImage.Resampling.LANCZOS)
        img.save('<出力パス>')
```

**環境変数（`~/studygram/.env`）:**
- `GEMINI_API_KEY` — API キー（必須）
- `GEMINI_IMAGE_MODEL` — 画像編集モデル名（必須、例: `gemini-3.1-flash-image-preview`）

モデル名・API キーのハードコード禁止。

### STEP 7: 最終確認・納品
1. NB2 出力を tmpfiles.org にアップし、直リンクをユーザーに渡す
2. ユーザーの反応に応じて対応:
   - **テキスト微修正** → NB2 に修正プロンプトを送って再編集（ベースからやり直す必要なし）
   - **デザインが気に入らない** → STEP 6 をリトライ
   - **OK** → 納品へ
3. 納品:
   - シンプルなファイル名でコピー: `{YYYY-MM-DD}.png` + `{YYYY-MM-DD}.md`（caption を Write）
   - Surface に SCP で転送:
     ```
     scp <ファイル> stsrj@surface:"/mnt/c/Users/stsrj/Desktop/Instagram投稿/"
     ```
4. 納品完了を報告する

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
- subhead は20文字程度
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
2. フルパイプラインの STEP 3 → STEP 7 と同じ手順を実行する（STEP 3 でアイキャッチを生成するため事前の eyecatch.concept は不要）

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

STEP 3 で、投稿テキスト確定後にアイキャッチSVGのコンセプトを3案考える。

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

## テキスト生成（STEP 2）

```
📸 Instagram投稿を生成しました

━━━ 画像テキスト ━━━
🔤 headline: {headline}
🔤 subhead: {subhead}
📝 body:
{body}

━━━ キャプション ━━━
{caption}
```

表示後、AskUserQuestion でテキスト内容の確認を求める。テキスト内容に問題があればこの時点で指摘してもらう旨を question テキストに含める。

## アイキャッチ選択（STEP 3）

```
━━━ アイキャッチ候補 ━━━
1. {概要1}
2. {概要2}
3. {概要3}
```

表示後、AskUserQuestion で番号選択を求める。

## ベース画像プレビュー（STEP 5）

```
🖼️ ベース画像を生成しました
🔗 {tmpfiles.org の直リンク}

テキスト・構成に問題なければ「GO」、修正があれば指示してください。
```

## NB2 ブラッシュアップ結果（STEP 7）

```
✨ Nano Banana 2 でブラッシュアップしました
🔗 {tmpfiles.org の直リンク}

OKなら「納品」、修正があれば指示してください。
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
- Noto Sans JP variable font がローカルインストール済みであること（weight 900 のレンダリングに必要）
- google-genai, python-dotenv Python パッケージがインストール済みであること（Nano Banana 2 で使用）
- `~/studygram/.env` に `GEMINI_API_KEY` と `VITE_GEMINI_IMAGE_MODEL` が設定されていること
