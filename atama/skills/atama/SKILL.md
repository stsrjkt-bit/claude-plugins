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

Chromiumを起動し、chrome-devtools MCP経由でatama+ COACHにログイン。
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

### snapshot ルール（厳守）

- **生徒詳細ページ以降の `take_snapshot` は必ず `filePath` を指定する**
- インライン取得はトークン上限（50,000文字）を超えてエラーになる
- 保存後は `Grep` ツールで必要な情報を検索する

### UID の注意事項

- ページ遷移後は全 UID が無効。必ず `take_snapshot` を再取得する
- モーダルを閉じた後も UID は無効になる場合がある

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
- `--remote-debugging-port=9222` で chrome-devtools MCP 接続
- `--user-data-dir=~/.config/chrome-atama` でセッション永続化
- 起動後5秒待機

#### 1b. ログイン

1. `list_pages` でページ一覧を取得
2. atama+ COACH のページがあれば `select_page`。なければ `navigate_page` で `https://coach.atama.plus/` に遷移
3. `take_screenshot` でページ状態を確認

**URL判定:**
- `/user/home` → ログイン済み。Phase 2 へ
- `/public/login` → ログインフロー:

```bash
source ~/.env.atama && echo "ID=$ATAMA_ID PW_LEN=${#ATAMA_PW}"
```
`.env.atama` が存在しない場合はユーザーに手動入力を依頼。

`evaluate_script` で ID/PW を入力:
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

`take_snapshot` → ログインボタンの uid で `click(uid)`。20秒待つ。`take_screenshot` で確認。

**`/atama login` の場合はここで終了。**

### 成功条件
- [ ] `curl -s http://localhost:9222/json` が応答する
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

#### 2c. 誤答分析（モーダル確認）

1. 対象単元の行を `click(uid)` で展開
2. `take_snapshot(filePath="/tmp/hoshu_material/snapshot_detail.txt")` で詳細行を取得
3. 各セッション行の処理優先度:
   - 不正解がある行（演習・講義）→ 必ずクリック
   - アラート付きの行 → クリック
   - 0正解0不正解で(中止)かつ1分未満 → スキップ
   - 確認テスト → スキップ

**モーダルの処理手順（セッションごと）:**
1. セッション行を `click(uid)` でモーダルを開く
2. `take_snapshot(filePath="/tmp/hoshu_material/snapshot_{種別}.txt")` で問題文と正誤マークを取得
3. `take_screenshot` で ○/❌ アイコンを視覚確認
4. 記録: 各問題のテーマ・正誤・アラート内容
5. モーダル内スクロールが必要な場合: `evaluate_script` で `.inner-scroll` の scrollTop を変更
6. `take_snapshot` → 「閉じる」ボタンの uid で `click(uid)` してモーダルを閉じる
7. 次のセッションへ

### 成功条件
- [ ] 指定単元の学習データ（日付・レベル・正解数・不正解数）が取得できた
- [ ] 全セッション（演習・講義）のモーダルを開いて問題の正誤を記録した
- → Phase 3 へ

---

## Phase 3: 図形抽出 & レポート作成【スキップ厳禁】

**スキップ厳禁。** 生徒が実際に間違えた問題の具体的な図形・寸法を把握しなければ、的確な足場がけプリントは作れない。

### 入力
- Phase 2 で記録した全セッションの問題一覧と正誤
- モーダルが閉じた状態の生徒詳細ページ

### 処理

#### 3a. 図形抽出

**base64 画像直接抽出方式を使う**（スクリーンショット方式は viewport 依存で図が切れるため非推奨）。

前提: `/tmp/node_modules/ws/` が必要（なければ `cd /tmp && npm install ws`）

各セッションについて:
1. セッション行を `click(uid)` でモーダルを開く
2. `take_snapshot(filePath=...)` で問題文テキストを取得（数式の構造を把握）
3. `extract-figures.mjs` で図形画像を抽出:
   ```bash
   node ~/.claude/skills/atama/scripts/extract-figures.mjs \
     --prefix <セッション種別のプレフィックス> \
     --outdir /tmp/hoshu_material
   ```
   - 演習: `--prefix kaitentai_enshu`
   - 講義: `--prefix kaitentai_kougi`
   - スクリプトは CDP WebSocket (port 9222) でモーダル内の全 `data:image` を抽出し PNG 保存
