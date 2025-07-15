import requests
import os
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import time
from session_manager_headless import session_manager
from logger import login_logger, bot_logger

# Bot instance handling
bot_instances = {}
chat_ids = {}
user_inputs = {}
last_message_id = {}
status_logs = {}

def set_bot_instance(bot, chat_id):
    global bot_instances, chat_ids
    bot_instances[chat_id] = bot
    chat_ids[chat_id] = chat_id

def bot_log(message, user_id=None):
    if user_id in bot_instances and user_id in chat_ids:
        try:
            # Delete previous status message if it exists
            if user_id in last_message_id:
                try:
                    bot_instances[user_id].delete_message(
                        chat_ids[user_id], last_message_id[user_id])
                except:
                    pass  # Ignore if message already deleted

            # Send new message and store its ID
            sent_message = bot_instances[user_id].send_message(
                chat_ids[user_id], str(message))
            last_message_id[user_id] = sent_message.message_id
            bot_logger.debug(f"Message sent to user {user_id}: {message}")
        except Exception as e:
            bot_logger.error(f"Failed to send message to bot: {e}")
            bot_logger.debug(f"Failed message content: {message}")
    else:
        bot_logger.debug(message)

def clear_status(user_id):
    """Clear the status message for a user"""
    if user_id in last_message_id:
        try:
            bot_instances[user_id].delete_message(chat_ids[user_id],
                                                  last_message_id[user_id])
        except:
            pass  # Ignore if message already deleted
        del last_message_id[user_id]

def bot_send_image(image_path, caption, user_id):
    if user_id in bot_instances and user_id in chat_ids:
        try:
            with open(image_path, 'rb') as photo:
                bot_instances[user_id].send_photo(chat_ids[user_id],
                                                  photo,
                                                  caption=caption)
        except Exception as e:
            print(f"Failed to send image to bot: {e}")
    else:
        print(f"Would send image: {image_path} with caption: {caption}")

def bot_input(prompt, user_id=None):
    if user_id in bot_instances and user_id in chat_ids:
        bot_instances[user_id].send_message(chat_ids[user_id], prompt)
        # Set the user as waiting for input
        user_inputs[user_id] = None
        # Wait for input (with timeout)
        timeout = 60  # 60 seconds timeout
        start_time = time.time()
        while user_inputs[user_id] is None:
            if time.time() - start_time > timeout:
                bot_log("⚠️ Input timeout. Please try again.", user_id)
                return None
            time.sleep(0.5)
        response = user_inputs[user_id]
        user_inputs[user_id] = None
        return response
    return input(prompt)

# --------------------------
# CONFIGURATION
# --------------------------
website_url = os.getenv('URL')
max_retries = 3

# XPaths (Pre-Login)
XPATHS = {
    "username":
    "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/div/input",
    "password":
    "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/div[2]/input",
    "captcha_img":
    "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/div[3]/div/img",
    "captcha_input":
    "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/div[4]/input",
    "login_button":
    "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/input",
    "login_failure":
    "/html/body/div[2]/h2",
    "login_success": [
        "/html/body/form/header/nav/div/div/div/div/div/ul/li/a/span",
        "/html/body/form/header/nav/div/div/div/div/div/ul/li/a"
    ]
}

# XPaths (Post-Login)
POST_LOGIN_XPATHS = {
    "Page1_btn_path": "/html/body/form/div[4]/div/div/div/div/div/div/input",
    "Page2_verify_path": "/html/body/form/div[4]/div/div/div/div/div/div/span",
    "Page2_btn_path":
    "/html/body/form/div[4]/div/div/div/div/div/div[2]/div[2]/div/div/div/div/ul/input",
    "Page3_btn_path": "/html/body/form/header/nav/div/div/ul/li[2]/a"
}

# RapidAPI OCR configuration
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
RAPIDAPI_OCR_URL = "https://ocr-extract-text.p.rapidapi.com/ocr"
RAPIDAPI_HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "ocr-extract-text.p.rapidapi.com"
}

# --------------------------
# LOGIN FUNCTIONS
# --------------------------
def handle_login_attempt(user_id, username, password):
    """Main login handler with automatic retries and manual fallback"""
    login_logger.info(f"Starting login attempt for user {user_id}")
    clear_status(user_id)  # Clear previous status

    try:
        session = session_manager.get_session(user_id)
        driver = session['driver']
        login_logger.debug("Session and driver obtained successfully")
    except Exception as e:
        login_logger.error(f"Failed to get session/driver: {str(e)}")
        bot_log("❌ Login failed: Could not initialize browser session",
                user_id)
        return False

    if not username or not password:
        login_logger.warning(f"Invalid credentials for user {user_id}")
        bot_log("❌ Login failed: Invalid credentials", user_id)
        return False

    bot_log("\n" + "=" * 40, user_id)
    bot_log("ATTEMPTING LOGIN".center(40), user_id)
    bot_log("=" * 40, user_id)

    # Try automatic login first
    success = automatic_login(driver, username, password, user_id)
    login_logger.info(
        f"Login attempt result for user {user_id}: {'success' if success else 'failed'}"
    )
    return success

