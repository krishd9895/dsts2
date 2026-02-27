#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "$(dirname "$0")"

if ! command -v python >/dev/null 2>&1; then
  echo "[!] Python not found. Install Termux packages first: pkg install -y python chromium chromium-driver tesseract"
  exit 1
fi

if [ ! -d ".venv" ]; then
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

if ! command -v chromium-browser >/dev/null 2>&1 && ! command -v chromium >/dev/null 2>&1; then
  echo "[!] Chromium not found. Install: pkg install -y chromium"
fi

if ! command -v chromedriver >/dev/null 2>&1 && ! command -v chromium-driver >/dev/null 2>&1; then
  echo "[!] ChromeDriver not found. Install: pkg install -y chromium-driver"
fi

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "[i] Created .env from .env.example. Edit .env before first run."
fi

python bot.py
