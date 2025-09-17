# app/schemas.py
import logging
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union
from uuid import UUID
from fastapi_users import schemas
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.utils.validators import (
    AllowedIPsStr,
    CORSOriginsStr,
    DomainNameStr,
    HostnameStr,
    IPAddressStr,
    LogLevelStr,
    MACAddressStr,
    NonEmptyStr,
    WinRMCertValidationStr,
)

logger = logging.getLogger(__name__)


# --- Визначення Enum для ідентифікаторів компонентів ---
class IdentifierField(Enum):
    """Унікальні ідентифікатори для компонентів комп'ютера."""

    NAME = "name"
    SERIAL = "serial"
    ADDRESS = "address"
    DEVICE_ID = "device_id"


class CheckStatus(Enum):
    success = "success"
    failed = "failed"
    unreachable = "unreachable"
    partially_successful = "partially_successful"
    disabled = "disabled"
    is_deleted = "is_deleted"


class ScanStatus(Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


# --- Базові класи ---
class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
    )


class TrackableComponent(BaseSchema):
    detected_on: Optional[datetime] = None
    removed_on: Optional[datetime] = None


class ComponentSchema(TrackableComponent):
    _identifier_field: IdentifierField = IdentifierField.NAME


# --- Схеми компонентів комп'ютера ---
class Role(ComponentSchema):
    _identifier_field = IdentifierField.NAME
    name: NonEmptyStr = Field(..., alias="Name")


class OperatingSystemRead(BaseSchema):
    name: NonEmptyStr
    version: Optional[str] = None
    architecture: Optional[str] = None


class InstalledSoftwareRead(BaseSchema):
    name: NonEmptyStr
    version: Optional[str] = None
    publisher: Optional[str] = None
    install_date: Optional[datetime] = None


class PhysicalDisk(ComponentSchema):
    _identifier_field = IdentifierField.SERIAL
    id: Optional[int] = None
    computer_id: int
    model: Optional[NonEmptyStr] = Field(None, alias="model", max_length=255)
    serial: Optional[NonEmptyStr] = Field(None, alias="serial", max_length=100)
    interface: Optional[NonEmptyStr] = Field(None, alias="interface", max_length=50)
    media_type: Optional[NonEmptyStr] = Field(None, alias="media_type", max_length=50)


class LogicalDisk(ComponentSchema):
    _identifier_field = IdentifierField.DEVICE_ID
    device_id: Optional[NonEmptyStr] = Field(None, alias="device_id", max_length=255)
    volume_label: Optional[NonEmptyStr] = Field(None, alias="volume_label", max_length=255)
    total_space: int = Field(ge=0, alias="total_space")
    free_space: Optional[int] = Field(None, ge=0, alias="free_space")
    parent_disk_serial: Optional[NonEmptyStr] = Field(None, alias="parent_disk_serial", max_length=100)


class Processor(ComponentSchema):
    _identifier_field = IdentifierField.NAME
    name: NonEmptyStr = Field(..., alias="Name")
    cores: Optional[int] = Field(None, ge=1, alias="NumberOfCores")
    threads: Optional[int] = Field(None, ge=1, alias="NumberOfThreads")
    speed_ghz: Optional[float] = Field(None, ge=0.0, alias="MaxClockSpeed")


class VideoCard(ComponentSchema):
    _identifier_field = IdentifierField.NAME
    name: NonEmptyStr = Field(..., alias="Name")
    vram: Optional[int] = Field(None, ge=0, alias="AdapterRAM")


class IPAddress(ComponentSchema):
    _identifier_field = IdentifierField.ADDRESS
    address: IPAddressStr = Field(..., alias="address")


class MACAddress(ComponentSchema):
    _identifier_field = IdentifierField.ADDRESS
    address: MACAddressStr = Field(..., alias="address")


