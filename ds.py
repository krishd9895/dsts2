import os
import re
import time

import requests
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from logger import bot_logger, login_logger
from session_manager_headless import session_manager

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

bot_instances = {}
chat_ids = {}
user_inputs = {}
last_message_id = {}
status_logs = {}

website_url = os.getenv('URL')
rainfall_entry_url = os.getenv('RAINFALL_ENTRY_URL', website_url)

XPATHS = {
    "username": "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/div/input",
    "password": "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/div[2]/input",
    "captcha_img": "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/div[3]/div/img",
    "captcha_input": "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/div[4]/input",
    "login_button": "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/input",
    "login_failure": "/html/body/div[2]/h2",
    "login_success": [
        "/html/body/form/header/nav/div/div/div/div/div/ul/li/a/span",
        "/html/body/form/header/nav/div/div/div/div/div/ul/li/a",
    ],
}

POST_LOGIN_XPATHS = {
    "Page1_btn_path": "/html/body/form/div[4]/div/div/div/div/div/div/input",
    "input_field_path": "/html/body/form/div[4]/div/div/div/div/div/div/div[2]/div/div/div[15]/input",
    "save_button_path": "/html/body/form/div[4]/div/div/div/div/div/div/div[2]/div/div/div[19]/input",
}

RAPIDAPI_OCR_URL = "https://ocr-extract-text.p.rapidapi.com/ocr"
RAPIDAPI_KEYS = [
    key.strip()
    for key in os.getenv("RAPIDAPI_KEYS", "").split(",")
    if key.strip()
]
if not RAPIDAPI_KEYS and os.getenv("RAPIDAPI_KEY"):
    RAPIDAPI_KEYS = [os.getenv("RAPIDAPI_KEY").strip()]

LOCAL_TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")


def set_bot_instance(bot, chat_id):
    bot_instances[chat_id] = bot
    chat_ids[chat_id] = chat_id


def bot_log(message, user_id=None, reply_markup=None, parse_mode=None):
    if user_id in bot_instances and user_id in chat_ids:
        try:
            if user_id in last_message_id:
                try:
                    bot_instances[user_id].delete_message(chat_ids[user_id], last_message_id[user_id])
                except Exception:
                    pass

            sent_message = bot_instances[user_id].send_message(
                chat_ids[user_id],
                str(message),
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            last_message_id[user_id] = sent_message.message_id
            bot_logger.debug(f"Message sent to user {user_id}: {message}")
        except Exception as e:
            bot_logger.error(f"Failed to send message to bot: {e}")
            bot_logger.debug(f"Failed message content: {message}")
    else:
        bot_logger.debug(message)


def clear_status(user_id):
    if user_id in last_message_id:
        try:
            bot_instances[user_id].delete_message(chat_ids[user_id], last_message_id[user_id])
        except Exception:
            pass
        del last_message_id[user_id]


def bot_send_image(image_path, caption, user_id):
    if user_id in bot_instances and user_id in chat_ids:
        try:
            with open(image_path, 'rb') as photo:
                sent_message = bot_instances[user_id].send_photo(chat_ids[user_id], photo, caption=caption)
                last_message_id[user_id] = sent_message.message_id
        except Exception as e:
            bot_logger.error(f"Failed to send image to bot: {e}")


def update_status_message(message, user_id):
    if user_id in bot_instances and user_id in chat_ids:
        try:
            if user_id in last_message_id:
                bot_instances[user_id].edit_message_text(
                    chat_id=chat_ids[user_id],
                    message_id=last_message_id[user_id],
                    text=str(message),
                )
                return
        except Exception:
            if user_id in last_message_id:
                del last_message_id[user_id]

    bot_log(message, user_id)


def bot_input(prompt, user_id=None):
    if user_id in bot_instances and user_id in chat_ids:
        bot_instances[user_id].send_message(chat_ids[user_id], prompt)
        user_inputs[user_id] = None
        timeout = 60
        start_time = time.time()
        while user_inputs.get(user_id) is None:
            if time.time() - start_time > timeout:
                bot_log("⚠️ Input timeout. Please try again.", user_id)
                return None
            time.sleep(0.5)
        response = user_inputs[user_id]
        del user_inputs[user_id]
        return response
    return input(prompt)


def normalize_captcha_text(raw_text):
    return re.sub(r"[^A-Za-z0-9]", "", raw_text or "").strip()


def solve_captcha_locally(captcha_path, user_id):
    if Image is None or pytesseract is None:
        return None
    try:
        pytesseract.pytesseract.tesseract_cmd = LOCAL_TESSERACT_CMD
        text = pytesseract.image_to_string(
            Image.open(captcha_path),
            config="--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
        )
        text = normalize_captcha_text(text)
        if text:
            bot_logger.info(f"User {user_id}: Local OCR recognized Captcha: {text}")
            return text
    except Exception as local_error:
        bot_logger.warning(f"User {user_id}: Local OCR failed: {local_error}")
    return None


def solve_captcha_with_rapidapi(captcha_url, user_id):
    querystring = {"url": captcha_url}

    for api_key in RAPIDAPI_KEYS:
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "ocr-extract-text.p.rapidapi.com",
        }
        try:
            ocr_response = requests.get(RAPIDAPI_OCR_URL, headers=headers, params=querystring, timeout=30)
            if ocr_response.status_code == 200:
                data = ocr_response.json()
                captcha_text = normalize_captcha_text(data.get("text", ""))
                if captcha_text:
                    bot_logger.info(f"User {user_id}: RapidAPI recognized Captcha: {captcha_text}")
                    return captcha_text
                return None
            if ocr_response.status_code in [401, 403, 429]:
                continue
            return None
        except requests.exceptions.RequestException:
            return None

    return None


