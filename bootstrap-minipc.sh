#!/usr/bin/env bash
# ミニPC (GMKtec G10 / Win11 Pro + WSL2) 初期セットアップ
# Chromebook から SSH 接続後に実行する
set -euo pipefail

echo "=== GMKtec G10 ミニPC セットアップ ==="
echo ""

# --- 基本パッケージ ---
echo "[1/7] 基本パッケージ"
sudo apt-get update
sudo apt-get install -y \
  git curl wget unzip jq \
  build-essential \
  poppler-utils qpdf \
  python3 python3-pip python3-venv \
  openssh-server

# --- Node.js (v20 LTS) ---
echo "[2/7] Node.js"
if ! command -v node &> /dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
node --version
npm --version

# --- GitHub CLI ---
echo "[3/7] GitHub CLI"
if ! command -v gh &> /dev/null; then
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli-stable.list > /dev/null
  sudo apt-get update && sudo apt-get install -y gh
fi
echo "gh auth login でログインしてください"

# --- Doppler CLI ---
echo "[4/7] Doppler CLI"
if ! command -v doppler &> /dev/null; then
  curl -sS https://cli.doppler.com/install.sh | sudo sh
fi
echo "doppler login でログインしてください"

# --- Claude Code ---
echo "[5/7] Claude Code"
if ! command -v claude &> /dev/null; then
  sudo npm install -g @anthropic-ai/claude-code
fi
claude --version

# --- Python パッケージ (pdf_splitter 用) ---
echo "[6/7] Python パッケージ"
pip3 install --user google-generativeai Pillow PyMuPDF 2>/dev/null || \
  pip3 install --break-system-packages google-generativeai Pillow PyMuPDF

# --- AWS CLI (R2 操作用) ---
echo "[7/7] AWS CLI"
if ! command -v aws &> /dev/null; then
  pip3 install --user awscli 2>/dev/null || \
    pip3 install --break-system-packages awscli
fi

echo ""
echo "=== インストール完了 ==="
echo ""
echo "次のステップ:"
echo "  1. gh auth login"
echo "  2. doppler login"
echo "  3. git clone https://github.com/stsrjkt-bit/claude-plugins.git"
echo "  4. cd claude-plugins && ./setup.sh"
echo "  5. 主要リポジトリを clone:"
echo "     git clone https://github.com/stsrjkt-bit/kakomon-generator.git"
echo "     git clone https://github.com/stsrjkt-bit/kakomon-manager.git"
echo "     git clone https://github.com/stsrjkt-bit/studygram.git"
echo "  6. ./setup.sh を再実行（.env 生成）"
echo ""
echo "CHROME_PATH について:"
echo "  ミニPCではChromeが使えます（x86_64）:"
echo "  wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
echo "  sudo dpkg -i google-chrome-stable_current_amd64.deb"
echo "  CHROME_PATH=/usr/bin/google-chrome-stable"
