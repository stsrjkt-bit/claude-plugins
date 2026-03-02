---
name: instagram-daily
description: 日常授業記録のInstagram投稿（atama+スクショ軽量取得 + ほっこり系テキスト + 画像生成）
user_invocable: true
arguments:
  - name: input
    description: "一言メモ（例: 小6体験生が来た。笑顔で帰った）、または screenshot <生徒名>"
    required: true
---

# /instagram-daily - 日常授業記録の投稿スキル

毎日の授業後にサクッとインスタ投稿を作るための軽量スキル。
`/instagram` のフルパイプライン（リサーチ→テキスト→SVG→画像）を簡略化し、
「塾長の一言メモ」→「ほっこり系テキスト」→「アイキャッチ」→「画像納品」を5分で完結させる。

## コマンド体系

| コマンド | 説明 |
|---------|------|
| `/instagram-daily <一言メモ>` | テキスト生成→アイキャッチ→画像生成→納品 |
| `/instagram-daily screenshot <生徒名>` | atama+スクショ取得のみ（名前マスク済み） |

## 共用リソース（instagram スキルと共有）

- パターン定義: `~/.claude/skills/instagram/patterns.md`
- 画像生成スクリプト: `~/.claude/skills/instagram/scripts/render.mjs`
- HTMLテンプレート: `~/.claude/skills/instagram/scripts/template.html`
- アイキャッチSVG: `~/.claude/skills/instagram/scripts/eyecatch.svg`（投稿ごとに上書き）
- 最新投稿JSON: `~/.claude/projects/-home-stsrj/memory/instagram-latest.json`

## 共通パス

- 画像納品先（デフォルト）: `/mnt/c/Users/stsrj/Desktop/Instagram投稿/`
- ユーザーが別の納品先を指定した場合はそちらを使う

---

# フルフロー: `/instagram-daily <一言メモ>`

## STEP 1: atama+ スクショ（任意）

AskUserQuestion で「atama+ のスクショも撮りますか？」と確認する。
選択肢: 「はい（生徒名を入力）」「いいえ（テキストだけ）」

### 「はい」の場合 → スクショ取得（軽量版）

atama+ COACH にログインし、指定生徒の「学習タイムライン」「マイレベル」のスクショを撮る。

#### 1a. Chromium起動

```bash
bash ~/.claude/skills/atama/scripts/launch-chrome.sh
```

- 既に起動中（`pgrep -f "chrome.*--remote-debugging-port=9222"`）ならスキップ
- 起動後5秒待機

#### 1b. MCP接続 & ログイン

1. `list_pages` でページ一覧を取得
2. atama+ COACHのページがあれば `select_page`。なければ `navigate_page` で `https://coach.atama.plus/` に遷移
3. `take_screenshot` でページの状態を確認

**URL判定:**
- `/user/home` → ログイン済み
- `/public/login` → ログインフロー実行:

認証情報の取得:
```bash
source ~/.env.atama && echo "ID=$ATAMA_ID PW_LEN=${#ATAMA_PW}"
```

`.env.atama` が存在しない場合はユーザーに手動入力を依頼。

Bash で認証情報を読み取り、JS文字列を構築して `evaluate_script` に渡す:
```javascript
() => {
  const inputs = document.querySelectorAll('input');
  let idInput = null, pwInput = null;
  for (const inp of inputs) {
    if (inp.type === 'text' || inp.type === 'email') idInput = inp;
    if (inp.type === 'password') pwInput = inp;
  }
  if (idInput) {
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    nativeInputValueSetter.call(idInput, '${ATAMA_ID}');
    idInput.dispatchEvent(new Event('input', { bubbles: true }));
    nativeInputValueSetter.call(pwInput, '${ATAMA_PW}');
    pwInput.dispatchEvent(new Event('input', { bubbles: true }));
  }
  return 'filled';
}
```

`take_snapshot` → ログインボタンの uid で `click(uid)`。20秒待機。`take_screenshot` でログイン成功を確認。

**重要: `navigate_page` の `initScript` は絶対に使わないこと。**

#### 1c. 生徒詳細ページへ遷移

1. ホーム画面で `evaluate_script` で「全員」タブをクリック
2. `take_snapshot` で生徒一覧取得 → 対象生徒名の uid で `click(uid)`
3. 生徒詳細ページへ遷移を `take_screenshot` で確認

#### 1d. 名前マスク & スクショ撮影

**重要: 名前マスクを先に適用してからスクショを撮る。**

AskUserQuestion で入力された生徒名を `STUDENT_NAME` 変数として保持する。

まず名前マスクを適用する。`evaluate_script` で名前要素を白い矩形で覆う:

```javascript
(studentName) => {
  const allText = document.querySelectorAll('*');
  for (const el of allText) {
    if (el.children.length === 0 && el.textContent.includes(studentName)) {
      el.style.backgroundColor = 'white';
      el.style.color = 'white';
    }
  }
  return 'masked';
}
```
※ `studentName` は Bash で取得した生徒名を `args` パラメータ経由で渡す。

マスク適用後に以下の2画面のスクショを撮る:

1. **学習タイムライン**: 生徒詳細ページのデフォルト表示。`take_screenshot(filePath="/tmp/atama_timeline.png")` で撮影。
2. **マイレベル**: `take_snapshot` → 「マイレベル」の uid で `click(uid)` → 名前マスクを再適用（ページ内容が変わるため） → `take_screenshot(filePath="/tmp/atama_mylevel.png")` で撮影。

