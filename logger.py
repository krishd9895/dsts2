import logging
import os
from logging.handlers import RotatingFileHandler
from collections import deque

# Bot owner ID for logs access
BOT_OWNER_ID = int(os.getenv('BOT_OWNER_ID'))
MAX_LOG_LINES = 6000

def trim_log_file(file_path, max_lines):
    """Keep only the latest max_lines in the log file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = deque(f, max_lines)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        print(f"Error trimming log file: {e}")

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Remove old log file if it exists
log_file = 'logs/debug.txt'
if os.path.exists(log_file):
    os.remove(log_file)

# Configure rotating file handler for debug logs
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=1024 * 1024,  # 1MB per file
    backupCount=1,  # Keep only one backup file
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Configure console handler for user interaction logs only
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(console_formatter)

# Configure different loggers
bot_logger = logging.getLogger('bot')
bot_logger.setLevel(logging.DEBUG)
bot_logger.addHandler(file_handler)

login_logger = logging.getLogger('login')
login_logger.setLevel(logging.DEBUG)
login_logger.addHandler(file_handler)

session_logger = logging.getLogger('session')
session_logger.setLevel(logging.DEBUG)
session_logger.addHandler(file_handler)

db_logger = logging.getLogger('db')
db_logger.setLevel(logging.DEBUG)
db_logger.addHandler(file_handler)

# User interaction logger - both file and console
user_interaction_logger = logging.getLogger('user_interaction')
user_interaction_logger.setLevel(logging.INFO)
user_interaction_logger.addHandler(file_handler)
user_interaction_logger.addHandler(console_handler)

# Prevent loggers from propagating to root logger
bot_logger.propagate = False
login_logger.propagate = False
session_logger.propagate = False
db_logger.propagate = False
user_interaction_logger.propagate = False