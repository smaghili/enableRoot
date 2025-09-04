import os
import stat
import logging
from typing import Optional


logger = logging.getLogger(__name__)


def secure_file_permissions(file_path: str) -> bool:
    try:
        os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)
        logger.info(f"Set secure permissions for {file_path}")
        return True
    except (OSError, IOError) as e:
        logger.error(f"Failed to set permissions for {file_path}: {e}")
        return False


def secure_directory_permissions(dir_path: str) -> bool:
    try:
        os.chmod(dir_path, stat.S_IRWXU)
        logger.info(f"Set secure permissions for directory {dir_path}")
        return True
    except (OSError, IOError) as e:
        logger.error(f"Failed to set directory permissions for {dir_path}: {e}")
        return False


def create_secure_directory(dir_path: str) -> bool:
    try:
        os.makedirs(dir_path, mode=0o700, exist_ok=True)
        logger.info(f"Created secureییییییی directory {dir_path}")
        return True
    except (OSError, IOError) as e:
        logger.error(f"Failed to create secure directory {dir_path}: {e}")
        return False


def validate_file_path(file_path: str, base_dir: Optional[str] = None) -> bool:
    try:
        abs_path = os.path.abspath(file_path)
        
        if base_dir:
            base_abs = os.path.abspath(base_dir)
            if not abs_path.startswith(base_abs):
                logger.warning(f"Path traversal attempt detected: {file_path}")
                return False
                
        if any(dangerous in abs_path for dangerous in ['..', '~', '$']):
            logger.warning(f"Dangerous path detected: {file_path}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error validating path {file_path}: {e}")
        return False


def sanitize_filename(filename: str) -> str:
    import re
    
    sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
    sanitized = sanitized[:255]
    
    if not sanitized or sanitized.startswith('.'):
        sanitized = 'file_' + sanitized
        
    return sanitized


def check_disk_space(path: str, min_free_mb: int = 100) -> bool:
    try:
        statvfs = os.statvfs(path)
        free_bytes = statvfs.f_frsize * statvfs.f_bavail
        free_mb = free_bytes / (1024 * 1024)
        
        if free_mb < min_free_mb:
            logger.warning(f"Low disk space: {free_mb:.1f}MB free, minimum required: {min_free_mb}MB")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Error checking disk space for {path}: {e}")
        return False
