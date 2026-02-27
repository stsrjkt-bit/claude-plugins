---
name: kakomon-subject-audit
description: >
  特定の大学×科目について、DBの過去問PDFと公式サイトの公開PDFを突合し、
  不足（バリアント漏れ・解答欠落）や不正データ（重複・誤レコード）を発見・修正するワークフロー。
  「数学の見落としチェック」「○○大学の物理を監査」「不足PDFを埋める」等で発火。
---

# Subject Audit Workflow（科目別 過去問監査+修正）

## 概要

rebuild スキルが「大学まるごと新規ingest」なのに対し、
このスキルは **既にingest済みの大学の特定科目について差分を埋める** 作業。
対象科目がDB未登録（0件）のケースも対象。その場合は全新規追加になる。

典型的な発見パターン:
- 文系数学だけ入れて理系数学（数III含む）を見落とし
- 学部別バリアントを1つの generic レコードに潰してしまった
- 解答PDFの取り忘れ
- 存在しない試験種別（後期が無い大学に後期レコード）
- subject名の表記揺れ（`数学` vs `math`）← **normalizeSubject gate により今後は発生しない**

## Hard Gates

1. **スコープを明確に**: 対象の `(university_id, subject)` を最初に確定する。複数大学を一括監査する場合は Phase 1-3 を全大学で完了してから Phase 4 にまとめて進んでよい
2. **プロジェクトルート**: `/home/stsrjkt/kakomon-generator`
3. **環境変数**: `./scripts/with-env.sh` 経由で全コマンドを実行する（`npx tsx` に限らず `node -e`, `curl` 等も）。直接 `export $(cat .env ...)` を使わない
   ```bash
   ./scripts/with-env.sh bash -c 'env | grep -E "^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY|R2_)" | cut -c1-40'
   ```
4. **dry-run first**: ingest は必ず `--dry-run` → 確認 → `--force`
5. **後期(kouki)の削除に注意**: バリアントが1種類しかない後期は generic パスのままでよい。削除しない
6. **normalizeSubject gate**: 全 ingest パスに `normalizeSubject()` が適用済み（`src/lib/normalize-subject.ts`）。日本語 subject 名は DB 書き込み時に自動的に英語キーに変換される。未知の subject は例外で停止する
7. **subject_variant カラム**: `kakomon_documents.subject_variant` に variant キー（rikei, bunkei, med 等）が格納される。R2 パスのパースは不要
8. **合冊PDFは分割必須**: `ingest-add-by-fixes.ts` はPDFをそのままアップロードする。合冊PDFには使用禁止。合冊は必ず kakomon-university-rebuild スキルの分割ワークフロー（`pdf_splitter.py` → `manual-split-upload.ts`）を使うこと
9. **Phase 進行ゲート**: 各 Phase の完了条件を全て満たしてから次に進むこと。記憶に頼らず、毎回スキルを参照して手順を確認する
10. **「軽微」禁止**: 全ての発見事項に分類 A〜G を付けること。「軽微」「メモ」「修正不要」として分類外に置くことを禁止する。判断に迷ったら分類 G（データ品質問題）に入れて対応方針を明示する

## Phase 進行チェックリスト

**各 Phase の完了後、次の Phase に進む前にこのリストを確認すること。**

### Phase 1 → Phase 2 に進む前に
- [ ] 対象科目のDBレコードを全件取得した
- [ ] `subject=science` のレコード有無を確認した（理科系科目の場合）
- [ ] `is_bundled_origin` フラグの整合性を確認した（同一バンドル由来の全科目で一致しているか）
- [ ] JA名レコードの残存チェックをした
- [ ] データ品質チェックを実施した（ハッシュvariant、NULL不整合、R2パス不一致、**variant名の年度間不統一**）
- [ ] **大問分割漏れチェック**: 各 problem document に紐づく `kakomon_questions` が 0件でないことを確認した

> **DB 0件の場合**: 上記チェックは全て N/A。Phase 2 に直行してよい。

### 大問分割漏れチェック（必須）

ingest 済みだが大問分割（kakomon-generate）が未実行の document を検出する。
解答PDFがない大学で見落としやすい（answer.pdf 不在でも問題の分割は可能）。

```bash
# 全 problem document の questions 件数を一括チェック
./scripts/with-env.sh bash -c '
  DOCS=$(curl -s "$SUPABASE_URL/rest/v1/kakomon_documents?university_id=eq.{id}&subject=like.*{subject}*&content_type=eq.problem&select=id,year,subject,exam_type" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY")
  echo "$DOCS" | jq -c ".[]" | while read -r doc; do
    did=$(echo "$doc" | jq -r .id)
    label=$(echo "$doc" | jq -r '"\(.year) \(.subject) \(.exam_type)"')
    qcount=$(curl -s "$SUPABASE_URL/rest/v1/kakomon_questions?document_id=eq.$did&select=id" \
      -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
      -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" | jq length)
    [ "$qcount" -eq 0 ] && echo "⚠ UNSPLIT: $label ($did)" || echo "  OK: $label ($qcount questions)"
  done
'
```

**questions が 0件の document があれば分類 H（大問分割漏れ）として報告し、kakomon-split-gha スキルでの分割を提案する。**

