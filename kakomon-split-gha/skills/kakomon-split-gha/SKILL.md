---
name: kakomon-split-gha
description: >
  大問分割（Generate Kakomon）を GitHub Actions で実行し、完了まで監視するワークフロー。
  GHA は --skip-tags で実行されるため、GHA 完了後に Sonnet でトピックタグを新規付与する。
  「大問分割」「GHAで分割」「splitをGHAで」「数学を分割して」等で発火。
user_invocable: true
---

# 大問分割 GHA ワークフロー

## 概要

kakomon-generator の大問分割パイプライン（Phase 1〜5）を GitHub Actions で実行する。
ローカルの Chromebook（RAM 2.6GB）では Gemini API 呼び出し＋画像処理がメモリ不足になりがちなため、
GHA の ubuntu-latest（7GB RAM）で実行し、ローカルからは gh CLI で監視する。

GHA は --skip-tags で実行されるため、トピックタグは空の状態で完了する。
GHA 完了後、3-tier パイプライン（Tagger[Sonnet] → Auditor[Sonnet] → Opus Judge[low-confidence のみ]）でトピックタグを新規付与する。

## Hard Gates

1. **プロジェクトルート**: `/home/stsrjkt/kakomon-generator`
2. **gh 認証**: `~/.config/gh/hosts.yml` に GitHub トークンが必要。`gh auth status` で確認
3. **リポジトリ**: `stsrjkt-bit/kakomon-generator`
4. **ワークフローファイル**: `.github/workflows/generate.yml`
5. **ビルドが最新であること**: ワークフローは `npm run build` → `node dist/index.js` を実行する。ローカルの変更が push されていなければ古いコードで動く。必ず Phase 1 で確認
6. **R2 に problem.pdf が存在すること**: ワークフローは R2 から `{university}/{year}/{subject}/{exam_type}/problem.pdf` をダウンロードする。なければジョブ失敗
7. **解答PDF (answer.pdf) は必須ではない**: answer.pdf が R2 に無くても GHA は正常に動く（Phase 4 をスキップし、問題の切り出し+タグ付けのみ実行）。計画時に「解答なし＝スキップ」としてはならない。問題PDFのみの大学も分割対象に含めること

## Phase 1: 事前確認

### 1a. パラメータ確認

ユーザーから以下を確認する（不足があれば質問）:

| パラメータ | 必須 | 説明 | 例 |
|-----------|------|------|-----|
| mode | Yes | 実行モード | single, batch, scan, list |
| university | single時 | 大学ID | akita |
| universities | batch/scan時 | カンマ区切り大学リスト | akita,yamanashi,okayama |
| subject | Yes | 科目名（英語キー） | math, physics, chemistry |
| year | single/batch時 | 年度 | 2025 |
| exam_type | single/batch時 | 試験種別 | zenki, kouki, chuki, ippan |
| entries | list時 | JSON配列 | [{"university":"x","year":"y","exam_type":"z"}] |

### 1b. R2 exam_type 全量確認（漏れ防止）

対象大学×科目で、R2 に存在する **全 exam_type** を列挙してユーザーに提示する。
scan で exam_type を絞ると他の exam_type が処理されない事故が起きるため、必ず実施する。

```bash
./scripts/with-env.sh bash -c '
  export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
  export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
  aws s3 ls "s3://$R2_BUCKET_NAME/{university}/" --recursive --endpoint-url "https://$R2_ACCOUNT_ID.r2.cloudflarestorage.com" \
    | grep "{subject}" | grep "problem.pdf" | sed "s|.*{university}/||" | sort
'
```

出力例:
```
2023/math/chuki/problem.pdf
2023/math_1/zenki/problem.pdf
2023/math_2/zenki/problem.pdf
```

→ ユーザーに「zenki (math_1, math_2) と chuki (math) があります。全部処理しますか？」と確認。
**exam_type が複数ある場合、1回の scan/batch で全部カバーできないことがある。**
exam_type ごとに分けて実行するか、list モードで全エントリを指定すること。

**注意: answer.pdf の有無も確認して報告する**が、answer.pdf が無い大学も分割対象から除外しない。
GHA は answer.pdf が無ければ Phase 4（解答切り出し）をスキップし、問題の分割のみを実行する。

### 1c. ローカル変更の確認

```bash
cd /home/stsrjkt/kakomon-generator
git status --short
git log --oneline -1
git log --oneline origin/main -1
```

ローカルの main と origin/main が一致していること。差分がある場合はユーザーに push するか確認。

## Phase 2: ワークフロー起動

### single モード

