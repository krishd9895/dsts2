import os
import threading
import time
from datetime import datetime

import telebot
from pytz import timezone
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

import ds
import schedule
from db import (
    get_credential_by_username,
    get_user_usernames,
    remove_all_user_credentials,
    remove_user_credential,
    save_user_credentials,
)
from logger import (
    BOT_OWNER_ID,
    MAX_LOG_LINES,
    bot_logger,
    log_file,
    trim_log_file,
    user_interaction_logger,
)
from session_manager_headless import session_manager

API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

bot_logger.info('Starting bot...')


def trim_logs_periodically():
    while True:
        time.sleep(3600)
        trim_log_file(log_file, MAX_LOG_LINES)
        bot_logger.info('Log file trimmed to keep latest lines')


trim_thread = threading.Thread(target=trim_logs_periodically, daemon=True)
trim_thread.start()

ds.user_inputs = {}
user_states = {}


def create_credentials_keyboard(user_id):
    keyboard = InlineKeyboardMarkup()
    usernames = get_user_usernames(str(user_id))
    if not usernames:
        return keyboard
    for username in usernames:
        keyboard.add(InlineKeyboardButton(username, callback_data=f"login_{username}"))
    keyboard.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    return keyboard


def create_rfentry_credentials_keyboard(user_id):
    keyboard = InlineKeyboardMarkup()
    usernames = get_user_usernames(str(user_id))
    if not usernames:
        return keyboard
    for username in usernames:
        keyboard.add(InlineKeyboardButton(username, callback_data=f"rfentry_{username}"))
    keyboard.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    return keyboard


def create_remove_credentials_keyboard(user_id):
    keyboard = InlineKeyboardMarkup()
    usernames = get_user_usernames(str(user_id))
    for username in usernames:
        keyboard.add(InlineKeyboardButton(f"Remove {username}", callback_data=f"remove_{username}"))
    keyboard.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    return keyboard