### Phase 3 → Phase 4 に進む前に
- [ ] Gap分析の分類 A〜G を全て判定した（分類外の「メモ」が残っていないこと）
- [ ] 分類 G がある場合、全件の対応方針を決めた
- [ ] 合冊PDFが含まれる場合、全科目（earth_science 含む）を確認した
- [ ] 合冊の場合: fixes-add.json ではなく manual-split-plan.json で対応することを確認した
- [ ] 個別PDFの場合のみ: fixes-add.json を作成する

### Phase 4 → Phase 5 に進む前に
- [ ] 追加したレコードの `is_bundled_origin` が正しいことをDBで確認した
- [ ] R2のファイルサイズ/ページ数が想定通りか確認した（合冊がそのまま入っていないか）
- [ ] verify-fixes-db-r2.ts を実行した

## 科目名マッピング（JA/EN）

`normalizeSubject` gate（2026-02-23導入）により、**新規 ingest では subject は必ず英語キーで格納される**。
backfill 済みのため既存データも英語キーに統一されている。
マッピング定義: `src/lib/normalize-subject.ts` の `SUBJECT_MAP_JA_TO_EN`

| 英語キー (正) | 日本語名 |
|---|---|
| math | 数学 |
| physics | 物理 |
| chemistry | 化学 |
| biology | 生物 |
| earth_science | 地学 |
| english | 英語 |
| japanese_lang | 国語 |
| essay | 小論文 |
| general | 総合問題 |
| world_history | 世界史 |
| japanese_history | 日本史 |
| geography | 地理 |
| civics | 公民 |
| info | 情報 |
| science | 理科 |

**バンドルエイリアス**: `science` → [physics, chemistry, biology, earth_science]

## Phase 1: 現状把握（DB棚卸し）

対象大学×科目の全レコードを取得する。**`query-documents.ts` を使うのが最も簡潔**:

```bash
# 全件表示（コンパクト形式）
./scripts/with-env.sh npx tsx scripts/query-documents.ts --university {id} --subject {subject_en} --compact

# バリアント一覧のみ
./scripts/with-env.sh npx tsx scripts/query-documents.ts --university {id} --subject {subject_en} --variants

# 年度別グループ表示（デフォルト）
./scripts/with-env.sh npx tsx scripts/query-documents.ts --university {id} --subject {subject_en}
```

JA名レコードの残存チェック（通常0件）:
```bash
./scripts/with-env.sh npx tsx scripts/query-documents.ts --university {id} --subject {subject_ja}
```

> **Note**: normalizeSubject gate + backfill（2026-02-23実施）により、JA名レコードは原則0件。
> 残存している場合は `audit-recheck-jaen.ts --fix --force` で一括修正可能。

### バリアント構成の確認

`subject_variant` カラムにより、バリアント構成が一目でわかる:
- `null` → generic（バリアント分けなし）
- `"rikei"` / `"bunkei"` → 理系/文系
- `"med"` / `"nursing"` 等 → 学部別

### 理科バンドルチェック

対象科目が理科系（physics, chemistry, biology, earth_science）の場合、`science` レコードも確認:

```bash
# science レコードの存在チェック
curl -s "$SUPABASE_URL/rest/v1/kakomon_documents?university_id=eq.{id}&subject=eq.science&select=id,year,subject,exam_type,content_type,pdf_storage_path&order=year,exam_type,content_type" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
```

理科レコードが存在した場合の判定:
1. 同一年に対象科目の個別レコードが**ある** → 理科レコードはバンドル誤登録の可能性（Phase 3 で分類 D として報告）
2. 同一年に個別科目レコードが**ない** → 理科レコードが唯一の情報源。Phase 3.5 でPDF内容を確認して対象科目を含むか判定

### 確認ポイント

- 年度×試験種別×content_type のマトリクスに穴がないか
- variant付きパス（`math_rikei/`）と generic パス（`math/`）が混在していないか
- `subject_variant` の値が variant 付きレコードと一致していること
- 理科バンドルレコードの有無
- **generic 重複パターン**: variant 付きレコードが揃っているのに `subject_variant=NULL` の generic レコードが残存していないか（最頻出の分類 B パターン。md5sum で variant レコードとの同一性を確認 → 一致なら generic を削除対象に）

### データ品質チェック（必須）

以下に該当するレコードは Phase 3 で **分類 G** として報告する:

1. **ハッシュvariant**: `subject_variant` が `/^[0-9a-f]{6,}$/` にマッチする（例: `3b5a79c3`）→ 意味のある名前に修正が必要
2. **NULL不整合**: `subject_variant=NULL` なのに `pdf_storage_path` に `_bunkei/`, `_rikei/`, `_med/` 等の variant 情報がある → subject_variant を設定する必要がある
3. **NULL重複**: 同一 `(year, exam_type, content_type)` で `subject_variant=NULL` のレコードが複数ある → variant が未設定のまま複数登録されている
4. **variant名の年度間不統一**: 同一科目の同種バリアントが年度によって異なる名前になっている（例: 2022=`sorigo_other`, 2024=`sorigo_zaiene`; 2024=`med_suuri`, 2025=`med`）→ `rename-variant.ts` で統一する

## Phase 2: 公式サイト突合