```bash
gh workflow run generate.yml \
  -f mode=single \
  -f university="{university}" \
  -f subject="{subject}" \
  -f year="{year}" \
  -f exam_type="{exam_type}"
```

### batch モード

```bash
gh workflow run generate.yml \
  -f mode=batch \
  -f universities="{universities}" \
  -f subject="{subject}" \
  -f year="{year}" \
  -f exam_type="{exam_type}"
```

### scan モード（バリアント自動検出、推奨）

R2 をスキャンしてバリアント（math_rikei, math_bunkei 等）を自動発見する。
バリアント付き科目には **single/batch ではなく scan を使う**。
year と exam_type はオプションフィルタ（省略すると全年度・全試験種別）。

```bash
gh workflow run generate.yml \
  -f mode=scan \
  -f universities="{universities}" \
  -f subject="{subject}" \
  -f year="{year}" \
  -f exam_type="{exam_type}"
```

例: 大阪大学 2025 前期の数学（rikei + bunkei を自動発見）:
```bash
gh workflow run generate.yml \
  -f mode=scan \
  -f universities="osaka" \
  -f subject=math \
  -f year=2025 \
  -f exam_type=zenki
```

**注意**:
- year を省略すると全年度を処理する。既に分割済みの年度がある場合は year を指定して無駄な再実行を避けること。
- **exam_type を指定すると、他の exam_type は完全に無視される。** 例: `exam_type=zenki` を指定すると chuki は処理されない。Phase 1b で確認した全 exam_type をカバーすること。
- 複数の exam_type がある場合は **exam_type を省略**するか、**list モードで全エントリを明示的に指定**すること。
- batch モードは year が必須（空だとパスが壊れる）。複数年度×複数 exam_type は list モードを使うこと。

### list モード

```bash
gh workflow run generate.yml \
  -f mode=list \
  -f subject="{subject}" \
  -f entries='{entries_json}'
```

### 起動直後にやること（ジョブ数検証を含む）

ワークフロー起動はすぐに完了するが、run ID が即座に取得できないことがある。
5秒待ってから最新の run を取得:

```bash
sleep 5
gh run list --workflow=generate.yml --limit=1 --json databaseId,status,url,createdAt
```

取得した URL を **即座にユーザーに提示する**:

```
GitHub Actions URL: https://github.com/stsrjkt-bit/kakomon-generator/actions/runs/{run_id}
```

**scan/batch/list の場合: ジョブ数を検証する。**
ジョブが作成されるまで少し待ってから、ジョブ数が Phase 1b で確認した期待数と一致するか確認:

```bash
gh run view {run_id} --json jobs --jq '.jobs | length'
```

**期待ジョブ数 = R2 の (exam_type × 年度 × バリアント) 数。**
一致しなければワークフローの入力パラメータ（exam_type フィルタ等）を再確認する。
過去にワークフローの `default` 値が暗黙のフィルタとして作用し、kouki が全て無視された事例あり（2026-02 shiga_pref）。

## Phase 3: 監視

`gh run watch` でリアルタイム監視する:

```bash
gh run watch {run_id} --exit-status
```

**注意**: `gh run watch` はジョブ完了まで待機するコマンド。timeout は 600秒（10分）に設定。
single モードなら通常3〜8分で完了する。
batch/scan は matrix の数×3〜8分かかる。max-parallel=10 で並列実行される。

### タイムアウト時の対応

10分で終わらない場合（batch/scan の大量実行時）:

```bash
gh run view {run_id} --json status,conclusion,jobs
```

で途中経過を確認し、ユーザーに報告する。
まだ実行中なら再度 `gh run watch` するか、URL を提示して手動監視を促す。

### matrix ジョブの進捗確認

batch/scan/list モードでは複数ジョブが並列実行される:

```bash
# 全ジョブの状態一覧
gh run view {run_id} --json jobs --jq '.jobs[] | "\(.name)\t\(.status)\t\(.conclusion)"'
```

## Phase 4: 結果確認

### 成功時

```bash
gh run view {run_id} --json conclusion,jobs --jq '{conclusion, jobs: [.jobs[] | {name, conclusion}]}'
```

ユーザーに以下を報告:
- 全ジョブの成功/失敗
- 処理された大学×年度×科目の一覧
- 失敗したジョブがあればログの要約

### 4b. 未処理 document 検出（漏れ防止）

GHA 成功後、対象大学×科目の **全 documents** を DB から取得し、questions が 0 件の document がないか確認する。

