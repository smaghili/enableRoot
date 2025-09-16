import time
import logging
from typing import Dict, Any, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)

class StateType(Enum):
    WAITING_FOR_CITY = "waiting_for_city"
    EDITING_REMINDER = "editing_reminder"
    ADMIN_BROADCAST = "admin_broadcast"
    ADMIN_PRIVATE_MESSAGE = "admin_private_message"
    ADMIN_CHANNEL_INPUT = "admin_channel_input"
    ADMIN_USER_LIMIT = "admin_user_limit"
    ADMIN_DELETE_USER = "admin_delete_user"
    ADMIN_LOG_CHANNEL = "admin_log_channel"

class StateManager:
    def __init__(self, timeout_seconds: int = 600):
        self.timeout_seconds = timeout_seconds
        self.user_states: Dict[int, Dict[StateType, Any]] = {}
        self.state_timestamps: Dict[int, Dict[StateType, float]] = {}
    
    def set_state(self, user_id: int, state_type: StateType, value: Any = True) -> None:
        if user_id not in self.user_states:
            self.user_states[user_id] = {}
            self.state_timestamps[user_id] = {}
        
        self.user_states[user_id][state_type] = value
        self.state_timestamps[user_id][state_type] = time.time()
        logger.info(f"Set state {state_type.value} for user {user_id}")
    
    def get_state(self, user_id: int, state_type: StateType) -> Any:
        self._check_and_clear_expired_state(user_id, state_type)
        return self.user_states.get(user_id, {}).get(state_type)
    
    def has_state(self, user_id: int, state_type: StateType) -> bool:
        return self.get_state(user_id, state_type) is not None
    
    def clear_state(self, user_id: int, state_type: StateType) -> None:
        if user_id in self.user_states:
            self.user_states[user_id].pop(state_type, None)
        if user_id in self.state_timestamps:
            self.state_timestamps[user_id].pop(state_type, None)
        logger.info(f"Cleared state {state_type.value} for user {user_id}")
    
    def clear_all_states(self, user_id: int) -> None:
        self.user_states.pop(user_id, None)
        self.state_timestamps.pop(user_id, None)
        logger.info(f"Cleared all states for user {user_id}")
    
    def clear_expired_states(self, user_id: int) -> None:
        if user_id not in self.user_states:
            return
        
        current_time = time.time()
        expired_states = []
        
        for state_type in list(self.user_states[user_id].keys()):
            if user_id in self.state_timestamps and state_type in self.state_timestamps[user_id]:
                if current_time - self.state_timestamps[user_id][state_type] > self.timeout_seconds:
                    expired_states.append(state_type)
        
        for state_type in expired_states:
            self.clear_state(user_id, state_type)
            logger.info(f"Auto-cleared expired state {state_type.value} for user {user_id}")
    
    def _check_and_clear_expired_state(self, user_id: int, state_type: StateType) -> None:
        if user_id not in self.state_timestamps:
            return
        
        if state_type not in self.state_timestamps[user_id]:
            return
        
        current_time = time.time()
        
        if current_time - self.state_timestamps[user_id][state_type] > self.timeout_seconds:
            self.clear_state(user_id, state_type)
    
    def get_active_states(self, user_id: int) -> Set[StateType]:
        self.clear_expired_states(user_id)
        return set(self.user_states.get(user_id, {}).keys())
    
    def cleanup_all_expired(self) -> None:
        for user_id in list(self.user_states.keys()):
            self.clear_expired_states(user_id)