def automatic_login(driver, username, password, user_id=None):
    """Attempt automatic login with OCR-based CAPTCHA solving"""
    bot_log("\n📝 Starting automatic login process...", user_id)

    # Try automatic CAPTCHA solving first
    for attempt in range(3):  # Limited to 3 automatic attempts
        bot_log(f"🔄 Automatic login attempt {attempt + 1}/3", user_id)

        # Refresh page for each attempt
        driver.get(website_url)
        time.sleep(2)

        if not enter_credentials(driver, username, password, user_id):
            return False

        captcha_text = process_captcha(driver, user_id)
        if not captcha_text:
            continue

        submit_login(driver, user_id)

        # Check for invalid credentials before proceeding
        try:
            error_element = driver.find_elements(By.XPATH,
                                                 XPATHS["login_failure"])
            if error_element:
                error_text = error_element[0].text.strip()
                if "invalid" in error_text.lower() or "incorrect" in error_text.lower():
                    bot_log(
                        "❌ Login Failed: Invalid credentials. Please try again with correct username and password.",
                        user_id)
                    return False
        except Exception:
            pass

        if check_login_result(driver, user_id):
            bot_log("🎉 AUTOMATIC LOGIN SUCCESSFUL!, now try /operations",
                    user_id)
            return True

    # If automatic attempts fail, switch to manual entry
    bot_log("🔄 Switching to manual CAPTCHA entry", user_id)
    return manual_login(driver, username, password, user_id)

def manual_login(driver, username, password, user_id):
    """Manual login handler"""
    bot_log("\n📝 Starting manual login process...", user_id)

    # Refresh page for clean start
    driver.get(website_url)
    time.sleep(2)

    if not enter_credentials(driver, username, password, user_id):
        return False

    # Try to get captcha multiple times if needed
    for attempt in range(3):
        captcha_text = process_captcha_manual(driver, user_id)
        if captcha_text:
            break
        time.sleep(1)

    if not captcha_text:
        bot_log("❌ Failed to get captcha response from user", user_id)
        return False

    submit_login(driver, user_id)

    # Check for invalid credentials before proceeding
    try:
        error_element = driver.find_elements(By.XPATH, XPATHS["login_failure"])
        if error_element:
            error_text = error_element[0].text.strip()
            if "invalid" in error_text.lower() or "incorrect" in error_text.lower():
                bot_log(
                    "❌ Login Failed: Invalid credentials. Please try again with correct username and password.",
                    user_id)
                return False
    except Exception:
        pass

    if check_login_result(driver, user_id):
        bot_log("🎉 MANUAL LOGIN SUCCESSFUL!, now try /operations", user_id)
        return True

    return False

# --------------------------
# LOGIN HELPER FUNCTIONS
# --------------------------
def enter_credentials(driver, username, password, user_id):
    """Enter username and password"""
    try:
        # Clear existing fields first
        username_field = driver.find_element(By.XPATH, XPATHS["username"])
        password_field = driver.find_element(By.XPATH, XPATHS["password"])
        username_field.clear()
        password_field.clear()

        # Enter new credentials
        username_field.send_keys(username)
        password_field.send_keys(password)
        bot_log("✅ Credentials entered", user_id)
        return True
    except Exception as e:
        bot_log(f"❌ Error entering credentials: {str(e)}", user_id)
        return False

def process_captcha(driver, user_id):
    """Automatic captcha processing using RapidAPI OCR with direct URL"""
    try:
        captcha_element = driver.find_element(By.XPATH, XPATHS["captcha_img"])
        captcha_url = captcha_element.get_attribute("src")
        
        # Use the CAPTCHA URL directly in the RapidAPI request
        querystring = {"url": captcha_url}
        
        try:
            ocr_response = requests.get(RAPIDAPI_OCR_URL, headers=RAPIDAPI_HEADERS, params=querystring)
            if ocr_response.status_code == 200:
                data = ocr_response.json()
                captcha_text = data.get("text", "").replace(" ", "").strip()
                bot_log(f"🔍 Recognized Captcha: {captcha_text}", user_id)
                
                if captcha_text:
                    captcha_input = driver.find_element(By.XPATH, XPATHS["captcha_input"])
                    captcha_input.clear()
                    captcha_input.send_keys(captcha_text)
                    return captcha_text
                else:
                    bot_log("❌ No text recognized from CAPTCHA", user_id)
            else:
                bot_log(f"❌ OCR API error: {ocr_response.status_code}", user_id)
        except Exception as api_error:
            bot_log(f"❌ OCR API request failed: {str(api_error)}", user_id)
        
        return None
    except Exception as e:
        bot_log(f"❌ Captcha processing failed: {str(e)}", user_id)
        return None

