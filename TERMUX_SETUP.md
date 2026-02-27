# Run the bot on Android (Termux)

## 1) Install system packages in Termux

### Option A: Chromium + ChromeDriver
```bash
pkg update && pkg upgrade -y
pkg install -y python chromium chromium-driver tesseract
```

### Option B: Firefox + GeckoDriver
```bash
pkg update && pkg upgrade -y
pkg install -y x11-repo
pkg install -y python firefox geckodriver tesseract
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

Then edit `.env`:

```bash
# Required
TELEGRAM_BOT_TOKEN="..."
BOT_OWNER_ID="..."
URL="..."

# Browser mode: chrome or firefox
BROWSER="chrome"

# Optional MongoDB
MONGO_URI=""

# Optional RapidAPI fallback (used only if local OCR fails)
RAPIDAPI_KEY=""

# Optional explicit paths (normally leave empty for auto-detect)
CHROME_BINARY=""
CHROMEDRIVER_PATH=""
FIREFOX_BINARY=""
GECKODRIVER_PATH=""

# Optional: local JSON credentials file path
LOCAL_DB_PATH="credentials.json"
```

## 4) Verify binaries
```bash
# For Chromium mode
which chromium-browser || which chromium
which chromedriver || which chromium-driver

# For Firefox mode
which firefox
which geckodriver
```

## 5) Start bot
```bash
python bot.py
```

## Quick start script (recommended)
```bash
bash termux_run_bot.sh
```

## Notes
- Local OCR (Tesseract) is attempted first for CAPTCHA.
- RapidAPI OCR is used only as fallback.
- If MongoDB/pymongo is unavailable on your device, the bot automatically uses `credentials.json` local storage.
- Docker and Flask keep-alive are not required anymore.
