#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "$(dirname "$0")"

if ! command -v python >/dev/null 2>&1; then
  echo "[!] Python not found. Install Termux packages first."
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

if ! command -v firefox >/dev/null 2>&1; then
  echo "[!] Firefox not found. Install: pkg install -y x11-repo && pkg install -y firefox"
fi
if ! command -v geckodriver >/dev/null 2>&1; then
  echo "[!] GeckoDriver not found. Install: pkg install -y geckodriver"
fi

python bot.py