def process_captcha_manual(driver, user_id):
    """Manual captcha handling"""
    try:
        # Get and save captcha
        captcha_element = driver.find_element(By.XPATH, XPATHS["captcha_img"])
        captcha_url = captcha_element.get_attribute("src")
        response = requests.get(captcha_url)
        captcha_path = "captcha_manual.png"

        # Save the image and verify it exists
        with open(captcha_path, 'wb') as f:
            f.write(response.content)

        if not os.path.exists(captcha_path):
            bot_log("❌ Failed to save captcha image", user_id)
            return None

        # Send captcha image to bot and wait for response
        try:
            bot_send_image(
                captcha_path,
                "📝 Please enter the captcha text shown in the image:", user_id)
            captcha_text = bot_input("Type the captcha text:", user_id)

            if captcha_text:
                captcha_input = driver.find_element(By.XPATH,
                                                    XPATHS["captcha_input"])
                captcha_input.clear()
                captcha_input.send_keys(captcha_text)
                return captcha_text
        except Exception as e:
            bot_log(f"❌ Error in bot communication: {str(e)}", user_id)

        return None
    except Exception as e:
        bot_log(f"❌ Manual captcha failed: {str(e)}", user_id)
        return None

def submit_login(driver, user_id):
    """Click login button"""
    try:
        driver.find_element(By.XPATH, XPATHS["login_button"]).click()
        bot_log("🔄 Submitting login...", user_id)
        time.sleep(5)
    except Exception as e:
        bot_log(f"❌ Login submission failed: {str(e)}", user_id)

def check_login_result(driver, user_id):
    """Check login success/failure with simple text content logging"""
    try:
        error_element = driver.find_elements(By.XPATH, XPATHS["login_failure"])
        if error_element:
            error_text = error_element[0].text.strip()
            bot_log(f"❌ Login Failed: {error_text}", user_id)
            return False

        bot_log("\nChecking success elements:", user_id)
        for path in XPATHS["login_success"]:
            elements = driver.find_elements(By.XPATH, path)
            if elements:
                bot_log(f"✅ Found: {elements[0].text.strip()}", user_id)
                return True
            else:
                bot_log(f"❌ Element not found", user_id)

        bot_log("⚠️ Unknown login status - no success elements found", user_id)
        return False
    except Exception as e:
        bot_log(f"❌ Login check failed: {str(e)}", user_id)
        return False

# --------------------------
# POST-LOGIN OPERATIONS
# --------------------------
def post_login_click_button(driver, button_element, user_id):
    """Attempts to click a button using multiple methods"""
    button_text = button_element.text.strip() or button_element.get_attribute(
        'value')

    try:
        driver.execute_script("arguments[0].click();", button_element)
        bot_log(f"✅ Clicked '{button_text}' using JavaScript", user_id)
        return True
    except Exception as e:
        bot_log(f"❌ JavaScript click failed for '{button_text}': {str(e)}",
                user_id)

    try:
        from selenium.webdriver.common.action_chains import ActionChains
        actions = ActionChains(driver)
        actions.move_to_element(button_element).click().perform()
        bot_log(f"✅ Clicked '{button_text}' using Action Chains", user_id)
        return True
    except Exception as e:
        bot_log(f"❌ Action Chains click failed for '{button_text}': {str(e)}",
                user_id)

    try:
        driver.execute_script(
            """
            arguments[0].style.opacity = '1'; 
            arguments[0].style.display = 'block';
            arguments[0].style.visibility = 'visible';
        """, button_element)
        button_element.click()
        bot_log(f"✅ Clicked '{button_text}' after forcing visibility", user_id)
        return True
    except Exception as e:
        bot_log(
            f"❌ Forced visibility click failed for '{button_text}': {str(e)}",
            user_id)

    return False