def handle_login_attempt(user_id, username, password):
    login_logger.info(f"Starting login attempt for user {user_id}")
    clear_status(user_id)

    try:
        session = session_manager.get_session(user_id)
        driver = session['driver']
    except Exception as e:
        login_logger.error(f"Failed to get session/driver: {str(e)}")
        bot_log("❌ Login failed: Could not initialize browser session", user_id)
        return False

    if not username or not password:
        bot_log("❌ Login failed: Invalid credentials", user_id)
        return False

    total_steps = 5
    current_step = 0
    update_status_message(f"⚙️ Attempting Login... ({current_step}/{total_steps})", user_id)

    success = automatic_login(driver, username, password, user_id, total_steps, current_step)
    login_logger.info(f"Login attempt result for user {user_id}: {'success' if success else 'failed'}")
    return success


def automatic_login(driver, username, password, user_id=None, total_steps=5, current_step=0):
    for _ in range(1):
        driver.get(website_url)
        time.sleep(2)

        if not enter_credentials(driver, username, password, user_id):
            return False
        current_step = 2
        update_status_message(f"⚙️ Attempting Login... ({current_step}/{total_steps})", user_id)

        captcha_text = process_captcha(driver, user_id)
        current_step = 3
        update_status_message(f"⚙️ Attempting Login... ({current_step}/{total_steps})", user_id)
        if not captcha_text:
            continue

        submit_login(driver, user_id)
        current_step = 4
        update_status_message(f"⚙️ Attempting Login... ({current_step}/{total_steps})", user_id)

        success, message = check_login_result(driver, user_id)
        if success:
            current_step = 5
            update_status_message(f"✅ LOGIN SUCCESSFUL! {message}", user_id)
            return True

        if "invalid" in message.lower() or "incorrect" in message.lower():
            bot_log(f"❌ {message}. Please try again with correct username and password.", user_id)
            return False

    return manual_login(driver, username, password, user_id, total_steps, current_step)


