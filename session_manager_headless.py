import os
import shutil
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService

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

    def _resolve_firefox_binary(self):
        env_binary = os.getenv("FIREFOX_BINARY", "").strip()
        candidates = [
            env_binary,
            shutil.which("firefox"),
            "/data/data/com.termux/files/usr/bin/firefox",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        raise FileNotFoundError(
            "Firefox binary not found. Set FIREFOX_BINARY or install firefox in Termux: pkg install firefox"
        )

    def _resolve_geckodriver_path(self):
        env_driver = os.getenv("GECKODRIVER_PATH", "").strip()
        candidates = [
            env_driver,
            shutil.which("geckodriver"),
            "/data/data/com.termux/files/usr/bin/geckodriver",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        raise FileNotFoundError(
            "GeckoDriver not found. Install it in Termux (pkg install geckodriver) or set GECKODRIVER_PATH."
        )

    def _build_driver(self):
        firefox_binary = self._resolve_firefox_binary()
        geckodriver_path = self._resolve_geckodriver_path()

        options = FirefoxOptions()
        options.add_argument("-headless")
        options.binary_location = firefox_binary

        session_logger.info(
            "Starting Firefox with binary=%s geckodriver=%s",
            firefox_binary,
            geckodriver_path,
        )
        return webdriver.Firefox(
            service=FirefoxService(executable_path=geckodriver_path),
            options=options,
        )

    def get_session(self, user_id):
        session_logger.info(f"Getting session for user {user_id}")

        if user_id in self.sessions and self.sessions[user_id]["driver"]:
            session_logger.debug(f"Existing session found for user {user_id}")
            return self.sessions[user_id]

        session_logger.info(f"Creating new browser session for user {user_id}")
        try:
            driver = self._build_driver()
            self.sessions[user_id] = {"driver": driver}
            return self.sessions[user_id]
        except Exception as e:
            session_logger.error(f"Failed to create browser session: {str(e)}")
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
