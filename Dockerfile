# Build stage
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy AS builder

# Set up working directory
WORKDIR /app

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set up working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Command to run the bot
CMD ["python", "bot.py"]
