---
name: atama
description: atama+ COACH 操作（学習データ取得→つまずき分析→補習プリント＆解説動画作成）
user_invocable: true
arguments:
  - name: target
    description: "生徒名と教科・単元（例: 鈴木愛莉 中学数学 回転体の表面積と体積）、または 'login' でログインのみ"
    required: true
---

# atama+ COACH 自動化スキル

**Playwright MCP** でatama+ COACHを操作（COACH/Ionic は Playwright 一択）。
指定生徒・指定単元の学習データ取得→誤答分析→足場がけ補習プリント作成→解説動画作成→PDF・動画出力を一気通貫で実行する。

## コマンド体系

| コマンド | 説明 |
|---------|------|
| `/atama <生徒名> <教科> <単元>` | フルパイプライン（Phase 0〜6） |
| `/atama <生徒名> <部分的な指示>` | Phase 0 で不足情報を聞いてからフルパイプライン |
| `/atama login` | Chromium起動＆ログインのみ（Phase 1 のみ） |

**つまずきマークの有無は関係ない。** ユーザーが指定した単元の補習プリントを作成する。

## 設定情報

`reference.md` を参照すること。

---

## 全 Phase 共通ルール

### ブラウザ操作の制約（違反厳禁）

- クリックは原則 `take_snapshot` → `click(uid)` で行う
- 唯一の例外: 「全員」タブの切替のみ `evaluate_script` で `el.click()` 可
- `evaluate_script` は読み取り専用（DOM確認・文字取得・スクロール操作のみ）
- `navigate_page` の `initScript` は絶対に使わない（Firebase Auth を破壊する）
- `navigate_page(type: "back")` は禁止（生徒一覧まで戻ってしまう）
- モーダルは必ず「閉じる」ボタンで閉じる
- 「問題を見る」ボタンは絶対に押さない（全問題が展開されトークン爆発）
- 確認テスト行はスキップ（クリックしてもツールチップが出るだけ）
- パスワード等の機密情報を echo/出力/ログに残さない

### スクリーンショットルール（厳守）

- **スクショは常に Playwright MCP の `browser_take_screenshot` を使う**
- Chrome DevTools MCP の `screenshot` は使用禁止（PNG100%+5秒固定で重い画面で失敗する）
- 長いページは `fullPage: true` で1回で撮る。scroll→screenshot を繰り返すな
- 特定セクションだけ必要なら要素指定スクショ

### snapshot ルール（厳守）

- **生徒詳細ページ以降の `take_snapshot` は必ず `filePath` を指定する**
- インライン取得はトークン上限（50,000文字）を超えてエラーになる
- 保存後は `Grep` ツールで必要な情報を検索する

### UID の注意事項

- ページ遷移後は全 UID が無効。必ず `take_snapshot` を再取得する
- モーダルを閉じた後も UID は無効になる場合がある

### セッション分断時の引き継ぎ

コンテキスト切れで新セッションに移行する場合、`.claude/tmp/atama-state.md` に以下を追記してから終了する:
- 現在の Phase 番号と次のアクション
- ブラウザ状態（URL、ログイン済みか、モーダル開閉状態）
- 開いたモーダル一覧とスキップしたモーダル（理由付き）
- 取得済みスクショ/snapshot のパス一覧
- 未完了の作業

### 報告タイミング（途中で質問するな）

ユーザーへの報告は **2回だけ**:
1. **Phase 0 後** — ヒアリング結果の確認（ユーザー入力が必要）
2. **Phase 6 完了後** — 全工程の結果をまとめて1回

**Phase 1〜6 は途中報告なし・一気通貫で実行する。「どうしますか？」等の質問を挟まない。**

---

## Phase 0: ヒアリング & 初期化

### 入力
- ユーザーの指示テキスト

### 処理

1. **状態を初期化する（前セッションのゴミを使い回さない）**:
   ```bash
   rm -rf /tmp/hoshu_material/ && mkdir -p /tmp/hoshu_material/
   rm -f .claude/tmp/atama-state.md
   ```

2. ユーザーの指示から不足情報だけを聞く（1つのメッセージにまとめる）:
   - **教科**: 既に指示に含まれていれば聞かない
   - **単元**: 既に指示に含まれていれば聞かない
   - **名前の読み方（フルネーム）**: 選択肢形式で提示（「その他」必須）