def extract_form_data(driver, user_id):
    """Extracts and prints relevant information from the data entry form dynamically."""
    try:
        bot_log("\n" + "=" * 40, user_id)
        bot_log("FORM INFORMATION".center(40), user_id)
        bot_log("=" * 40, user_id)

        bot_log("\n📝 Form Data:", user_id)

        input_elements = driver.find_elements(By.TAG_NAME, "input")

        for element in input_elements:
            field_id = element.get_attribute('id')
            value = element.get_attribute('value')
            readonly = element.get_attribute('readonly')
            label_elements = driver.find_elements(
                By.XPATH, f"//label[@for='{field_id}']")
            label = label_elements[0].text if label_elements else field_id

            if any(substring in field_id.lower() for substring in [
                    "event", "viewstate", "scroll", "validation",
                    "clientstate", "hidden", "logout", "pwchange"
            ]):
                continue

            label = label.replace("HomeContentPlaceHolder_txt", "")

            status = "🔒" if readonly else "✏️"
            bot_log(f"{status} {label}: {value}", user_id)

    except Exception as e:
        bot_log(f"❌ Error extracting form information: {str(e)}", user_id)

def post_login_operations(user_id):
    """Execute actions after successful login"""
    clear_status(user_id)  # Clear previous status
    session = session_manager.get_session(user_id)
    driver = session['driver']
    bot_log("\n" + "=" * 40, user_id)
    bot_log("POST-LOGIN OPERATIONS".center(40), user_id)
    bot_log("=" * 40, user_id)

    try:
        # Clean up captcha files
        for file in ["captcha_manual.png"]:  # Only clean up manual captcha file
            if os.path.exists(file):
                os.remove(file)

        # Page 1: Initial button
        Page1_btn = driver.find_element(By.XPATH,
                                        POST_LOGIN_XPATHS["Page1_btn_path"])
        button_text = Page1_btn.text.strip() or Page1_btn.get_attribute(
            'value')
        bot_log(f"🖱️ Found button: {button_text}", user_id)
        if not post_login_click_button(driver, Page1_btn, user_id):
            raise Exception(f"Failed to click '{button_text}' button")
        time.sleep(2)

        # Page 2: Verification and next button
        Page2_verify = driver.find_element(
            By.XPATH, POST_LOGIN_XPATHS["Page2_verify_path"])
        verify_text = Page2_verify.text.strip()
        bot_log(f"📋 Found section: {verify_text}", user_id)

        Page2_btn = driver.find_element(By.XPATH,
                                        POST_LOGIN_XPATHS["Page2_btn_path"])
        button_text = Page2_btn.text.strip() or Page2_btn.get_attribute(
            'value')
        bot_log(f"🖱️ Found button: {button_text}", user_id)
        if not post_login_click_button(driver, Page2_btn, user_id):
            raise Exception(f"Failed to click '{button_text}' button")
        time.sleep(2)

        # Page 3: Final button
        Page3_btn = driver.find_element(By.XPATH,
                                        POST_LOGIN_XPATHS["Page3_btn_path"])
        button_text = Page3_btn.text.strip() or Page3_btn.get_attribute(
            'value')
        bot_log(f"🖱️ Found button: {button_text}", user_id)
        if not post_login_click_button(driver, Page3_btn, user_id):
            raise Exception(f"Failed to click '{button_text}' button")
        time.sleep(2)

        # Extract and display form data
        extract_form_data(driver, user_id)

        # Handle input field and save
        try:
            input_field = driver.find_element(
                By.XPATH,
                "/html/body/form/div[4]/div/div/div/div/div/div[2]/div[2]/div/div/div/div/div/input"
            )
            save_button = driver.find_element(
                By.XPATH,
                "/html/body/form/div[4]/div/div/div/div/div/div[2]/div[2]/div/div/div/div/ul/input"
            )

            if input_field.is_displayed() and save_button.is_displayed():
                bot_log("📝 Please enter the value:", user_id)
                input_value = bot_input("Enter value:", user_id)
                if input_value:
                    input_field.clear()
                    input_field.send_keys(input_value)
                    if not post_login_click_button(driver, save_button,
                                                   user_id):
                        raise Exception("Failed to click save button")
                    bot_log("✅ Value saved successfully!", user_id)
                    return True
                else:
                    bot_log("⚠️ No value entered", user_id)
                    return False
            else:
                bot_log(
                    "ℹ️ Form elements not visible. Data might have been saved already.",
                    user_id)
                return True

        except NoSuchElementException:
            bot_log(
                "ℹ️ Form elements not found. Data might have been saved already.",
                user_id)
            return True
        except Exception as e:
            bot_log(f"❌ Error handling form: {str(e)}", user_id)
            return False

    except Exception as e:
        bot_log(f"❌ Error during post-login operations: {str(e)}", user_id)
        return False
