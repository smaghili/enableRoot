"""
Configuration module for Telegram Reminder Bot
Contains configuration management and interfaces.
"""

from .config import Config
from .config_manager import ConfigManager
from .interfaces import *

__all__ = [
    'Config',
    'ConfigManager'
]
