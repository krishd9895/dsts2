from playwright.sync_api import sync_playwright
from logger import session_logger


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.busy_users = set()  # Track users who are currently in an operation
        self.login_queue = {}  # Track login attempt timestamps
        self.playwright = None

    def is_user_busy(self, user_id):
        """Check if user is currently performing an operation"""
        return user_id in self.busy_users

    def can_attempt_login(self, user_id):
        """Check if user can attempt login based on cooldown"""
        import time
        current_time = time.time()
        if user_id in self.login_queue:
            last_attempt = self.login_queue[user_id]
            if current_time - last_attempt < 5:  # 5 seconds cooldown
                return False
        self.login_queue[user_id] = current_time
        return True

    def set_user_busy(self, user_id, busy=True):
        """Set user's busy status"""
        if busy:
            self.busy_users.add(user_id)
        else:
            self.busy_users.discard(user_id)
            if user_id in self.login_queue:
                del self.login_queue[user_id]

    def get_session(self, user_id):
        """Get existing session or create new one"""
        session_logger.info(f"Getting session for user {user_id}")
        
        if user_id in self.sessions and self.sessions[user_id].get('context'):
            session_logger.debug(f"Existing session found for user {user_id}")
            return self.sessions[user_id]

        session_logger.info(f"Creating new browser session for user {user_id}")
        try:
            if not self.playwright:
                self.playwright = sync_playwright().start()
            
            browser = self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            self.sessions[user_id] = {
                'browser': browser,
                'context': context,
                'page': page
            }
            return self.sessions[user_id]
        except Exception as e:
            session_logger.error(f"Failed to create browser session: {str(e)}")
            raise

    def close_session(self, user_id):
        """Close and remove session"""
        if user_id in self.sessions:
            try:
                self.sessions[user_id]['page'].close()
                self.sessions[user_id]['context'].close()
                self.sessions[user_id]['browser'].close()
            except:
                pass
            del self.sessions[user_id]
        self.set_user_busy(user_id, False)  # Make sure to clear busy status

    def close_all_sessions(self):
        """Close all active sessions"""
        for user_id in list(self.sessions.keys()):
            self.close_session(user_id)
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
        self.busy_users.clear()
        self.login_queue.clear()


session_manager = SessionManager()
