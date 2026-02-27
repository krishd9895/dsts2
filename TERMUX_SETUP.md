# Run the bot on Android (Termux)

## 1) Install system packages in Termux
```bash
pkg update && pkg upgrade -y
pkg install -y python chromium tesseract
```

## 2) Install Python dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3) Configure environment variables
Create a `.env` file (or export manually):

```bash
export TELEGRAM_BOT_TOKEN="..."
export BOT_OWNER_ID="..."
export URL="..."
# Optional: use MongoDB if available
export MONGO_URI="..."

# Optional RapidAPI fallback (used only if local OCR fails)
export RAPIDAPI_KEY="..."

# Optional overrides for Termux binaries
export CHROME_BINARY="/data/data/com.termux/files/usr/bin/chromium-browser"
export CHROMEDRIVER_PATH="/data/data/com.termux/files/usr/bin/chromedriver"
export TESSERACT_CMD="tesseract"

# Optional: local JSON credentials file path
export LOCAL_DB_PATH="credentials.json"

```

## 4) Start bot
```bash
python bot.py
```

## Notes
- Local OCR (Tesseract) is attempted first for CAPTCHA.
- RapidAPI OCR is used only as fallback.
- If MongoDB/pymongo is unavailable on your device, the bot automatically uses `credentials.json` local storage.
- Docker and Flask keep-alive are not required anymore.