3. `.claude/tmp/atama-state.md` を新規作成（生徒名・教科・単元・読み・出力先を記載）

### 成功条件
- [ ] 教科・単元・名前の読み方が全て確定した
- [ ] `/tmp/hoshu_material/` が空の状態で存在する
- [ ] `.claude/tmp/atama-state.md` が新規作成された
- → Phase 1 へ（以降、Phase 6 完了まで途中報告なし）

---

## Phase 1: 接続 & ログイン

### 入力
- なし

### 処理

#### 1a. Chrome 起動

```bash
bash ~/.claude/skills/atama/scripts/launch-chrome.sh
```

- 既に起動中（`pgrep -f "chrome.*--remote-debugging-port=9222"`）ならスキップ
- `--remote-debugging-port=9222` でセッション永続化用 Chrome を起動（Playwright MCP が操作する）
- `--user-data-dir=~/.config/chrome-atama` でセッション永続化
- 起動後5秒待機

#### 1b. ログイン

1. `browser_navigate` で `https://coach.atama.plus/` に遷移
2. `browser_take_screenshot` でページ状態を確認

**URL判定:**
- `/user/home` → ログイン済み。Phase 2 へ
- `/public/login` → ログインフロー:

```bash
source ~/.env.atama && echo "ID=$ATAMA_ID PW_LEN=${#ATAMA_PW}"
```
`.env.atama` が存在しない場合はユーザーに手動入力を依頼。

Bash で認証情報を読み取り、JS 文字列を構築して `browser_evaluate` に渡す（`${ATAMA_ID}` と `${ATAMA_PW}` は bash の source で取得した値を JS 文字列内に展開する）:
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

`browser_snapshot` → ログインボタンの ref で `browser_click`。20秒待つ。`browser_take_screenshot` で確認。

**`/atama login` の場合はここで終了。**

### 成功条件
- [ ] ブラウザが操作可能（`browser_snapshot` が応答する）
- [ ] URL が `/user/home` を含む
- → Phase 2 へ

---

## Phase 2: データ収集

生徒詳細ページに遷移し、指定単元の学習データ取得→全セッションのモーダルを開いて誤答分析を行う。

### 入力
- ログイン済みホーム画面 + atama-state.md の生徒名・教科・単元名

### 処理

#### 2a. 生徒詳細ページへ遷移

1. `evaluate_script` で「全員」タブをクリック:
   ```javascript
   (() => {
     const allElements = document.querySelectorAll('*');
     for (const el of allElements) {
       if (el.textContent.trim() === '全員' && el.offsetParent !== null) {
         el.click();
         return 'Clicked';
       }
     }
     return 'Not found';
   })()
   ```
2. `take_snapshot` で生徒一覧を取得
3. 対象生徒の名前の uid を特定し `click(uid)` → 詳細ページに遷移
4. `take_screenshot` で遷移確認（URL が `/detail` を含む）

#### 2b. 指定単元の学習データ取得

1. `take_snapshot(filePath="/tmp/hoshu_material/snapshot_tabs.txt")` → 「単元ごとの学習状況」の uid で `click(uid)`
2. 教科セレクタボタンの uid で `click(uid)` → 教科選択メニューで指定教科を `click(uid)`
3. `take_snapshot(filePath="/tmp/hoshu_material/snapshot_units.txt")` でファイル保存
4. `Grep` で指定単元名を検索し、前後の行から学習データを記録:
   - 最終学習日、レベル、学習時間、正解数・不正解数
5. 指定単元が見つからない場合はユーザーに報告して終了

#### 2c. セッション選別 & 誤答分析（モーダル確認）

1. 対象単元の行を `click(uid)` で展開
2. `take_snapshot(filePath="/tmp/hoshu_material/snapshot_detail.txt")` で詳細行を取得
3. **全セッションを一覧化し、開く/スキップを判定してから操作に入る**

**セッション選別ルール:**
| 条件 | 判定 | 理由 |
|------|------|------|
| 不正解がある行（演習・講義） | **開く** | 誤答パターンの分析に必須 |
| アラート付きの行 | **開く** | 学習姿勢の問題を把握 |
| 0正解0不正解で(中止)かつ1分未満 | スキップ | 情報なし |
| 確認テスト | スキップ | クリックしてもツールチップが出るだけ |
| 正解のみ＆アラートなし | スキップ | 問題ないセッション |
| 既に同一問題を別セッションでカバー済み | スキップ | 重複回避 |

