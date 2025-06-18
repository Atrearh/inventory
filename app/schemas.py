from pydantic import BaseModel, field_validator, Field
from typing import Optional, List
from datetime import datetime
import logging
from .models import CheckStatus, ScanStatus
from .utils import validate_hostname, validate_mac_address, validate_ip_address, validate_non_empty_string

logger = logging.getLogger(__name__)

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
    is_deleted: bool = Field(default=False)

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
    last_boot: Optional[datetime] = None
    is_virtual: Optional[bool] = None
    check_status: Optional[CheckStatus] = None
    disks: List[Disk] = []  
    roles: List[Role] = []  
    software: List[Software] = []  

    @field_validator('hostname')
    @classmethod
    def validate_hostname_field(cls, v):
        return validate_hostname(cls, v)

    @field_validator('mac')
    @classmethod
    def validate_mac(cls, v):
        return validate_mac_address(cls, v)

    @field_validator('ip')
    @classmethod
    def validate_ip(cls, v):
        return validate_ip_address(cls, v)

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

class AppSettingUpdate(BaseModel):
    ad_server_url: Optional[str] = None
    domain: Optional[str] = None
    ad_username: Optional[str] = None
    ad_password: Optional[str] = None
    api_url: Optional[str] = None
    test_hosts: Optional[str] = None
    log_level: Optional[str] = None
    scan_max_workers: Optional[int] = None
    polling_days_threshold: Optional[int] = None
    winrm_operation_timeout: Optional[int] = None
    winrm_read_timeout: Optional[int] = None
    winrm_port: Optional[int] = None
    winrm_server_cert_validation: Optional[str] = None
    winrm_retries: Optional[int] = None
    winrm_retry_delay: Optional[int] = None
    ping_timeout: Optional[int] = None
    powershell_encoding: Optional[str] = None
    json_depth: Optional[int] = None
    server_port: Optional[int] = None
    cors_allow_origins: Optional[List[str]] = None
    allowed_ips: Optional[List[str]] = None

    @field_validator('ad_username', 'ad_password')
    @classmethod
    def validate_non_empty(cls, v, info):
        if v is not None:
            return validate_non_empty_string(cls, v, info.field_name)
        return v

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        if v and v not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError("Log level должен быть одним из: DEBUG, INFO, WARNING, ERROR, CRITICAL")
        return v

    @field_validator('winrm_server_cert_validation')
    @classmethod
    def validate_cert_validation(cls, v):
        if v and v not in ["validate", "ignore"]:
            raise ValueError("winrm_server_cert_validation должен быть 'validate' или 'ignore'")
        return v

    class Config:
        from_attributes = True