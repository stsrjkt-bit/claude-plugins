---
name: pdf-splitter
description: >
  大学入試の理科PDF（物理・化学・生物・地学が1つにまとめられたもの）を科目別に分割するスキル。
  社会PDF（地理・日本史・世界史・政経などが1つにまとめられたもの）の分割にも使う。
  理科PDFの科目分割、ページ境界の特定、過去問PDFの前処理に関するタスクで使用する。
  「理科を科目別に分ける」「物理だけ取り出す」「PDFのページ構成を調べる」等のリクエストで発火する。
  このスキルを使わずに自力でページ境界を推測してはいけない。
---

# 理科PDF 科目自動分割

## 背景と重要な注意

大学入試の理科PDFには以下の罠がある。**絶対に自力でページ番号を推測するな。**

- **白紙ページ**: 科目間に白紙ページが挿入されていることがあり、PDFのページ番号と印刷されたフッターのページ番号がずれる
- **表紙のページ情報は信用できない**: 表紙に記載された「物理 p.1〜8」等のページ範囲は印刷上のページ番号であり、PDFの物理ページ番号とは一致しないことが多い
- **解答用紙の位置が不定**: 解答用紙が各科目の直後にある場合と、全科目の後にまとめて配置されている場合がある

## 手順

## Human-in-the-loop (必須)

Geminiの分類はズレる。**必ず目視で境界を確認し、必要なら分類JSONを修正してから分割を確定**する。

判断ガイド（分類JSONの読み方、修正ルール、fixes.json例、よくあるパターン）は:
- `references/decision-guide.md`

### 例: analyze -> review -> (edit json) -> split

```bash
# 1) analyze (分類JSON作成)
python3 <this_skill_dir>/scripts/pdf_splitter.py analyze <science_bundle.pdf> --json /tmp/science_bundle.classification.json

# 2) review (境界候補をPNG化)
python3 <this_skill_dir>/scripts/pdf_splitter.py review <science_bundle.pdf> \
  --classification /tmp/science_bundle.classification.json \
  -o /tmp/science_bundle_review/

# 3) JSONを手で修正（必要なら）
# - /tmp/science_bundle.classification.json をコピーして edited.json を作り、
#   pages[] の type/subject を直す

# 4) split (修正済みJSONで確定分割。Geminiを再実行しない)
python3 <this_skill_dir>/scripts/pdf_splitter.py split <science_bundle.pdf> \
  --classification /tmp/science_bundle.edited.json \
  -o /tmp/science_bundle_split/
```

注意:
- `split` は `problem` と `answer_sheet` を別PDFに出す（必要なら ingest 側でどう扱うか判断する）
- `review` は「少数ページだけ」PNG化する。怪しい境界は追加で確認すること（`references/decision-guide.md`）

### ステップ1: スクリプトで全ページ分類を取得

```bash
python3 <this_skill_dir>/scripts/pdf_splitter.py analyze <input.pdf> --json <output.json>
```

環境変数 `GEMINI_API_KEY` が設定されている必要がある。
モデルは環境変数 `GEMINI_MODEL` で変更可能（デフォルト: gemini-2.5-flash）。

### ステップ2: 出力JSONを確認

出力JSONには全ページの分類が含まれる:

```json
{
  "total_pages": 42,
  "pages": [
    {"page": 1, "type": "cover", "subject": null, "note": "理科 問題冊子 表紙"},
    {"page": 2, "type": "problem", "subject": "physics", "note": "物理 問1"},
    {"page": 10, "type": "blank", "subject": null, "note": "白紙"},
    {"page": 11, "type": "problem", "subject": "chemistry", "note": "化学 問1"},
    {"page": 28, "type": "answer_sheet", "subject": "physics", "note": "物理解答用紙"}
  ],
  "subjects": {
    "physics": {"problem_pages": [2,3,...,9], "answer_pages": [28]},
    "chemistry": {"problem_pages": [11,12,...], "answer_pages": [29]}
  }
}
```

**このJSONのpages配列を信頼してページ範囲を決定すること。**

### ステップ3: 自動分割（オプション）

分類結果に基づいてPDFを科目別に分割する場合:

```bash
python3 <this_skill_dir>/scripts/pdf_splitter.py split <input.pdf> -o <output_dir>/
```

Gemini分類を再実行せず、修正済み分類JSONで分割を確定する場合:

```bash
python3 <this_skill_dir>/scripts/pdf_splitter.py split <input.pdf> --classification <edited.json> -o <output_dir>/
```

一括処理:

```bash
python3 <this_skill_dir>/scripts/pdf_splitter.py batch <input_dir>/ -o <output_dir>/
```

## type一覧

| type | 説明 |
|------|------|
| cover | 表紙、目次、注意事項 |
| problem | 問題ページ |
| answer_sheet | 解答用紙 |
| blank | 白紙ページ |
| other | その他 |

## subject一覧

| subject | 説明 |
|---------|------|
| physics | 物理 |
| chemistry | 化学 |
| biology | 生物 |
| earth_science | 地学 |
| null | 科目に属さない |

## よくある失敗パターン（やってはいけないこと）

1. **表紙のページ番号を信じる** → 白紙ページの存在でずれる
2. **フッターのページ番号からオフセットを計算する** → 白紙・解答用紙の挿入でずれる
3. **スクリプトを使わず画像を1枚ずつ見てページ構成を推測する** → 時間がかかる上にずれる
4. **科目の切れ目を表紙情報だけで決定する** → 1ページずれて全科目の分割がおかしくなる