```bash
./scripts/with-env.sh bash -c '
  curl -s "$SUPABASE_URL/rest/v1/kakomon_documents?university_id=eq.{university}&subject=like.*{subject}*&content_type=eq.problem&select=id,year,subject,subject_variant,exam_type" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" | jq -c ".[] | {id, year, subject, subject_variant, exam_type}"
'
```

各 document の questions 件数を確認:
```bash
./scripts/with-env.sh bash -c '
  curl -s "$SUPABASE_URL/rest/v1/kakomon_questions?document_id=eq.{doc_id}&select=id" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" | jq length
'
```

**questions が 0 件の document があれば警告し、追加の GHA 実行を提案する。**
よくある原因:
- scan で exam_type を絞ったため他の exam_type が未処理
- batch で year 未指定でパスが壊れた
- GHA が新しい document を別の subject 名（日本語）で作成し、元の document が残った

### 失敗時

失敗したジョブのログを取得:

```bash
# 失敗ジョブの特定
gh run view {run_id} --json jobs --jq '.jobs[] | select(.conclusion == "failure") | .name'

# ログ取得（末尾50行）
gh run view {run_id} --log-failed 2>&1 | tail -50
```

よくある失敗原因:
- **R2 に PDF がない**: `fatal error: An error occurred (404)` → 対象の PDF を先に R2 にアップロードする必要あり
- **Gemini API エラー**: `429 Too Many Requests` → rate limit。時間をおいて再実行
- **Gemini 分類失敗**: JSON パースエラー → Phase 1 (detect) の Gemini レスポンスが壊れた。再実行で直ることが多い
- **1ページ answer PDF でページ範囲エラー**: `Wrong page range given: the first page (N) can not be after the last page (1)` → 解答PDFが「出題の意図」等で1ページしかない場合、Gemini が存在しないページ番号を返す。**再実行で直る非決定的エラー**。list モードで失敗エントリのみ再実行するのが効率的
- **npm ci 失敗**: lockfile 不整合 → ローカルで `npm install` → push

失敗原因を報告し、対処方法を提案する。

## Phase 5: 3-tier タグ付け（トピックタグ新規付与）

GHA は --skip-tags で実行されるため、トピックタグは空の状態で完了する。
Phase 5 では 3-tier パイプライン（Tagger → Auditor → Opus Judge）でトピックタグを新規付与する。
**API ではなく Task tool (model: sonnet/opus) を使う**（サブスク範囲内）。

### 5a. データ収集

処理された各 document について、kakomon_questions と切り出し画像を取得する:

```bash
# document_id の特定
./scripts/with-env.sh bash -c '
  curl -s "$SUPABASE_URL/rest/v1/kakomon_documents?university_id=eq.{university}&subject=eq.{subject_key}&exam_type=eq.{exam_type}&year=eq.{year}&content_type=eq.problem&select=id,subject_variant,pdf_storage_path" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" | jq .
'

# questions 取得
./scripts/with-env.sh bash -c '
  curl -s "$SUPABASE_URL/rest/v1/kakomon_questions?document_id=eq.{doc_id}&select=id,question_number,question_label,topic_tags,split_image_path&order=question_number" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" | jq .
'

# 切り出し画像を R2 からダウンロード
VERIFY_DIR="/tmp/{university}-{subject}-verify"
mkdir -p "$VERIFY_DIR"
./scripts/with-env.sh npx tsx scripts/download-r2.ts \
  --prefix "{university}/{year}/{subject_key}/{exam_type}/q" \
  --out-dir "$VERIFY_DIR"
```

### 5b. 3-tier パイプライン（Tagger → Auditor → Opus Judge）

**3段階パイプラインで精度と再現率を両立する（F1=0.909 実証済み）。**
コスト: Task tool (model: sonnet) × 2段階 + Task tool (model: opus) × low-confidence のみ。全てサブスク範囲内。

| 役割 | モデル | 対象 | 目的 |
|------|--------|------|------|
| Tagger | Sonnet | 全問 | 初回タグ付け |
| Auditor | Sonnet | 全問 | 過不足チェック＋confidence判定 |
| Opus Judge | Opus | low-confidence のみ | 最終裁定 |

#### Step 1: Tagger（バッチタグ付け）

10〜15問をバッチにまとめて Task tool (model: sonnet) を並列起動する。
1メッセージで全バッチを同時に起動すること（直列にしない）。
最大3〜4バッチ並列。40問なら 13+13+14 の3バッチが目安。

Tagger プロンプトテンプレート:

