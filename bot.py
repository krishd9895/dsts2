import telebot
import ds
import logging
import os
from session_manager_headless import session_manager
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from db import (
    save_user_credentials,
    get_user_usernames,
    get_credential_by_username,
    remove_user_credential,
    remove_all_user_credentials
)
from logger import bot_logger, user_interaction_logger
from webserver import keep_alive

# Initialize bot with your token
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

# Configure logging
from logger import (
    bot_logger, user_interaction_logger, login_logger, session_logger,
    BOT_OWNER_ID, MAX_LOG_LINES, trim_log_file, log_file
)

# Log bot startup
bot_logger.info('Starting bot...')

# Set up periodic log trimming
import threading
import time

def trim_logs_periodically():
    while True:
        time.sleep(3600)  # Check every hour
        trim_log_file(log_file, MAX_LOG_LINES)
        bot_logger.info('Log file trimmed to keep latest lines')

# Start log trimming thread
trim_thread = threading.Thread(target=trim_logs_periodically, daemon=True)
trim_thread.start()

# User input handling
ds.user_inputs = {}

# User state tracking
user_states = {}

def create_credentials_keyboard(user_id):
    """Create inline keyboard with user's credentials."""
    keyboard = InlineKeyboardMarkup()
    usernames = get_user_usernames(str(user_id))
    if not usernames:
        return keyboard
    for username in usernames:
        keyboard.add(InlineKeyboardButton(username, callback_data=f"login_{username}"))
    keyboard.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    return keyboard

def create_remove_credentials_keyboard(user_id):
    """Create inline keyboard for removing credentials."""
    keyboard = InlineKeyboardMarkup()
    usernames = get_user_usernames(str(user_id))
    for username in usernames:
        keyboard.add(InlineKeyboardButton(f"Remove {username}", callback_data=f"remove_{username}"))
    keyboard.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    return keyboard

