import threading
import time
from datetime import datetime, time as dt_time

import pytz

import ds
from db import get_credential_by_username
from logger import bot_logger
from session_manager_headless import session_manager

IST = pytz.timezone('Asia/Kolkata')

RUN_AFTER_TIME = dt_time(8, 30)
SCHEDULE_START_TIME = dt_time(7, 30)
SCHEDULE_END_TIME = dt_time(8, 29)

scheduled_jobs = {}
jobs_lock = threading.Lock()


def schedule_rf_entry(user_id, username, value):
    with jobs_lock:
        if user_id not in scheduled_jobs:
            scheduled_jobs[user_id] = []

        for job in scheduled_jobs[user_id]:
            if job['username'] == username:
                job['value'] = value
                job['status'] = 'pending'
                bot_logger.info(f"Updated scheduled RF entry for user {user_id}, username {username}")
                return

        scheduled_jobs[user_id].append(
            {"username": username, "value": value, "status": "pending"}
        )
        bot_logger.info(f"Scheduled new RF entry for user {user_id}, username {username}")


def get_scheduled_jobs_for_user(user_id):
    with jobs_lock:
        return [job for job in scheduled_jobs.get(user_id, []) if job.get('status') == 'pending']


def clear_job(user_id, username):
    with jobs_lock:
        if user_id in scheduled_jobs:
            initial_count = len(scheduled_jobs[user_id])
            scheduled_jobs[user_id] = [j for j in scheduled_jobs[user_id] if j['username'] != username]
            if len(scheduled_jobs[user_id]) < initial_count:
                bot_logger.info(f"Cleared job for user {user_id}, username {username}")
            if not scheduled_jobs[user_id]:
                del scheduled_jobs[user_id]


def runner():
    processing_users = set()

    while True:
        now_ist = datetime.now(IST)

        if now_ist.time() >= RUN_AFTER_TIME:
            with jobs_lock:
                user_ids = list(scheduled_jobs.keys())

            for user_id in user_ids:
                if user_id in processing_users:
                    continue

                with jobs_lock:
                    has_pending_jobs = any(
                        job['status'] == 'pending' for job in scheduled_jobs.get(user_id, [])
                    )

                if has_pending_jobs:
                    processing_users.add(user_id)
                    bot_logger.info(f"Scheduler: Starting job execution for user {user_id}")
                    threading.Thread(
                        target=execute_all_jobs_for_user,
                        args=(user_id, processing_users),
                        daemon=True,
                    ).start()

        time.sleep(60)


def execute_all_jobs_for_user(user_id, processing_users_set):
    with jobs_lock:
        jobs_to_run = [job for job in scheduled_jobs.get(user_id, []) if job['status'] == 'pending']

    for job_info in jobs_to_run:
        with jobs_lock:
            for job in scheduled_jobs.get(user_id, []):
                if job['username'] == job_info['username']:
                    job['status'] = 'running'
                    break

        bot_logger.info(f"Executing job for user {user_id}, username {job_info['username']}")
        ds.bot_log(f"⏰ Starting scheduled RF entry for {job_info['username']}...", user_id)

        session_manager.get_session(user_id)
        session_manager.set_user_busy(user_id, True)

        try:
            credentials = get_credential_by_username(str(user_id), job_info['username'])
            if not credentials:
                ds.bot_log(
                    f"❌ Scheduled entry for {job_info['username']} failed: Credentials not found.",
                    user_id,
                )
                continue

            login_success = ds.handle_login_attempt(
                user_id,
                credentials['username'],
                credentials['password'],
            )
            if not login_success:
                ds.bot_log(f"❌ Scheduled entry for {job_info['username']} failed during login.", user_id)
                continue

            entry_result = ds.post_login_operations(user_id, value_to_enter=job_info['value'])
            if entry_result == 'success':
                ds.bot_log(
                    f"✅ Scheduled entry for {job_info['username']} with value '{job_info['value']}' completed successfully.",
                    user_id,
                )
            elif entry_result == 'already_saved':
                ds.bot_log(
                    f"ℹ️ Schedule entry for {job_info['username']} not possible. Data was already entered.",
                    user_id,
                )
            else:
                ds.bot_log(
                    f"⚠️ Scheduled entry for {job_info['username']} failed during data submission.",
                    user_id,
                )
        except Exception as e:
            bot_logger.error(
                f"Error executing job for user {user_id}, username {job_info['username']}: {e}"
            )
            ds.bot_log(
                f"❌ An unexpected error occurred during the scheduled entry for {job_info['username']}.",
                user_id,
            )
        finally:
            clear_job(user_id, job_info['username'])
            session_manager.close_session(user_id)
            bot_logger.info(
                f"Finished job for user {user_id}, username {job_info['username']}. Session closed."
            )

    processing_users_set.discard(user_id)
    bot_logger.info(f"Scheduler: Finished all jobs for user {user_id}")


def start_scheduler():
    scheduler_thread = threading.Thread(target=runner, daemon=True)
    scheduler_thread.start()
    bot_logger.info("Scheduler thread started.")