```
あなたは大学入試の{subject}問題のトピック付けを行う専門家です。

## 問題画像
以下の画像を全て Read tool で読んでください:
{image_path_list}

## タグ付けタスク（各問題について）
1. 画像の問題内容を確認する
2. 各小問を確認し、**問題文が実際に問うているテーマ** を特定する
3. 問題の「核心テーマ」となるタグを選ぶ
   - 核心 = その問題固有のテーマ。なければ別の問題になる
   - 補助 = 汎用的な計算道具。なくても問題の個性は変わらない
   - 判断基準:「何の問題？」と聞かれて答えに含まれるか

### 核心 vs 補助の判定例（重要）
- 接線を求めてから面積を計算 → 核心は「面積」、接線は補助
- サイクロイドの回転体の体積 → 核心は「媒介変数」「回転体の体積」、微分計算は補助
- 確率漸化式を立てて解く → 核心は「確率漸化式」、漸化式の解法は補助
- グラフを描いて面積を求める → 核心は「面積」、増減表・凹凸は補助（凹凸を*問う*小問があれば核心）

### オムニバス型問題（独立小問の集合）への注意
(1)極限 (2)逆関数 (3)ベクトル (4)回転体体積 のように、**完全に独立した分野の小問が4つ以上並ぶ**問題がある。
この場合、各小問を独立に分類し、全ての核心テーマをタグに含めること。
「1問なのにタグが多すぎる」と感じても削らない。小問ごとに異なる分野なら全部入れる。
マスターリストに合うタグがない小問は、無理にタグを付けずスキップしてよい（Auditor/Opus に委ねる）。

### よくある誤付与パターン（避けること）
- 「凹凸と変曲点」: 凹凸を*問う小問*がない限り付けない（グラフ描画の準備で使うだけなら補助）
- 「反復試行の確率」: nCr × p^r × q^(n-r) の公式を*直接適用*する問題にのみ付ける。復元抽出＝反復試行ではない
- 「第2次導関数」: 凹凸タグと重複しやすい。凹凸タグがあれば不要
- 「導関数の定義」: lim定義から求める問題にのみ付ける。普通の微分計算には付けない
- 「無理関数の極限（有理化）」: 有理化を用いる*無理関数*の極限にのみ付ける。有理関数の0/0不定形極限には付けない（滋賀県立大2024で誤付与）

**重要**: 証明手法（背理法、数学的帰納法等）や幾何的性質（凹凸と変曲点、回転体の体積等）は、
問題で明示的に問われていれば核心テーマに含めること。

4. マスターリストから該当する5階層パスを選ぶ

## マスターリスト（抜粋: {subject}）
{該当科目のトピック全リスト}

## 出力
全問をまとめた JSON 配列を1つの json コードブロックで出力すること:
```json
[
  {"question_id": "{id}", "question_label": "{label}", "topic_tags": ["5階層フルパス"]}
]
```
```

#### Step 2: Auditor（監査・修正）

全 Tagger が完了したら、結果を集約して Auditor を起動する。
Auditor も同じバッチサイズ（10〜15問）で並列起動する。

Auditor プロンプトテンプレート:

```
あなたは大学入試の{subject}問題のトピックタグの監査役です。
別の専門家（Tagger）が付けたタグに「過不足」がないかチェックし、最終タグを決定してください。

## Tagger の出力
{tagger_output_json}

## 問題画像
以下の画像を全て Read tool で読んでください:
{image_path_list}

## 監査基準

### 削除すべきタグ（過剰）
- 「補助テーマ」= 汎用的な計算道具。なくても問題の個性は変わらない
  - 例: 合成関数の微分、増減表、第2次導関数（それ自体が問題の主題でない場合）

### 追加すべきタグ（不足）
- 「核心テーマ」= その問題固有のテーマ。なければ別の問題になる
- **特に見逃しやすいもの**:
  - 証明手法（背理法、数学的帰納法）→ 証明が問題の設問として明示されていれば核心
  - 幾何的性質（凹凸と変曲点）→ 変曲点を明示的に求める設問があれば核心
  - 体積の具体手法（回転体の体積、バウムクーヘン積分）→ 片方だけでなく両方付ける
  - 定積分と不等式 → 不等式の証明に定積分が使われていれば核心

### 判定のコツ
- 問題の各小問を確認し、「この小問は何を問うているか？」を考える
- Tagger が落としがちなのは「証明系タグ」と「幾何的性質タグ」
- Tagger が過剰に付けがちなのは「計算道具系タグ」（指数関数の微分、合成関数の微分等）

## マスターリスト（抜粋: {subject}）
{該当科目のトピック全リスト}

## 出力（JSON のみ）
各問題について、変更の有無・理由・確信度・最終タグを出力:
```json
[
  {
    "question_id": "{id}",
    "question_label": "{label}",
    "confidence": "high または low",
    "uncertainty": "(low時のみ) 迷いの理由を1文で",
    "changes": "+追加タグ / -削除タグ / なし",
    "reason": "変更理由（1文）",
    "final_tags": ["最終タグリスト（5階層フルパス）"]
  }
]
```

**confidence 判定基準:**
- `high`: タグの選択に迷いがない。核心テーマが明確
- `low`: 分類の境界が曖昧、マスターリストに適切なタグがない、複数分野にまたがる等
```

