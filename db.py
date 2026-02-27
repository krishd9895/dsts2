import json
import os
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

from logger import db_logger

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None


MONGO_URI = os.getenv('MONGO_URI')
LOCAL_DB_PATH = Path(os.getenv('LOCAL_DB_PATH', 'credentials.json'))
_storage_lock = Lock()


class MongoStorage:
    def __init__(self, mongo_uri: str):
        db_logger.info('Attempting to connect to MongoDB...')
        self.client = MongoClient(mongo_uri)
        self.client.admin.command('ping')
        self.db = self.client['dsts_bot']
        self.credentials_collection = self.db['credentials']
        db_logger.info('Successfully connected to MongoDB')

    def get_user_doc(self, user_id: str) -> Optional[Dict]:
        return self.credentials_collection.find_one({'user_id': str(user_id)})

    def replace_user_credentials(self, user_id: str, credentials: List[Dict[str, str]]):
        self.credentials_collection.update_one(
            {'user_id': str(user_id)},
            {'$set': {'credentials': credentials}},
            upsert=True,
        )

    def delete_user(self, user_id: str) -> bool:
        result = self.credentials_collection.delete_one({'user_id': str(user_id)})
        return result.deleted_count > 0


class JsonStorage:
    def __init__(self, path: Path):
        self.path = path
        if not self.path.exists():
            self.path.write_text('{}', encoding='utf-8')
        db_logger.info(f'Using local JSON credential store: {self.path}')

    def _read_all(self) -> Dict[str, Dict]:
        with _storage_lock:
            try:
                return json.loads(self.path.read_text(encoding='utf-8') or '{}')
            except json.JSONDecodeError:
                db_logger.warning('credentials.json is invalid JSON. Resetting file.')
                self.path.write_text('{}', encoding='utf-8')
                return {}

    def _write_all(self, payload: Dict[str, Dict]):
        with _storage_lock:
            self.path.write_text(json.dumps(payload, indent=2), encoding='utf-8')

    def get_user_doc(self, user_id: str) -> Optional[Dict]:
        data = self._read_all()
        return data.get(str(user_id))

    def replace_user_credentials(self, user_id: str, credentials: List[Dict[str, str]]):
        data = self._read_all()
        data[str(user_id)] = {'user_id': str(user_id), 'credentials': credentials}
        self._write_all(data)

    def delete_user(self, user_id: str) -> bool:
        data = self._read_all()
        key = str(user_id)
        if key in data:
            del data[key]
            self._write_all(data)
            return True
        return False


def _get_storage_backend():
    if MONGO_URI and MongoClient is not None:
        try:
            return MongoStorage(MONGO_URI)
        except Exception as mongo_error:
            db_logger.warning(f'MongoDB unavailable, falling back to local JSON store: {mongo_error}')

    if MONGO_URI and MongoClient is None:
        db_logger.warning('MONGO_URI is set but pymongo is not installed. Falling back to local JSON store.')

    return JsonStorage(LOCAL_DB_PATH)


storage = _get_storage_backend()


def save_user_credentials(user_id: str, username: str, password: str) -> bool:
    """Save user credentials with a limit of 4 per user."""
    user_doc = storage.get_user_doc(str(user_id))

    if user_doc:
        credentials = user_doc.get('credentials', [])
        if any(cred['username'] == username for cred in credentials):
            return False
        if len(credentials) < 4:
            credentials.append({'username': username, 'password': password})
            storage.replace_user_credentials(str(user_id), credentials)
            return True
        return False

    storage.replace_user_credentials(str(user_id), [{'username': username, 'password': password}])
    return True


def get_user_credentials(user_id: str) -> List[Dict[str, str]]:
    user_doc = storage.get_user_doc(str(user_id))
    if user_doc:
        return user_doc.get('credentials', [])
    return []


def get_user_usernames(user_id: str) -> List[str]:
    return [cred['username'] for cred in get_user_credentials(str(user_id))]


def get_credential_by_username(user_id: str, username: str) -> Optional[Dict[str, str]]:
    try:
        credentials = get_user_credentials(str(user_id))
        for cred in credentials:
            if cred['username'] == username:
                return cred
        return None
    except Exception as e:
        db_logger.error(f'Error retrieving credentials: {str(e)}')
        raise


def remove_user_credential(user_id: str, username: str) -> bool:
    try:
        credentials = get_user_credentials(str(user_id))
        if not credentials:
            return False

        updated = [cred for cred in credentials if cred['username'] != username]
        if len(updated) == len(credentials):
            return False

        if updated:
            storage.replace_user_credentials(str(user_id), updated)
        else:
            storage.delete_user(str(user_id))
        return True
    except Exception as e:
        db_logger.error(f'Error removing credentials for user {user_id}: {str(e)}')
        return False


def remove_all_user_credentials(user_id: str) -> bool:
    return storage.delete_user(str(user_id))
