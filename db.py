from pymongo import MongoClient
import os
from typing import Dict, List, Optional
from logger import db_logger

# MongoDB connection
MONGO_URI = os.getenv('MONGO_URI')

try:
    db_logger.info("Attempting to connect to MongoDB...")
    client = MongoClient(MONGO_URI)
    # Verify connection
    client.admin.command('ping')
    db_logger.info("Successfully connected to MongoDB")
    
    db = client['dsts_bot']
    credentials_collection = db['credentials']
    
    # Log collection info
    db_logger.info(f"Using database: {db.name}")
    db_logger.info(f"Using collection: {credentials_collection.name}")
    
except Exception as e:
    db_logger.error(f"Failed to connect to MongoDB: {str(e)}")
    raise

def save_user_credentials(user_id: str, username: str, password: str) -> bool:
    """Save user credentials to MongoDB with a limit of 4 per user."""
    user_credentials = credentials_collection.find_one({'user_id': str(user_id)})
    
    if user_credentials:
        # Update existing credentials list
        credentials = user_credentials.get('credentials', [])
        # Check if username already exists
        for cred in credentials:
            if cred['username'] == username:
                return False
        # Add new credentials if limit not reached
        if len(credentials) < 4:
            credentials.append({'username': username, 'password': password})
            credentials_collection.update_one(
                {'user_id': str(user_id)},
                {'$set': {'credentials': credentials}}
            )
            return True
        return False
    else:
        # Create new user entry
        credentials_collection.insert_one({
            'user_id': str(user_id),
            'credentials': [{'username': username, 'password': password}]
        })
        return True

def get_user_credentials(user_id: str) -> List[Dict[str, str]]:
    """Get all credentials for a user."""
    user_credentials = credentials_collection.find_one({'user_id': str(user_id)})
    if user_credentials:
        return user_credentials.get('credentials', [])
    return []

def get_user_usernames(user_id: str) -> List[str]:
    """Get all usernames for a user."""
    user_credentials = credentials_collection.find_one({'user_id': str(user_id)})
    if user_credentials:
        return [cred['username'] for cred in user_credentials.get('credentials', [])]
    return []

def get_credential_by_username(user_id: str, username: str) -> Optional[Dict[str, str]]:
    """Get specific credentials by username."""
    try:
        db_logger.debug(f"Searching credentials for user {user_id} with username {username}")
        user_credentials = credentials_collection.find_one({'user_id': str(user_id)})
        
        if user_credentials:
            db_logger.debug(f"Found user document for {user_id}")
            credentials = user_credentials.get('credentials', [])
            db_logger.debug(f"User has {len(credentials)} saved credentials")
            
            for cred in credentials:
                if cred['username'] == username:
                    db_logger.info(f"Found matching credentials for username {username}")
                    return cred
            
            db_logger.warning(f"No matching credentials found for username {username}")
        else:
            db_logger.warning(f"No user document found for user {user_id}")
        
        return None
    except Exception as e:
        db_logger.error(f"Error retrieving credentials: {str(e)}")
        raise

def remove_user_credential(user_id: str, username: str) -> bool:
    """Remove a specific credential for a user."""
    try:
        # First check if the credential exists
        user_credentials = credentials_collection.find_one({'user_id': str(user_id)})
        if not user_credentials:
            db_logger.warning(f"No credentials found for user {user_id}")
            return False

        # Check if the specific username exists
        credentials = user_credentials.get('credentials', [])
        db_logger.info(f"Current credentials for user {user_id}: {[cred['username'] for cred in credentials]}")
        
        username_exists = any(cred['username'] == username for cred in credentials)
        if not username_exists:
            db_logger.warning(f"Username {username} not found for user {user_id}")
            return False

        # Remove the credential
        result = credentials_collection.update_one(
            {'user_id': str(user_id)},
            {'$pull': {'credentials': {'username': username}}}
        )
        
        # Verify removal
        updated_credentials = credentials_collection.find_one({'user_id': str(user_id)})
        updated_usernames = [cred['username'] for cred in updated_credentials.get('credentials', [])]
        db_logger.info(f"Updated credentials for user {user_id}: {updated_usernames}")
        
        if result.modified_count > 0 and username not in updated_usernames:
            db_logger.info(f"Successfully removed credentials for username {username} from user {user_id}")
            return True
        else:
            db_logger.error(f"Failed to remove credentials for username {username} from user {user_id}")
            return False
    except Exception as e:
        db_logger.error(f"Error removing credentials for user {user_id}: {str(e)}")
        return False

def remove_all_user_credentials(user_id: str) -> bool:
    """Remove all credentials for a user."""
    result = credentials_collection.delete_one({'user_id': str(user_id)})
    return result.deleted_count > 0