#### 効果（holdout + 実地検証済み）

| 方式 | Precision | Recall | F1 |
|---|---|---|---|
| 3-tier (Tagger+Auditor+Opus) | 1.000 | 0.833 | **0.909** |
| Tagger+Auditor (2-tier) | 1.000 | 0.833 | **0.909** |
| Tagger単体 | 0.900 | 0.750 | 0.818 |
| Original DB（GHA Gemini） | 0.643 | 0.750 | 0.692 |

未知の5問（kobe + osaka_metro）で検証。Opus は Auditor の non-deterministic な品質低下時のセーフティネットとして機能する。
広島大学28問の実地テストで、Opus は6問に介入し5問で実質改善（帰納法の誤判定修正、軌跡タグ追加等）。

#### 実地テスト結果（中国地方5大学）

| 大学 | 問題数 | Opus介入率 | Tagger重大エラー | ギャップ |
|------|--------|-----------|----------------|---------|
| 広島 | 28q | 21% (6/28) | 0 | 0 |
| 鳥取 | 48q | ~5% | 0 | 0 |
| 島根 | 49q | 31% (15/49) | 1件（空間ベクトルを微積分と誤判定） | 0 |
| 滋賀県立 | 40q | 10% (4/40) | 0 | 0 |

**Tagger の重大エラー事例（島根）**: `shimane_2022_math_hs_bs_zenki_q3` を「接線の方程式 + 1/12公式」とタグ付けしたが、
実際の問題画像は3D四面体（空間座標 + 空間ベクトルの内積）だった。Auditor が画像を確認して修正。
→ **Auditor の画像確認は省略不可。Tagger 結果をそのまま信頼してはならない。**

#### Step 3: Opus Judge（低確信度の最終裁定）

Auditor の結果から `confidence: "low"` の問題だけを抽出し、各問題に対して Task tool (model: opus) を並列起動する。
`confidence: "high"` の問題はそのまま Auditor の `final_tags` を採用する。

Opus Judge プロンプトテンプレート:

```
あなたは大学入試数学のトピックタグ判定における最終審判役（Opus Judge）です。
Auditor（Sonnet）が「確信度が低い」と判定した問題について、画像を確認し最終タグを決定してください。

## 問題
Read tool で以下の画像を確認してください:
{image_path}

## Auditor の判定
- question_id: {id}
- question_label: {label}
- Auditor付与タグ: {auditor_final_tags}
- confidence: low
- uncertainty: {uncertainty_reason}

## 旧DBタグ（参考）
{old_db_tags}

## タグ選択ルール
- 「核心テーマ」= その問題固有のテーマ。なければ別の問題になる
- 「補助テーマ」= 汎用的な計算道具。なくても問題の個性は変わらない → 含めない
- 判断基準:「何の問題？」と聞かれて答えに含まれるか

## マスターリスト（関連分野の抜粋）
{relevant_master_list_tags}

## 出力（JSON のみ、余計な説明不要）
{
  "question_id": "{id}",
  "ruling": "Auditor の判定を支持 / Auditor のタグを修正",
  "reason": "判断理由を1-2文で",
  "final_tags": ["最終タグリスト（5階層フルパス）"]
}
```

**注意: Opus もマスターリスト外のタグを発明する。** 広島大学28問で4件発生（うち3件はマスターリスト欠落、1件は表記揺れ）。
Opus の結果も必ず `--dry-run` でバリデーションすること。発明されたタグの対処:
- **表記揺れ**（括弧の有無等）: マスターリストの正確なパスに修正
- **マスターリスト欠落**: 5e の手順でユーザーに報告し、追加を検討
- **該当タグなし**: その問題のタグから除外し、最も近い既存タグで代替

### 5c. 結果の集約と DB 書き込み

**high-confidence → Auditor の `final_tags`、low-confidence → Opus Judge の `final_tags` を最終結果として使う。**
Tagger の出力は中間結果であり DB に書き込まない。

結果を集約してユーザーに報告する:

| Q | 最終タグ | 決定者 | 変更 |
|---|---------|--------|------|
| 1 | ... | Auditor / Opus | +追加 / -削除 / なし |

