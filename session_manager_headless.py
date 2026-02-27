import os
import shutil
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from logger import session_logger


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.busy_users = set()
        self.login_queue = {}

    def is_user_busy(self, user_id):
        return user_id in self.busy_users

    def can_attempt_login(self, user_id):
        import time

        current_time = time.time()
        if user_id in self.login_queue:
            last_attempt = self.login_queue[user_id]
            if current_time - last_attempt < 5:
                return False
        self.login_queue[user_id] = current_time
        return True

    def set_user_busy(self, user_id, busy=True):
        if busy:
            self.busy_users.add(user_id)
        else:
            self.busy_users.discard(user_id)
            if user_id in self.login_queue:
                del self.login_queue[user_id]

    def _resolve_chrome_binary(self):
        env_binary = os.getenv("CHROME_BINARY", "").strip()
        candidates = [
            env_binary,
            shutil.which("chromium-browser"),
            shutil.which("chromium"),
            shutil.which("google-chrome"),
            "/data/data/com.termux/files/usr/bin/chromium-browser",
            "/data/data/com.termux/files/usr/bin/chromium",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        raise FileNotFoundError(
            "Chromium/Chrome binary not found. Set CHROME_BINARY or install chromium in Termux: pkg install chromium"
        )

    def _resolve_chromedriver_path(self):
        env_driver = os.getenv("CHROMEDRIVER_PATH", "").strip()
        candidates = [
            env_driver,
            shutil.which("chromedriver"),
            shutil.which("chromium-driver"),
            "/data/data/com.termux/files/usr/bin/chromedriver",
            "/data/data/com.termux/files/usr/bin/chromium-driver",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        raise FileNotFoundError(
            "ChromeDriver not found. Install it in Termux (pkg install chromium-driver) or set CHROMEDRIVER_PATH."
        )

    def _build_driver(self):
        chrome_binary = self._resolve_chrome_binary()
        chromedriver_path = self._resolve_chromedriver_path()

        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1280,720")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.binary_location = chrome_binary

        session_logger.info(
            "Starting Chromium with binary=%s chromedriver=%s",
            chrome_binary,
            chromedriver_path,
        )

        return webdriver.Chrome(
            service=Service(executable_path=chromedriver_path),
            options=chrome_options,
        )

    def get_session(self, user_id):
        session_logger.info(f"Getting session for user {user_id}")

        if user_id in self.sessions and self.sessions[user_id]["driver"]:
            session_logger.debug(f"Existing session found for user {user_id}")
            return self.sessions[user_id]

        session_logger.info(f"Creating new Chrome session for user {user_id}")
        try:
            driver = self._build_driver()
            self.sessions[user_id] = {"driver": driver}
            return self.sessions[user_id]
        except Exception as e:
            session_logger.error(f"Failed to create Chrome session: {str(e)}")
            raise

    def close_session(self, user_id):
        if user_id in self.sessions:
            try:
                self.sessions[user_id]["driver"].quit()
            except Exception:
                pass
            del self.sessions[user_id]
        self.set_user_busy(user_id, False)

    def close_all_sessions(self):
        for user_id in list(self.sessions.keys()):
            self.close_session(user_id)
        self.busy_users.clear()
        self.login_queue.clear()


session_manager = SessionManager()
