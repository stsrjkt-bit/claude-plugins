---
name: kakomon-university-rebuild
description: >
  大学入試の過去問PDFを公式ページから発見し、ダウンロード、合冊PDF分割（Gemini分類+目視確認）、
  DB+R2へのingestを一大学ずつ実行するワークフロー。
  「大学のrebuild」「過去問をingest」「公式ページからPDFを取り込む」「合冊を分割」「nagasakiをやる」等で発火。
---

# University Past Exam Ingest Workflow

## Hard Gates

1. **一大学ゲート**: 常に1大学ずつ処理する。他大学のPDFに触らない
2. **作業ディレクトリ**: `rebuild-{university_id}-{YYYYMMDD}/` をプロジェクトルート直下に作成
3. **プロジェクトルート**: `/home/stsrjkt/kakomon-generator`
4. **環境変数**: 各Phase実行前に確認
   ```bash
   bash -lc 'set -a; source .env; set +a; env | grep -E "^(GEMINI_API_KEY|SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY|SUPABASE_ACCESS_TOKEN|R2_)" | cut -c1-40'
   ```
   - `SUPABASE_ACCESS_TOKEN` (sbp_...): DDL実行（ALTER TABLE等）に必要。Management API 経由でスキーマ変更を自動化する場合に使用
5. **dry-run first**: 破壊的操作（DB削除/R2削除/ingest）は必ず `--dry-run` → 確認 → `--force`
6. **対象**: 一般選抜（前期/後期/中期等）の「問題」「解答」PDFのみ。出題意図のみのPDFは対象外
7. **normalizeSubject gate**: 全 ingest スクリプトに `normalizeSubject()` が適用済み（`src/lib/normalize-subject.ts`）。`subject_id` に日本語名を渡してもENキーに自動変換される。未知の subject は例外で停止する
8. **subject_variant カラム**: `kakomon_documents.subject_variant` に variant キーが直接格納される。fixes-add.json / manual-split-plan.json の `subject_variant` がそのまま DB に書かれる
9. **subject_variant は人間が読める名前にする**: `agr`, `med`, `sci_eng`, `bunkei`, `rikei` 等の短い英語名を使う。ハッシュ値・UUID・自動生成IDを subject_variant に入れてはならない。PDFの中身やHTMLの学部名から意味のある名前を付けること
10. **answer の中身を信用するな**: 大学はいい加減。「解答」とラベルされていても出題意図や解答用紙しか入っていないことがある。逆にファイル名が「出題意図」でも中身は解答のこともある。怪しい場合はPDFの先頭ページを確認する（Phase B1.5 参照）

## CRITICAL: Subject Tuple Rule（科目の衝突防止）

**科目は `(subject_id, subject_variant)` の2単位ペアで管理する。subject_idだけで考えるな。**

### なぜこれが重要か

同じ大学・年度・試験種別で「物理」が複数存在しうる:
- 物理（医学部向け）→ `subject_id: "physics", subject_variant: "med"`
- 物理（工学部向け）→ `subject_id: "physics", subject_variant: "eng"`
- 物理（共通）→ `subject_id: "physics", subject_variant: null`

これを全部 `subject_id: "physics", subject_variant: null` にすると R2パスが衝突し、
片方だけ登録されてデータが消える。

### 実例（DB上の実データ）

```
kochi_tech: biology_di (生物 D&I学群), biology_sys_sci_info (生物 理系3学群)
kochi_tech: math_econ (数学 経マネ), math_sys_sci_info (数学 理系3学群)
kochi_tech: english_di (英語 D&I), english_econ (英語 経マネ)
fukushima:  math (数学), math_shokuno (数学 食農学類)
kumamoto:   math (数学), math_1 (数学①), math_2 (数学②)
ryukyu:     essay variants by faculty (小論文 x 多数学部)
waseda:     english_rikou (英語 理工), math_rikou (数学 理工), spatial_expression_kenchiku (空間表現 建築)
            → 11学部が独立入試。同一科目名が複数学部で存在するため全てにvariant必須
```

### ルール