def manual_login(driver, username, password, user_id, total_steps=5, current_step=0):
    driver.get(website_url)
    current_step = 1
    update_status_message(f"⚙️ Attempting Login... ({current_step}/{total_steps})", user_id)
    time.sleep(2)

    if not enter_credentials(driver, username, password, user_id):
        return False
    current_step = 2
    update_status_message(f"⚙️ Attempting Login... ({current_step}/{total_steps})", user_id)

    captcha_text = None
    for _ in range(3):
        captcha_text = process_captcha_manual(driver, user_id)
        if captcha_text:
            break
        time.sleep(1)

    current_step = 3
    update_status_message(f"⚙️ Attempting Login... ({current_step}/{total_steps})", user_id)

    if not captcha_text:
        bot_log("❌ Failed to get captcha response from user", user_id)
        return False

    submit_login(driver, user_id)
    current_step = 4
    update_status_message(f"⚙️ Attempting Login... ({current_step}/{total_steps})", user_id)

    success, message = check_login_result(driver, user_id)
    if success:
        current_step = 5
        update_status_message(f"✅ LOGIN SUCCESSFUL! {message}", user_id)
        return True

    bot_log(f"❌ {message}", user_id)
    return False


def enter_credentials(driver, username, password, user_id):
    try:
        username_field = driver.find_element(By.XPATH, XPATHS["username"])
        password_field = driver.find_element(By.XPATH, XPATHS["password"])
        username_field.clear()
        password_field.clear()
        username_field.send_keys(username)
        password_field.send_keys(password)
        return True
    except Exception as e:
        bot_log(f"❌ Error entering credentials: {str(e)}", user_id)
        return False


def process_captcha(driver, user_id):
    try:
        captcha_element = driver.find_element(By.XPATH, XPATHS["captcha_img"])
        captcha_url = captcha_element.get_attribute("src")
        captcha_path = "captcha_auto.png"

        response = requests.get(captcha_url, timeout=30)
        response.raise_for_status()
        with open(captcha_path, 'wb') as f:
            f.write(response.content)

        captcha_text = solve_captcha_locally(captcha_path, user_id)
        if not captcha_text:
            captcha_text = solve_captcha_with_rapidapi(captcha_url, user_id)

        if captcha_text:
            captcha_input = driver.find_element(By.XPATH, XPATHS["captcha_input"])
            captcha_input.clear()
            captcha_input.send_keys(captcha_text)
            return captcha_text
        return None
    except Exception as e:
        bot_log(f"❌ Captcha processing failed: {str(e)}", user_id)
        return None


def process_captcha_manual(driver, user_id):
    try:
        captcha_element = driver.find_element(By.XPATH, XPATHS["captcha_img"])
        captcha_url = captcha_element.get_attribute("src")
        response = requests.get(captcha_url, timeout=30)
        captcha_path = "captcha_manual.png"

        with open(captcha_path, 'wb') as f:
            f.write(response.content)

        if not os.path.exists(captcha_path):
            bot_log("❌ Failed to save captcha image", user_id)
            return None

        bot_send_image(captcha_path, "📝 Please enter the captcha text shown in the image:", user_id)
        captcha_text = bot_input("Type the captcha text:", user_id)

        if captcha_text:
            captcha_input = driver.find_element(By.XPATH, XPATHS["captcha_input"])
            captcha_input.clear()
            captcha_input.send_keys(captcha_text)
            return captcha_text
        return None
    except Exception as e:
        bot_log(f"❌ Manual captcha failed: {str(e)}", user_id)
        return None


def submit_login(driver, user_id):
    try:
        driver.find_element(By.XPATH, XPATHS["login_button"]).click()
        bot_logger.info(f"User {user_id}: Submitting login...")
        time.sleep(5)
    except Exception as e:
        bot_log(f"❌ Login submission failed: {str(e)}", user_id)


def check_login_result(driver, user_id):
    try:
        error_element = driver.find_elements(By.XPATH, XPATHS["login_failure"])
        if error_element:
            error_text = error_element[0].text.strip()
            return False, f"Login Failed: {error_text}"

        for path in XPATHS["login_success"]:
            elements = driver.find_elements(By.XPATH, path)
            if elements:
                success_text = elements[0].text.strip()
                return True, success_text if success_text else "Welcome!"

        return False, "Unknown login status - no success elements found"
    except Exception as e:
        return False, f"Login check failed: {str(e)}"


