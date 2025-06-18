from pydantic import BaseModel, field_validator, Field
from typing import Optional, List
from datetime import datetime
import logging
from .models import CheckStatus, ScanStatus
import re
import ipaddress
from .settings import validate_non_empty_string 

logger = logging.getLogger(__name__)

def validate_non_empty_string(cls, v, field_name):
    """Общая функция валидации непустых строк."""
    logger.debug(f"Валидация {field_name}: {v}")
    if not v or not v.strip():
        raise ValueError(f"{field_name} не может быть пустым")
    return v.strip()

class Role(BaseModel):
    name: str = Field(..., alias="Name")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        return validate_non_empty_string(cls, v, "Role Name")

    class Config:
        from_attributes = True
        populate_by_name = True

class Software(BaseModel):
    name: str = Field(..., min_length=1, alias="DisplayName")
    version: Optional[str] = Field(None, alias="DisplayVersion")
    install_date: Optional[datetime] = Field(None, alias="InstallDate")
    action: Optional[str] = Field(None, alias="Action")
    is_deleted: bool = Field(default=False)  # Новое поле

    @field_validator('name')
    @classmethod
    def validate_display_name(cls, v):
        return validate_non_empty_string(cls, v, "Software Name")

    @field_validator('action')
    @classmethod
    def validate_action(cls, v):
        if v and v not in ["Installed", "Uninstalled"]:
            raise ValueError("Action должно быть 'Installed' или 'Uninstalled'")
        return v

    class Config:
        from_attributes = True
        populate_by_name = True

class Disk(BaseModel):
    device_id: str = Field(..., alias="DeviceID")
    total_space: float = Field(ge=0, alias="TotalSpace")
    free_space: float = Field(ge=0, alias="FreeSpace")

    @field_validator('device_id')
    @classmethod
    def validate_device_id(cls, v):
        return validate_non_empty_string(cls, v, "Disk device_id")

    class Config:
        from_attributes = True
        populate_by_name = True

class ComputerBase(BaseModel):
    hostname: str
    ip: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    cpu: Optional[str] = None
    ram: Optional[int] = None
    mac: Optional[str] = None
    motherboard: Optional[str] = None
    last_boot: Optional[datetime] = None  # Змінено на datetime
    is_virtual: Optional[bool] = None
    check_status: Optional[CheckStatus] = None

    @field_validator('hostname')
    @classmethod
    def hostname_must_not_be_empty(cls, v):
        return validate_non_empty_string(cls, v, "hostname")

    @field_validator('mac')
    @classmethod
    def validate_mac(cls, v):
        if v and not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', v):
            raise ValueError("Invalid MAC address format")
        return v

    @field_validator('ip')
    @classmethod
    def validate_ip(cls, v):
        if v:
            try:
                ipaddress.ip_address(v)
            except ValueError:
                raise ValueError("Invalid IP address format")
        return v

    class Config:
        from_attributes = True

class ComputerCreate(ComputerBase):
    roles: List[Role] = []
    software: List[Software] = []
    disks: List[Disk] = []

class Computer(ComputerBase):
    id: int
    last_updated: datetime
    roles: List[Role] = []  # Добавлено явно
    software: List[Software] = []  # Добавлено явно
    disks: List[Disk] = []  # Добавлено явно

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True  # Разрешает сериализацию сложных типов
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class ComputerUpdateCheckStatus(BaseModel):
    hostname: str
    check_status: CheckStatus

class ChangeLog(BaseModel):
    id: int
    computer_id: int
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class ScanTask(BaseModel):
    id: str
    status: ScanStatus
    created_at: datetime
    updated_at: datetime
    scanned_hosts: int
    successful_hosts: int
    error: Optional[str] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class ComputersResponse(BaseModel):
    data: List[Computer]
    total: int

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True  # Разрешает сериализацию сложных типов

class OsVersion(BaseModel):
    os_version: Optional[str]
    count: int

    class Config:
        from_attributes = True

class LowDiskSpace(BaseModel):
    hostname: str
    disk_id: str
    free_space_percent: float

    class Config:
        from_attributes = True

class StatusStats(BaseModel):
    status: CheckStatus
    count: int

    class Config:
        from_attributes = True

class OsStats(BaseModel):
    os_versions: List[OsVersion]

    class Config:
        from_attributes = True

class DiskStats(BaseModel):
    low_disk_space: List[LowDiskSpace]

    class Config:
        from_attributes = True

class ScanStats(BaseModel):
    last_scan_time: Optional[datetime]
    status_stats: List[StatusStats]

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class DashboardStats(BaseModel):
    total_computers: Optional[int]
    os_stats: OsStats
    disk_stats: DiskStats
    scan_stats: ScanStats

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    correlation_id: Optional[str] = None