4. `take_snapshot` → 「閉じる」ボタンの uid で `click(uid)` してモーダルを閉じる
5. 次のセッションへ

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
- [ ] 全セッションの `_summary.json` が存在する
- [ ] 図形画像が1枚以上抽出されている
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
import json, os, sys
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
- ローカルに `manim` v0.20.1, `manim-voiceover`, `sox` がインストール済み
- `~/studygram/.env` に `GEMINI_API_KEY` と `GEMINI_TTS_MODEL` が設定済み
- TTS ラッパー: `~/.claude/skills/atama/scripts/gemini_tts_service.py`

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

#### 5b. JSON → Manim スクリプト変換

```python
import sys
sys.path.insert(0, '/home/yuki/.claude/skills/atama/scripts')
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

**日本語テキスト注意:**
- `Text()` には `font="Noto Sans CJK JP"` を指定
- `MathTex()` の `\text{}` 内に日本語を入れない。`Text` + `MathTex` を `VGroup().arrange(RIGHT)` で横並び

**TTS テキストルール:**
1. 分数は「分母ぶんの分子」の順（厳守）
2. 数字・数式は話し言葉で書く（`3cm` → `さんセンチ`）
3. 句読点で間をコントロール
4. 変数はカタカナ（x→エックス）

#### 5c. ローカルレンダリング

```bash
cd /tmp/hoshu_material && manim render -qm --format mp4 {単元名}_video.py HoshuVideo
```

#### 5d. 動画圧縮

```bash
ffmpeg -i /tmp/hoshu_material/{単元名}_video.mp4 \
  -vcodec libx264 -crf 28 -preset fast \
  -acodec aac -b:a 96k \
  /tmp/hoshu_material/{単元名}_video_final.mp4 -y
```

#### 5e. 動画品質レビュー

1. Manim スクリプトからシーン仕様書を `/tmp/hoshu_material/scene_spec.txt` に作成
2. Gemini Flash でレビュー:
   ```bash
   python3 ~/.claude/skills/atama/scripts/video_reviewer.py \
     /tmp/hoshu_material/{単元名}_video_final.mp4 \
     /tmp/hoshu_material/scene_spec.txt
   ```
3. HIGH issue → Manim 修正 → 再レンダリング → 再レビュー
4. LOW のみ / issues なし → PASS

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
| タブ切替（全員、単元進捗など） | `evaluate_script` で `el.click()` | 同一ページ内の切替は JS クリックで動く |
| 教科選択メニューの項目選択 | `take_snapshot` → `click(uid)` | uid クリック推奨 |
| **生徒行のクリック（ページ遷移）** | **`take_snapshot` → `click(uid)`** | **Angular ルーター遷移は実マウスイベントが必要** |
| 教科セレクタボタンを開く | `take_snapshot` → `click(uid)` | ボタン要素は uid クリックが確実 |
| 学習履歴サブタブ切替 | `take_snapshot` → `click(uid)` | 「学習タイムライン」「単元ごとの学習状況」の切替 |
| 単元の展開行（詳細表示） | `take_snapshot` → `click(uid)` | 単元行クリックで詳細行が展開される |
| 詳細行のクリック（モーダル表示） | `take_snapshot` → `click(uid)` | 演習/講義の詳細行→問題リストモーダル |
| モーダルの「閉じる」ボタン | `take_snapshot` → `click(uid)` または `evaluate_script` | uid 無効時は JS フォールバック |

### 教科切替の手順
1. 教科セレクタボタンの uid を `take_snapshot` で取得し、`click(uid)` で開く
2. 教科選択メニューが表示されたら、`take_snapshot` で教科名の uid を取得し `click(uid)`
3. 切替後に `take_snapshot` で新しい教科の単元一覧を取得

### データ取得方法
| 目的 | 方法 |
|------|------|
| 画面の視覚確認 | `take_screenshot` |
| テキストデータ一括取得 | `take_snapshot(filePath=...)` → `Grep` で検索 |
| API レスポンス取得 | `list_network_requests` → `get_network_request(reqid)` |
| DOM 直接検索 | `evaluate_script` |

### つまずき検出方法
- snapshot 内で `StaticText "つまずき"` を探す
- つまずきマークは単元行に付与される（レベル表示の近く）

## API エンドポイント（参考）
- 組織ID: `5566`
- 生徒一覧: `GET /v3/organizations/5566/organization_users/?sort=last_seen&limit=300&include_session_summary=true&include_personal_info=true&include_study_stats=true`
- 認証ヘッダ: `Authorization: ATAMA-SessionToken {token}`

## 注意事項
- **claude-in-chrome は使わない**。chrome-devtools MCP を使う
- Ionic の `ion-select` はプログラム操作が困難。ポップオーバーが開いた後にテキスト要素をクリック
- 高校生の場合、中学教科はスキップ
