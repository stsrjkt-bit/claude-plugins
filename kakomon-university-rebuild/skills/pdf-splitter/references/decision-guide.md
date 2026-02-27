# pdf-splitter Decision Guide (Human-in-the-loop)

このスキルは「Geminiに全ページ分類をさせ、**人間(Codex)が境界を目視検証・必要なら修正してから**分割を確定する」ためのガイド。

## 基本方針

- **最初に `analyze` を走らせる**: 表紙のページ範囲やフッター番号は信用しない。
- **境界は必ず目視確認する**: `review` で境界付近のページをPNG化して確認する。
- **必要なら分類JSONを手で直す**: 1ページのズレが全科目のPDFを破壊する。
- `split --classification <edited.json>` で **Gemini再実行なし**で分割を確定する。

## 分類JSONの読み方

`pages[]` は 1始まりの物理ページ番号。重要なのは:

- `type`: `cover` / `problem` / `answer_sheet` / `blank` / `other`
- `subject`: `physics` / `chemistry` / `biology` / `earth_science` / `null`
- `note`: 見出し・問題番号などの根拠

見るべきポイント:

- `blank` が混じる箇所（ズレ原因）
- `subject` が切り替わる直前直後のページ
- `answer_sheet` が「科目直後」か「巻末まとめ」か

## 目視確認のやり方

1. `review` で境界候補(+/-1ページ)と白紙/解答用紙をPNGにして確認。
2. それでも不安な場合は、境界の前後を追加でPNG化する。
   - 例: `review` の出力に含まれないページ番号を手でレンダする場合は `pymupdf` で追加生成してよい（スキル本体の修正ではなく、その場の調査として）。

## 分類JSONの修正ルール

やることは単純で、`pages[]` の該当ページの `type` / `subject` を直す。

- 科目の先頭ページが誤って `cover` 扱い: `type="problem"` に直す
- 白紙が `other` 扱い: `type="blank"`, `subject=null` に直す
- 科目が1ページだけ誤分類: そのページの `subject` を直す
- 解答用紙が科目不明: 目視で科目を判定して `subject` を直す

編集後は `split --classification edited.json` を使うこと（`split` が勝手にGemini再実行しないように）。

## 代表パターン

- パターンA: 科目ごとに「問題」セクションが連続している
  - `problem_pages` が連番になるはず。飛びがあれば `blank/cover` の見落としを疑う。
- パターンB: 解答用紙が巻末にまとまる
  - `answer_sheet` が後ろに固まる。科目に正しく紐づいているか要確認。
- パターンC: 「理科(共通)」表紙が各科目の前に入る
  - `cover` が科目間に挟まる。`split` が「problemだけ抽出」なので、表紙を含めたい場合は設計を変える必要がある（現状は問題ページ主体で切る）。

## kakomon-collector fixes.json の書き方（例）

pdf-splitter は **fixes.json を自動生成しない**。分類JSONと分割PDFを見て、毎回Codexが判断して作る。

`kakomon-collector fix --apply` は `FixEntry[]` を受け取る。

ローカルで分割したPDFをそのまま ingest する場合:
- `action`: `"add"`
- `url`: 公式の元PDF URL（DBの `original_url` になる）
- `file_path`: ローカルPDFのパス（アップロード実体）
- `r2_path`: `{university_id}/{year}/{subject_id}/{exam_type}/{content_type}.pdf`
- `subject_raw`: 合冊側のラベル（例: `理科（共通問題）`）
- `subject_display`: 科目表示（例: `物理`）
- `is_bundled`: `true`（bundle由来である印）
- `bundled_subjects`: `["physics","chemistry","biology"]` など

```json
[
  {
    "action": "add",
    "url": "https://example.ac.jp/admissions/R07_science.pdf",
    "file_path": "/tmp/split/R07_science_physics.pdf",
    "university_id": "hokkaido",
    "year": 2025,
    "subject_id": "physics",
    "subject_variant": null,
    "subject_raw": "理科（共通問題）",
    "subject_display": "物理",
    "exam_type": "zenki",
    "exam_variant": null,
    "exam_type_raw": "前期日程",
    "content_type": "problem",
    "is_bundled": true,
    "bundled_subjects": ["physics","chemistry","biology"],
    "r2_path": "hokkaido/2025/physics/zenki/problem.pdf"
  }
]
```

注:
- `subject_display` はDBの表示に直結するので、PDF本文の表記に合わせる（`物理` / `化学` / `生物` など）。
- `content_type` を `answer` で入れるかどうかは大学・PDF構造次第（問題冊子と解答冊子が別URLなら別entryにするのが基本）。