# --- Базова схема для комп'ютерів з мінімальними полями ---
class ComputerCore(BaseSchema):
    hostname: HostnameStr = Field(..., max_length=255)
    os: Optional[OperatingSystemRead] = None
    ram: Optional[int] = Field(None, ge=0)
    motherboard: Optional[NonEmptyStr] = None
    last_boot: Optional[datetime] = None
    is_virtual: Optional[bool] = False
    check_status: Optional[CheckStatus] = Field(None, examples=["reachable", "unreachable"])


# --- Схема для створення та оновлення комп'ютерів ---
class ComputerCreate(ComputerCore):
    ip_addresses: List[IPAddress] = []
    mac_addresses: List[MACAddress] = []
    processors: List[Processor] = []
    video_cards: List[VideoCard] = []
    software: List[InstalledSoftwareRead] = []
    roles: List[Role] = []
    physical_disks: List[PhysicalDisk] = []
    logical_disks: List[LogicalDisk] = []


# --- Схема для спискового представлення ---
class ComputerListItem(ComputerCore):
    id: int
    last_updated: Optional[datetime] = None
    last_full_scan: Optional[datetime] = None
    domain_id: Optional[int] = None
    domain_name: Optional[NonEmptyStr] = None
    ip_addresses: List[IPAddress] = []
    os: Optional[OperatingSystemRead] = None


# --- Схема для детального перегляду комп'ютера ---
class ComputerDetail(ComputerCore):
    id: int
    last_updated: Optional[datetime] = None
    last_full_scan: Optional[datetime] = None
    domain_id: Optional[int] = None
    domain_name: Optional[NonEmptyStr] = None
    object_guid: Optional[str] = None
    when_created: Optional[datetime] = None
    when_changed: Optional[datetime] = None
    enabled: Optional[bool] = None
    ad_notes: Optional[NonEmptyStr] = None
    local_notes: Optional[NonEmptyStr] = None
    last_logon: Optional[datetime] = None
    ip_addresses: List[IPAddress] = []
    mac_addresses: List[MACAddress] = []
    processors: List[Processor] = []
    video_cards: List[VideoCard] = []
    software: List[InstalledSoftwareRead] = []
    roles: List[Role] = []
    physical_disks: List[PhysicalDisk] = []
    logical_disks: List[LogicalDisk] = []


# --- Схема для списку комп'ютерів ---
class ComputersResponse(BaseSchema):
    data: List[ComputerListItem]
    total: int


# --- Схеми статистики ---
class StatusStats(BaseSchema):
    status: CheckStatus
    count: int = Field(ge=0)


class OsCategoryStats(BaseSchema):
    category: str
    count: int


class OsStats(BaseSchema):
    client_os: List[OsCategoryStats] = []
    server_os: List[OsCategoryStats] = []
    os_name: Optional[NonEmptyStr] = None
    count: int = Field(ge=0)
    software_distribution: List[OsCategoryStats] = []


class DiskVolume(BaseSchema):
    id: int
    hostname: HostnameStr
    device_id: NonEmptyStr
    volume_label: Optional[NonEmptyStr] = None
    total_space_gb: float = Field(ge=0.0)
    free_space_gb: float = Field(ge=0.0)


class DiskStats(BaseSchema):
    low_disk_space: List[DiskVolume]


class ScanStats(BaseSchema):
    last_scan_time: Optional[datetime]
    status_stats: List[StatusStats]


class ComponentChangeStats(BaseSchema):
    component_type: NonEmptyStr
    changes_count: int = Field(ge=0)


class ScanResponse(BaseSchema):
    status: NonEmptyStr
    task_id: NonEmptyStr


class DashboardStats(BaseSchema):
    total_computers: Optional[int] = None
    os_stats: OsStats
    disk_stats: DiskStats
    scan_stats: ScanStats
    component_changes: List[ComponentChangeStats] = []


class ErrorResponse(BaseSchema):
    error: NonEmptyStr
    detail: Optional[NonEmptyStr] = None
    correlation_id: Optional[NonEmptyStr] = None