1. **公式ページで同一科目名が複数行に分かれているか必ず確認する**
2. 学部・学群・コースで区別されている場合 → `subject_variant` を付与
3. variant命名: 短い英語で `"med"`, `"eng"`, `"econ"`, `"di"`, `"sys_sci_info"` 等
4. 迷ったらユーザーに確認。勝手にvariantを省略するな
5. **R2パスの一意性チェック**: fixes生成後、r2_pathに重複がないか必ず確認:
   ```bash
   jq -r '.[].r2_path' fixes-add.json | sort | uniq -d
   ```
   重複があれば subject_variant の付与漏れ

### R2パス生成式

```
subject_part = subject_variant ? `${subject_id}_${subject_variant}` : subject_id
exam_part    = exam_variant    ? `${exam_type}_${exam_variant}`     : exam_type
r2_path      = `${university_id}/${year}/${subject_part}/${exam_part}/${content_type}.pdf`
```

## Private University Notes（私立大学の注意点）

私立大学は国公立と構造が大きく異なる:

1. **マルチページ構造**: メインページ → 学部別サブページ → PDF。
   国公立のように1ページで完結しない。サブページを全て巡回する必要がある
2. **exam_type = "ippan"**: 前期/後期の区別なし、`exam_type_raw: "一般選抜"`
3. **学部ごとの独立試験**: 同一科目名（英語、数学等）が複数学部で存在 → subject_variant必須
4. **解答PDF非公開が多い**: Wasedaはマーク解答のみ外部ページで公開。answer PDFがない大学もある
5. **errataページ混入**: PDFの先頭に訂正内容ページが付くことがある（Gemini分類で `type: "other"` になる）
6. **ファイル名にコード番号**: 学部コード等がファイル名に含まれる（例: `262728_2025_ippan_eigo.pdf`）
7. **一般選抜以外のPDFも同ページに混在**: AO入試、学士編入、グローバル入試等のPDFが同じサブページにある。
   ファイル名やHTML構造で `ippan` をフィルタする
8. **削除注意**: 部分スコープ（1学部のみ等）でingestする場合、既存の他学部データを削除しないこと。
   dry-run出力で削除対象が想定範囲内か確認

## Phase A: Discovery（公式ページからPDFリンク発見）

### A1: 公式HTML取得

```bash
REBUILD_DIR=rebuild-{university_id}-{YYYYMMDD}
mkdir -p "$REBUILD_DIR"

# メインページ取得
scripts/fetch-official-html.sh "{official_url}" "$REBUILD_DIR/official.html"
```

### A2: PDFリンク抽出

```bash
# HTMLからリンク一覧を抽出
.tools/bin/pup 'a[href] json{}' < "$REBUILD_DIR/official.html" | \
  .tools/bin/jq -r '.[].href' | sort -u > "$REBUILD_DIR/hrefs.txt"

# PDFリンクのみ抽出
grep -i '\.pdf' "$REBUILD_DIR/hrefs.txt" > "$REBUILD_DIR/pdf_urls.txt" || true
```

### A3: 中間ページの探索

公式ページが年度別リンク（中間ページ）を持つ場合:
1. 中間ページURLを特定（HTMLを読んで年度別リンクを見つける）
2. 各中間ページをfetch → PDFリンク抽出
3. 全URLを `pdf_urls.txt` に統合

```bash
# 中間ページの例（年度別ページ等）
scripts/fetch-official-html.sh "{intermediate_url}" "$REBUILD_DIR/year_page.html"
.tools/bin/pup 'a[href] json{}' < "$REBUILD_DIR/year_page.html" | \
  .tools/bin/jq -r '.[].href' | grep -i '\.pdf' >> "$REBUILD_DIR/pdf_urls.txt"
sort -u -o "$REBUILD_DIR/pdf_urls.txt" "$REBUILD_DIR/pdf_urls.txt"
```

### A4: URL正規化

- 相対URLを絶対URLに変換
- 重複除去
- 入試関連以外のPDF（広報資料等）を除外

## Phase B: PDFダウンロード・合冊判定・分割

### B1: PDFダウンロード

