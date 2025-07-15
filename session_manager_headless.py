from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
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

    def get_session(self, user_id):
        session_logger.info(f"Getting session for user {user_id}")

        if user_id in self.sessions and self.sessions[user_id]['driver']:
            session_logger.debug(f"Existing session found for user {user_id}")
            return self.sessions[user_id]

        session_logger.info(f"Creating new Chrome session for user {user_id}")
        try:
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--single-process')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--remote-debugging-port=9222')
            chrome_options.binary_location = '/usr/bin/google-chrome'

            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            self.sessions[user_id] = {'driver': driver}
            return self.sessions[user_id]
        except Exception as e:
            session_logger.error(f"Failed to create Chrome session: {str(e)}")
            raise

    def close_session(self, user_id):
        if user_id in self.sessions:
            try:
                self.sessions[user_id]['driver'].quit()
            except:
                pass
            del self.sessions[user_id]
        self.set_user_busy(user_id, False)

    def close_all_sessions(self):
        for user_id in list(self.sessions.keys()):
            self.close_session(user_id)
        self.busy_users.clear()
        self.login_queue.clear()


session_manager = SessionManager()