対象大学の公式過去問ページをフェッチし、対象科目のPDFリンクを全て抽出:

```bash
REBUILD_DIR=audit-{university_id}-{subject}-{YYYYMMDD}
mkdir -p "$REBUILD_DIR"

scripts/fetch-official-html.sh "{official_url}" "$REBUILD_DIR/official.html"

.tools/bin/pup 'a[href] json{}' < "$REBUILD_DIR/official.html" | \
  .tools/bin/jq -r '.[].href' | grep -i '{subject_keyword}' | sort -u
```

### サブページ構造の確認（重要）

**多くの大学はPDFリンクをトップページに直接置かず、年度別・日程別のサブページに分けている。**
トップページにPDFリンクが見つからない場合は、以下を確認:

1. サブページへのリンクを抽出:
```bash
.tools/bin/pup 'a[href] json{}' < "$REBUILD_DIR/official.html" | \
  .tools/bin/jq -r '.[].href' | grep -iE '(kakomon|koukai|mondai|past|R[0-9]|department)' | sort -u
```

2. 各サブページをフェッチしてPDFリンクを取得:
```bash
for page in r7_iz r7_ik r6_iz r6_ik; do
  scripts/fetch-official-html.sh "{base_url}/${page}" "$REBUILD_DIR/${page}.html"
  .tools/bin/pup 'a[href] json{}' < "$REBUILD_DIR/${page}.html" | \
    .tools/bin/jq -r '.[].href' | grep -iE '(sug|math|suugaku|\.pdf)' | sort -u
done
```

**既知のサブページ構造パターン:**
- 広島大学: `/koukai/r7_iz`（前期）, `/koukai/r7_ik`（後期）
- 島根大学: `/department/department_R07_1.html`（一般選抜）
- 山口大学: `/mondaikouhyo/zenki/`, `/mondaikouhyo/kouki/`
- 鳥取大学: 1ページに全年度（R5〜R7）まとめて掲載

**WordPress サイトのファイル名に注意:**
WordPress で同名ファイルを再アップロードすると `_1`, `_2` 等のサフィックスが自動付与される。
これはバリアント違いではなくファイル更新の連番。高知工科大学で実例あり（`r7_zenki_suugaku_1.pdf` は `r6_zenki_suugaku.pdf` の R7 版であり、別バリアントではない）。
同名で `_1` 付きと無しがある場合は md5sum で同一性を確認すること。

### cybercollege.jp サイト構造

cybercollege.jp は複数の国立大学の過去問を掲載する第三者サイト。独自の構造を持つため注意が必要。

**対象大学**: saitama（埼玉大学）, yokohama_national（横浜国立大学）, u_gakugei（東京学芸大学）

**PDFパスワード**: `略称+年度`（例: `saitama2025`, `ynu2025`, `tgu2025`）。ただし実際にはパスワード不要（Encrypted: no）の場合もある。パスワード保護の有無は `pdfinfo` で確認。

**ディレクトリ構造と列の意味（重要）**:
- `pdf/YEAR/NN.pdf` = **問題** （全大学共通）
- `ans/ans_YEAR/NN.pdf` = **解答用紙**（空欄の答案用紙）← **answer ではない！**
- `ex/ex_YEAR/NN.pdf` = **解答例**（実際の模範解答）← これが本当の answer

**大学別の公開状況**:
| 大学 | 問題 (pdf/) | 解答用紙 (ans/) | 解答例 (ex/) |
|------|-------------|-----------------|-------------|
| 埼玉大学 | ✓ | ✓（空欄） | ✗ |
| 横浜国立大学 | ✓ | ✓（見本） | ✗ |
| 東京学芸大学 | ✓ | ✓（空欄） | ✓（手書き解法） |

**罠**: img タグの `alt="解答"` と列ヘッダー「解答用紙」が矛盾する場合がある（埼玉大学で確認）。**列ヘッダーを優先**し、必ず1件ダウンロードして中身を確認すること。

**年度別サブページ**: 各大学で `index.php`（最新年度）, `2024.php`, `2023.php` のようにサブページがある。

```bash
# 年度ページを一括フェッチ
for year in 2024 2023; do
  scripts/fetch-official-html.sh "https://www.cybercollege.jp/{univ_path}/${year}.php" "$REBUILD_DIR/cyber_${year}.html"
done
```

HTML内のテーブル構造から、各PDFがどの学部・バリアント向けかを特定:

```bash
# テーブル行からPDFリンクの前後の学部名を取得
grep -B15 '{pdf_filename}' "$REBUILD_DIR/{page}.html" | grep -E '学部|学科|文系|理系'
```

### 突合チェックリスト

| チェック項目 | 方法 |
|---|---|
| バリアント数の一致 | 公式サイトの同一科目PDFの行数 = DBのvariant数 |
| problem/answer ペア | 各バリアント×年度で問題+解答が揃っているか |
| 試験種別の存在確認 | その大学に後期/中期が本当にあるか（廃止されていないか） |
| 相対URL→絶対URL変換 | `curl -sI -L -w "%{url_effective}"` で実URLを確認 |

### 解答レコードの信頼性チェック（必須）

