# Експортуємо всі моделі для зворотної сумісності
from .enums import CheckStatus, ScanStatus
from .domain import Domain
from .computer import Computer
from .hardware import Processor, IPAddress, MACAddress, VideoCard, PhysicalDisk, LogicalDisk
from .software import Software, Role
from .scan import ScanTask
from .user import User, RefreshToken
from .settings import AppSetting

# Для зворотної сумісності експортуємо змінні шифрування
ENCRYPTION_KEY = None
cipher = None

__all__ = [
    'CheckStatus',
    'ScanStatus',
    'Domain',
    'Computer',
    'Processor',
    'IPAddress',
    'MACAddress',
    'VideoCard',
    'PhysicalDisk',
    'LogicalDisk',
    'Software',
    'Role',
    'ScanTask',
    'User',
    'RefreshToken',
    'AppSetting',
    'ENCRYPTION_KEY',
    'cipher'
]