4. **選別結果を `/tmp/hoshu_material/session_selection.json` に記録する（スキップ前に必ず）:**
```json
{
  "total_sessions": 11,
  "opened": [
    {"index": 1, "type": "講義", "date": "3/11", "reason": "不正解2問"},
    {"index": 3, "type": "講義", "date": "3/11", "reason": "不正解1問"}
  ],
  "skipped": [
    {"index": 2, "type": "演習", "date": "3/11", "reason": "0正解0不正解、中止、2分"},
    {"index": 4, "type": "演習", "date": "3/11", "reason": "0正解0不正解、不明"}
  ]
}
```

**モーダルの処理手順（固定フロー — 順序厳守）:**
1. セッション行を `click(uid)` でモーダルを開く
2. 2〜3秒待機（モーダル表示待ち）
3. `take_snapshot(filePath="/tmp/hoshu_material/snapshot_{種別}_{日付}_{連番}.txt")` でテキスト取得
4. `take_screenshot`（Playwright MCP）で ○/❌ アイコンを視覚確認
5. 記録: 各問題のテーマ・正誤・アラート内容
6. モーダル内スクロールが必要な場合: `evaluate_script` で `.inner-scroll` の scrollTop を変更 → 追加 snapshot/screenshot
7. `take_snapshot` → 「閉じる」ボタンの uid で `click(uid)` してモーダルを閉じる
8. 1〜2秒待機（モーダル非表示待ち）
9. 次のセッションへ

**注意: snapshot → screenshot の順序を必ず守ること。逆にしない。**

### 成功条件
- [ ] 指定単元の学習データ（日付・レベル・正解数・不正解数）が取得できた
- [ ] `session_selection.json` にスキップ理由が記録されている
- [ ] 選別で「開く」と判定したセッションのモーダルを全て開いて問題の正誤を記録した
- → Phase 3 へ

---

## Phase 3: 図形抽出 & レポート作成【スキップ厳禁】

**スキップ厳禁。** 生徒が実際に間違えた問題の具体的な図形・寸法を把握しなければ、的確な足場がけプリントは作れない。

### 入力
- Phase 2 で記録した全セッションの問題一覧と正誤
- モーダルが閉じた状態の生徒詳細ページ

### 処理

#### 3a. 図形抽出

**Playwright MCP の evaluate で base64 画像を直接抽出する。**
（旧方式の `extract-figures.mjs` は CDP WebSocket 接続が必要で、Playwright MCP の内部ブラウザとは別インスタンスになるため使えない。）

各セッションについて:
1. セッション行を `click(uid)` でモーダルを開く（Phase 2c と同じ固定フロー）
2. `take_snapshot(filePath=...)` で問題文テキストを取得（数式の構造を把握）
3. **`browser_evaluate` で画像メタデータを取得:**
   ```javascript
   (() => {
     const modal = document.querySelector('ion-modal.show-modal');
     if (!modal) return JSON.stringify({error: 'no-modal'});
     const imgs = [...modal.querySelectorAll('img')].filter(i => i.src.startsWith('data:image'));
     return JSON.stringify({
       count: imgs.length,
       sizes: imgs.map((img, i) => ({i, w: img.naturalWidth, h: img.naturalHeight, bytes: img.src.length}))
     });
   })()
   ```
4. **各画像の base64 データを取得（1枚ずつ）:**
   ```javascript
   (() => {
     const modal = document.querySelector('ion-modal.show-modal');
     const imgs = [...modal.querySelectorAll('img')].filter(i => i.src.startsWith('data:image'));
     return imgs[INDEX].src.split(',')[1];
   })()
   ```
5. **Bash で base64 データを PNG ファイルに保存:**
   ```bash
   echo "BASE64_DATA" | base64 -d > /tmp/hoshu_material/{prefix}_img{index}.png
   ```
   - prefix はセッションごとにユニークにする（例: `enshu_0301`, `kougi_0228_2`）
6. 全画像を保存したら **サマリー JSON を Write ツールで作成:**
   ```json
   {"prefix": "enshu_0301", "outdir": "/tmp/hoshu_material", "figures": [
     {"filename": "enshu_0301_img0.png", "width": 400, "height": 300, "bytes": 12345}
   ]}
   ```
   → `/tmp/hoshu_material/{prefix}_summary.json`
7. `take_snapshot` → 「閉じる」ボタンの uid で `click(uid)` してモーダルを閉じる
8. 次のセッションへ

**画像がない場合（テキストのみの問題）:** `_summary.json` に `"figures": []` で記録して次へ進む。スキップ扱いにしない。

**base64 データが大きすぎる場合（100KB超）のフォールバック:**
- `browser_take_screenshot` で要素スクショを使う（`selector: "ion-modal.show-modal img:nth-of-type(N)"`）

#### 3b. レポート作成

Phase 2 の分析データを以下の形式でまとめて `/tmp/hoshu_material/report.txt` に保存:
1. **セッション時系列表**: 全セッションを古い順にテーブル表示
2. **集計**: 総セッション数、完了/中止の内訳、総回答数、正答率
3. **不正解パターン分析**: 問題テーマごとの正誤パターン
4. **つまずきポイント**: 具体的な弱点と学習傾向

`.claude/tmp/atama-state.md` に不正解問題一覧を追記。

### 出力
- `/tmp/hoshu_material/<prefix>_img0.png`, `img1.png`, ... （図形画像）
- `/tmp/hoshu_material/<prefix>_summary.json` （抽出サマリー）
- `/tmp/hoshu_material/report.txt` （分析レポート）

### 成功条件
- [ ] 開いたセッションの `_summary.json` が存在する（画像0枚でも可 — テキストのみの問題は figures: [] でよい）
- [ ] `report.txt` が存在する
- → Phase 4 へ

---

## Phase 4: プリント制作

問題プリント + 解答プリント + PDF を一括で作成する。

### 入力
- Phase 3 のレポート + 図形画像

### 処理

#### 4a. Gemini Pro によるプリント内容設計

Claude 単独で足場がけ設計・数式・SVG を生成すると誤りが発生しやすい。
**Gemini Pro にプリント内容を JSON で一括設計させ、Claude は HTML 組立のみを担当する。**

```python
# ~/studygram/.env から GEMINI_API_KEY と GEMINI_PARSE_MODEL を読み込む（ハードコード禁止）
import json
import os
import sys
from google import genai

env_vars = {}
with open(os.path.expanduser("~/studygram/.env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = map(str.strip, line.split("=", 1))
            env_vars[k] = v.strip("'\"")

api_key = env_vars.get("GEMINI_API_KEY")
parse_model = env_vars.get("GEMINI_PARSE_MODEL")
if not api_key or not parse_model:
    print("ERROR: GEMINI_API_KEY または GEMINI_PARSE_MODEL が未設定", file=sys.stderr)
    sys.exit(1)

client = genai.Client(api_key=api_key)
```

**プロンプトに含める情報:**
- 生徒名・学年・教科
- つまずき内容（Phase 3 のレポート）
- 足場がけルール（各ステップは「前のステップの知識だけで解けること」）
- 数式は LaTeX 穴埋め形式で出力すること
- 幾何の単元では SVG コードも生成すること（`viewBox='0 0 320 300'`）
- 自己検証（`self_review`）を含めること

**Gemini に要求する JSON 出力形式:**
```json
{
  "steps": [
    {
      "title": "ステップタイトル",
      "scaffolding_rationale": "前ステップの○○を使えば解ける",
      "problems": [
        {
          "number": 1,
          "statement": "問題文",
          "math_template": "\\pi \\times \\underline{\\hspace{3em}}^2 \\times ...",
          "svg": "<svg viewBox='0 0 320 300'>...</svg>",
          "hint": "ヒント",
          "answer": "6\\pi",
          "answer_steps": ["途中計算1", "途中計算2"]
        }
      ]
    }
  ],
  "self_review": {
    "math_errors": [],
    "scaffolding_gaps": [],
    "svg_issues": []
  }
}
```

**設計原則:**
1. **既知から出発**: 生徒が正解した内容・前提知識から始める
2. **穴埋め形式で導出**: 公式を丸暗記させず、1ステップずつ穴埋めで導かせる
3. **具体的数値で練習**: 文字式だけでなく、具体的な値で計算させる
4. **atama+と同形式で仕上げ**: 最終問題はatama+の出題形式に合わせる

#### 4b. 問題プリント HTML 作成

- MathJax v3 (tex-svg) で数式レンダリング
- `<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>`
- インライン数式: `$...$`、ディスプレイ数式: `$$...$$`
- 穴埋め箇所: `\underline{\hspace{3em}}` で下線付き空欄
- 幾何図形: SVG をインライン埋め込み（`.figure-box` 内）
- CSS: `~/.claude/skills/atama/scripts/print_style.css` をリンク

#### 4c. 解答プリント HTML 作成

- タイトルに「解答」ラベル（赤背景の白文字バッジ）
- 穴埋め箇所の答えを `\textcolor{red}{...}` で赤色表示
- 最終答えを `\boxed{...}` で枠囲み
- 途中計算の過程を省略せず記載
- 最後に全問の解答一覧表を掲載

#### 4d. PDF 生成

```bash
cd ~/.claude/skills/atama/scripts && node generate-pdf.mjs /tmp/hoshu_material/{単元名}_補習プリント.html
cd ~/.claude/skills/atama/scripts && node generate-pdf.mjs /tmp/hoshu_material/{単元名}_補習プリント_解答.html
```

- MathJax v3 のレンダリング完了を `MathJax.startup.promise` で待機
- A4サイズ、マージン上下20mm・左右18mm
- デフォルト出力先: `/mnt/c/Users/stsrj/Desktop/補習プリント/`

### 出力
- `/tmp/hoshu_material/{単元名}_補習プリント.html`
- `/tmp/hoshu_material/{単元名}_補習プリント_解答.html`
- `/tmp/hoshu_material/{単元名}_補習プリント.pdf`
- `/tmp/hoshu_material/{単元名}_補習プリント_解答.pdf`

### 成功条件
- [ ] HTML 2ファイルが存在する
- [ ] PDF 2ファイルが存在する
- → Phase 5 へ

---

## Phase 5: 動画制作

### 入力
- Phase 3 のレポート + 図形画像

### 前提条件
- `~/studygram/.env` に `GEMINI_API_KEY` と `GEMINI_TTS_MODEL` が設定済み
- TTS ラッパー: `~/.claude/skills/atama/scripts/gemini_tts_service.py`
- Modal CLI がインストール済み（`modal` コマンドが使える）
- 初回デプロイ: `modal deploy ~/.claude/skills/atama/scripts/modal_manim_app.py`

### レンダリングバックエンド

環境変数 `ATAMA_RENDER_BACKEND` で切り替え（デフォルト: `modal`）:

| 値 | 動作 |
|------|------|
| `modal` | Modal で実行（デフォルト） |
| `local` | ローカル manim render（従来動作。manim + sox がローカルに必要） |
| `auto` | Modal 失敗時にローカルへ自動フォールバック |

**例外分類（`auto` モード時）:**
- Modal API 接続失敗 / タイムアウト → フォールバック対象
- 音声ファイル不足 (RuntimeError: "音声ファイルが見つかりません") → **即 fail**（フォールバックしても直らない）
- manim 実行失敗 → スクリプト修正して再試行

### 処理

#### 5a. Gemini Pro に脚本 JSON を生成させる

プロンプトに含める情報:
- 生徒の名前の読み方（Phase 0 で確認）
- つまずき内容（Phase 3 のレポート）
- 足場がけルール
- ナレーションは話し言葉（「〜なんですよ」「〜でしょう？」）
- ボイスの選択（Puck/Kore/Charon/Fenrir/Aoede 等）
  - 女子生徒向けには爽やか系男性ボイス（Puck）を推奨

**Gemini に要求する JSON:**
```json
{
  "title": "単元名",
  "voice": "Puck",
  "scenes": [
    {
      "scene_id": "scene1",
      "step": 1,
      "title": "シーンタイトル",
      "narration": "話し言葉のナレーション全文",
      "narration_reading_guide": "数式の読み方メモ",
      "scaffolding_check": "前提知識と順序の根拠",
      "animations": [
        {"type": "draw_sector", "radius": 6, "angle": 60, "position": "left"},
        {"type": "write_math", "text": "S = \\pi r^2 \\times \\frac{a}{360}"}
      ],
      "scene_summary": "このシーンで学んだこと1文"
    }
  ],
  "self_review": { "scaffolding_gaps": [], "math_errors": [], "narration_issues": [] }
}
```