大学の公開姿勢はいい加減なことが多い。「解答」と書いてあっても出題意図しか入っていなかったり、逆にファイル名が「出題意図」なのに中身は解答だったりする。HTMLのラベルやファイル名だけでは判断できないため、以下の嗅覚ベースのトリアージを行う:

**列ヘッダーとリンクラベルの矛盾チェック（必須）:**
列ヘッダーが「解答用紙」なのに個別リンクの alt/テキストが「解答」になっている場合がある（cybercollege.jp で確認済み）。**列ヘッダーを優先**しつつ、必ず1件ダウンロードして空欄用紙か実解答かを確認する。空欄用紙は answer として登録しない。

**要注意パターン（該当する answer レコードは R2 から PDF をダウンロードして中身を確認）:**

1. **解答を公開しないことで知られる大学に answer レコードがある**
   - 佐賀・琉球・京都など出題意図のみ公開の大学
   - DB に answer があったら「本当に解答か？出題意図では？」と疑う
2. **公式ページで「解答」と「出題意図」の両方を公開しているが、DB の answer 数と公式の解答 PDF 数が合わない**
   - 出題意図を解答として取り込んでいる可能性
3. **年度によって公開方針が変わっている**
   - 例: 長崎大学は R03 (2021) まで出題意図のみ、R04 (2022) から解答を公開開始
   - 古い年度に answer レコードがあれば、中身が出題意図の可能性
4. **ファイル名に `ito`（意図）、`shushi`（趣旨）、`yoshi`（用紙）が含まれる**
   - ただしファイル名と中身が一致しないケースもある（長崎 R03 は `sugakuito.pdf` だが中身は解答）
5. **answer レコードの R2 ファイルサイズが極端に小さい**（数十KB）
   - 解答用紙（空欄のみ）の可能性

**確認が不要なケース:**
- 公式ページのテーブルで明確に「解答」列に配置され、同一行に「出題意図」も別途存在する → 取り違えの可能性が低い
- 過去の監査で同一大学の answer を確認済みで、公開方針に変更がない

## Phase 3: Gap分析

Phase 1,2 の結果を突合して以下を分類:

### A. 不足（追加が必要）
- バリアント漏れ: 公式サイトにあるがDBにない
- 解答欠落: problemはあるがanswerがない（公式サイトには存在する）

### B. 不正データ（削除が必要）
- 存在しない試験種別のレコード
- subject名の表記揺れによる重複
- **generic 重複**: variant 付きレコードが全て揃っているのに `subject_variant=NULL` の generic レコードが残存（最頻出パターン。関東20大学監査で6大学で検出）。md5sum で variant レコードとの同一性を確認してから削除

### C. 問題なし
- variant不要なレコード（後期が1種類のみ等）

### D. 理科バンドル要確認
- `subject=理科/science` のレコードが存在し、対象科目（chemistry等）の個別レコードがない
- 公式サイトで対象科目の個別PDFが公開されているか確認:
  - **個別PDFあり** → Phase 4 で個別科目として追加。理科レコードは Phase 5 で削除検討
  - **個別PDFなし（合冊のみ）** → 対象科目で `is_bundled=true` のレコードを追加。理科レコードは残す
- 同一年に個別科目レコード**と**理科レコードが**両方**ある場合 → 理科レコードはバンドル誤登録の可能性。Phase 5 で削除検討

### E. JA/EN重複
- 同一 (year, exam_type, content_type) で英語名レコードと日本語名レコードの両方が存在
- 対応: Phase 5 で日本語名レコードを削除（英語名レコードを正として残す）
- 注意: pdf_storage_path が異なる場合は R2 オブジェクトも確認（同一PDFの重複アップロードの可能性）
- **自動化**: `audit-recheck-jaen.ts --fix --force` で一括削除可能

### F. JA-only（EN側なし）
- 日本語名レコードのみ存在し、対応する英語名レコードがない
- 対応: `subject` を英語キーに UPDATE（レコード削除は不要）
- **自動化**: `audit-recheck-jaen.ts --fix --force` で一括 UPDATE 可能
- normalizeSubject gate 導入前のレガシーデータで発生。今後の新規 ingest では発生しない

### G. データ品質問題（修正が必要）

レコードは存在するが、中身や属性が正しくない問題。「PDFの有無」ではなく「データの正しさ」に関する分類。

典型的なパターン:
- **ハッシュvariant名**: `subject_variant` が `3b5a79c3` のような意味不明な値 → PDFの中身を確認して正しい学部名に修正（agr, med, sci_eng 等）
- **subject_variant 未設定**: NULL だが R2 パスに variant 情報がある → R2 パスから特定して設定
- **content_type 不一致**: answer として登録されているが中身が出題意図・解答用紙 → content_type を修正 or レコード削除
- **variant名の年度間不統一**: 同じ学部なのに 2023 はハッシュ、2024 は正名 → 統一

**対応手順**:
1. Phase 1 のデータ品質チェックまたは Phase 2 の解答信頼性チェックで検出
2. 必要に応じて PDF の中身を確認（`download-r2.ts` でダウンロード → 先頭ページ確認）
3. DB の UPDATE（subject_variant, content_type, pdf_storage_path）
4. R2 パスの変更が必要な場合: Copy → DB UPDATE → Delete old

## Phase 3.5: PDF内容確認（Sonnet 4.6 検証）