#### 1e. スクショ保存

撮影したスクショを納品先フォルダにコピーする:
```bash
cp /tmp/atama_timeline.png "/mnt/c/Users/stsrj/Desktop/Instagram投稿/atama-timeline-$(date +%Y%m%d).png"
cp /tmp/atama_mylevel.png "/mnt/c/Users/stsrj/Desktop/Instagram投稿/atama-mylevel-$(date +%Y%m%d).png"
```

---

## STEP 2: テキスト生成（ほっこり系トーン）

1. `~/.claude/skills/instagram-daily/reference.md` を Read してトーン定義を確認する
2. `~/.claude/skills/instagram/reference.md` を Read して塾プロフィール・テンプレート設定を確認する
3. 以下の仕様でテキストを生成する

### テキスト生成仕様

あなたは小さな個人塾の塾長です。今日の教室での出来事を、1970年代の教育実践記録のような温かみのある文体で書いてください。

**コンテキスト:**
- 塾情報: instagram/reference.md の塾プロフィール
- 今日の出来事: ユーザーの一言メモ（$ARGUMENTS）

**トーン（★最重要★）:**
instagram-daily/reference.md のトーン定義に厳密に従うこと。
instagram/reference.md のトーン指定も併せて遵守すること。

**生成ルール:**
1. 一言メモの中から子どもの小さな変化を見つけ出し、丁寧に拾い上げる
2. 数値データは使わない（or 最小限）。「55分で3単元合格」ではなく「算数のモヤモヤを解消して、そのまま中1に入れた」
3. 箇条書き禁止。短い文章を3-4段落で
4. キャプションの最後は先生の素朴な感想で静かに締める
5. 画像テキスト（headline/subhead/body）だけで内容が伝わること

**出力形式:**
instagram/reference.md の出力JSON形式に従う。

4. アイキャッチSVGのコンセプトを3案考える（instagram/SKILL.md の「アイキャッチ提案仕様」に準拠）
5. 生成結果とアイキャッチ3案を画面に整形表示する
6. AskUserQuestion でアイキャッチの選択を求める（テキスト修正もこの時点で受付）
7. 結果を `~/.claude/projects/-home-stsrj/memory/instagram-latest.json` に保存する

### 画面表示フォーマット

```
📸 日常投稿を生成しました

━━━ 画像テキスト ━━━
headline: {headline}
subhead: {subhead}
body:
{body}

━━━ キャプション ━━━
{caption}

━━━ アイキャッチ候補 ━━━
1. {概要1}
2. {概要2}
3. {概要3}
```

### JSON保存形式

```json
{
  "generatedAt": "ISO日時",
  "month": 月番号,
  "input": "塾長の一言メモ",
  "source": "instagram-daily",
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

## STEP 3: アイキャッチSVG生成

instagram/SKILL.md の「STEP 3: アイキャッチSVG生成」と同じ手順。

1. JSONの `eyecatch.concept` を元に仕様書を作成する（Opusが担当）
2. `~/.claude/skills/instagram/reference.md` から月別カラー（accentColor, highlightBg）を取得する
3. Agent tool（model: sonnet）でSVGを生成する
4. SVGコードを `~/.claude/skills/instagram/scripts/eyecatch.svg` に保存する

仕様書テンプレート:
```
以下の仕様に従ってSVGを1つ作成せよ。仕様に忠実に、余計な要素は加えないこと。

## サイズ・形
- viewBox: 0 0 150 150
- 背景: 透過（円枠・背景塗りなし）

## メインイラスト
{ここにOpusがコンセプトを元に各要素の形状・座標・色を具体的に記述する}

## カラーパレット
- メイン: {accentColor}
- サブ: {highlightBg}
- ダーク: #4a4a4a
- ベース: #fefcf7

## 禁止事項
- テキスト一切不可
- 指定外の装飾要素不可（星、光線、チェックマーク等を勝手に加えない）
- filter / グラデーション不使用（フラットデザイン）

SVGコードのみを ```svg ``` で囲んで出力せよ。
```

---

## STEP 4: 画像生成 & 納品

1. Bash で Puppeteer スクリプトを実行する:
   ```bash
   node ~/.claude/skills/instagram/scripts/render.mjs
   ```
2. Read ツールで生成された画像ファイルを読み込んで表示する
3. キャプションを .txt ファイルとして納品先に保存する
   - ファイル名: `sato-math-post-{YYYY-MM-DD}-caption.txt`
4. 生成結果を画面に表示する

### 画面表示フォーマット

```
画像を生成しました

アイキャッチ: {eyecatch.concept の要約}

保存先: /mnt/c/Users/stsrj/Desktop/Instagram投稿/
  - sato-math-post-{タイムスタンプ}.png
  - sato-math-post-{日付}-caption.txt
```

---

# サブコマンド: `/instagram-daily screenshot <生徒名>`

atama+ のスクショ取得のみを実行する（テキスト生成・画像生成は行わない）。

## 手順

STEP 1 の 1a〜1e をそのまま実行する。生徒名は引数から取得。

---

# 前提条件

- Node.js と puppeteer がインストール済み（`~/.claude/skills/instagram/scripts/node_modules/` にローカルインストール済み）
- Chromium がインストール済み（atama+ スクショ取得時に使用）
- `~/.env.atama` にatama+の認証情報がある（スクショ取得時に使用）
