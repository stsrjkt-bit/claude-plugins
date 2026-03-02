# コピーパターン別再生成

直前の投稿生成結果を読み込み、指定されたコピーパターンで画像テキスト（headline/subhead/body）を再生成する。キャプションはそのまま維持する。

## 引数

$ARGUMENTS

コピーパターン名またはID（例: `問いかけ型` または `1`）。引数なしの場合は10パターン全てを一覧生成する。

## 参照ファイル

以下の2ファイルを Read ツールで読み込むこと：
- `~/.claude/skills/instagram/patterns.md` - パターン定義
- `~/.claude/skills/instagram/reference.md` - 塾プロフィール・制約

## 手順

1. `~/.claude/projects/-home-stsrj/memory/instagram-latest.json` を Read して直前の生成結果を読み込む
   - ファイルが存在しない場合はエラー: 「先に /instagram で投稿を生成してください」
2. `~/.claude/skills/instagram-retry/patterns.md` を Read してパターン定義を確認する
3. `~/.claude/skills/instagram/reference.md` を Read して塾プロフィール・トーン指定を確認する
4. 引数に応じて処理を分岐する：

### A. 特定パターン指定時

指定されたパターンで headline/subhead/body を再生成する。

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

生成仕様：

あなたは学習塾のSNS担当です。以下のキャプションに合う「画像用テキスト」を、10パターン全てで作成してください。

- 塾情報: reference.md の塾プロフィール
- 今日やったこと: instagram-latest.json の input
- 生成済みキャプション: instagram-latest.json の caption
- 10パターン: patterns.md の全パターン定義

制約は特定パターン時と同じ。

結果を一覧表示する。ユーザーが番号を選んだら instagram-latest.json を更新する。

## 画面表示フォーマット（特定パターン時）

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
🖼️ 画像生成: /instagram-image を実行してください
```

## 画面表示フォーマット（全パターン時）

```
🔄 10パターンを生成しました

1. ❓ 問いかけ型
   headline: {headline}
   subhead: {subhead}
   body: {body}

2. 🔀 意外な組み合わせ型
   headline: {headline}
   subhead: {subhead}
   body: {body}

... (3〜10も同様)

👉 使いたい番号を教えてください（instagram-latest.json を更新します）
```
