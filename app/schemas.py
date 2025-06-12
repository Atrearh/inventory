from pydantic import BaseModel, field_validator, Field
from typing import Optional, List
from datetime import datetime
import logging
from .models import CheckStatus, ScanStatus

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
        populate_by_name = True  # Позволяет использовать как name, так и Name

class Software(BaseModel):
    name: str = Field(..., min_length=1, alias="DisplayName")
    version: Optional[str] = Field(None, alias="DisplayVersion")
    install_date: Optional[datetime] = Field(None, alias="InstallDate")

    @field_validator('name')
    @classmethod
    def validate_display_name(cls, v):
        return validate_non_empty_string(cls, v, "Software Name")

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
    last_boot: Optional[str] = None
    is_virtual: Optional[bool] = None
    check_status: Optional[CheckStatus] = None

    @field_validator('hostname')
    @classmethod
    def hostname_must_not_be_empty(cls, v):
        return validate_non_empty_string(cls, v, "hostname")

    class Config:
        from_attributes = True

class ComputerCreate(ComputerBase):
    roles: List[Role] = []
    software: List[Software] = []
    disks: List[Disk] = []

class Computer(ComputerBase):
    id: int
    last_updated: datetime

    class Config:
        from_attributes = True
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

class StatusStats(BaseModel):  # Добавлено новое определение
    status: Optional[str]
    count: int

    class Config:
        from_attributes = True

class DashboardStats(BaseModel):
    total_computers: Optional[int]
    os_versions: List[OsVersion]
    low_disk_space: List[LowDiskSpace]
    last_scan_time: Optional[datetime]
    status_stats: Optional[List[StatusStats]]  # Изменено с dict на List[StatusStats]

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }