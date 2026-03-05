---
name: atama
description: atama+ COACH 操作（学習データ取得→つまずき分析→補習プリント＆解説動画作成）
user_invocable: true
arguments:
  - name: target
    description: "生徒名と教科（例: 鎮守杏 物理）、または 'login' でログインのみ"
    required: true
---

# atama+ COACH 自動化スキル

Chromiumを起動し、chrome-devtools MCP経由でatama+ COACHにログイン。
指定生徒の学習データ取得→つまずき分析→足場がけ補習プリント作成→解説動画作成→PDF・動画出力を一気通貫で実行する。

## コマンド体系

| コマンド | 説明 |
|---------|------|
| `/atama <生徒名> <教科>` | 指定教科のフルパイプライン（Phase 1〜12） |
| `/atama <生徒名>` | 全教科つまずきスキャン → 選択 → プリント作成（Phase 1〜12） |
| `/atama login` | Chromium起動＆ログインのみ（Phase 1〜2） |

## 設定情報

`reference.md` を参照すること。

---

## Phase 1: Chromium起動

`launch-chrome.sh` でChromiumを起動する。

```bash
bash ~/.claude/skills/atama/scripts/launch-chrome.sh
```

- 既に起動中（`pgrep -f "chrome.*--remote-debugging-port=9222"`）ならスキップ
- `--remote-debugging-port=9222` でchrome-devtools MCP接続
- `--user-data-dir=~/.config/chrome-atama` でセッション永続化
- 起動後5秒待機してからPhase 2へ

---

## Phase 2: MCP接続＆ログイン

1. `list_pages` でページ一覧を取得
2. atama+ COACHのページがあれば `select_page` で選択。なければ `navigate_page` で `https://coach.atama.plus/` に遷移
3. `take_screenshot` でページの状態を確認

**URL判定:**
- `/user/home` → ログイン済み。Phase 3へ進む
- `/public/login` → ログインフロー実行:

#### 2a. ID・パスワード入力
`~/.env.atama` から認証情報を読み取る。**パスワードは長さのみ表示**:
```bash
source ~/.env.atama && echo "ID=$ATAMA_ID PW_LEN=${#ATAMA_PW}"
```
`.env.atama` が存在しない場合はユーザーに手動入力を依頼して Phase 3 へ進む。

Bash で認証情報を読み取り、JS文字列を構築して `evaluate_script` に渡す。
**セキュリティ注意: 生パスワードを echo/出力してはならない。Bash 内で JS を組み立てて直接渡す。**

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
**注意:** `${ATAMA_ID}` と `${ATAMA_PW}` は Bash の `source` で取得した値を JS 文字列内に展開する。

#### 2b. ログインボタンクリック
1. `take_snapshot` → ログインボタンの uid で `click(uid)`。
2. 20秒待つ（ページ遷移に時間がかかる）。
3. `take_screenshot` でログイン成功を確認する（URLが `/user/home` なら成功）。
4. エラーダイアログが出た場合はユーザーに手動ログインを依頼する。

**重要: `navigate_page` の `initScript` は絶対に使わないこと。initScript は以降の全ページ読み込みに永続的に適用され、Firebase Auth を破壊する。**

**`/atama login` の場合はここで終了。**

---

## Phase 3: 生徒詳細ページへ遷移

1. ホーム画面はデフォルトで「ログイン中」タブ。`evaluate_script` で「全員」タブをクリック:
   ```javascript
   () => {
     const allElements = document.querySelectorAll('*');
     for (const el of allElements) {
       if (el.textContent.trim() === '全員' && el.offsetParent !== null) {
         el.click();
         return 'Clicked';
       }
     }
     return 'Not found';
   }
   ```

2. `take_snapshot` で生徒一覧のスナップショットを取得する。
3. 対象生徒の名前の uid を特定する（例: `StaticText "鎮守 杏"` → `uid=5_12`）。

**重要: `evaluate_script` の JS クリックではページ遷移しない。`take_snapshot` → `click(uid)` を使う。**

4. `click(uid)` で生徒名をクリックする → 詳細ページに遷移する。
5. `take_screenshot` で遷移を確認する。URLが `/user/home/organization-users/{id}/detail` なら成功。