#### 5b. JSON → Manim スクリプト変換 + ナレーション一覧抽出

スクリプト生成と同時に、**全ナレーションテキストのリスト `narrations`** も出力すること。
（静的 regex 抽出は f-string/変数展開でズレるため、生成時に一覧を出す。）

```python
import os, sys
sys.path.insert(0, os.path.expanduser('~/.claude/skills/atama/scripts'))
from manim import *
from manim_voiceover import VoiceoverScene
from gemini_tts_service import GeminiTTSService

class HoshuVideo(VoiceoverScene):
    def setup(self):
        super().setup()
        self.set_speech_service(GeminiTTSService(voice_name="Puck"))
    def construct(self):
        self.scene_intro()
        self.scene_summary()
```

**`narrations` リスト（別途出力）:**
```python
narrations = [
    "こんにちは、あいりさん。今日は扇形の面積を一緒にやっていきましょう。",
    "まず、円の面積の公式を思い出してみましょう。...",
    # ... 全シーンのナレーション
]
```

**日本語テキスト注意:**
- `Text()` には `font="Noto Sans CJK JP"` を指定
- `MathTex()` の `\text{}` 内に日本語を入れない。`Text` + `MathTex` を `VGroup().arrange(RIGHT)` で横並び

**TTS テキストルール:**
1. 分数は「分母ぶんの分子」の順（厳守）
2. 数字・数式は話し言葉で書く（`3cm` → `さんセンチ`）
3. 句読点で間をコントロール
4. 変数はカタカナ（x→エックス）

#### 5c. TTS 事前生成（ローカル）

全ナレーションの WAV をローカルで事前生成する。Gemini TTS API を使用。

```python
import os, sys
sys.path.insert(0, os.path.expanduser('~/.claude/skills/atama/scripts'))
from gemini_tts_service import GeminiTTSService

tts = GeminiTTSService(voice_name="Puck")  # voice は 5a の JSON から取得
voice_files = tts.pre_generate_all(narrations)
# voice_files: dict[str, bytes] = {cache_key: wav_bytes, ...}
```

**注意:** Modal に Gemini API キーは渡さない。TTS はこのステップでローカル完結。

#### 5d. レンダリング（Modal or ローカル）

**Modal モード（デフォルト）:**
```python
import modal
render_fn = modal.Function.from_name("manim-render", "render_video")
mp4_bytes = render_fn.remote(script_content, voice_files)

# MP4 をローカルに保存
with open("/tmp/hoshu_material/{単元名}_video_final.mp4", "wb") as f:
    f.write(mp4_bytes)
```

Modal 側で manim render + ffmpeg 圧縮（crf=28, preset fast, movflags +faststart）が実行される。
返却される MP4 は圧縮済みなので 5d の手動 ffmpeg は不要。

**ローカルモード（フォールバック）:**
```bash
cd /tmp/hoshu_material && manim render -qm --format mp4 {単元名}_video.py HoshuVideo
ffmpeg -i /tmp/hoshu_material/{単元名}_video.mp4 \
  -vcodec libx264 -crf 28 -preset fast \
  -movflags +faststart -acodec aac -b:a 96k \
  /tmp/hoshu_material/{単元名}_video_final.mp4 -y
```

#### 5e. 動画品質レビュー

1. Manim スクリプトからシーン仕様書を `/tmp/hoshu_material/scene_spec.txt` に作成
2. Gemini Flash でレビュー（日本語ファイル名は自動的にASCII名に変換される）:
   ```bash
   python3 ~/.claude/skills/atama/scripts/video_reviewer.py \
     /tmp/hoshu_material/{単元名}_video_final.mp4 \
     /tmp/hoshu_material/scene_spec.txt
   ```
3. HIGH issue → Manim 修正 → 5c から再実行（TTS キャッシュが効くので WAV 再生成は不要）
4. MEDIUM 以下 / issues なし → PASS

### 出力
- `/tmp/hoshu_material/{単元名}_video_final.mp4`

### 成功条件
- [ ] `_final.mp4` が存在する
- [ ] レビュー結果が PASS
- → Phase 6 へ