def create_settings_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("View Credentials", callback_data="view_creds"),
        InlineKeyboardButton("Add Credential", callback_data="add_cred"),
    )
    keyboard.row(
        InlineKeyboardButton("Remove Credential", callback_data="remove_cred"),
        InlineKeyboardButton("Remove All", callback_data="remove_all"),
    )
    keyboard.row(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    return keyboard


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    user_interaction_logger.info(f"User {user_id} sent /start: {message.text}")
    if session_manager.is_user_busy(user_id):
        sent_msg = bot.send_message(
            user_id,
            "⚠️ Session is already active. Please wait for the current operation to complete or use /logout to reset.",
        )
        ds.last_message_id[user_id] = sent_msg.message_id
        return

    ds.clear_status(user_id)
    ds.set_bot_instance(bot, user_id)
    session_manager.get_session(user_id)
    sent_msg = bot.send_message(
        user_id,
        "👋 Welcome! I'm ready to help you. Use /login to begin or /settings to manage your credentials.",
    )
    ds.last_message_id[user_id] = sent_msg.message_id


@bot.message_handler(commands=['login'])
def handle_login(message):
    user_id = message.chat.id

    if session_manager.is_user_busy(user_id):
        sent_msg = bot.send_message(
            user_id,
            "⚠️ Session is already active. Please wait for the current operation to complete or use /logout to reset.",
        )
        ds.last_message_id[user_id] = sent_msg.message_id
        return

    if not session_manager.can_attempt_login(user_id):
        sent_msg = bot.send_message(user_id, "⚠️ Please wait 5 seconds before attempting to login again.")
        ds.last_message_id[user_id] = sent_msg.message_id
        return

    usernames = get_user_usernames(str(user_id))
    if not usernames:
        keyboard = create_settings_keyboard()
        sent_msg = bot.send_message(
            user_id,
            "❌ No saved credentials found. Use the menu below to add your credentials:",
            reply_markup=keyboard,
        )
        ds.last_message_id[user_id] = sent_msg.message_id
        return

    keyboard = create_credentials_keyboard(user_id)
    sent_msg = bot.send_message(user_id, "Select a username to login:", reply_markup=keyboard)
    ds.last_message_id[user_id] = sent_msg.message_id


@bot.message_handler(commands=['rfentry'])
def handle_rf_entry(message):
    user_id = message.chat.id
    ds.set_bot_instance(bot, user_id)

    now_ist_time = datetime.now(timezone('Asia/Kolkata')).time()
    if not (schedule.SCHEDULE_START_TIME <= now_ist_time <= schedule.SCHEDULE_END_TIME):
        ds.bot_log(
            f"❌ Scheduling is only allowed between {schedule.SCHEDULE_START_TIME.strftime('%I:%M %p')} and {schedule.SCHEDULE_END_TIME.strftime('%I:%M %p')} IST.",
            user_id,
        )
        return

    if session_manager.is_user_busy(user_id):
        sent_msg = bot.send_message(user_id, "⚠️ A session is already active. Please wait or use /logout.")
        ds.last_message_id[user_id] = sent_msg.message_id
        return

    usernames = get_user_usernames(str(user_id))
    if not usernames:
        keyboard = create_settings_keyboard()
        sent_msg = bot.send_message(
            user_id,
            "❌ No saved credentials found. Please add credentials first.",
            reply_markup=keyboard,
        )
        ds.last_message_id[user_id] = sent_msg.message_id
        return

    keyboard = create_rfentry_credentials_keyboard(user_id)
    sent_msg = bot.send_message(
        user_id,
        "Select a username to schedule an RF entry for 8:30 AM IST:",
        reply_markup=keyboard,
    )
    ds.last_message_id[user_id] = sent_msg.message_id


@bot.message_handler(commands=['values'])
def handle_values(message):
    user_id = message.chat.id
    ds.set_bot_instance(bot, user_id)

    scheduled_jobs = schedule.get_scheduled_jobs_for_user(user_id)
    if not scheduled_jobs:
        ds.bot_log("ℹ️ You have no scheduled entries.", user_id)
        return

    keyboard = InlineKeyboardMarkup()
    message_text = "Your currently scheduled entries:\n\n"
    for job in scheduled_jobs:
        username = job['username']
        value = job['value']
        message_text += f"👤 **Username:** `{username}`\n💾 **Value:** `{value}`\n\n"
        keyboard.add(
            InlineKeyboardButton(
                f"❌ Cancel for {username}",
                callback_data=f"cancel_schedule_{username}",
            )
        )

    keyboard.add(InlineKeyboardButton("✅ Close", callback_data="cancel"))
    ds.bot_log(message_text, user_id, reply_markup=keyboard, parse_mode="Markdown")


@bot.message_handler(commands=['settings'])
def handle_settings(message):
    user_id = message.chat.id
    keyboard = create_settings_keyboard()
    sent_msg = bot.send_message(user_id, "Credential Management Settings:", reply_markup=keyboard)
    ds.last_message_id[user_id] = sent_msg.message_id


@bot.message_handler(commands=['logout'])
def handle_logout(message):
    user_id = message.chat.id
    ds.set_bot_instance(bot, user_id)
    ds.clear_status(user_id)
    session_manager.close_session(user_id)
    sent_msg = bot.send_message(user_id, '👋 Logged out successfully.')
    ds.last_message_id[user_id] = sent_msg.message_id


@bot.message_handler(commands=['logs'])
def handle_logs(message):
    user_id = message.chat.id
    if user_id != BOT_OWNER_ID:
        sent_msg = bot.send_message(user_id, "⚠️ This command is only available to the bot owner.")
        ds.last_message_id[user_id] = sent_msg.message_id
        return

    try:
        trim_log_file(log_file, MAX_LOG_LINES)
        with open(log_file, 'rb') as f:
            sent_msg = bot.send_document(user_id, f, caption="📋 Here are the latest logs.")
            ds.last_message_id[user_id] = sent_msg.message_id
    except Exception as e:
        sent_msg = bot.send_message(user_id, f"❌ Error sending logs: {str(e)}")
        ds.last_message_id[user_id] = sent_msg.message_id


@bot.message_handler(commands=['operations'])
def handle_operations(message):
    user_id = message.chat.id
    if user_id not in session_manager.sessions or not session_manager.sessions[user_id].get('driver'):
        usernames = get_user_usernames(str(user_id))
        if not usernames:
            keyboard = create_settings_keyboard()
            sent_msg = bot.send_message(
                user_id,
                "❌ No saved credentials found. Use the menu below to add your credentials:",
                reply_markup=keyboard,
            )
        else:
            keyboard = create_credentials_keyboard(user_id)
            sent_msg = bot.send_message(
                user_id,
                "⚠️ Please login first to perform operations.",
                reply_markup=keyboard,
            )
        ds.last_message_id[user_id] = sent_msg.message_id
        return

    if session_manager.is_user_busy(user_id):
        sent_msg = bot.send_message(
            user_id,
            "⚠️ Session is already active. Please wait for the current operation to complete or use /logout to reset.",
        )
        ds.last_message_id[user_id] = sent_msg.message_id
        return

    ds.clear_status(user_id)
    ds.set_bot_instance(bot, user_id)
    session_manager.set_user_busy(user_id, True)
    try:
        ds.post_login_operations(user_id)
    finally:
        session_manager.set_user_busy(user_id, False)


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    data = call.data

    if data == "cancel":
        bot.answer_callback_query(call.id, "Operation cancelled")
        try:
            bot.delete_message(user_id, call.message.message_id)
        except Exception:
            pass
        ds.clear_status(user_id)
        sent_msg = bot.send_message(user_id, "Operation cancelled.")
        ds.last_message_id[user_id] = sent_msg.message_id
        if user_id in user_states:
            del user_states[user_id]
        return

    if data.startswith("cancel_schedule_"):
        username_to_cancel = data[16:]
        bot.answer_callback_query(call.id, f"Cancelling schedule for {username_to_cancel}...")
        schedule.clear_job(user_id, username_to_cancel)
        try:
            bot.delete_message(user_id, call.message.message_id)
        except Exception:
            pass
        ds.bot_log(f"✅ The scheduled entry for {username_to_cancel} has been cancelled.", user_id)
        return

    if data.startswith("rfentry_"):
        username = data[8:]
        bot.answer_callback_query(call.id, f"Scheduling for {username}...")
        try:
            bot.delete_message(user_id, call.message.message_id)
        except Exception:
            pass

        ds.set_bot_instance(bot, user_id)
        value = ds.bot_input(f"Please enter the value to be submitted for {username}:", user_id)

        if value:
            schedule.schedule_rf_entry(user_id, username, value)
            ds.bot_log(
                f"✅ RF entry for {username} with value '{value}' has been scheduled. It will run after {schedule.RUN_AFTER_TIME.strftime('%I:%M %p')} IST.",
                user_id,
            )
        else:
            ds.bot_log("⚠️ Value not provided. Scheduling cancelled.", user_id)
        return

    if data.startswith("login_"):
        username = data[6:]
        bot.answer_callback_query(call.id, f"Attempting to login with {username}...")
        try:
            bot.delete_message(user_id, call.message.message_id)
        except Exception:
            pass

        credentials = get_credential_by_username(str(user_id), username)
        if not credentials:
            sent_msg = bot.send_message(user_id, f"❌ Credentials not found for {username}")
            ds.last_message_id[user_id] = sent_msg.message_id
            return

        ds.clear_status(user_id)
        ds.set_bot_instance(bot, user_id)

        try:
            session = session_manager.get_session(user_id)
            if not session:
                sent_msg = bot.send_message(user_id, "❌ Failed to initialize session")
                ds.last_message_id[user_id] = sent_msg.message_id
                return

            session_manager.set_user_busy(user_id, True)
            success = ds.handle_login_attempt(user_id, credentials["username"], credentials["password"])
            if not success:
                session_manager.close_session(user_id)
            else:
                ds.post_login_operations(user_id)
                session_manager.close_session(user_id)
        except Exception as e:
            sent_msg = bot.send_message(user_id, f"❌ Error during login: {str(e)}")
            ds.last_message_id[user_id] = sent_msg.message_id
            session_manager.close_session(user_id)
        finally:
            session_manager.set_user_busy(user_id, False)
        return

    if data == "view_creds":
        try:
            bot.delete_message(user_id, call.message.message_id)
        except Exception:
            pass

        usernames = get_user_usernames(str(user_id))
        if usernames:
            keyboard = InlineKeyboardMarkup()
            creds_list = "Your saved credentials:\n" + "\n".join([f"- {username}" for username in usernames])
            keyboard.add(InlineKeyboardButton("❌ Close", callback_data="cancel"))
            ds.clear_status(user_id)
            sent_msg = bot.send_message(user_id, creds_list, reply_markup=keyboard)
            ds.last_message_id[user_id] = sent_msg.message_id
        else:
            ds.clear_status(user_id)
            sent_msg = bot.send_message(user_id, "No credentials found.")
            ds.last_message_id[user_id] = sent_msg.message_id
        bot.answer_callback_query(call.id)
        return

    if data == "add_cred":
        try:
            bot.delete_message(user_id, call.message.message_id)
        except Exception:
            pass

        user_states[user_id] = {"state": "waiting_username"}
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
        bot.answer_callback_query(call.id)
        ds.clear_status(user_id)
        sent_msg = bot.send_message(user_id, "Please enter your username:", reply_markup=keyboard)
        ds.last_message_id[user_id] = sent_msg.message_id
        return

    if data == "remove_cred":
        try:
            bot.delete_message(user_id, call.message.message_id)
        except Exception:
            pass

        keyboard = create_remove_credentials_keyboard(user_id)
        if keyboard.keyboard:
            bot.answer_callback_query(call.id)
            ds.clear_status(user_id)
            sent_msg = bot.send_message(user_id, "Select credential to remove:", reply_markup=keyboard)
            ds.last_message_id[user_id] = sent_msg.message_id
        else:
            ds.clear_status(user_id)
            sent_msg = bot.send_message(user_id, "No credentials found to remove.")
            ds.last_message_id[user_id] = sent_msg.message_id
            bot.answer_callback_query(call.id)
        return

    if data.startswith("remove_"):
        try:
            bot.delete_message(user_id, call.message.message_id)
        except Exception:
            pass

        username = data[7:]
        if remove_user_credential(str(user_id), username):
            bot.answer_callback_query(call.id, f"Removed credentials for {username}")
            keyboard = create_settings_keyboard()
            ds.clear_status(user_id)
            sent_msg = bot.send_message(user_id, f"✅ Removed credentials for {username}", reply_markup=keyboard)
            ds.last_message_id[user_id] = sent_msg.message_id
        else:
            ds.clear_status(user_id)
            sent_msg = bot.send_message(user_id, f"❌ Failed to remove credentials for {username}")
            ds.last_message_id[user_id] = sent_msg.message_id
            bot.answer_callback_query(call.id)
        return

    if data == "remove_all":
        try:
            bot.delete_message(user_id, call.message.message_id)
        except Exception:
            pass

        if remove_all_user_credentials(str(user_id)):
            bot.answer_callback_query(call.id, "All credentials removed")
            keyboard = create_settings_keyboard()
            ds.clear_status(user_id)
            sent_msg = bot.send_message(
                user_id,
                "✅ All credentials have been removed.",
                reply_markup=keyboard,
            )
            ds.last_message_id[user_id] = sent_msg.message_id
        else:
            ds.clear_status(user_id)
            sent_msg = bot.send_message(user_id, "Failed to remove credentials")
            ds.last_message_id[user_id] = sent_msg.message_id
            bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda message: True)
