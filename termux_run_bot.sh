#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "$(dirname "$0")"

if ! command -v python >/dev/null 2>&1; then
  echo "[!] Python not found. Install Termux packages first: pkg install -y python chromium tesseract"
  exit 1
fi

if [ ! -d ".venv" ]; then
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "[i] Created .env from .env.example. Edit .env before first run."
fi

python bot.py