Gap分析で「追加が必要」と判定したPDFについて、ingest前にPDFの中身を実際に確認する。
**公式サイトのHTML構造だけでは判別できないリスク** を排除するためのステップ。

### いつ実行するか

以下のいずれかに該当する場合は **必須**:
- URLがハッシュベース（例: `uploads/00ba09e0d7d836828cc79f6d290c35e3.pdf`）で科目名が読み取れない
- 「物理・数学」のような合冊科目
- 公式サイトのテーブル構造が曖昧で、同じPDFが複数行から参照されている可能性がある
- 新規大学の初回audit（HTML構造の信頼度が低い）
- **Phase 3 で分類 D（理科バンドル要確認）** に該当するレコードがある場合 → 理科PDFに対象科目が含まれているか確認

以下の場合は **スキップ可**:
- URLに科目名が含まれる（例: `R7_01sug11_kaito.pdf`）
- 既に同一大学の別年度で同じ構造を確認済み
- 公式サイトが明確な1対1テーブル構造

### md5sum による重複判定（Agent 起動前に実施）

同一内容の疑いがあるPDF（異なるURLだが同じ試験の可能性）は、Sonnet エージェントを起動する前に `md5sum` で比較する。
ローカルコマンドなので API コスト・通信ゼロ。ハッシュ一致 = バイト列完全一致なので誤判定の可能性はない（偶然の衝突確率 1/2^128 ≈ 0）。

**特に有効な場面:**
- **分類 B（generic 重複）の判定**: generic レコードと variant レコードの R2 PDF を md5sum 比較 → 一致なら generic は重複確定。Phase 1 の段階で実施すると分類が即決する
- **cybercollege.jp と R2 の比較**: ソースが異なるため md5sum は不一致になることが多い（再処理差異）。サイズの近似で判断し、内容確認は Sonnet に委ねる

```bash
# 公式サイトのPDF同士を比較
curl -sS -L -o /tmp/verify/a.pdf "{url_a}"
curl -sS -L -o /tmp/verify/b.pdf "{url_b}"
md5sum /tmp/verify/a.pdf /tmp/verify/b.pdf

# R2 に既存のPDF同士を比較（download-r2.ts を使う）
./scripts/with-env.sh npx tsx scripts/download-r2.ts "{university}/2025/math/zenki/problem.pdf" /tmp/verify/a.pdf
./scripts/with-env.sh npx tsx scripts/download-r2.ts "{university}/2025/math_ri/zenki/problem.pdf" /tmp/verify/b.pdf
md5sum /tmp/verify/a.pdf /tmp/verify/b.pdf

# R2 の特定ディレクトリ配下を一括ダウンロード
./scripts/with-env.sh npx tsx scripts/download-r2.ts --prefix "{university}/2025/math" --out-dir /tmp/verify

# ハッシュ一致 → 同一ファイル。片方を除外
# ハッシュ不一致 → 別内容。Agent 確認に進む
```

### 手順

1. **問題PDFのみダウンロード**（解答は問題と対になるので省略可）:

```bash
VERIFY_DIR="/tmp/${university_id}-${year}-verify"
mkdir -p "$VERIFY_DIR"
curl -sS -L -o "$VERIFY_DIR/zenki_bunkei_problem.pdf" "{url}"
```

2. **先頭ページをPNGに変換**:

```bash
/usr/bin/pdftoppm -png -r 200 -l 1 "$VERIFY_DIR/{name}.pdf" "$VERIFY_DIR/{name}_p1"
```

3. **Sonnet 4.6 エージェントで並行確認**（Task tool, model: sonnet）:

各PDFに対して1エージェントを起動し、先頭ページのPNG画像を Read させて以下を判定:

```
判定項目:
1. これは「学部の一般選抜入試（前期/後期日程）」の問題か？
   → 編入学試験、大学院入試、推薦入試、AO入試、総合型選抜 ではないか
2. 科目は対象科目（数学等）か？
3. 表紙/ヘッダーの記載情報（年度、学部、試験種別、試験時間、配点）
4. 他のPDFと内容が重複していないか（同一問題の使い回し）
5. 不自然な点はあるか
```

4. **結果を記録**（audit ディレクトリに保存）:

全エージェントの結果を表にまとめ、問題がなければ Phase 4 に進む。
問題があれば該当PDFを fixes-add.json から除外するか、ユーザーに確認。

### 判定 NG のパターンと対応

| NG パターン | 対応 |
|---|---|
| 大学院入試・編入学だった | fixes-add.json から除外 |
| 科目が違う（物理のみ等） | subject_id を修正 or 除外 |
| 別バリアントと同一内容だった | 片方を除外（重複排除） |
| 合冊（物理+数学等） | subject_variant/subject_raw を適切に設定して続行 |

## Phase 4: 不足PDFの追加

fixes-add.json を作成（kakomon-university-rebuild スキルの Phase C 形式）:

```json
[
  {
    "action": "add",
    "url": "https://...",
    "university_id": "{id}",
    "year": 2025,
    "subject_id": "math",
    "subject_variant": "rikei",
    "subject_raw": "数学（理系）",
    "subject_display": "数学（理系）",
    "exam_type": "zenki",
    "exam_variant": null,
    "exam_type_raw": "前期日程",
    "content_type": "problem",
    "is_bundled": false,
    "bundled_subjects": null,
    "r2_path": "{id}/2025/math_rikei/zenki/problem.pdf"
  }
]
```