---

## Phase 4: つまずきスキャン

教科が指定されていれば指定教科のみ、未指定なら全高校教科（または全中学教科）を巡回し、`StaticText "つまずき"` マークを持つ単元を検出する。

1. 「単元ごとの学習状況」タブに切り替える:
   - `take_snapshot` → 「単元ごとの学習状況」の uid で `click(uid)`。

2. 教科セレクタを開いて教科一覧を取得する:
   - `take_snapshot` → 教科セレクタボタン（例:「高校化学」）の uid で `click(uid)`。
   - 教科選択メニューが表示されたら `take_snapshot` で全教科名を取得。

3. 高校生判定:
   - 教科リストに「高校」で始まる教科が含まれれば高校生と判定。
   - 高校生の場合、「中学」で始まる教科はスキップする。

4. 各教科について以下を実行:
   a. 教科選択メニューの `take_snapshot` から対象教科名の uid を特定し、`click(uid)` でクリックする。
      - **`evaluate_script` による教科名クリックは不安定なため使わない。**
   b. **`take_snapshot(filePath="/tmp/snapshot_{教科名}.txt")` でファイルに保存する。**
      - 生徒詳細ページのスナップショットは巨大（50KB超）になるため、インライン取得するとトークン上限エラーになる。
      - **必ず `filePath` を指定**し、保存後は `Grep` ツールで `つまずき` を検索する。
   c. `Grep` で `つまずき` を検索（`-B 5 -A 3` で前後のコンテキストを取得）:
      - つまずきがある場合、前後の行から単元の情報を記録する:
        - 単元名（つまずきの5行前付近の StaticText）
        - レベル（つまずきの1行前の StaticText）
        - 最終学習日（つまずきの2行前の StaticText）
        - 学習時間（つまずきの1行後の StaticText）
        - 正解数・不正解数（つまずきの2-3行後の StaticText）
   d. 次の教科に切り替える:
      - 教科セレクタボタンを再度 `click(uid)` で開く。
      - 次の教科名の uid で `click(uid)` する。

5. **日付フィルタリング**: ユーザーが期間を指定した場合（例:「ここ3日間」）、検出したつまずきの最終学習日が期間内かチェックし、期間外のものは除外する。

6. 全教科スキャン完了後、つまずき一覧をテーブルで報告する:
   | 教科 | 単元名 | レベル | 学習時間 | 正解 | 不正解 |
   |------|--------|--------|----------|------|--------|

---

## Phase 5: つまずき報告・単元選択・呼び方確認

1. Phase 4 で検出したつまずき単元一覧をユーザーに提示する。
2. つまずきが **0件** の場合はその旨報告して終了する。
3. どの単元の補習プリントを作成するかユーザーに選ばせる。
4. **生徒の呼び方を確認する**: 「動画・プリントでの呼びかけ名は何にしますか？（例: あんさん、杏さん、鎮守さん）」とユーザーに聞く。
   - この呼び方は Phase 9（プリント）と Phase 11.5（動画脚本）の Gemini プロンプトに渡す。
   - 漢字名の読みは必ず確認すること（例: 杏 → あん / あんず の区別）。
5. ユーザーが選択した単元について Phase 6 以降を実行する。

---

## Phase 6: 誤答分析

選択されたつまずき単元の展開された詳細行を1行ずつクリックして問題内容を確認する。

1. 「単元ごとの学習状況」タブで、対象単元の行を `click(uid)` でクリック → 詳細行が展開される。
2. 展開後に `take_snapshot` で詳細行を取得する。

**対象行の優先度:**
1. 不正解がある行（演習・講義）→ 必ずクリックして問題内容を確認
2. アラート付きの行（時間超過など）→ クリックして問題セットを確認
3. 0正解0不正解で(中止)かつ1分未満 → スキップ可（内容なし）
4. 0正解0不正解でも学習時間がある行 → クリックして問題セットを確認
5. **確認テスト → スキップ**（クリックしてもツールチップが表示されるだけで問題詳細は見られない）

**重要: 「問題を見る」ボタンは使わない。** 全日分の全問題が1ページに展開され、スナップショットがトークン上限を超える。代わりに、タイムライン上の各セッション行を個別にクリックしてモーダルで確認すること。