```bash
mkdir -p "$REBUILD_DIR/pdfs"
# 各PDFをダウンロード
curl -sS -L --fail --compressed -A "Mozilla/5.0" -o "$REBUILD_DIR/pdfs/{filename}.pdf" "{url}"
```

### B1.5: 解答PDFの信頼性トリアージ

**大学は解答ラベルをいい加減に付ける。** ファイル名や公式ページで「解答」と書いてあっても、中身が出題意図や解答用紙（白紙）のことがある。逆に「出題意図」とラベルされたPDFに実質的な解答が含まれることもある。

#### いつ実行するか

以下の「怪しいパターン」に**1つでも該当**する解答PDFは、先頭ページを目視確認する:

| # | 怪しいパターン | 例 |
|---|---|---|
| 1 | ファイル名に `ito`/`intent`/`shushi`/`youshi` を含む | `sugakuito.pdf`, `R7_01sug11_ito.pdf` |
| 2 | ファイル名が問題PDFと酷似（`_a` vs `_q` 等の最小差分のみ） | 解答用紙の可能性 |
| 3 | 公式HTMLで「出題の意図」「出題意図」「解答用紙」の近くにリンクがある | テーブル行のラベルを確認 |
| 4 | 同一科目に「解答」「出題意図」「解答用紙」の3種類のPDFがある | どれが本当の解答か判別が必要 |
| 5 | ファイルサイズが極端に小さい（< 50KB） | 解答用紙（白紙フォーム）の可能性 |

**該当しない場合はスキップしてB2へ進んでよい。**

#### 確認手順

1. 対象PDFの先頭ページをPNGに変換:
```bash
/usr/bin/pdftoppm -png -r 200 -l 1 "$REBUILD_DIR/pdfs/{answer}.pdf" "$REBUILD_DIR/pdfs/{answer}_p1"
```

2. PNGを目視確認（Read tool）し、以下を判定:
   - **ヘッダーに「解答」と明記** → 本物の解答。content_type: answer でOK
   - **「出題の意図」「出題意図」と明記** → 解答ではない。content_type: answer として登録しない（fixes から除外 or `intent` として別管理）
   - **白紙フォーム（マス目、解答欄のみ）** → 解答用紙。除外する
   - **計算過程・模範解答が記載** → ヘッダーが何であれ本物の解答

3. 判定結果に基づいてPhase Cのfixes-add.jsonを調整:
   - 本物の解答 → `content_type: "answer"` で登録
   - 出題意図のみ → fixes-add.json から除外（解答なしの大学として扱う）
   - 解答用紙 → fixes-add.json から除外

#### 注意

- **全解答PDFを確認する必要はない。** 上記パターンに該当するもののみトリアージする
- 1大学で1つの年度を確認すれば、同一大学の他年度も同じ命名規則のことが多い。最初の年度で確認した結果を他年度に適用してよい
- 解答を公開していない大学（京都大学、佐賀大学等）では、出題意図のみのPDFを解答として誤登録しないよう特に注意

### B2: 合冊判定

HTMLの構造（テーブルのヘッダー、リンクテキスト）から合冊PDFを特定する。
合冊の典型例:
- 「理科（物理、化学、生物、地学）」→ 1つの問題PDF
- 「数学/理科（物理・化学）」→ 1つの問題冊子PDF

**単一科目PDF** → そのまま fixes-add.json に登録（Phase C）
**合冊PDF** → Gemini分類で分割してから manual-split-plan.json に登録

### B2.5: 理科・社会の強制分類チェック

**HTMLで単一科目と判定された場合でも、「理科」「社会」のPDFは必ず pdf_splitter.py analyze でGemini分類を実行する。**

理由: 教育大学等では「理科」「社会」を一つの科目として出題するが、実際のPDF内部は物理・化学・生物や日本史・世界史・地理等の個別科目に分かれていることが多い。HTMLのリンクテキストには個別科目が記載されないため、B2のHTML判定だけでは検出できない。

対象条件:
- HTMLで `理科` `社会` `Science` `Social Studies` 等と表記されている単一科目PDF
- B2で「合冊」と判定されなかったもの

