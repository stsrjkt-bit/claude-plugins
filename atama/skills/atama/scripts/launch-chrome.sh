#!/bin/bash
# Chrome起動スクリプト（atama+ COACH用）
# - WSL2環境でWSLg経由でGUI表示
# - --remote-debugging-port=9222 でchrome-devtools MCP接続
# - --user-data-dir でセッション永続化

USER_DATA_DIR="$HOME/.config/chrome-atama"
REMOTE_PORT=9222
LOGIN_URL="https://coach.atama.plus/public/login"

# 既に起動中ならスキップ
if pgrep -f "chrome.*--remote-debugging-port=$REMOTE_PORT" > /dev/null 2>&1; then
  echo "Chrome is already running (remote-debugging-port=$REMOTE_PORT)"
  exit 0
fi

# ユーザーデータディレクトリ作成
mkdir -p "$USER_DATA_DIR"

# Chrome起動
nohup google-chrome \
  --no-sandbox \
  --disable-setuid-sandbox \
  --disable-dev-shm-usage \
  --disable-gpu \
  --no-first-run \
  --disable-background-networking \
  --disable-default-apps \
  --disable-translate \
  --disable-sync \
  --disable-component-update \
  --metrics-recording-only \
  --mute-audio \
  --remote-debugging-port=$REMOTE_PORT \
  --remote-allow-origins=* \
  --user-data-dir="$USER_DATA_DIR" \
  "$LOGIN_URL" \
  > /tmp/chrome-atama.log 2>&1 &

echo "Chrome started (PID: $!, port: $REMOTE_PORT)"
echo "Log: /tmp/chrome-atama.log"
