# Start from the official Python slim image
FROM python:3.11-slim

# Install system dependencies required for Chrome and Selenium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    unzip \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxi6 \
    libxrender1 \
    libxtst6 \
    libxss1 \
    libgl1 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libjpeg-dev \
    libxshmfence1 \
    xdg-utils \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Add Google Chrome repository and install Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set display port to avoid crash (not strictly needed for headless, but helps some builds)
ENV DISPLAY=:99

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables for unbuffered output
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python", "bot.py"]
