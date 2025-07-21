# app/schemas.py
from pydantic import BaseModel, field_validator, Field, ConfigDict
from typing import Optional, List, Union
from datetime import datetime
from .models import CheckStatus, ScanStatus
from .utils import NonEmptyStr, validate_hostname, validate_mac_address, validate_ip_address
import logging
from fastapi_users import schemas
from pydantic import EmailStr
import ipaddress

logger = logging.getLogger(__name__)

class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )

class TrackableComponent(BaseSchema):
    detected_on: Optional[datetime] = None
    removed_on: Optional[datetime] = None

class Role(TrackableComponent):
    name: NonEmptyStr = Field(..., alias="Name")

class Software(TrackableComponent):
    name: str = Field(..., alias="DisplayName", min_length=1)
    version: Optional[str] = Field("Unknown", alias="DisplayVersion")
    install_date: Optional[datetime] = Field(None, alias="InstallDate")

    @field_validator('install_date', mode='before')
    @classmethod
    def validate_install_date(cls, v):
        if v is None or v == '':
            return None
        try:
            if isinstance(v, str):
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            logger.warning(f"Некоректный формат install_date: {v}, возвращаем None")
            return None

class PhysicalDisk(TrackableComponent):
    id: Optional[int] = None
    computer_id: Optional[int] = None
    model: Optional[NonEmptyStr] = Field(None, alias="model", max_length=255)
    serial: NonEmptyStr = Field(..., alias="serial", max_length=100)
    interface: Optional[NonEmptyStr] = Field(None, alias="interface", max_length=50)
    media_type: Optional[NonEmptyStr] = Field(None, alias="media_type", max_length=50)

class LogicalDisk(TrackableComponent):
    device_id: Optional[NonEmptyStr] = Field(None, alias="device_id", max_length=255)
    volume_label: Optional[NonEmptyStr] = Field(None, alias="volume_label", max_length=255)
    total_space: int = Field(ge=0, alias="total_space")
    free_space: Optional[int] = Field(None, ge=0, alias="free_space")
    parent_disk_serial: Optional[NonEmptyStr] = Field(None, alias="parent_disk_serial", max_length=100)

    @property
    def total_space_gb(self) -> float:
        return self.total_space / (1024 ** 3) if self.total_space else 0.0

    @property
    def free_space_gb(self) -> Optional[float]:
        return self.free_space / (1024 ** 3) if self.free_space else None

class DiskVolume(BaseSchema):
    id: int
    hostname: NonEmptyStr
    disk_id: NonEmptyStr = Field(..., alias="disk_id", max_length=255)
    volume_label: Optional[NonEmptyStr] = Field(None, alias="volume_label", max_length=255)
    total_space_gb: float = Field(ge=0.0)
    free_space_gb: float = Field(ge=0.0)

    @field_validator('hostname')
    @classmethod
    def validate_hostname_field(cls, v):
        return validate_hostname(cls, v)

class VideoCard(TrackableComponent):
    id: Optional[int] = None
    name: NonEmptyStr = Field(..., alias="name")
    driver_version: Optional[NonEmptyStr] = Field(None, alias="driver_version")

class Processor(TrackableComponent):
    name: NonEmptyStr = Field(..., alias="name")
    number_of_cores: int = Field(..., alias="number_of_cores")
    number_of_logical_processors: int = Field(..., alias="number_of_logical_processors")

class IPAddress(TrackableComponent):
    address: NonEmptyStr

    @field_validator('address')
    @classmethod
    def validate_ip(cls, v):
        return validate_ip_address(cls, v, "IP address")

class MACAddress(TrackableComponent):
    address: NonEmptyStr

    @field_validator('address')
    @classmethod
    def validate_mac(cls, v):
        return validate_mac_address(cls, v, "MAC address")

class ComputerBase(BaseSchema):
    hostname: NonEmptyStr
    ip_addresses: List[IPAddress] = []
    physical_disks: List[PhysicalDisk] = []
    logical_disks: List[LogicalDisk] = []
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    processors: Optional[List[Processor]] = None
    ram: Optional[int] = None
    mac_addresses: List[MACAddress] = []
    motherboard: Optional[str] = None
    last_boot: Optional[datetime] = None
    is_virtual: Optional[bool] = None
    check_status: Optional[CheckStatus] = None
    roles: List[Role] = []
    software: List[Software] = []
    video_cards: List[VideoCard] = []
    # Нові поля
    object_guid: Optional[NonEmptyStr] = None
    when_created: Optional[datetime] = None
    when_changed: Optional[datetime] = None
    enabled: Optional[bool] = None
    ad_notes: Optional[NonEmptyStr] = None
    local_notes: Optional[NonEmptyStr] = None
    is_deleted: Optional[bool] = None

    @field_validator('hostname')
    @classmethod
    def validate_hostname_field(cls, v):
        return validate_hostname(cls, v)

    @field_validator('os_name')
    @classmethod
    def normalize_os_name(cls, v):
        if not v or v.strip() == '':
            return 'Unknown'
        return v.replace('Майкрософт ', '').replace('Microsoft ', '')

    @field_validator('ram')
    @classmethod
    def normalize_ram(cls, v):
        if v is None:
            return None
        if not isinstance(v, (int, float)):
            logger.warning(f"Некорректный тип RAM: {type(v)}, ожидается int или float")
            return None
        if v > 4294967295:
            logger.warning(f"Значение RAM ({v} МБ) превышает допустимый диапазон, обрезается до 4294967295")
            return 4294967295
        return int(v)