def create_settings_keyboard():
    """Create inline keyboard for settings."""
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("View Credentials", callback_data="view_creds"),
        InlineKeyboardButton("Add Credential", callback_data="add_cred")
    )
    keyboard.row(
        InlineKeyboardButton("Remove Credential", callback_data="remove_cred"),
        InlineKeyboardButton("Remove All", callback_data="remove_all")
    )
    keyboard.row(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    return keyboard

# Start command handler
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    user_interaction_logger.info(f"User {user_id} sent /start: {message.text}")
    if session_manager.is_user_busy(user_id):
        sent_msg = bot.send_message(user_id,
                     "⚠️ Session is already active. Please wait for the current operation to complete or use /logout to reset.")
        ds.last_message_id[user_id] = sent_msg.message_id
        user_interaction_logger.info(f"Bot to {user_id}: Session is already active.")
        return

    ds.clear_status(user_id)  # Clear any existing status
    ds.set_bot_instance(bot, user_id)
    session_manager.get_session(user_id)
    sent_msg = bot.send_message(user_id, '👋 Welcome! I\'m ready to help you. Use /login to begin or /settings to manage your credentials.')
    ds.last_message_id[user_id] = sent_msg.message_id
    user_interaction_logger.info(f"Bot to {user_id}: 👋 Welcome! I'm ready to help you. Use /login to begin or /settings to manage your credentials.")

# Login command handler
@bot.message_handler(commands=['login'])
def handle_login(message):
    user_id = message.chat.id
    user_interaction_logger.info(f"User {user_id} sent /login: {message.text}")
    
    if session_manager.is_user_busy(user_id):
        sent_msg = bot.send_message(user_id,
                     "⚠️ Session is already active. Please wait for the current operation to complete or use /logout to reset.")
        ds.last_message_id[user_id] = sent_msg.message_id
        user_interaction_logger.info(f"Bot to {user_id}: Session is already active.")
        return

    if not session_manager.can_attempt_login(user_id):
        sent_msg = bot.send_message(user_id,
                     "⚠️ Please wait 5 seconds before attempting to login again.")
        ds.last_message_id[user_id] = sent_msg.message_id
        user_interaction_logger.info(f"Bot to {user_id}: Login cooldown active.")
        return

    # Check for credentials before creating keyboard
    usernames = get_user_usernames(str(user_id))
    user_interaction_logger.info(f"Found {len(usernames)} credentials for user {user_id}")
    
    if not usernames:
        keyboard = create_settings_keyboard()
        sent_msg = bot.send_message(user_id, "❌ No saved credentials found. Use the menu below to add your credentials:", reply_markup=keyboard)
        ds.last_message_id[user_id] = sent_msg.message_id
        user_interaction_logger.info(f"Bot to {user_id}: No saved credentials, showing settings menu.")
        return

    keyboard = create_credentials_keyboard(user_id)
    sent_msg = bot.send_message(user_id, "Select a username to login:", reply_markup=keyboard)
    ds.last_message_id[user_id] = sent_msg.message_id
    user_interaction_logger.info(f"Bot to {user_id}: Showing credential selection keyboard with {len(usernames)} options.")

# Settings command handler
@bot.message_handler(commands=['settings'])
def handle_settings(message):
    user_id = message.chat.id
    user_interaction_logger.info(f"User {user_id} sent /settings: {message.text}")
    keyboard = create_settings_keyboard()
    sent_msg = bot.send_message(user_id, "Credential Management Settings:", reply_markup=keyboard)
    ds.last_message_id[user_id] = sent_msg.message_id
    user_interaction_logger.info(f"Bot to {user_id}: Credential Management Settings:")

# Logout command handler
@bot.message_handler(commands=['logout'])
def handle_logout(message):
    user_id = message.chat.id
    user_interaction_logger.info(f"User {user_id} sent /logout: {message.text}")
    ds.clear_status(user_id)  # Clear any existing status
    session_manager.close_session(user_id)
    sent_msg = bot.send_message(user_id, '👋 Logged out successfully.')
    ds.last_message_id[user_id] = sent_msg.message_id
    user_interaction_logger.info(f"Bot to {user_id}: 👋 Logged out successfully.")

# Logs command handler
@bot.message_handler(commands=['logs'])
def handle_logs(message):
    user_id = message.chat.id
    user_interaction_logger.info(f"User {user_id} sent /logs: {message.text}")
    
    if user_id != BOT_OWNER_ID:
        sent_msg = bot.send_message(user_id, "⚠️ This command is only available to the bot owner.")
        ds.last_message_id[user_id] = sent_msg.message_id
        user_interaction_logger.info(f"Bot to {user_id}: Command not available - not owner")
        return
    
    try:
        # Trim logs before sending
        trim_log_file(log_file, MAX_LOG_LINES)
        
        # Send the log file
        with open(log_file, 'rb') as f:
            sent_msg = bot.send_document(user_id, f, caption="📋 Here are the latest logs.")
            ds.last_message_id[user_id] = sent_msg.message_id
            user_interaction_logger.info(f"Bot to {user_id}: Sent log file")
    except Exception as e:
        sent_msg = bot.send_message(user_id, f"❌ Error sending logs: {str(e)}")
        ds.last_message_id[user_id] = sent_msg.message_id
        user_interaction_logger.error(f"Error sending logs to owner: {str(e)}")

# Operations command handler
@bot.message_handler(commands=['operations'])
def handle_operations(message):
    user_id = message.chat.id
    user_interaction_logger.info(f"User {user_id} sent /operations: {message.text}")
    
    # Check if user has an active session
    if user_id not in session_manager.sessions or not session_manager.sessions[user_id].get('driver'):
        usernames = get_user_usernames(str(user_id))
        if not usernames:
            keyboard = create_settings_keyboard()
            sent_msg = bot.send_message(user_id, "❌ No saved credentials found. Use the menu below to add your credentials:", reply_markup=keyboard)
        else:
            keyboard = create_credentials_keyboard(user_id)
            sent_msg = bot.send_message(user_id, "⚠️ Please login first to perform operations.", reply_markup=keyboard)
        ds.last_message_id[user_id] = sent_msg.message_id
        user_interaction_logger.info(f"Bot to {user_id}: Please login first to perform operations.")
        return

    if session_manager.is_user_busy(user_id):
        sent_msg = bot.send_message(user_id,
                     "⚠️ Session is already active. Please wait for the current operation to complete or use /logout to reset.")
        ds.last_message_id[user_id] = sent_msg.message_id
        user_interaction_logger.info(f"Bot to {user_id}: Session is already active.")
        return

    ds.clear_status(user_id)  # Clear any existing status
    ds.set_bot_instance(bot, user_id)
    session_manager.set_user_busy(user_id, True)
    try:
        ds.post_login_operations(user_id)
    except Exception as e:
        sent_msg = bot.send_message(user_id, "⚠️ Please login first to perform operations.")
        ds.last_message_id[user_id] = sent_msg.message_id
        user_interaction_logger.info(f"Bot to {user_id}: Please login first to perform operations.")
    finally:
        session_manager.set_user_busy(user_id, False)

# Callback query handler
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    data = call.data
    user_interaction_logger.info(f"User {user_id} callback: {data}")

    if data == "cancel":
        bot.answer_callback_query(call.id, "Operation cancelled")
        # Delete the message containing the cancel button
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass
        ds.clear_status(user_id)  # Clear any existing status message
        sent_msg = bot.send_message(user_id, "Operation cancelled.")
        ds.last_message_id[user_id] = sent_msg.message_id
        user_interaction_logger.info(f"Bot to {user_id}: Operation cancelled.")
        if user_id in user_states:
            del user_states[user_id]
        return

    if data.startswith("login_"):
        # Get the full username by removing just the 'login_' prefix
        username = data[6:]
        bot_logger.info(f"Login button clicked for user {user_id} with username {username}")
        bot.answer_callback_query(call.id, f"Attempting to login with {username}...")
        user_interaction_logger.info(f"Bot to {user_id}: Attempting to login with {username}...")
        
        # Delete the message containing the username button
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass

        try:
            credentials = get_credential_by_username(str(user_id), username)
            if not credentials:
                bot_logger.warning(f"No credentials found for user {user_id} with username {username}")
                ds.clear_status(user_id)  # Clear any existing status message
                sent_msg = bot.send_message(user_id, f"❌ Credentials not found for {username}")
                ds.last_message_id[user_id] = sent_msg.message_id
                user_interaction_logger.info(f"Bot to {user_id}: ❌ Credentials not found for {username}")
                return
                
            bot_logger.debug(f"Credentials found for user {user_id}")
            ds.clear_status(user_id)
            ds.set_bot_instance(bot, user_id)
            
            try:
                # Initialize session first
                bot_logger.debug(f"Initializing session for user {user_id}")
                session = session_manager.get_session(user_id)
                if not session:
                    bot_logger.error(f"Failed to initialize session for user {user_id}")
                    sent_msg = bot.send_message(user_id, f"❌ Failed to initialize session")
                    ds.last_message_id[user_id] = sent_msg.message_id
                    user_interaction_logger.info(f"Bot to {user_id}: ❌ Failed to initialize session")
                    return
                
                bot_logger.debug(f"Session initialized successfully for user {user_id}")
                session_manager.set_user_busy(user_id, True)
                
                success = ds.handle_login_attempt(user_id, credentials["username"], credentials["password"])
                if not success:
                    bot_logger.warning(f"Login failed for user {user_id} with username {username}")
                    session_manager.close_session(user_id)
                    sent_msg = bot.send_message(user_id, f"❌ Login failed for {username}")
                    ds.last_message_id[user_id] = sent_msg.message_id
                    user_interaction_logger.info(f"Bot to {user_id}: ❌ Login failed for {username}")
                else:
                    bot_logger.info(f"Login successful for user {user_id} with username {username}")
                    sent_msg = bot.send_message(user_id, f"✅ Successfully logged in as {username}")
                    ds.last_message_id[user_id] = sent_msg.message_id
                    user_interaction_logger.info(f"Bot to {user_id}: ✅ Successfully logged in as {username}")
            except Exception as e:
                bot_logger.error(f"Error during login for user {user_id}: {str(e)}")
                sent_msg = bot.send_message(user_id, f"❌ Error during login: {str(e)}")
                ds.last_message_id[user_id] = sent_msg.message_id
                user_interaction_logger.info(f"Bot to {user_id}: ❌ Error during login: {str(e)}")
                session_manager.close_session(user_id)
            finally:
                session_manager.set_user_busy(user_id, False)
        except Exception as e:
            bot_logger.error(f"Error handling login callback for user {user_id}: {str(e)}")
            sent_msg = bot.send_message(user_id, f"❌ Internal error occurred")
            ds.last_message_id[user_id] = sent_msg.message_id
            user_interaction_logger.info(f"Bot to {user_id}: ❌ Internal error occurred")

    elif data == "view_creds":
        # Delete the message containing the view credentials button
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass

        usernames = get_user_usernames(str(user_id))
        if usernames:
            keyboard = InlineKeyboardMarkup()
            creds_list = "Your saved credentials:\n" + "\n".join([f"- {username}" for username in usernames])
            keyboard.add(InlineKeyboardButton("❌ Close", callback_data="cancel"))
            bot.answer_callback_query(call.id)
            ds.clear_status(user_id)  # Clear any existing status message
            sent_msg = bot.send_message(user_id, creds_list, reply_markup=keyboard)
            ds.last_message_id[user_id] = sent_msg.message_id
            user_interaction_logger.info(f"Bot to {user_id}: {creds_list}")
        else:
            ds.clear_status(user_id)  # Clear any existing status message
            sent_msg = bot.send_message(user_id, "No credentials found.")
            ds.last_message_id[user_id] = sent_msg.message_id
            bot.answer_callback_query(call.id)
            user_interaction_logger.info(f"Bot to {user_id}: No credentials found.")

    elif data == "add_cred":
        # Delete the message containing the add credential button
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass

        user_states[user_id] = {"state": "waiting_username"}
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
        bot.answer_callback_query(call.id)
        ds.clear_status(user_id)  # Clear any existing status message
        sent_msg = bot.send_message(user_id, "Please enter your username:", reply_markup=keyboard)
        ds.last_message_id[user_id] = sent_msg.message_id
        user_interaction_logger.info(f"Bot to {user_id}: Please enter your username:")

    elif data == "remove_cred":
        # Delete the message containing the remove credential button
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass

        keyboard = create_remove_credentials_keyboard(user_id)
        if keyboard.keyboard:  # Check if there are any credentials
            bot.answer_callback_query(call.id)
            ds.clear_status(user_id)  # Clear any existing status message
            sent_msg = bot.send_message(user_id, "Select credential to remove:", reply_markup=keyboard)
            ds.last_message_id[user_id] = sent_msg.message_id
            user_interaction_logger.info(f"Bot to {user_id}: Select credential to remove:")
        else:
            ds.clear_status(user_id)  # Clear any existing status message
            sent_msg = bot.send_message(user_id, "No credentials found to remove.")
            ds.last_message_id[user_id] = sent_msg.message_id
            bot.answer_callback_query(call.id)
            user_interaction_logger.info(f"Bot to {user_id}: No credentials found to remove.")

    elif data.startswith("remove_"):
        # Delete the message containing the remove username button
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass

        username = data[7:]  # Get username after 'remove_'
        bot_logger.info(f"Attempting to remove credentials for user {user_id} with username {username}")
        
        if remove_user_credential(str(user_id), username):
            bot.answer_callback_query(call.id, f"Removed credentials for {username}")
            keyboard = create_settings_keyboard()
            ds.clear_status(user_id)  # Clear any existing status message
            sent_msg = bot.send_message(user_id, f"✅ Removed credentials for {username}", reply_markup=keyboard)
            ds.last_message_id[user_id] = sent_msg.message_id
            user_interaction_logger.info(f"Bot to {user_id}: ✅ Removed credentials for {username}")
        else:
            bot_logger.warning(f"Failed to remove credentials for user {user_id} with username {username}")
            ds.clear_status(user_id)  # Clear any existing status message
            sent_msg = bot.send_message(user_id, f"❌ Failed to remove credentials for {username}")
            ds.last_message_id[user_id] = sent_msg.message_id
            bot.answer_callback_query(call.id)
            user_interaction_logger.info(f"Bot to {user_id}: ❌ Failed to remove credentials for {username}")

    elif data == "remove_all":
        # Delete the message containing the remove all button
        try:
            bot.delete_message(user_id, call.message.message_id)
        except:
            pass

        if remove_all_user_credentials(str(user_id)):
            bot.answer_callback_query(call.id, "All credentials removed")
            keyboard = create_settings_keyboard()
            ds.clear_status(user_id)  # Clear any existing status message
            sent_msg = bot.send_message(user_id, "✅ All credentials have been removed.", reply_markup=keyboard)
            ds.last_message_id[user_id] = sent_msg.message_id
            user_interaction_logger.info(f"Bot to {user_id}: ✅ All credentials have been removed.")
        else:
            ds.clear_status(user_id)  # Clear any existing status message
            sent_msg = bot.send_message(user_id, "Failed to remove credentials")
            ds.last_message_id[user_id] = sent_msg.message_id
            bot.answer_callback_query(call.id)
            user_interaction_logger.info(f"Bot to {user_id}: Failed to remove credentials")

# Update the input handler
@bot.message_handler(func=lambda message: True)
def handle_user_input(message):
    user_id = message.chat.id
    text = message.text
    user_interaction_logger.info(f"User {user_id} input: {text}")

    # Delete user's message for security
    try:
        bot.delete_message(user_id, message.message_id)
    except:
        pass

    # Handle CAPTCHA input
    if user_id in ds.user_inputs and ds.user_inputs[user_id] is None:
        ds.user_inputs[user_id] = text
        # Delete previous bot message if exists
        if hasattr(message, 'reply_to_message') and message.reply_to_message:
            try:
                bot.delete_message(user_id, message.reply_to_message.message_id)
            except:
                pass
        sent_msg = bot.send_message(user_id, '✅ CAPTCHA received!')
        user_interaction_logger.info(f"Bot to {user_id}: ✅ CAPTCHA received!")
        # Store message ID for later deletion
        ds.last_message_id[user_id] = sent_msg.message_id
        return

    # Handle credential input
    if user_id in user_states:
        state = user_states[user_id].get('state')
        if state == 'waiting_username':
            user_states[user_id] = {'state': 'waiting_password', 'username': text}
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
            # Delete previous bot message if exists
            if hasattr(message, 'reply_to_message') and message.reply_to_message:
                try:
                    bot.delete_message(user_id, message.reply_to_message.message_id)
                except:
                    pass
            sent_msg = bot.send_message(user_id, "Please enter your password:", reply_markup=keyboard)
            user_interaction_logger.info(f"Bot to {user_id}: Please enter your password:")
            # Store message ID for later deletion
            ds.last_message_id[user_id] = sent_msg.message_id

        elif state == 'waiting_password':
            username = user_states[user_id].get('username')
            if save_user_credentials(str(user_id), username, text):
                keyboard = create_settings_keyboard()
                # Delete previous bot message if exists
                if hasattr(message, 'reply_to_message') and message.reply_to_message:
                    try:
                        bot.delete_message(user_id, message.reply_to_message.message_id)
                    except:
                        pass
                sent_msg = bot.send_message(user_id, f"✅ Credentials saved for {username}", reply_markup=keyboard)
                user_interaction_logger.info(f"Bot to {user_id}: ✅ Credentials saved for {username}")
                # Store message ID for later deletion
                ds.last_message_id[user_id] = sent_msg.message_id
            else:
                keyboard = create_settings_keyboard()
                # Delete previous bot message if exists
                if hasattr(message, 'reply_to_message') and message.reply_to_message:
                    try:
                        bot.delete_message(user_id, message.reply_to_message.message_id)
                    except:
                        pass
                sent_msg = bot.send_message(user_id, "❌ Failed to save credentials", reply_markup=keyboard)
                user_interaction_logger.info(f"Bot to {user_id}: ❌ Failed to save credentials")
                # Store message ID for later deletion
                ds.last_message_id[user_id] = sent_msg.message_id

            del user_states[user_id]  # Clear the state

keep_alive()
# Start the bot
if __name__ == '__main__':
    bot_logger.info('Starting bot...')
    bot.infinity_polling()
