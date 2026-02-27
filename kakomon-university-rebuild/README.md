# kakomon-university-rebuild

大学入試過去問の公式PDF取得・合冊分割・DB/R2 ingestワークフロー。

## 含まれるスキル

| スキル | 説明 |
|--------|------|
| `kakomon-university-rebuild` | 公式ページ→PDF発見→ダウンロード→分類→ingest の全体ワークフロー |
| `pdf-splitter` | 合冊PDF（理科・社会等）をGemini分類で科目別に分割 |

## インストール

```bash
# ~/.claude/skills/ にシンボリックリンクを作成
ln -s $(pwd)/skills/kakomon-university-rebuild ~/.claude/skills/kakomon-university-rebuild
ln -s $(pwd)/skills/pdf-splitter ~/.claude/skills/pdf-splitter
```

## 依存

- `pdf_splitter.py`: `GEMINI_API_KEY` 環境変数、`pymupdf`、`google-generativeai`
- `kakomon-university-rebuild`: `kakomon-generator` リポジトリのスクリプト群