class ComputerList(ComputerBase):
    id: int
    last_updated: datetime

class Computer(ComputerBase):
    id: int
    last_updated: datetime

class ComputerCreate(ComputerBase):
    pass

class ComputerUpdateCheckStatus(BaseSchema):
    hostname: NonEmptyStr
    check_status: CheckStatus

    @field_validator('hostname')
    @classmethod
    def validate_hostname_field(cls, v):
        return validate_hostname(cls, v)

class ScanTask(BaseSchema):
    id: NonEmptyStr
    status: ScanStatus
    created_at: datetime
    updated_at: datetime
    scanned_hosts: int
    successful_hosts: int
    error: Optional[str] = None

class ComputersResponse(BaseSchema):
    data: List[ComputerList]
    total: int

class OsDistribution(BaseSchema):
    category: str
    count: int

class ServerDistribution(BaseSchema):
    category: str
    count: int

class StatusStats(BaseSchema):
    status: CheckStatus
    count: int

class OsStats(BaseSchema):
    client_os: List[OsDistribution]
    server_os: List[ServerDistribution]

class DiskStats(BaseSchema):
    low_disk_space: List[DiskVolume]

class ScanStats(BaseSchema):
    last_scan_time: Optional[datetime]
    status_stats: List[StatusStats]

class ComponentChangeStats(BaseSchema):
    component_type: str
    changes_count: int

class DashboardStats(BaseSchema):
    total_computers: Optional[int] = None
    os_stats: OsStats
    disk_stats: DiskStats
    scan_stats: ScanStats
    component_changes: List[ComponentChangeStats] = []

class ErrorResponse(BaseSchema):
    error: NonEmptyStr
    detail: Optional[str] = None
    correlation_id: Optional[str] = None

class AppSettingUpdate(BaseSchema):
    ad_server_url: Optional[NonEmptyStr] = None
    domain: Optional[NonEmptyStr] = None
    ad_username: Optional[NonEmptyStr] = None
    ad_password: Optional[NonEmptyStr] = None
    api_url: Optional[NonEmptyStr] = None
    test_hosts: Optional[str] = None
    log_level: Optional[NonEmptyStr] = None
    scan_max_workers: Optional[int] = None
    polling_days_threshold: Optional[int] = None
    winrm_operation_timeout: Optional[int] = None
    winrm_read_timeout: Optional[int] = None
    winrm_port: Optional[int] = None
    winrm_server_cert_validation: Optional[NonEmptyStr] = None
    ping_timeout: Optional[int] = None
    powershell_encoding: Optional[NonEmptyStr] = None
    json_depth: Optional[int] = None
    server_port: Optional[int] = None
    cors_allow_origins: Optional[NonEmptyStr] = None
    allowed_ips: Optional[NonEmptyStr] = None
    encryption_key: Optional[NonEmptyStr] = None

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

    @field_validator('cors_allow_origins')
    @classmethod
    def validate_cors_origins(cls, v):
        if v:
            origins = [origin.strip() for origin in v.split(",") if origin.strip()]
            if not origins:
                raise ValueError("CORS origins не могут быть пустыми")
            for origin in origins:
                if not origin.startswith(("http://", "https://")):
                    raise ValueError(f"Недопустимый origin: {origin}. Должен начинаться с http:// или https://")
        return v

    @field_validator('allowed_ips')
    @classmethod
    def validate_allowed_ips(cls, v):
        if v:
            ips = [ip.strip() for ip in v.split(",") if ip.strip()]
            if not ips:
                raise ValueError("Allowed IPs не могут быть пустыми")
            for ip in ips:
                try:
                    if '/' in ip:
                        ipaddress.ip_network(ip, strict=False)
                    else:
                        ipaddress.ip_address(ip)
                except ValueError:
                    raise ValueError(f"Недопустимый IP или диапазон: {ip}")
        return v

class ComponentHistory(BaseSchema):
    component_type: str
    data: Union[PhysicalDisk, LogicalDisk, Processor, VideoCard, IPAddress, MACAddress, Software]
    detected_on: Optional[str] = None
    removed_on: Optional[str] = None

class UserRead(schemas.BaseUser[int]):
    username: str
    role: Optional[str] = None

class UserCreate(schemas.BaseUserCreate):
    username: str
    email: EmailStr
    password: str
    role: Optional[str] = None

class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[str] = None
    role: Optional[str] = None

class ComputerListItem(ComputerBase):
    id: int
    last_updated: datetime