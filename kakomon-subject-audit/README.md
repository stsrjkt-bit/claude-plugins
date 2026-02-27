# kakomon-subject-audit

過去問PDFの監査・修正ワークフロー。

DBの過去問データと公式サイトの公開PDFを突合し、不足（バリアント漏れ・解答欠落）や不正データ（重複・誤レコード）を発見・修正する。

## インストール

```bash
ln -s $(pwd)/skills/kakomon-subject-audit ~/.claude/skills/kakomon-subject-audit
```

## 依存

- `kakomon-generator` リポジトリのスクリプト群
- `kakomon-university-rebuild` スキル（合冊PDF分割が必要な場合）
