# Run the bot on Android (Termux) with Firefox + GeckoDriver

## 1) Install system packages in Termux
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
Create a `.env` file from template:

```bash
cp .env.example .env
```

Then edit `.env`:

```bash
TELEGRAM_BOT_TOKEN="..."
BOT_OWNER_ID="..."
URL="..."
RAPIDAPI_KEY=""
FIREFOX_BINARY=""
GECKODRIVER_PATH=""
LOW_BANDWIDTH_MODE="1"
LOCAL_DB_PATH="credentials.json"
```

## 4) Verify binaries
```bash
which firefox
which geckodriver
```

## 5) Start bot
```bash
python bot.py
```

## Quick start script
```bash
bash termux_run_bot.sh
```

## Notes
- The bot uses Firefox + GeckoDriver only.
- `LOW_BANDWIDTH_MODE=1` (default) disables heavy graphics (images/video/WebGL/fonts) to help on slow networks while keeping core form flow.
- Local OCR (Tesseract) is attempted first for CAPTCHA.
- RapidAPI OCR is used only as fallback.
- If MongoDB/pymongo is unavailable, the bot automatically uses `credentials.json` local storage.
