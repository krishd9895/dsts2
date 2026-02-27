# Run the bot on Android (Termux)

## 1) Install system packages in Termux
```bash
pkg update && pkg upgrade -y
pkg install -y python chromium chromium-driver tesseract
```

## 2) Install Python dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3) Configure environment variables
Create a `.env` file from template (recommended):

```bash
cp .env.example .env
```

Then edit `.env` (or export manually):

```bash
export TELEGRAM_BOT_TOKEN="..."
export BOT_OWNER_ID="..."
export URL="..."
# Optional: use MongoDB if available
export MONGO_URI="..."

# Optional RapidAPI fallback (used only if local OCR fails)
export RAPIDAPI_KEY="..."

# Optional overrides for Termux binaries
export CHROME_BINARY=""
export CHROMEDRIVER_PATH=""
export TESSERACT_CMD="tesseract"

# Optional: local JSON credentials file path
export LOCAL_DB_PATH="credentials.json"

```

## 4) Verify binaries
```bash
which chromium-browser || which chromium
which chromedriver || which chromium-driver
```

## 5) Start bot
```bash
python bot.py
```

## Notes
- Local OCR (Tesseract) is attempted first for CAPTCHA.
- RapidAPI OCR is used only as fallback.
- If MongoDB/pymongo is unavailable on your device, the bot automatically uses `credentials.json` local storage.
- Docker and Flask keep-alive are not required anymore.


## Quick start script (recommended)
```bash
bash termux_run_bot.sh
```
This script creates `.venv`, installs requirements, creates `.env` from `.env.example` (if missing), and starts the bot.