手順:
1. 対象PDFに対して `pdf_splitter.py analyze` を実行（B3と同じコマンド）
2. 分類結果を確認:
   - **複数科目が検出された場合** → 合冊扱いに変更。B3〜B5の通常フローに合流（境界確認→分割計画生成）
   - **単一科目のみ検出された場合** → そのまま単一科目PDFとしてPhase Cへ進む（ただし subject_id は分類結果の具体的科目名を使う。`"science"` `"social_studies"` のような汎用IDは使わない）

**同一PDF重複チェック**: 教育大学等では初等(shotou)と中等(chutou)で同一の理科PDFを使い回すことがある。
variantが異なるのにPDFが同一（md5sum一致）の場合、variant無しで1エントリに統合する。
重複登録すると大問分割が2回走って無駄になる。

### B3: 合冊PDFの分割（Gemini分類）

**表紙のページ番号を自力で読んで分割するな。必ず pdf_splitter.py analyze を使え。**

表紙に「物理 p.1〜8」と書いてあっても、白紙ページの挿入等でPDFの物理ページ番号とは
一致しないことが多い。1ページずれて全科目の分割がおかしくなる事故が頻発する。

**注意: pdf_splitter.py には絶対パスを渡すこと。**
相対パスだとNode.jsサブプロセスがファイルを見つけられない場合がある。

```bash
WDIR=/home/stsrjkt/kakomon-generator
SPLITTER=$HOME/.claude/skills/pdf-splitter/scripts/pdf_splitter.py

# Step 1: Gemini分類（全ページのtype/subject判定）
bash -lc "set -a; source .env; set +a; python3 \
  $SPLITTER \
  analyze '$WDIR/$REBUILD_DIR/pdfs/{bundled}.pdf' \
  --json '$WDIR/$REBUILD_DIR/classification_{stem}.json'"

# Step 2: 境界ページのPNG生成（目視確認用）
python3 $SPLITTER \
  review "$WDIR/$REBUILD_DIR/pdfs/{bundled}.pdf" \
  --classification "$WDIR/$REBUILD_DIR/classification_{stem}.json" \
  -o "$WDIR/$REBUILD_DIR/boundary_review/{stem}/"
```

分類結果の `subjects` セクションで `problem_pages` を確認。
`answer_sheet` や `other`（errataなど）のページは分割対象外にする。

### B4: 境界の目視確認（Human-in-the-loop）

境界候補ページのPNGを Chrome DevTools MCP で1枚ずつ確認:

```
navigate_page → file:///absolute/path/to/boundary_review/{stem}/page_NNN.png
take_screenshot → ユーザーに提示
```

確認ポイント:
- 分類（type/subject）は正しいか？
- 科目の切り替わり位置は正しいか？
- 白紙ページは正しくblankとして分類されているか？

ユーザーが修正指示した場合 → classification JSONの該当ページを編集

### B5: 分割計画生成

確認済みのclassification JSONからcontiguous page rangeを抽出し、`manual-split-plan.json` を生成。
分割はPhase Eで `manual-split-upload.ts` が `qpdf` を使って実行する。

## Phase C: Fixes JSON生成

### fixes-add.json（単一科目PDF）

```json
[
  {
    "action": "add",
    "url": "https://...",
    "university_id": "{university_id}",
    "year": 2025,
    "subject_id": "physics",
    "subject_variant": null,
    "subject_raw": "物理",
    "subject_display": "物理",
    "exam_type": "zenki",
    "exam_variant": null,
    "exam_type_raw": "前期日程",
    "content_type": "problem",
    "is_bundled": false,
    "bundled_subjects": null,
    "r2_path": "{university_id}/2025/physics/zenki/problem.pdf"
  }
]
```

学部別にPDFが分かれている場合:
```json
[
  {
    "subject_id": "physics", "subject_variant": "med",
    "subject_raw": "物理（医学部）", "subject_display": "物理（医学部）",
    "r2_path": "{university_id}/2025/physics_med/zenki/problem.pdf"
  },
  {
    "subject_id": "physics", "subject_variant": "eng",
    "subject_raw": "物理（工学部）", "subject_display": "物理（工学部）",
    "r2_path": "{university_id}/2025/physics_eng/zenki/problem.pdf"
  }
]
```