**並列化:** Phase 4 と Phase 5 は Agent ツールで並列実行可能。必須ではない。

---

## Phase 6: アップロード

### 入力
- PDF 2ファイル + 動画ファイル

### 処理

```bash
python3 ~/.claude/skills/atama/scripts/upload_hoshu.py \
  --student "生徒名" \
  --title "【補習】単元名" \
  --subject "教科" \
  --problem /tmp/hoshu_material/{単元名}_補習プリント.pdf \
  --answer  /tmp/hoshu_material/{単元名}_補習プリント_解答.pdf \
  --video   /tmp/hoshu_material/{単元名}_video_final.mp4
```

**既存プリントの差し替え:**
```bash
python3 ~/.claude/skills/atama/scripts/upload_hoshu.py \
  --replace {PRINT_ID} \
  --problem ... --answer ... --video ...
```

**動画なしの場合:** `--video` を省略。

### 出力
- R2 にアップロード + DB レコード作成 + 生徒配信
- `rm -rf /tmp/hoshu_material/` でクリーンアップ

### 成功条件
- [ ] アップロードスクリプトがエラーなく完了
- [ ] クリーンアップ完了
- → **ここでユーザーに全工程の結果をまとめて報告する**
- 報告内容: 分析結果サマリー + プリント名 + 動画再生時間 + 配信先生徒名

---

## SPA 操作のルール

### クリック方法の使い分け
| 操作 | 方法 | 理由 |
|------|------|------|
| タブ切替（全員、単元進捗など） | `browser_evaluate` で `el.click()` | 同一ページ内の切替は JS クリックで動く |
| 教科選択メニューの項目選択 | `browser_snapshot` → `browser_click(ref)` | ref クリック推奨 |
| **生徒行のクリック（ページ遷移）** | **`browser_snapshot` → `browser_click(ref)`** | **Angular ルーター遷移は実マウスイベントが必要** |
| 教科セレクタボタンを開く | `browser_snapshot` → `browser_click(ref)` | ボタン要素は ref クリックが確実 |
| 学習履歴サブタブ切替 | `browser_snapshot` → `browser_click(ref)` | 「学習タイムライン」「単元ごとの学習状況」の切替 |
| 単元の展開行（詳細表示） | `browser_snapshot` → `browser_click(ref)` | 単元行クリックで詳細行が展開される |
| 詳細行のクリック（モーダル表示） | `browser_snapshot` → `browser_click(ref)` | 演習/講義の詳細行→問題リストモーダル |
| モーダルの「閉じる」ボタン | `browser_snapshot` → `browser_click(ref)` または `browser_evaluate` | ref 無効時は JS フォールバック |

### 教科切替の手順
1. 教科セレクタボタンの uid を `take_snapshot` で取得し、`click(uid)` で開く
2. 教科選択メニューが表示されたら、`take_snapshot` で教科名の uid を取得し `click(uid)`
3. 切替後に `take_snapshot` で新しい教科の単元一覧を取得

### データ取得方法
| 目的 | 方法 |
|------|------|
| 画面の視覚確認 | `browser_take_screenshot` |
| テキストデータ一括取得 | `browser_snapshot` → `Grep` で検索 |
| API レスポンス取得 | `browser_network_requests` |
| DOM 直接検索 | `browser_evaluate` |

### つまずき検出方法
- snapshot 内で `StaticText "つまずき"` を探す
- つまずきマークは単元行に付与される（レベル表示の近く）

## API エンドポイント（参考）
- 組織ID: `5566`
- 生徒一覧: `GET /v3/organizations/5566/organization_users/?sort=last_seen&limit=300&include_session_summary=true&include_personal_info=true&include_study_stats=true`
- 認証ヘッダ: `Authorization: ATAMA-SessionToken {token}`

## 注意事項
- **COACH/Ionic は Playwright MCP 一択**。Chrome DevTools MCP の evaluate で shadow DOM は操作不可
- **スクショは常に Playwright MCP**。DevTools screenshot は使用禁止
- Ionic の `ion-select` はプログラム操作が困難。ポップオーバーが開いた後にテキスト要素をクリック
- 高校生の場合、中学教科はスキップ
- 動画レビュー時、日本語ファイル名は video_reviewer.py が自動的にASCII名にコピーする
