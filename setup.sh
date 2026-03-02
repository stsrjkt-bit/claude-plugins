#!/usr/bin/env bash
# claude-plugins セットアップスクリプト
# git clone/pull 後に実行すると ~/.claude/skills/ と ~/.claude/commands/ に全symlinkを張る
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
COMMANDS_DIR="$HOME/.claude/commands"

mkdir -p "$SKILLS_DIR" "$COMMANDS_DIR"

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

link_command() {
  local target="$1"
  local name="$(basename "$target")"

  if [ -L "$COMMANDS_DIR/$name" ]; then
    local current="$(readlink "$COMMANDS_DIR/$name")"
    if [ "$current" = "$target" ]; then
      echo "  OK  $name"
      return
    fi
    rm "$COMMANDS_DIR/$name"
  elif [ -e "$COMMANDS_DIR/$name" ]; then
    echo "  SKIP $name (実体ファイルが存在。手動で削除してから再実行)"
    return
  fi

  ln -s "$target" "$COMMANDS_DIR/$name"
  echo "  LINK $name -> $target"
}

echo "claude-plugins: symlinkセットアップ"
echo "repo: $REPO_DIR"
echo "dest: $SKILLS_DIR"
echo ""

# --- スキルのsymlink ---
echo "=== Skills ==="
for plugin_dir in "$REPO_DIR"/*/; do
  [ -d "${plugin_dir}skills" ] || continue
  for skill_dir in "${plugin_dir}skills"/*/; do
    [ -d "$skill_dir" ] || continue
    link_skill "$skill_dir"
  done
done

# --- コマンドのsymlink ---
echo ""
echo "=== Commands ==="
for plugin_dir in "$REPO_DIR"/*/; do
  [ -d "${plugin_dir}commands" ] || continue
  for cmd_file in "${plugin_dir}commands"/*.md; do
    [ -f "$cmd_file" ] || continue
    link_command "$cmd_file"
  done
done

echo ""
echo "完了。現在のスキル一覧:"
ls -la "$SKILLS_DIR/"
echo ""
echo "現在のコマンド一覧:"
ls -la "$COMMANDS_DIR/" 2>/dev/null || echo "  (なし)"

# --- 出力ディレクトリ作成 ---
echo ""
echo "=== 出力ディレクトリ ==="
mkdir -p ~/sato-card-builder/output
echo "  OK  ~/sato-card-builder/output/"

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

# リポジトリ別 .env
generate_env "$HOME/kakomon-generator" sato-juku dev .env
generate_env "$HOME/kakomon-manager"   sato-juku dev .env.local
generate_env "$HOME/studygram"         sato-juku dev_studygram .env

# --- atama+ 認証情報 ---
echo ""
echo "=== atama+ 認証情報 ==="
ALL=$(doppler secrets download --project sato-juku --config dev --no-file --format env-no-quotes 2>/dev/null || true)
if [ -n "$ALL" ]; then
  echo "$ALL" | grep -E '^(ATAMA_ID|ATAMA_PW)=' > ~/.env.atama 2>/dev/null || true
  local_count=$(wc -l < ~/.env.atama 2>/dev/null || echo 0)
  echo "  OK   ~/.env.atama ($local_count lines)"
else
  echo "  SKIP Dopplerからシークレットを取得できませんでした"
fi

# --- StudyGram 認証情報 ---
echo ""
echo "=== StudyGram 認証情報 ==="
if [ -n "$ALL" ]; then
  {
    echo "# StudyGram CLI credentials (for atama+ Phase 14)"
    echo "$ALL" | grep -E '^(SUPABASE_URL|SUPABASE_ANON_KEY|ADMIN_USER_ID|ADMIN_ACCESS_CODE)=' || true
    echo ""
    echo "# Auth credentials (email/password for token refresh)"
    echo "$ALL" | grep -E '^(ADMIN_CLI_EMAIL|ADMIN_CLI_PASSWORD)=' || true
    echo ""
    echo "# Access token (auto-refreshed by refresh_studygram_token function)"
    echo "$ALL" | grep -E '^(ADMIN_ACCESS_TOKEN|ADMIN_REFRESH_TOKEN)=' || true
    echo ""
    cat <<'FUNCEOF'
# Helper: refresh expired token
# Usage: refresh_studygram_token && source ~/.env.studygram
refresh_studygram_token() {
  local _URL _KEY _EMAIL _PW
  _URL=$(grep '^SUPABASE_URL=' ~/.env.studygram | cut -d= -f2-)
  _KEY=$(grep '^SUPABASE_ANON_KEY=' ~/.env.studygram | cut -d= -f2-)
  _EMAIL=$(grep '^ADMIN_CLI_EMAIL=' ~/.env.studygram | cut -d= -f2-)
  _PW=$(grep '^ADMIN_CLI_PASSWORD=' ~/.env.studygram | cut -d= -f2-)
  local RESULT=$(curl -s "${_URL}/auth/v1/token?grant_type=password" \
    -H "apikey: ${_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${_EMAIL}\",\"password\":\"${_PW}\"}")
  local NEW_TOKEN=$(echo "${RESULT}" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
  local NEW_REFRESH=$(echo "${RESULT}" | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")
  if [ -n "${NEW_TOKEN}" ] && [ "${#NEW_TOKEN}" -gt 100 ]; then
    sed -i "s|^ADMIN_ACCESS_TOKEN=.*|ADMIN_ACCESS_TOKEN=${NEW_TOKEN}|" ~/.env.studygram
    sed -i "s|^ADMIN_REFRESH_TOKEN=.*|ADMIN_REFRESH_TOKEN=${NEW_REFRESH}|" ~/.env.studygram
    echo "Token refreshed (length: ${#NEW_TOKEN})"
  else
    echo "Token refresh failed: ${RESULT}"
    return 1
  fi
}
FUNCEOF
  } > ~/.env.studygram
  sg_count=$(wc -l < ~/.env.studygram 2>/dev/null || echo 0)
  echo "  OK   ~/.env.studygram ($sg_count lines)"
else
  echo "  SKIP Dopplerからシークレットを取得できませんでした"
fi

echo ""
echo "セットアップ完了"