### fixes-split.json（合冊PDF）

```json
[
  {
    "action": "split",
    "url": "https://...",
    "university_id": "{university_id}",
    "year": 2025,
    "exam_type": "zenki",
    "exam_variant": null,
    "exam_type_raw": "前期日程",
    "content_type": "problem",
    "bundled_subjects": ["physics", "chemistry", "biology", "earth_science"]
  }
]
```

### manual-split-plan.json（合冊の分割計画）

```json
{
  "generated_at": "2026-02-16T00:00:00Z",
  "items": [
    {
      "source_url": "https://...",
      "university_id": "{university_id}",
      "year": 2025,
      "outputs": [
        {
          "r2_path": "{university_id}/2025/physics/zenki/problem.pdf",
          "pages": "3-8",
          "subject_id": "physics",
          "subject_raw": "物理",
          "subject_display": "物理",
          "exam_type": "zenki",
          "exam_type_raw": "前期日程",
          "content_type": "problem"
        }
      ]
    }
  ]
}
```

### 生成後の必須チェック

```bash
# R2パス重複チェック（fixes-add）
.tools/bin/jq -r '.[].r2_path' "$REBUILD_DIR/fixes-add.json" | sort | uniq -d
# URL重複チェック
.tools/bin/jq -r '.[].url' "$REBUILD_DIR/fixes-add.json" | sort | uniq -d
# subject_id が英語キーであること（normalizeSubject gate が変換するが、入力時点で確認推奨）
.tools/bin/jq -r '.[].subject_id' "$REBUILD_DIR/fixes-add.json" | sort -u
# → math, chemistry 等の英語キーのみであること
# split plan出力のR2パス重複チェック
.tools/bin/jq -r '.items[].outputs[].r2_path' "$REBUILD_DIR/manual-split-plan.json" | sort | uniq -d
```

```bash
# add + split の全R2パスを結合して重複チェック
(
  .tools/bin/jq -r '.[].r2_path' "$REBUILD_DIR/fixes-add.json"
  .tools/bin/jq -r '.items[].outputs[].r2_path' "$REBUILD_DIR/manual-split-plan.json"
) | sort | uniq -d
```

いずれも出力が空であること（重複なし）を確認。

## Phase D: 既存データ削除（レガシーデータ掃除用）

**通常は不要。** ingestスクリプトはupsertなので、同じr2_pathは上書き、新しいr2_pathは追加される。

削除が必要なのは **過去に不正確なパスでアップロードされた既存データをゼロにしたい場合のみ**。
（例: variant無しでアップされたデータを、variant付きで入れ直す場合）

削除は `(university_id, year)` 単位で全消しになる。
部分的な再ingestだけなら Phase D をスキップして Phase E に進め。

**実行する場合は必ず `--dry-run` を先に実行し、削除対象を確認してからユーザーに提示する。**

```bash
# DB削除 dry-run
bash -lc 'set -a; source .env; set +a; npx tsx scripts/reset-universities-by-fixes.ts \
  --add-fixes "$REBUILD_DIR/fixes-add.json" \
  --split-fixes "$REBUILD_DIR/fixes-split.json" --dry-run'

# R2削除 dry-run
bash -lc 'set -a; source .env; set +a; npx tsx scripts/delete-r2-prefixes-by-fixes.ts \
  --add-fixes "$REBUILD_DIR/fixes-add.json" \
  --split-fixes "$REBUILD_DIR/fixes-split.json" --dry-run'
```

dry-run出力確認後、ユーザー承認を得て `--force` で実行:

```bash
bash -lc 'set -a; source .env; set +a; npx tsx scripts/reset-universities-by-fixes.ts \
  --add-fixes "$REBUILD_DIR/fixes-add.json" \
  --split-fixes "$REBUILD_DIR/fixes-split.json" --force'

bash -lc 'set -a; source .env; set +a; npx tsx scripts/delete-r2-prefixes-by-fixes.ts \
  --add-fixes "$REBUILD_DIR/fixes-add.json" \
  --split-fixes "$REBUILD_DIR/fixes-split.json" --force'
```