### subject_id ルール

- `subject_id` は **必ず英語キー** を使用（`math`, `chemistry` 等）。`normalizeSubject` gate が自動変換するが、入力時点で英語キーにするのが望ましい
- `理科` / `science` は `subject_id` に **使用禁止** → 個別科目名 + `is_bundled: true` で登録
- `subject_raw` に日本語元名を記録（表示用）
- `subject_variant` は DB の `subject_variant` カラムに直接格納される（`rikei`, `bunkei`, `med` 等。不要なら `null`）

### 必須チェック

```bash
# R2パス重複チェック
.tools/bin/jq -r '.[].r2_path' "$REBUILD_DIR/fixes-add.json" | sort | uniq -d
# URL重複チェック
.tools/bin/jq -r '.[].url' "$REBUILD_DIR/fixes-add.json" | sort | uniq -d
# subject_id が英語キーであることを確認（日本語名が混入していないか）
.tools/bin/jq -r '.[].subject_id' "$REBUILD_DIR/fixes-add.json" | sort -u
# → math, chemistry 等の英語キーのみであること。「数学」「理科」等が出たらNG
```

### Ingest

**合冊PDFの場合は `ingest-add-by-fixes.ts` を使ってはいけない。** `ingest-add-by-fixes.ts` はPDFをそのままR2にアップロードするため、合冊PDFが分割されずに全科目のR2パスに同一ファイルがコピーされてしまう。

合冊PDFは **kakomon-university-rebuild スキルの Phase B3〜B5 + Phase E** の手順で分割してからアップロードする:
1. `pdf_splitter.py analyze` でGemini分類（科目境界を特定）
2. `pdf_splitter.py review` で目視確認
3. `pdf_splitter.py split` + `manual-split-plan.json` 生成
4. `manual-split-upload.ts` で分割PDF→R2アップロード→DB upsert

詳細は kakomon-university-rebuild スキルを参照。

**個別PDFのみ** `ingest-add-by-fixes.ts` を使用する:

```bash
# dry-run
./scripts/with-env.sh npx tsx scripts/ingest-add-by-fixes.ts \
  --add-fixes "$REBUILD_DIR/fixes-add.json" --dry-run

# 本番
./scripts/with-env.sh npx tsx scripts/ingest-add-by-fixes.ts \
  --add-fixes "$REBUILD_DIR/fixes-add.json" --force
```

### Verification

```bash
./scripts/with-env.sh npx tsx scripts/verify-fixes-db-r2.ts \
  --add-fixes "$REBUILD_DIR/fixes-add.json"
```

## Phase 5: 不正データの削除

### DB + R2 一括削除（推奨: `delete-documents.ts`）

```bash
# ID指定で削除
./scripts/with-env.sh npx tsx scripts/delete-documents.ts --ids "id1,id2,id3" --dry-run
./scripts/with-env.sh npx tsx scripts/delete-documents.ts --ids "id1,id2,id3" --force

# フィルタ指定で削除（例: tottori の zenki null variant を全削除）
./scripts/with-env.sh npx tsx scripts/delete-documents.ts \
  --university tottori --subject math --exam-type zenki --variant-is-null --dry-run
./scripts/with-env.sh npx tsx scripts/delete-documents.ts \
  --university tottori --subject math --exam-type zenki --variant-is-null --force

# 複数 exam_type の OR 指定（例: zenki と kouki の null だけ消して chuki の null は残す）
./scripts/with-env.sh npx tsx scripts/delete-documents.ts \
  --university nagoya_city --subject math --exam-type-in zenki,kouki --variant-is-null --dry-run

# kakomon_questions が紐づくレコードを削除する場合は --cascade
./scripts/with-env.sh npx tsx scripts/delete-documents.ts --ids "id1" --force --cascade
```

### variant 名のリネーム（推奨: `rename-variant.ts`）

DB の `subject_variant` と R2 パスを同時にリネームする:

```bash
# dry-run で確認
./scripts/with-env.sh npx tsx scripts/rename-variant.ts \
  --university shimane --subject math --from sorigo_other --to sorigo_zaiene --dry-run

# 実行（R2 copy → DB update → R2 delete old → verify）
./scripts/with-env.sh npx tsx scripts/rename-variant.ts \
  --university shimane --subject math --from sorigo_other --to sorigo_zaiene --force

# 特定年度のみ
./scripts/with-env.sh npx tsx scripts/rename-variant.ts \
  --university shimane --subject math --from med_suuri --to med --year 2024 --force
```

**制約: `subject_variant=NULL` → named variant へのリネームは非対応。**
`rename-variant.ts` は `.eq("subject_variant", from!)` で検索するため NULL にマッチしない。
NULL → named variant のリネームは手動で行う:

```bash
# 1. 対象レコードを特定（NULL variant のみ）
./scripts/with-env.sh npx tsx scripts/query-documents.ts \
  --university {id} --subject {subject} --compact | grep '  -  '

# 2. R2 パスを手動コピー（subject/ → subject_newVariant/）
./scripts/with-env.sh bash -c '
  for path in "{id}/2025/math/zenki/problem.pdf" "{id}/2025/math/zenki/answer.pdf"; do
    new_path=$(echo "$path" | sed "s|/math/|/math_bunkei/|")
    node -e "
      const { S3Client, CopyObjectCommand } = require(\"@aws-sdk/client-s3\");
      const s3 = new S3Client({ region: \"auto\", endpoint: \"https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com\", credentials: { accessKeyId: process.env.R2_ACCESS_KEY_ID, secretAccessKey: process.env.R2_SECRET_ACCESS_KEY } });
      s3.send(new CopyObjectCommand({ Bucket: process.env.R2_BUCKET_NAME, CopySource: process.env.R2_BUCKET_NAME + \"/\" + \"$path\", Key: \"$new_path\" })).then(() => console.log(\"OK: $new_path\"));
    "
  done
'

# 3. DB を UPDATE（subject_variant + pdf_storage_path）
./scripts/with-env.sh bash -c '
  curl -s -o /dev/null -w "%{http_code}" -X PATCH \
    "$SUPABASE_URL/rest/v1/kakomon_documents?university_id=eq.{id}&subject=eq.math&exam_type=eq.zenki&subject_variant=is.null" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"subject_variant\": \"bunkei\", \"pdf_storage_path\": \"REPLACE_EACH\"}"
'
# 注意: pdf_storage_path はレコードごとに異なるため、実際には ID 単位で PATCH する

# 4. 旧 R2 パスを削除
```

### 手動削除（スクリプトが使えない場合のみ）

```bash
curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  "$SUPABASE_URL/rest/v1/kakomon_documents?id=eq.{record_id}" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
```

### JA/EN重複の解消（分類 E + F）

**推奨: 自動スクリプトを使う**

```bash
# レポート（dry-run）
./scripts/with-env.sh npx tsx scripts/audit-recheck-jaen.ts --report

# 修正実行（分類E: JA重複削除 + 分類F: JA-only→EN UPDATE）
./scripts/with-env.sh npx tsx scripts/audit-recheck-jaen.ts --fix --force

# 特定大学・科目に絞る場合
./scripts/with-env.sh npx tsx scripts/audit-recheck-jaen.ts --report --universities kobe,kyoto --subjects math
```

手動対応が必要な場合のみ以下を実行:

1. **削除前確認**: 英語名レコードと日本語名レコードの `pdf_storage_path` を比較
   - 同一パス → 日本語名レコードのみ DB 削除（R2 は残す）
   - 異なるパス → R2 オブジェクトも確認。英語名レコードのR2ファイルが存在することを確認してから日本語名レコード + R2 を削除
2. **kakomon_questions の確認**: 日本語名 document に紐づく questions レコードがある場合、先にそちらを削除（外部キー制約）

### 削除時の注意

- **後期(kouki)でバリアントが1種類のみ**: generic パス `math/kouki/` のままでよい。削除しない
- **削除前に必ず variant 付きレコードが存在することを確認**: 先に Phase 4 の追加を完了してから Phase 5 で旧レコードを消す

## Phase 6: 最終確認

`query-documents.ts` で全件取得し、対象科目のレコードが想定通りになっているか確認:

```bash
# 全件コンパクト表示
./scripts/with-env.sh npx tsx scripts/query-documents.ts --university {id} --subject {subject_en} --compact

# バリアント一覧
./scripts/with-env.sh npx tsx scripts/query-documents.ts --university {id} --subject {subject_en} --variants

# 理科バンドルの残存確認（理科系科目の場合）
./scripts/with-env.sh npx tsx scripts/query-documents.ts --university {id} --subject science --compact

# JA/EN一括確認（E=0, F=0 を確認）
./scripts/with-env.sh npx tsx scripts/audit-recheck-jaen.ts --report --universities {id} --subjects {subject_en}
```

確認ポイント:
- generic パスの残存: variant 付きが入った科目×試験種別で `math/zenki/` が残っていないこと
- 後期のgeneric: バリアント不要な後期は `math/kouki/` のままでOK
- `subject_variant` がR2パスの variant 部分と一致していること
- audit-recheck で E=0, F=0 であること
- 理科バンドルレコード: 分類 D の対応が正しく完了していること

### exam_page_url の書き戻し

Phase 2 で使用した公式ページURLが `kakomon_universities.exam_page_url` に未登録（NULL）の場合、書き戻す:

```bash
./scripts/with-env.sh npx tsx scripts/update-exam-url.ts \
  --university {id} --url "{official_url}" --dry-run
./scripts/with-env.sh npx tsx scripts/update-exam-url.ts \
  --university {id} --url "{official_url}"
```

## 過去の監査実績

具体的な実行結果は [audit-history.md](audit-history.md) を参照。
**注意: 過去に監査済みの大学×科目でも、再監査が指示された場合は最新のDBと公式サイトで再実行すること。実績はあくまで参考情報であり、「完了済みだからスキップ」してはならない。**

## 過去の監査から得られたノウハウ