**詳細行クリック → モーダル表示:**
- 演習の場合: 問題1〜N が表示される。各問題に ○（正解）/ ❌（不正解）/ マークなし（未回答）がつく。
- 講義の場合: 講義動画名 + 練習問題が表示される。練習問題に ❌ があれば不正解。
- `take_snapshot` で問題文とマークを一括取得する。
- `take_screenshot` で ○/❌ のアイコンを視覚確認する（snapshot に ○/❌ が出ない場合がある）。
- モーダル内スクロールが必要な場合は `evaluate_script` でスクロールする。

**モーダルの閉じ方:**
- `take_snapshot` → 「閉じる」ボタンの uid で `click(uid)`
- uid が無効な場合: `evaluate_script` で `el.textContent.trim() === '閉じる'` を探してクリック

**⚠️ ナビゲーション注意:**
- モーダル内の問題詳細画面から `navigate_page(type: "back")` で戻ると、モーダルではなく**生徒一覧ページまで戻ってしまう**ことがある。
- 必ずモーダルの「閉じる」ボタンを使うこと。
- 万一生徒一覧まで戻ってしまった場合は、生徒名を再クリック → 教科再選択 → 単元再展開が必要になる。

**分析の記録（各セッションごと）:**
- 日付、種別（演習/講義/診断）、学習時間、中止有無
- 各問題のテーマ（問題文から判断）と正誤
- アラート内容

---

## Phase 7: 結果まとめ

取得したデータを以下の形式でまとめてユーザーに報告する:

1. **セッション時系列表**: 全セッションを古い順にテーブル表示（日付、種別、時間、正解数、不正解数、状態、詳細）
2. **集計**: 総セッション数、完了/中止の内訳、総回答数、正答率
3. **不正解パターン分析**: 問題テーマごとに各日付の正誤を並べ、改善/未解決を判定
4. **つまずきポイント**: 具体的な弱点と学習傾向（中止の多さ、動画視聴不足など）

---

## Phase 8: 誤答問題の詳細確認（補習プリント材料収集）

Phase 6 の分析で特定した不正解問題について、数式・図を正確に把握するためにスクリーンショットを保存する。

1. 保存先ディレクトリを作成する: `mkdir -p /tmp/hoshu_material/`
2. つまずき単元の詳細行をクリックしてモーダルを開く（Phase 6 と同じ手順）。
3. 不正解の問題について:
   - `take_snapshot` で問題文テキストを取得する（数式の構造を把握）。
   - `take_screenshot(filePath=...)` で問題のスクリーンショットを保存する。
   - ファイル名例: `/tmp/hoshu_material/enshu1224_q3.png`
4. モーダル内にスクロールが必要な場合:
   - `evaluate_script` で `document.querySelector('.inner-scroll').scrollTop = N` を実行。
   - snapshot データは scroll 位置に関係なく全内容を取得できる。
   - screenshot は表示範囲のみ撮影される（スクロール前後で複数枚撮影する）。
5. 全不正解問題のスクリーンショットと問題文テキストを収集する。

**記録する情報:**
- 各問題の正確な問題文（数式含む）
- 小問構成（(1)(2)(3)...の各設問内容）
- 正誤マーク（○/❌/未回答）
- 使われている物理量の記号・条件設定

---

## Phase 9: 補習プリント作成（足場がけ設計）

Phase 7-8 の分析結果に基づき、生徒がatama+の学習に戻れるよう足場がけ（scaffolding）の補習プリントを作成する。

**複数単元の場合:** つまずき単元が複数ある場合は、Task ツール（`subagent_type: "general-purpose"`）で並列に作成する。各エージェントに単元名・誤答分析結果・設計原則・CSS パスを渡し、問題HTML + 解答HTML を同時に生成させる。

### Gemini Pro によるプリント内容設計（推奨）

Claude 単独で足場がけ設計・数式・SVG を生成すると、数式テンプレートの誤りや足場がけの飛躍が発生しやすい。
**Gemini Pro にプリント内容を JSON で一括設計させ、Claude は HTML 組立のみを担当する**パターンを推奨する。

```python
# ~/studygram/.env から GEMINI_API_KEY と GEMINI_PARSE_MODEL を読み込む（ハードコード禁止）
from google import genai
import json, os, sys

env_vars = {}
with open(os.path.expanduser("~/studygram/.env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env_vars[k] = v.strip('"').strip("'")

api_key = env_vars.get("GEMINI_API_KEY")
parse_model = env_vars.get("GEMINI_PARSE_MODEL")
if not api_key:
    print("ERROR: GEMINI_API_KEY が未設定", file=sys.stderr); sys.exit(1)
if not parse_model:
    print("ERROR: GEMINI_PARSE_MODEL が未設定", file=sys.stderr); sys.exit(1)

client = genai.Client(api_key=api_key)
```

**プロンプトに含める情報:**
- 生徒名・学年・教科
- つまずき内容（Phase 7-8 の分析結果）
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

**Claude の役割（JSON → HTML 変換）:**
- Gemini の JSON 出力を読み取る
- `self_review` にエラーが報告されていたら修正を要求する
- MathJax + SVG インラインの HTML を組み立てる

**設計原則:**
1. **既知から出発**: 生徒が正解した内容・前提知識から始める
2. **穴埋め形式で導出**: 公式を丸暗記させず、1ステップずつ穴埋めで導かせる
3. **具体的数値で練習**: 文字式だけでなく、具体的な値で計算させる
4. **atama+と同形式で仕上げ**: 最終問題はatama+の出題形式に合わせる

**ファイル作成:**
1. HTML ファイル (`/tmp/hoshu_material/{単元名}_補習プリント.html`):
   - MathJax v3 (tex-svg) で数式レンダリング
   - `<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>`
   - インライン数式: `$...$`、ディスプレイ数式: `$$...$$`
   - 穴埋め箇所: `\underline{\hspace{3em}}` で下線付き空欄
   - underbrace: `\underbrace{...}_{\text{ラベル}}` で式の意味を注釈
   - 幾何図形: SVG をインライン埋め込み（`.figure-box` 内）
2. CSS: `~/.claude/skills/atama/scripts/print_style.css` をリンク

---

## Phase 10: 解答プリント作成

問題プリント（Phase 9）に対応する解答プリントを作成する。

**解答HTML (`/tmp/hoshu_material/{単元名}_補習プリント_解答.html`) の構成:**
1. タイトルに「解答」ラベルを追加（赤背景の白文字バッジ）
2. 各問題の解答を赤枠の【解答】ボックスで表示:
   - 穴埋め箇所の答えを `\textcolor{red}{...}` で赤色表示
   - 最終答えを `\boxed{...}` で枠囲み
   - 途中計算の過程を省略せず記載
   - 補足説明（式変形のコツなど）をイタリックで追記
3. 最後に全問の解答一覧表を掲載

**設計原則:**
- 問題プリントと同じステップ構成を維持する
- 答えだけでなく途中計算を丁寧に書く
- 式変形のポイントを補足する

---

## Phase 11: PDF生成

Puppeteer で HTML → PDF 変換する。

```bash
cd ~/.claude/skills/atama/scripts && node generate-pdf.mjs /tmp/hoshu_material/{単元名}_補習プリント.html
cd ~/.claude/skills/atama/scripts && node generate-pdf.mjs /tmp/hoshu_material/{単元名}_補習プリント_解答.html
```

- MathJax v3のレンダリング完了を `MathJax.startup.promise` で待機
- A4サイズ、マージン上下20mm・左右18mm
- ヘッダー/フッターなし
- デフォルト出力先: `/mnt/c/Users/stsrj/Desktop/補習プリント/`

**生成後の確認:**
- ブラウザで HTML を開いて `take_screenshot(fullPage=true)` でレイアウト・数式レンダリングを確認する
- `poppler-utils` がインストール済みなら Read ツールで PDF を直接確認してもよい

---

## Phase 11.5: Manim 解説動画の作成

Phase 7-8 の分析結果に基づき、つまずきポイントを解説する Manim アニメーション動画を生成する。

### 前提条件
- `modal` パッケージ + `modal token new` でセットアップ済みであること
- Modal アプリ `manim-render` がデプロイ済みであること（`~/.claude/skills/atama/scripts/modal_tts_app.py`）
- 音声は Microsoft Edge TTS（`ja-JP-KeitaNeural`）をコンテナ内でオンザフライ生成（GPU不要）

### Step 1: 動画脚本JSON生成 → Manim スクリプト変換

まず **Gemini Pro に動画脚本 JSON を生成させ**、それを Claude が Manim コードに変換する。
Claude が構成・ナレーション・アニメーション設計をゼロから考えるより、Gemini にシーン設計を任せた方が足場がけの一貫性が高い。

**Step 1a: Gemini Pro に脚本 JSON を生成させる**

```python
# ~/studygram/.env から GEMINI_API_KEY と GEMINI_PARSE_MODEL を読み込む
from google import genai
import json, os, sys

env_vars = {}
with open(os.path.expanduser("~/studygram/.env")) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env_vars[k] = v.strip('"').strip("'")

api_key = env_vars.get("GEMINI_API_KEY")
parse_model = env_vars.get("GEMINI_PARSE_MODEL")
if not api_key or not parse_model:
    print("ERROR: env 未設定", file=sys.stderr); sys.exit(1)

client = genai.Client(api_key=api_key)
```

**プロンプトに含める情報:**
- 生徒名・つまずき内容（Phase 7-8 の分析結果）
- 足場がけルール: 各シーンは「前のシーンで学んだ知識だけで理解できること」
- ナレーションは話し言葉（「〜なんですよ」「〜でしょう？」）
- 数式のナレーション読み方ルール（分数は「○ぶんの○」等）
- アニメーションタイプ一覧（write_math, transform_math, draw_shape, highlight 等）

**Gemini に要求する JSON 出力形式:**
```json
{
  "title": "おうぎ形の応用",
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
  "self_review": {
    "scaffolding_gaps": [],
    "math_errors": [],
    "narration_issues": []
  }
}
```

脚本 JSON は `/tmp/hoshu_material/video_script.json` に保存する。

**Step 1b: Claude が JSON → Manim スクリプトに変換**

脚本 JSON のシーン構成・ナレーション・アニメーション指示を読み取り、Manim の Python コードを `/tmp/hoshu_material/{単元名}_video.py` に生成する。

**スクリプト構造（基本パターン — メソッド分割は任意）:**

```python
import sys
sys.path.insert(0, '/home/yuki/.claude/skills/atama/scripts')

from manim import *
from manim_voiceover import VoiceoverScene
from edge_service import EdgeTTSService

class HoshuVideo(VoiceoverScene):
    def setup(self):
        super().setup()
        self.set_speech_service(EdgeTTSService())

    def construct(self):
        self.scene_intro()
        # ... 各ポイントのシーン
        self.scene_summary()
```

**シーン設計原則:**
1. **イントロ**: 単元名 + 「つまずきやすいポイントを確認しましょう」
2. **各ポイント（2-4シーン）**: つまずき分析で特定した具体的な弱点ごとに1シーン
   - ヘッダー（BLUE）でポイント番号とタイトル
   - 式の段階的表示（Write アニメーション）
   - よくある間違い（RED で ✕）→ 正解（GREEN で ✓）
   - 数直線・グラフ・図形を活用
3. **まとめ**: チェックリスト形式で全ポイントを復習
4. **エンディング**: 「補習プリントで練習しよう！」

**日本語テキストの注意:**
- `Text()` には `font="Noto Sans CJK JP"` を指定
- `MathTex()` の `\text{}` 内に日本語を入れるとエラーになる。日本語と数式が混在する場合は `Text` と `MathTex` を別 Mobject にして `VGroup().arrange(RIGHT)` で横に並べる
- voiceover の text は自然な日本語話し言葉で書く（「サイン t は」「コサイン2乗は」等）

**voiceover テキストの TTS 最適化ルール:**
Edge TTS（Microsoft）は日本語の読み上げ精度が高いが、以下に注意:

1. **分数は「分母ぶんの分子」の順で読む（厳守）**
   - `a/360` → 「さんびゃくろくじゅうぶんのエー」（✕「エーぶんのさんびゃくろくじゅう」）
   - `90/360` → 「さんびゃくろくじゅうぶんのきゅうじゅう」
   - `1/4` → 「よんぶんのいち」