fixes-split.json が空配列 `[]` の場合は `--split-fixes` を省略可。

## Phase E: Ingest実行

> **Note**: ingest-add と manual-split-upload の並列実行でフリーズした実績あり（北九州市立大学）。
> 順次実行を推奨。

両スクリプトとも `normalizeSubject()` gate が適用されており:
- `subject_id` が日本語名でも自動的に英語キーに変換される
- `subject_variant` が `kakomon_documents.subject_variant` カラムに直接書き込まれる
- 未知の subject は例外で停止する（間違った科目名がDBに入らない）

```bash
# 単一科目PDF: 公式URLからダウンロード → R2アップロード → DB upsert
bash -lc 'set -a; source .env; set +a; npx tsx scripts/ingest-add-by-fixes.ts \
  --add-fixes "$REBUILD_DIR/fixes-add.json" --dry-run'

# 合冊PDF: 分割 → R2アップロード → DB upsert
bash -lc 'set -a; source .env; set +a; npx tsx scripts/manual-split-upload.ts \
  --plan "$REBUILD_DIR/manual-split-plan.json" --dry-run'
```

dry-run確認後、`--force` で実行。

## Phase F: Verification

```bash
# DB + R2 の存在確認
bash -lc 'set -a; source .env; set +a; npx tsx scripts/verify-fixes-db-r2.ts \
  --add-fixes "$REBUILD_DIR/fixes-add.json" \
  --split-plan "$REBUILD_DIR/manual-split-plan.json"'
```

期待される出力:
```
DB OK: N/N
R2 OK: N/N
```

全件OKでなければ、Missing行を調査して修正・再ingest。

```bash
# JA/EN + subject_variant の健全性チェック（対象大学のみ）
bash -lc 'set -a; source .env; set +a; npx tsx scripts/audit-recheck-jaen.ts \
  --report --universities {university_id}'
```

期待される出力: 全コンボ Clean（E=0, F=0）。
JA名レコードが残存している場合は `--fix --force` で修正可能。

## Phase G: Report

`$REBUILD_DIR/REPORT.md` を作成:

```markdown
# {大学名} ({university_id}) Rebuild Report

Date: {YYYY-MM-DD}
Scope: {試験種別}の問題・解答PDF
Years: {対象年度}
Official page: {公式URL}

## 分類
- 単一科目PDF (add): {N}件
- 合冊PDF (split): {N}件（合冊{N}ファイル → {N}分割出力）
- スキップ: {N}件（理由: ...）

## Fixes
- fixes-add.json: {N} entries
- fixes-split.json: {N} entries
- manual-split-plan.json: {N} items → {N} outputs

## Verification
- Expected objects: {N}
- DB OK: {N}/{N}
- R2 OK: {N}/{N}

## Notes
- {特記事項}
```

## Reference

### Exam Types

exam_typeは大学・入試制度により多様。以下は代表例であり、これに限定されない:

| exam_type | exam_type_raw | 備考 |
|----------|---------------|------|
| zenki | 前期日程 | 国公立前期 |
| kouki | 後期日程 | 国公立後期 |
| chuki | 中期日程 | 公立中期 |
| ippan | 一般選抜 | 前期/後期の区別がない場合、私立一般等 |

exam_variantで同一exam_type内の細分化に対応（例: `zenki_a`）。
未知の試験種別に遭遇したらユーザーに確認。

### Content Types

| content_type | 説明 |
|-------------|------|
| problem | 問題PDF |
| answer | 解答PDF（模範解答・解答例） |

**answer として登録してはいけないもの:**
- 出題意図 / 出題の意図（問題の狙いを説明する文書。解答ではない）
- 解答用紙（白紙の解答フォーム。受験生が記入するためのもの）
- 配点表（得点配分のみ記載）

大学はこれらを「解答」と同じ場所に並べたり、紛らわしいファイル名を付けることがある。
Phase B1.5 のトリアージで判別すること。
