FROM python:3.11-slim

# Install system dependencies required for Chrome and Selenium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg unzip fonts-liberation fonts-dejavu \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 libcups2 \
    libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libx11-xcb1 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 libxi6 \
    libxrender1 libxtst6 libxss1 libgl1 libpango-1.0-0 libpangocairo-1.0-0 \
    libjpeg-dev libxshmfence1 xdg-utils ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install latest stable Google Chrome
RUN wget -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm /tmp/chrome.deb

# Ensure /tmp is writable and has enough space
RUN mkdir -p /tmp && chmod 1777 /tmp

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["python", "bot.py"]