def post_login_click_button(driver, button_element, user_id):
    button_text = button_element.text.strip() or button_element.get_attribute('value')

    try:
        driver.execute_script("arguments[0].click();", button_element)
        bot_logger.info(f"User {user_id}: hit '{button_text}' using JavaScript")
        return True
    except Exception:
        pass

    try:
        from selenium.webdriver.common.action_chains import ActionChains

        actions = ActionChains(driver)
        actions.move_to_element(button_element).click().perform()
        bot_logger.info(f"User {user_id}: hit '{button_text}' using Action Chains")
        return True
    except Exception:
        pass

    try:
        driver.execute_script(
            """
            arguments[0].style.opacity = '1';
            arguments[0].style.display = 'block';
            arguments[0].style.visibility = 'visible';
        """,
            button_element,
        )
        button_element.click()
        return True
    except Exception as e:
        bot_logger.error(f"User {user_id}: failed to click '{button_text}': {str(e)}")

    return False


def extract_form_data(driver, user_id):
    try:
        message_lines = ["\n" + "=" * 40, "FORM INFORMATION".center(40), "=" * 40, "\n📝 Form Data:"]

        input_elements = driver.find_elements(By.TAG_NAME, "input")
        for element in input_elements:
            field_id = element.get_attribute('id') or ''
            value = element.get_attribute('value')
            readonly = element.get_attribute('readonly')

            if any(
                substring in field_id.lower()
                for substring in [
                    "event",
                    "viewstate",
                    "scroll",
                    "validation",
                    "clientstate",
                    "hidden",
                    "logout",
                    "pwchange",
                ]
            ):
                continue

            label_elements = driver.find_elements(By.XPATH, f"//label[@for='{field_id}']")
            label = label_elements[0].text if label_elements else field_id
            label = label.replace("HomeContentPlaceHolder_txt", "")
            status = "🔒" if readonly else "✏️"
            message_lines.append(f"{status} {label}: {value}")

        bot_log("\n".join(message_lines), user_id)
    except Exception as e:
        bot_log(f"❌ Error extracting form information: {str(e)}", user_id)


def post_login_operations(user_id, value_to_enter=None):
    clear_status(user_id)
    session = session_manager.get_session(user_id)
    driver = session['driver']

    total_steps = 2
    current_step = 0
    update_status_message(f"⚙️ Processing... ({current_step}/{total_steps})", user_id)

    try:
        for file in ["captcha_auto.png", "captcha_manual.png"]:
            if os.path.exists(file):
                os.remove(file)

        page1_btn = driver.find_element(By.XPATH, POST_LOGIN_XPATHS["Page1_btn_path"])
        if not post_login_click_button(driver, page1_btn, user_id):
            raise Exception("Failed to click initial button")
        time.sleep(2)
        current_step += 1
        update_status_message(f"⚙️ Processing... ({current_step}/{total_steps})", user_id)

        if rainfall_entry_url:
            driver.get(rainfall_entry_url)
            time.sleep(2)
        current_step += 1
        update_status_message(f"⚙️ Processing... ({current_step}/{total_steps})", user_id)

        extract_form_data(driver, user_id)
        if user_id in last_message_id:
            del last_message_id[user_id]

        try:
            input_field = driver.find_element(By.XPATH, POST_LOGIN_XPATHS["input_field_path"])
            save_button = driver.find_element(By.XPATH, POST_LOGIN_XPATHS["save_button_path"])

            if input_field.is_displayed() and save_button.is_displayed():
                input_value = value_to_enter
                if input_value is None:
                    input_value = bot_input("📝 Please enter the value:", user_id)

                if input_value:
                    input_field.clear()
                    input_field.send_keys(input_value)
                    if not post_login_click_button(driver, save_button, user_id):
                        raise Exception("Failed to click save button")
                    bot_log(f"✅ Value '{input_value}' saved successfully!", user_id)
                    return 'success'

                bot_log("⚠️ No value entered, operation cancelled.", user_id)
                return 'cancelled'

            bot_log("ℹ️ Data might have been saved already. Save button not found.", user_id)
            return 'already_saved'

        except NoSuchElementException:
            bot_log("ℹ️ Data might have been saved already.", user_id)
            return 'already_saved'
        except Exception as e:
            bot_log(f"❌ Error handling form: {str(e)}", user_id)
            return 'failure'

    except Exception as e:
        bot_log(f"❌ Error during post-login operations: {str(e)}", user_id)
        return 'failure'
