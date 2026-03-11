import time
from typing import Dict, Optional

class CollaborationManager:
    """
    Manages operational locks (mutexes) for multi-user collaboration.
    Prevents conflicting edits in high-pressure environments.
    """
    def __init__(self, lock_timeout_sec: int = 3600):
        # resource_id -> {user_id, timestamp}
        self._locks: Dict[str, Dict[str, any]] = {}
        self.lock_timeout_sec = lock_timeout_sec

    def take_lock(self, resource_id: str, user_id: str) -> bool:
        """
        Attempts to acquire a lock on a resource.
        Returns True if successful (already owned or newly acquired).
        """
        now = time.time()
        current_lock = self._locks.get(resource_id)

        if current_lock:
            # Check if expired
            if now - current_lock["timestamp"] > self.lock_timeout_sec:
                self._locks[resource_id] = {"user_id": user_id, "timestamp": now}
                return True
            
            # Check if same user
            return current_lock["user_id"] == user_id
        
        # New lock
        self._locks[resource_id] = {"user_id": user_id, "timestamp": now}
        return True

    def release_lock(self, resource_id: str, user_id: str) -> bool:
        """
        Releases a lock if owned by the user.
        """
        current_lock = self._locks.get(resource_id)
        if current_lock and current_lock["user_id"] == user_id:
            del self._locks[resource_id]
            return True
        return False

    def get_locks(self) -> Dict[str, Dict[str, any]]:
        """
        Returns all active and non-expired locks.
        """
        now = time.time()
        # Clean up expired locks on read
        expired = [rid for rid, lock in self._locks.items() if now - lock["timestamp"] > self.lock_timeout_sec]
        for rid in expired:
            del self._locks[rid]
            
        return self._locks

    def is_locked(self, resource_id: str, exclude_user_id: Optional[str] = None) -> bool:
        """
        Checks if a resource is locked by someone else.
        """
        now = time.time()
        lock = self._locks.get(resource_id)
        if not lock:
            return False
        
        if now - lock["timestamp"] > self.lock_timeout_sec:
            return False
            
        if exclude_user_id and lock["user_id"] == exclude_user_id:
            return False
            
        return True
