# card-builder プラグイン

さとう数理塾のホームページ掲載用「お悩み解決カード」を、リサーチからエクスポートまで一貫して制作する Claude Code プラグインです。

## インストール

```bash
git clone https://github.com/stsrjkt-bit/claude-plugins.git ~/claude-plugins
cp -r ~/claude-plugins/card-builder/skills/card-builder ~/.claude/skills/card-builder
```

### ローカルテスト（開発用）

```bash
claude --plugin-dir ./claude-plugins/card-builder
```

## 使い方

インストール後、Claude Code で以下のスキルが使えます:

```
/card-builder:card-builder
```

## ワークフロー

1. **Phase 0**: ギャップ分析（既存カード棚卸し）
2. **Phase 1**: ヒアリング
3. **Phase 2**: マーケティングリサーチ
4. **Phase 3**: 商圏分析
5. **Phase 4**: カード生成
6. **Phase 5**: リファイン（競合ギャップ分析 → recommendPoints 最適化）
7. **Phase 6**: プレビュー & テキスト調整
8. **Phase 7**: 承認 & 本番デプロイ

## 前提条件

- `~/sato-card-builder/` にデータディレクトリが存在すること
- `~/stsrjk-web-netlify/` に本番サイトリポジトリが存在すること
- chrome-devtools MCP が有効であること（プレビュー表示用）