### Phase 3.5 関連
- PDFのURLがハッシュベースで科目名を含まない大学（北九州市立大学等）は Phase 3.5 が有効
- 「物理・数学」合冊はSonnet確認で構成を把握できる
- 同一ファイル疑い（別URL・別学群向けに同じPDFを掲載）は md5sum で即判定可能。高知工科大学で実証済み（suugaku_m = suugaku_m_1）

### データ品質（分類 G）関連
- 佐賀大学: ingest時にハッシュvariant名で登録されやすい。PDFヘッダーに学部名が明記されているので先頭ページ確認で特定可能
- 北九州市立大学: ハッシュベースURL + 文系/理系の区別が subject_variant に反映されず R2 パスにのみ残る問題が発生した
- 長崎大学: R03 (2021) は公式ファイル名が `sugakuito`（出題意図）だが、中身は実際の解答。ファイル名で判断せずPDFの中身を確認すること

### 私立大学パターン
- `exam_type=ippan`（zenki/kouki ではない）。日程は `exam_variant` で区別（`0206`, `0207` 等の日付ベース）
- 学部ごとに公開方針が異なる: 問題のみ / 解答のみ / 出題の意図のみ / 問題+解答
- 1つの generic レコードが「全学部共通選抜」を指す場合がある（中央大学の5学部共通等）。variant と generic が同一内容でないケースに注意
- 法政大学のように多数の学部×日程で独立した試験を実施する大学は variant 数が多い（36件等）。generic 重複が起きにくい

### 大学固有の注意点
- 解答を公開していない大学（佐賀・琉球・京都等）はDBにanswerが無くても正常
- 京都大学は解答を公開しない（出題意図のみ）
- 大阪公立大学は zenki/chuki/kouki の3日程あり。zenki は math1(IIAB)/math2(IIIIIAB) の2variant、解答なし。chuki のみ P+A 完備
- 神戸大学は文科系/理科系の2variant（zenki）+ 理科系のみ（kouki）
- 神戸大学の理科問題は物理/化学/生物/地学の合冊PDF。解答は科目別に単独公開
- 京都工繊大は2025年度から後期廃止
- 大阪公立大学の kouki は理学部向け合冊Science PDFで単独数学は存在しない
- 奈良女子大の kouki は数学・物理・英語・国語のみ（化学・生物なし）
- 京都府立大の「理科」は化学としてDB登録済み（生命環境学部向け）
- 愛媛大学は解答を公開しない（出題意図 ito のみ）。2025のみ掲載
- 香川大学は解答非公開。数学は学部別4バリアント（edu_med_psy_agr, law_eng_b, med_med, eng_a）。後期に数学なし
- 高知大学は問題+解答を公開。数学はbunkei（ⅠⅡABC）/rikei（ⅠⅡⅢabc）の2バリアント。URLがハッシュベース（p1.ssl-dl.jp）だが title 属性に科目名あり
- 高知工科大学は問題のみ公開（解答なし）。数学はrikei（sys/rikou/info学群）/bunkei（DI/マネジメント学群）の2バリアント。WordPressサイトで `_1` サフィックス注意。R6+R7の2年度掲載
- 徳島大学は問題+解答+出題意図を公開。数学はhoken_rikou（保健/理工、Ⅲなし）/med（医歯薬、Ⅲあり）の2バリアント。後期は理工のみ1種（generic）
- **埼玉大学**（cybercollege.jp）: zenki 3バリアント（econ_edu=経済+教育, sci_math=理学数学科, eng=工学部）+ kouki 1種（generic=理学+工学）。解答は非公開（解答用紙のみ）
- **横浜国立大学**（cybercollege.jp）: zenki 2バリアント（bunkei=経済/経営, rikei=理工/都市）+ kouki 2バリアント（同）。解答は非公開（解答用紙のみ）
- **東京学芸大学**（cybercollege.jp）: zenki generic 1種（A類数学/B類数学/B類情報/E類情報教育 共通）。後期に数学なし。解答例（ex/）あり
- 青山学院大学: ippan, 理工（rikou）問題+解答 + 全学部（zengakubu）問題のみ。generic = rikou の重複パターン。「解答」列のPDFが出題意図の場合あり
- 中央大学: ippan, 5学部共通選抜（5gakubu）問題+解答。他学部は解答例 or 出題の意図のみ。generic = 5gakubu の重複パターン
- 学習院大学: ippan, 理学科コア（rika_core）問題+解答。generic problem = rika_core の重複（answer は generic のみ残す）
- 法政大学: ippan, 多数の学部×日程で独立試験。36件。generic 重複なし
- 立教大学: ippan, bunkei/rikei の日付ベースバリアント。generic = bunkei の重複パターン
- 早稲田大学: ippan, 2026年度分と理工学部（rikou）の2系統。generic ≠ rikou（別内容）

### 理科系の注意点
- 多くの大学で理科はbundle（問題合冊+解答個別）パターン
- 佐賀大学の科目コード: ZRIKA=化学, ZRIBU=物理, ZIRI=医学部理科（bundle）。RIKAI/RIBUI=出題意図（解答ではない）
- 宮崎大学: zenki理科は医工農3学部共通bundle、kouki個別科目（物理=工農、化学=工農、生物=農のみ）
- 北九州市立大学: 2024 zenkiは理科bundle（個別physics/biologyなし）、koukiのみ個別科目
