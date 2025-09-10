import enum

class CheckStatus(enum.Enum):
    success = "success"
    failed = "failed"
    unreachable = "unreachable"
    partially_successful = "partially_successful"
    disabled = "disabled"
    is_deleted = "is_deleted"

class ScanStatus(enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"