**重要: Sonnet はマスターリストの正確なパスを知らない。** Sonnet が返したタグ名は
マスターリスト（`src/constants/topic-master.ts`）の実際のパスと微妙に異なることが多い。
例:
- Sonnet: `数学/数学Ⅲ/微分法/応用/接線・法線` → 実際: `数学/数学Ⅱ/微分法と積分法/微分/接線の方程式`
- Sonnet: `数学/数学Ⅲ/微分法/応用/関数の凹凸と変曲点` → 実際: `数学/数学Ⅲ/微分法の応用/グラフ/凹凸と変曲点`
- Sonnet: `数学/数学Ⅲ/極限/関数の極限/eの定義と極限` → 実際: `数学/数学Ⅲ/極限/関数の極限/eの定義`

**Auditor の結果を JSON にまとめた後、必ず `--dry-run` でバリデーションし、
SKIP されたタグは `grep` でマスターリストの正確なパスを確認して修正すること。**

### 5d. batch-update-tags.ts で DB 書き込み

`scripts/batch-update-tags.ts` を使う（マスターリスト検証付き）:

```bash
# 1. JSON ファイルを作成（形式は下記）
# [{"question_id":"uuid","question_label":"2023 Q1","topic_tags":["5階層パス"]}]

# 2. dry-run でバリデーション
./scripts/with-env.sh npx tsx scripts/batch-update-tags.ts tags.json --dry-run

# 3. SKIP が 0 になったら本番実行
./scripts/with-env.sh npx tsx scripts/batch-update-tags.ts tags.json
```

**curl による手動 PATCH は使わない。** batch-update-tags.ts がマスターリスト検証を行うため安全。

### 5e. マスターリスト欠落タグの追加

Sonnet/Opus が推奨したタグがマスターリストに存在しない場合:

1. **報告**: 欠落タグの一覧をユーザーに提示する
2. **ユーザー承認**: 追加してよいか確認する
3. **正本(kakomon-manager)に追加**: `~/kakomon-manager/lib/constants/topic-master.ts` のツリーに追記
   - 5階層（科目/分野/単元/サブ単元/トピック）を厳守
   - 同じサブ単元にすでに類似タグがないか確認（重複防止）
   - kakomon-manager をコミット＋push
4. **同期**: kakomon-generator で同期スクリプトを実行
   ```bash
   cd /home/stsrjkt/kakomon-generator
   npx tsx scripts/sync-topic-master.ts
   ```
5. **ビルド確認**: `npm run build` で型チェック通過を確認
6. **コミット**: kakomon-generator もコミット＋push（他の変更と混ぜない）

**重要**: タグの追加・修正は必ず kakomon-manager 側で行う（正本）。
kakomon-generator の `src/constants/topic-master.ts` は自動生成ファイルなので直接編集しない。

よくある欠落パターン:
- **確率漸化式**: `数学/数学A/場合の数と確率/確率/確率漸化式`
- **連立漸化式**: `数学/数学B/数列/漸化式/連立漸化式`
- **定積分と不等式**: `数学/数学Ⅲ/積分法/定積分/定積分と不等式`
- **条件つき確率の定義と計算**: `数学/数学A/場合の数と確率/条件つき確率/条件つき確率の定義と計算`（P(A|B)の直接計算。ベイズとくじ引きしかない）
- **虚数解（共役な複素数解）**: `数学/数学Ⅱ/複素数と方程式/高次方程式/虚数解（共役な複素数解）`（x³=1のω専用タグしかない）

### 5f. 一時ファイルの削除

検証完了後、ダウンロードした画像を削除する:

```bash
rm -rf /tmp/{university}-{subject}-verify
```

**ローカルに問題画像を蓄積しない。** R2 が正本であり、検証のたびに一時DLして終わったら消す。

## Phase 6: リタグ（既存タグの品質改善）

既にタグ付け済みの questions について、タグの質が低い（平均タグ数が少ない、誤タグがある等）場合に再タグ付けする。
Phase 5 と同じ Sonnet バッチ方式を使うが、対象の選定プロセスが異なる。

### 6a. 品質調査（大学別タグ平均）

対象地方 or 全体の大学別タグ平均を算出し、低品質大学を特定する:

