#!/usr/bin/env bash
# claude-plugins セットアップスクリプト
# git clone/pull 後に実行すると ~/.claude/skills/ に全スキルのsymlinkを張る
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"

mkdir -p "$SKILLS_DIR"

link_skill() {
  local target="$1"
  local name="$(basename "$target")"

  if [ -L "$SKILLS_DIR/$name" ]; then
    local current="$(readlink "$SKILLS_DIR/$name")"
    if [ "$current" = "$target" ]; then
      echo "  OK  $name"
      return
    fi
    rm "$SKILLS_DIR/$name"
  elif [ -e "$SKILLS_DIR/$name" ]; then
    echo "  SKIP $name (実体ファイルが存在。手動で削除してから再実行)"
    return
  fi

  ln -s "$target" "$SKILLS_DIR/$name"
  echo "  LINK $name -> $target"
}

echo "claude-plugins: symlinkセットアップ"
echo "repo: $REPO_DIR"
echo "dest: $SKILLS_DIR"
echo ""

# 各プラグインの skills/ 配下を走査
for plugin_dir in "$REPO_DIR"/*/; do
  [ -d "${plugin_dir}skills" ] || continue
  for skill_dir in "${plugin_dir}skills"/*/; do
    [ -d "$skill_dir" ] || continue
    link_skill "$skill_dir"
  done
done

echo ""
echo "完了。現在のスキル一覧:"
ls -la "$SKILLS_DIR/"

# --- Doppler → .env 生成 ---
echo ""
echo "=== Doppler → .env 生成 ==="

if ! command -v doppler &> /dev/null; then
  echo "  SKIP doppler がインストールされていません"
  echo "  インストール: curl -sS https://cli.doppler.com/install.sh | sh"
  exit 0
fi

if ! doppler me &> /dev/null; then
  echo "  SKIP doppler にログインしていません"
  echo "  ログイン: doppler login"
  exit 0
fi

generate_env() {
  local repo_dir="$1"
  local project="$2"
  local config="$3"
  local env_file="$4"
  local repo_name="$(basename "$repo_dir")"

  if [ ! -d "$repo_dir" ]; then
    echo "  SKIP $repo_name (ディレクトリなし: $repo_dir)"
    return
  fi

  doppler secrets download \
    --project "$project" --config "$config" \
    --format env --no-file > "$repo_dir/$env_file" 2>/dev/null

  local count=$(grep -c '=' "$repo_dir/$env_file" 2>/dev/null || echo 0)
  echo "  OK   $repo_name/$env_file ($count keys)"
}

generate_env "$HOME/kakomon-generator" sato-juku dev .env
generate_env "$HOME/kakomon-manager"   sato-juku dev .env.local
generate_env "$HOME/studygram"         sato-juku dev_studygram .env

echo ""
echo "セットアップ完了"
