# atama+ COACH 自動化

Chromiumを起動し、chrome-devtools MCP経由でatama+ COACHにログイン。
指定生徒の学習データ取得→つまずき分析→足場がけ補習プリント作成→PDF出力を一気通貫で実行する。

## 引数

$ARGUMENTS

引数は `<生徒名> <教科>` または `login`。

- `/atama login` → Chrome起動＆ログインのみ（Phase 1〜2）
- `/atama 鎮守杏 物理` → フルパイプライン（Phase 1〜10）

## 手順

`~/.claude/skills/atama/SKILL.md` に記載された Phase 1〜10 の手順に従って実行すること。
設定情報は `~/.claude/skills/atama/reference.md` を参照すること。

### 引数の解析

1. `$ARGUMENTS` が `login` の場合 → Phase 1〜2 のみ実行
2. それ以外 → 生徒名と教科を分離してフルパイプライン実行
   - 例: `鎮守杏 物理` → 生徒名=「鎮守杏」、教科=「物理」
   - 教科名は「高校」プレフィックスがなければ自動補完（物理→高校物理、化学→高校化学、数学→高校数学）

### 実行フェーズ

| Phase | 内容 |
|-------|------|
| 1 | Chrome起動（`bash ~/.claude/skills/atama/scripts/launch-chrome.sh`） |
| 2 | MCP接続＆ログイン確認 |
| 3 | 生徒詳細ページへ遷移 |
| 4 | 学習タイムライン取得 |
| 5 | 単元ごとの学習状況 |
| 6 | 誤答分析 |
| 7 | 結果まとめ（ユーザーに報告） |
| 8 | 補習プリント作成（足場がけHTML） |
| 9 | 解答プリント作成 |
| 10 | PDF生成（`node ~/.claude/skills/atama/scripts/generate-pdf.mjs`） |

各フェーズの詳細手順は `~/.claude/skills/atama/SKILL.md` を Read して参照すること。
