# kakomon-split-gha

大問分割（Generate Kakomon）を GitHub Actions で実行し、完了後に 3-tier パイプラインでトピックタグを付与するワークフロー。

## インストール

```bash
ln -s $(pwd)/skills/kakomon-split-gha ~/.claude/skills/kakomon-split-gha
```

## 依存

- `kakomon-generator` リポジトリ（GHA ワークフロー + スクリプト群）
- `gh` CLI（GitHub Actions 起動・監視）