2. **数字・数式は話し言葉で書く**
   - `3cm` → `さんセンチ`、`a²` → `エーのにじょう`
   - 算用数字や記号（+, =, ², √）は使わず、読み仮名で書く
3. **句読点で間をコントロール**
   - 式の区切りに読点「、」を入れる: 「エーのにじょう、たす、ビーのにじょう」
   - 文末は必ず句点「。」で終える
4. **変数はカタカナで**: x→エックス、y→ワイ、a→エー、b→ビー、c→シー、n→エヌ
5. **漢字はそのままでOK**: Edge TTS は漢字の読みが正確なので、無理にひらがなに開く必要はない

**色使いルール:**
- ヘッダー: BLUE
- 強調・ステップ: YELLOW
- 正解・結論: GREEN
- 間違い・注意: RED

### Step 2: レンダリング（Modal CPU）

Modal の `render_video` 関数でレンダリングする。ローカル manim は使わない。
音声（Edge TTS）はコンテナ内でオンザフライ生成される。事前の音声生成ステップは不要。

```python
import modal
from pathlib import Path

render_video = modal.Function.from_name("manim-render", "render_video")

script = Path("/tmp/hoshu_material/{単元名}_video.py").read_text()

# Modal CPU 8コアで実行（scene_name は省略可、自動検出される）
mp4_bytes = render_video.remote(script, scene_name="HoshuVideo")

# 結果を保存
output_path = "/tmp/hoshu_material/{単元名}_video.mp4"
with open(output_path, "wb") as f:
    f.write(mp4_bytes)
print(f"Rendered: {len(mp4_bytes)} bytes -> {output_path}")
```

- Modal CPU 8コア × 最大10分（`timeout=600`）
- Edge TTS でコンテナ内オンザフライ音声生成（GPU不要）
- スクリプト内の `sys.path.insert` は自動で `/work` に書き換わる
- コンテナ内に `edge_service.py` スタブが自動配置される
- 出力: MP4 バイト列がローカルに返る
- コスト: ~$0.03/回（CPU のみ、$30/月無料枠で余裕）

### Step 3: 動画圧縮＆確認

Modal から返る MP4 は無圧縮気味（4MB 超になりがち）。アップロード前に圧縮する:

```bash
ffmpeg -i /tmp/hoshu_material/{単元名}_video.mp4 \
  -vcodec libx264 -crf 28 -preset fast \
  -acodec aac -b:a 96k \
  /tmp/hoshu_material/{単元名}_video_final.mp4 -y
```

```bash
ffprobe -v quiet -show_entries format=duration,size -of default=noprint_wrappers=1 \
  /tmp/hoshu_material/{単元名}_video_final.mp4
```

- 圧縮後のファイル（`_final.mp4`）をアップロードに使う
- 再生時間と容量を確認・報告する

---

## Phase 11.6: 動画の自動品質レビュー

レンダリング済み動画を **Gemini 3 Flash** に直接アップロードし、シーン仕様書と照合してアニメーション品質を自動検証する。
目視確認だけでは見逃しやすい問題（塗りつぶし欠落、ラベル遷移なし、弓形ハイライト不足等）を機械的に検出する。

**なぜ Flash か:** Vision/OCR 精度が Pro より高く、false positive が少ない。コストも 1/4（$0.50/1M vs $2.00/1M）。

### Step 1: シーン仕様書の作成

Manim スクリプトを読み、各シーンで「画面上に何が表示されるべきか」を詳細に記述した仕様書を `/tmp/hoshu_material/scene_spec.txt` に作成する。

**記述する内容（シーンごと）:**
- ヘッダーテキスト
- 図形の種類・色・塗りつぶし（半透明か否か）
- ラベルの内容・位置・色
- 数式の内容・変形ステップ
- アニメーション遷移（例: 「直径8cm」→「半径4cm」に変化）
- 強調表示（囲み線、ハイライト）
- ナレーション内容

### Step 2: Gemini Flash でレビュー実行

`~/.claude/skills/atama/scripts/video_reviewer.py` を使用する。