```bash
./scripts/with-env.sh python3 << 'PYEOF'
import json, os, urllib.request
url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

unis = ["{university_list}"]  # 対象大学リスト
for uni in unis:
    req = urllib.request.Request(
        f"{url}/rest/v1/kakomon_documents?university_id=eq.{uni}&subject=like.*{{subject}}*&content_type=eq.problem&select=id",
        headers={"apikey": key, "Authorization": f"Bearer {key}"})
    docs = json.loads(urllib.request.urlopen(req).read())
    total_q, total_tags = 0, 0
    for d in docs:
        req2 = urllib.request.Request(
            f"{url}/rest/v1/kakomon_questions?document_id=eq.{d['id']}&select=id,topic_tags",
            headers={"apikey": key, "Authorization": f"Bearer {key}"})
        qs = json.loads(urllib.request.urlopen(req2).read())
        total_q += len(qs)
        for q in qs: total_tags += len(q.get("topic_tags") or [])
    avg = f"{total_tags/total_q:.1f}" if total_q > 0 else "N/A"
    print(f"{uni:20s}: {total_q:3d}q, avg {avg}")
PYEOF
```

**目安**: 平均 2.0 未満の大学はリタグ候補。

### 6b. リタグ実行

Phase 5a〜5f と同じ 3-tier パイプライン（Tagger→Auditor→Opus Judge）で実行する。対象が「全 questions」ではなく「特定大学の questions」になるだけ。

### 6c. リタグ前後の比較

```
リタグ前: wakayama_med avg 1.6, kyoto avg 1.7
リタグ後: wakayama_med avg 3.6, kyoto avg 2.8
```

リタグ後は avg 2.5 以上を目標とする。

## Phase 7: 地方PDCA（地方単位の一括リタグ）

「中国地方の数学をやって」「関東地方の物理をタグ付けして」等で発火する。
**地方を指定されたら、全大学を1つずつ処理して完走する。途中で承認を求めない。**

### 7a. 対象大学のリストアップ

指定地方に属する大学をDBから取得し、**問題数の少ない順**にソートする:

```bash
export $(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' .env | xargs)

# 地方の大学リスト（例: 中国地方）
UNIS="hiroshima,okayama,yamaguchi,tottori,shimane"

for uni in $(echo $UNIS | tr ',' '\n'); do
  count=$(curl -s "${SUPABASE_URL}/rest/v1/kakomon_questions?document_id=in.($(
    curl -s "${SUPABASE_URL}/rest/v1/kakomon_documents?university_id=eq.${uni}&subject=like.${SUBJECT}*&content_type=eq.problem&select=id" \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      | python3 -c "import json,sys;print(','.join(d['id'] for d in json.loads(sys.stdin.read())))"
  ))&select=id" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" | python3 -c "import json,sys;print(len(json.loads(sys.stdin.read())))")
  echo "${uni} ${count}q"
done | sort -t' ' -k2 -n
```

既にリタグ済みの大学は**スキップ**する（直前のPDCAセッションで完了したもの等）。
ユーザーに対象大学リストを提示し、処理順を確認してから開始する。

### 7b. 1大学のPDCAサイクル

各大学について以下を**自動で**実行する:

```
Plan:  DB から question 一覧取得 + R2 から画像ダウンロード
Do:    Tagger[Sonnet] → Auditor[Sonnet] → Opus Judge[low-confidence のみ]
Check: 全タグをマスターリストでバリデーション
Act:   DB書き込み + マスターリストギャップがあれば kakomon-manager に追加 → sync
```

#### 手順詳細

1. **画像取得**: 対象大学の全math問題画像をR2からダウンロード
   ```bash
   mkdir -p /tmp/${uni}-pdca/images
   export $(grep -E '^(R2_ACCOUNT_ID|R2_ACCESS_KEY_ID|R2_SECRET_ACCESS_KEY|R2_BUCKET_NAME)=' .env | xargs)
   endpoint="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
   # R2 の AWS CLI は R2_* → AWS_* のマッピングが必要
   AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
     aws s3 ls "s3://${R2_BUCKET_NAME}/${uni}/" --endpoint-url "$endpoint" --recursive \
     | grep -E 'math.*q[0-9]+\.png' | grep -v answer | awk '{print $4}' \
     | while read path; do
         fname=$(echo "$path" | sed 's/\//_/g')
         AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
           aws s3 cp "s3://${R2_BUCKET_NAME}/${path}" "/tmp/${uni}-pdca/images/${fname}" \
           --endpoint-url "$endpoint" --quiet
       done
   ```
   **注意**: `download-r2.ts` は環境によって動かないことがある。AWS CLI 直接が確実。