def handle_user_input(message):
    user_id = message.chat.id
    text = message.text

    try:
        bot.delete_message(user_id, message.message_id)
    except Exception:
        pass

    if user_id in ds.user_inputs and ds.user_inputs[user_id] is None:
        ds.user_inputs[user_id] = text
        if hasattr(message, 'reply_to_message') and message.reply_to_message:
            try:
                bot.delete_message(user_id, message.reply_to_message.message_id)
            except Exception:
                pass
        return

    if user_id in user_states:
        state = user_states[user_id].get('state')
        if state == 'waiting_username':
            user_states[user_id] = {'state': 'waiting_password', 'username': text}
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
            sent_msg = bot.send_message(user_id, "Please enter your password:", reply_markup=keyboard)
            ds.last_message_id[user_id] = sent_msg.message_id
        elif state == 'waiting_password':
            username = user_states[user_id].get('username')
            keyboard = create_settings_keyboard()
            if save_user_credentials(str(user_id), username, text):
                sent_msg = bot.send_message(user_id, f"✅ Credentials saved for {username}", reply_markup=keyboard)
            else:
                sent_msg = bot.send_message(user_id, "❌ Failed to save credentials", reply_markup=keyboard)
            ds.last_message_id[user_id] = sent_msg.message_id
            del user_states[user_id]


if __name__ == '__main__':
    bot_logger.info('Starting bot...')
    bot_logger.info('Starting scheduler...')
    schedule.start_scheduler()
    bot.infinity_polling()