# --- Схеми налаштувань та історії ---
class AppSettingUpdate(BaseSchema):
    ad_server_url: Optional[DomainNameStr] = None
    domain: Optional[DomainNameStr] = None
    ad_username: Optional[NonEmptyStr] = None
    ad_password: Optional[NonEmptyStr] = None
    api_url: Optional[HttpUrl] = None
    log_level: Optional[LogLevelStr] = None
    scan_max_workers: Optional[int] = Field(None, ge=1)
    polling_days_threshold: Optional[int] = Field(None, ge=1)
    winrm_operation_timeout: Optional[int] = Field(None, ge=1)
    winrm_read_timeout: Optional[int] = Field(None, ge=1)
    winrm_port: Optional[int] = Field(None, ge=1, le=65535)
    winrm_server_cert_validation: Optional[WinRMCertValidationStr] = None
    ping_timeout: Optional[int] = Field(None, ge=1)
    powershell_encoding: Optional[NonEmptyStr] = None
    json_depth: Optional[int] = Field(None, ge=1)
    server_port: Optional[int] = Field(None, ge=1, le=65535)
    cors_allow_origins: Optional[CORSOriginsStr] = None
    allowed_ips: Optional[AllowedIPsStr] = None
    encryption_key: Optional[NonEmptyStr] = None
    timezone: Optional[NonEmptyStr] = None


class ComponentHistory(BaseSchema):
    component_type: NonEmptyStr
    data: Union[
        PhysicalDisk,
        LogicalDisk,
        Processor,
        VideoCard,
        IPAddress,
        MACAddress,
        InstalledSoftwareRead,
        Role,
    ]
    detected_on: Optional[NonEmptyStr] = None
    removed_on: Optional[NonEmptyStr] = None


# --- Схеми користувачів ---
class UserRead(schemas.BaseUser[int]):
    username: NonEmptyStr
    role: Optional[NonEmptyStr] = None


class UserCreate(schemas.BaseUserCreate):
    username: NonEmptyStr
    email: EmailStr
    password: NonEmptyStr
    role: Optional[NonEmptyStr] = None


class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[NonEmptyStr] = None
    role: Optional[NonEmptyStr] = None


# --- Схеми доменів ---
class DomainCore(BaseSchema):
    name: DomainNameStr
    username: NonEmptyStr
    password: NonEmptyStr
    server_url: DomainNameStr
    ad_base_dn: NonEmptyStr


class DomainCreate(DomainCore):
    pass


class DomainBase(DomainCore):
    id: int
    last_updated: Optional[datetime] = None


class DomainUpdate(BaseSchema):
    id: int
    last_updated: Optional[datetime] = None
    name: Optional[DomainNameStr] = None
    username: Optional[NonEmptyStr] = None
    password: Optional[NonEmptyStr] = None
    server_url: Optional[DomainNameStr] = None
    ad_base_dn: Optional[NonEmptyStr] = None


class DomainRead(DomainBase):
    password: Optional[str] = Field(None, exclude=True)


class TaskRead(BaseSchema):
    id: NonEmptyStr
    name: NonEmptyStr
    status: NonEmptyStr
    created_at: NonEmptyStr


class ComputerUpdateCheckStatus(BaseSchema):
    hostname: HostnameStr
    check_status: CheckStatus


class ScanTask(BaseSchema):
    id: UUID
    status: ScanStatus
    scanned_hosts: int
    successful_hosts: int
    error: Optional[NonEmptyStr]
    created_at: datetime
    updated_at: datetime
    progress: float = 0.0
    name: Optional[NonEmptyStr] = None

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        data = super().model_validate(obj, **kwargs)
        data.progress = (data.successful_hosts / max(data.scanned_hosts, 1)) * 100
        return data


class SessionRead(BaseSchema):
    id: int
    issued_at: datetime
    expires_at: datetime
    is_current: bool = False