```bash
python3 ~/.claude/skills/atama/scripts/video_reviewer.py \
  /tmp/hoshu_material/{単元名}_video_final.mp4 \
  /tmp/hoshu_material/scene_spec.txt
```

- MP4 を Gemini File API で直接アップロード（フレーム抽出不要）
- シーン仕様書と実映像を 1 シーンずつ照合
- 結果は JSON で返る: `{issues: [{timestamp, scene, severity, description, suggestion}], overall_assessment}`
- レビュー結果は `{動画名}_review.json` に自動保存

**環境変数:** `~/studygram/.env` の `GEMINI_API_KEY` と `VITE_GEMINI_FLASH_MODEL` を使用する。

### Step 3: レビュー結果に基づく修正ループ

```
issues の severity を確認:
  HIGH → Manim スクリプトを修正 → Phase 11.5 Step 2 (再レンダリング) → Phase 11.6 Step 2 (再レビュー)
  LOW のみ / issues なし → PASS → Phase 12 へ進む
```

**よくある HIGH issue の例:**
- 図形の塗りつぶし・ハイライトが欠落している
- ラベルの遷移アニメーション（直径→半径等）がない
- ナレーションと画面表示のタイミングがずれている

---

### 並列化

**プリント作成（Phase 9-10）と動画作成（Phase 11.5-11.6）は Agent ツールで並列実行できる。**
Phase 7-8 の分析結果は両方に共通の入力なので、Phase 8 完了後に:
- Agent A: Phase 9（問題プリント）→ Phase 10（解答プリント）
- Agent B: Phase 11.5 Step 1-3（脚本JSON → Manim変換 → レンダリング → 圧縮）→ Phase 11.6（動画レビュー）
を同時に走らせ、両方完了後に Phase 11（PDF生成）→ Phase 12 へ進む。

**ただし並列化は必須ではない。** 逐次実行でも問題ない。

---

## Phase 12: StudyGram アップロード

`~/.claude/skills/atama/scripts/upload_hoshu.py` で PDF・動画を R2 にアップロードし、DB レコード作成・生徒配信を一括実行する。

**前提条件:** `~/studygram/.env` に以下が設定済みであること:
- `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` — Supabase REST API 認証
- `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` — R2 直接アクセス
- `boto3` がインストール済み（未インストールなら `pip3 install boto3 --break-system-packages`）

**Edge Function（hoshu-upload, hoshu-video-upload）は CLI から使えない（admin JWT 必須）。このスクリプトは R2 直接アップロード + Supabase REST API で動作する。**

#### 新規作成 + 生徒に配信

```bash
python3 ~/.claude/skills/atama/scripts/upload_hoshu.py \
  --student "鈴木 愛莉" \
  --title "【補習】おうぎ形の応用" \
  --subject "中学数学" \
  --problem /tmp/hoshu_material/{単元名}_補習プリント.pdf \
  --answer  /tmp/hoshu_material/{単元名}_補習プリント_解答.pdf \
  --video   /tmp/hoshu_material/{単元名}_video_final.mp4
```

処理内容:
1. 生徒名で `app_users` を検索（name, atama_student_name, ilike で柔軟マッチ）
2. PDF 2本 + 動画を R2 にアップロード（`prints/{uuid}/problem.pdf` 等）
3. `hoshu_prints` に DB レコード作成
4. `hoshu_print_assignments` に配信レコード作成

#### 既存プリントの差し替え

```bash
python3 ~/.claude/skills/atama/scripts/upload_hoshu.py \
  --replace {PRINT_ID} \
  --problem /tmp/hoshu_material/{単元名}_補習プリント.pdf \
  --answer  /tmp/hoshu_material/{単元名}_補習プリント_解答.pdf \
  --video   /tmp/hoshu_material/{単元名}_video_final.mp4
```

- 既存の R2 ファイルを上書きし、DB のサイズカラムを更新する
- `--video` を省略すれば PDF のみ差し替え

#### 動画なしの場合

`--video` を省略すれば PDF のみアップロードされる。

#### アップロード後のクリーンアップ

```bash
rm -rf /tmp/hoshu_material/
```

#### 結果報告
- **成功時（動画あり）**: 「プリント『【補習】{単元名}』と解説動画を {生徒名} のプリント棚に収納しました」
- **成功時（動画なし）**: 「プリント『【補習】{単元名}』を {生徒名} のプリント棚に収納しました」
- **エラー時**: エラー内容を表示し、ファイルパスを案内する

---

## SPA 操作のルール

### クリック方法の使い分け
| 操作 | 方法 | 理由 |
|------|------|------|
| タブ切替（全員、単元進捗など） | `evaluate_script` で `el.click()` | 同一ページ内の切替は JS クリックで動く |
| 教科選択メニューの項目選択 | `take_snapshot` → `click(uid)` | `evaluate_script` は不安定。uid クリック推奨 |
| **生徒行のクリック（ページ遷移）** | **`take_snapshot` → `click(uid)`** | **Angular ルーター遷移は実マウスイベントが必要** |
| 教科セレクタボタンを開く | `take_snapshot` → `click(uid)` | ボタン要素は uid クリックが確実 |
| 学習履歴サブタブ切替 | `take_snapshot` → `click(uid)` | 「学習タイムライン」「単元ごとの学習状況」の切替 |
| 単元の展開行（詳細表示） | `take_snapshot` → `click(uid)` | 単元行クリックで詳細行が展開される |
| 詳細行のクリック（モーダル表示） | `take_snapshot` → `click(uid)` | 演習/講義の詳細行→問題リストモーダル |
| モーダルの「閉じる」ボタン | `take_snapshot` → `click(uid)` または `evaluate_script` | uid 無効時は JS フォールバック |

### 教科切替の手順（効率的な方法）
1. 教科セレクタボタンの uid を `take_snapshot` で取得し、`click(uid)` で開く。
2. 教科選択メニューが表示されたら、`take_snapshot` で教科名の uid を取得し、`click(uid)` でクリックする。
3. 切替後に `take_snapshot` で新しい教科の単元一覧を取得する。
4. 次の教科に切り替える際は、手順1に戻る（教科セレクタボタンの uid は変わらない）。

### データ取得方法
| 目的 | 方法 |
|------|------|
| 画面の視覚確認 | `take_screenshot` |
| テキストデータ一括取得 | `take_snapshot(filePath=...)` → `Grep` で検索 |
| API レスポンス取得 | `list_network_requests` → `get_network_request(reqid)` |
| DOM 直接検索 | `evaluate_script` |

**重要: 生徒詳細ページ以降の `take_snapshot` は必ず `filePath` パラメータを指定すること。**
- インライン取得するとトークン上限（50,000文字）を超えてエラーになる。
- `filePath` で保存されるファイルはプレーンテキスト形式（JSON ではない）。
- 保存後は `Grep` ツールで必要な情報を検索するのが最も効率的。

### UID の注意事項
- **ページ遷移後は全 UID が無効になる。** 生徒一覧→生徒詳細、または生徒詳細→生徒一覧に遷移した後は、必ず `take_snapshot` を再取得して新しい uid を使うこと。
- モーダルを閉じた後も、モーダル内で取得した uid は無効になる場合がある。操作前に `take_snapshot` を取り直す。

### つまずき検出方法
- snapshot 内で `StaticText "つまずき"` を探す。
- 旧方式の「正解数 < 不正解数」は不正確。atama+ が内部判定した「つまずき」マークを直接探す。
- つまずきマークは単元行に付与される（レベル表示の近く）。

## API エンドポイント（参考）
- 組織ID: `5566`
- 生徒一覧: `GET /v3/organizations/5566/organization_users/?sort=last_seen&limit=300&include_session_summary=true&include_personal_info=true&include_study_stats=true`
- 認証ヘッダ: `Authorization: ATAMA-SessionToken {token}`（ネットワークリクエストから取得可能）

## 注意事項
- **claude-in-chrome は使わない**。chrome-devtools MCP を使う。
- 各フェーズの間でユーザーに確認を取ること
- Ionic の `ion-select` はプログラム操作が困難。ポップオーバーが開いた後にテキスト要素をクリックする。
- 高校生の場合、中学教科（「中学数学」「中学英語」等）はスキップする。
