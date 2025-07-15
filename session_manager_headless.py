from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.options import Options
from logger import session_logger

class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.busy_users = set()
        self.login_queue = {}

    def get_session(self, user_id):
        session_logger.info(f"Getting session for user {user_id}")
        
        if user_id in self.sessions and self.sessions[user_id]['driver']:
            session_logger.debug(f"Existing session found for user {user_id}")
            return self.sessions[user_id]

        session_logger.info(f"Creating new Firefox session for user {user_id}")
        try:
            firefox_options = Options()
            firefox_options.add_argument('--no-sandbox')
            firefox_options.add_argument('--disable-dev-shm-usage')
            firefox_options.add_argument('--window-size=1920x1080')
            firefox_options.add_argument('--headless')
            firefox_options.add_argument('--disable-gpu')
            
            session_logger.debug("Firefox options configured")
            
            driver = webdriver.Firefox(service=Service(GeckoDriverManager().install()), options=firefox_options)
            self.sessions[user_id] = {'driver': driver}
            return self.sessions[user_id]
        except Exception as e:
            session_logger.error(f"Failed to create Firefox session: {str(e)}")
            raise

    # Other methods (is_user_busy, can_attempt_login, set_user_busy, close_session, close_all_sessions) remain unchanged