2. **Tagger**: **年度単位**でバッチを切り、Task tool (model:sonnet) を**並列**起動
   - 年度でバッチを切ると同一年度の問題間で文脈を共有でき精度が上がる
   - 例: 2022(14q), 2023(11q), 2024(14q), 2025(10q) → 4並列
   - **バリアント共有問題の検出**: 画像ファイルが同一（hs_bs q1 = sorigo_zaiene q1 等）なら、
     Tagger には一方のみ含め、もう一方は同一タグをコピーする（島根で実証: 同一問題を別々に処理して無駄だった）

3. **Auditor**: Tagger結果をまとめて同じ年度バッチで並列起動
   - `confidence: low` の問題を特定
   - Auditor の low-confidence 率は 20-30% が正常（島根: 31%, 広島: 21%）

4. **Opus Judge**: low-confidence の問題を Task tool (model:opus) で起動
   - **5問以下**: 1つのOpusエージェントにバッチ投入してOK
   - **6問以上**: 5問ずつに分割して複数Opusを並列起動（注意力の希釈を防ぐ）
   - 島根で15件を1 Opus に投げたが、後半の問題への注意が不十分だった可能性あり
   - なければスキップ

5. **バリデーション**: 全タグをマスターリストに対して検証
   ```python
   # 100% valid を確認してから DB 書き込み
   ```

   **5b. バリアント共有問題の整合性チェック（必須）**:
   同一問題が複数バリアントに存在する場合（hs_bs q1 = sorigo_zaiene q1 等）、
   全バリアントで**同一タグ**が付いていることを確認する。
   不一致があれば、画像を比較して本当に同一問題か確認し、同一ならタグを統一する。
   ```python
   # 画像ファイル名からバリアント部分を除去してグループ化
   # 例: shimane_2025_math_hs_bs_zenki_q1 と shimane_2025_math_med_zenki_q1
   #   → 2025_zenki_q1 で同一グループ → タグが一致するか確認
   ```
   島根で Auditor が同一問題に異なるタグを付けた事例あり（Opus が修正したが、
   Opus がなければ整合性が壊れていた）。

6. **DB書き込み**: Supabase REST API で PATCH
   ```bash
   export $(grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY)=' .env | xargs)
   # Python で全問一括 PATCH
   ```

7. **マスターリストギャップ確認**: 使用タグに未登録タグがあれば
   - kakomon-manager の topic-master.ts に追加
   - `cd kakomon-generator && npx tsx scripts/sync-topic-master.ts`
   - **次の大学はギャップ追加後のマスターで処理される（PDCA効果）**

8. **一時ファイル削除**: `rm -rf /tmp/${uni}-pdca`
   **注意**: API 500 等でセッションが中断しても /tmp/ のファイルは残る。
   中間結果（tagger_results.txt, final_tags.json）を /tmp/${uni}-pdca/ に保存しておけば
   次セッションで途中から再開できる。

9. **サマリ出力**:
   ```
   ✓ {大学名}: {N}問更新, Opus介入{M}問, ギャップ{K}件追加
   ```

10. **次の大学へ** → 手順1に戻る（承認不要で自動進行）

### 7c. 完了報告

全大学完了後にまとめて報告:

```
## 地方PDCA完了: 中国地方 math

| 大学 | 問題数 | Opus介入 | ギャップ追加 | 状態 |
|------|--------|----------|-------------|------|
| 岡山 | 12 | 2 | 2 | ✓ |
| 山口 | 27 | 1 | 0 | ✓ |
| 鳥取 | 48 | 3 | 0 | ✓ |
| 島根 | 49 | ? | ? | ✓ |

マスター変更: +2タグ（指数関数の最大・最小（置換型）, 束縛条件をもつ2物体の運動）
```

### 7d. 地方の定義

| 地方 | 大学ID例 |
|------|----------|
| 北海道 | hokkaido, asahikawa_med, ... |
| 東北 | tohoku, akita, yamagata, ... |
| 関東 | tokyo, chiba, yokohama_national, tsukuba, ... |
| 中部 | nagoya, niigata, shizuoka, shinshu, ... |
| 近畿 | kyoto, osaka, kobe, nara_women, ... |
| 中国 | hiroshima, okayama, yamaguchi, tottori, shimane |
| 四国 | tokushima, kagawa, ehime, kochi |
| 九州 | kyushu, nagasaki, kumamoto, kagoshima, ... |

**注**: 大学IDは DB の `kakomon_universities.id` と一致させる。
地方に属する大学は DB にある分だけ処理する（DB にない大学は無視）。

## 再実行

同一パラメータで再実行する場合、`--force` フラグが既にワークフローに組み込まれているため、
既存の kakomon_questions を上書きする。Phase 2 からやり直せばよい。
Phase 5（Sonnet チェック）のみ再実行したい場合は Phase 5a から。
