# app/schemas.py
from pydantic import BaseModel, field_validator, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from .models import CheckStatus, ScanStatus
from .utils import NonEmptyStr, validate_hostname, validate_mac_address, validate_ip_address
import logging
import ipaddress

logger = logging.getLogger(__name__)

class Role(BaseModel):
    name: NonEmptyStr = Field(..., alias="Name")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class Software(BaseModel):
    name: str = Field(..., alias="DisplayName", min_length=1)
    version: Optional[str] = Field("Unknown", alias="DisplayVersion")
    install_date: Optional[datetime] = Field(None, alias="InstallDate")
    action: Optional[str] = Field("Installed", alias="Action")
    is_deleted: bool = Field(default=False)

    @field_validator('action')
    @classmethod
    def validate_action(cls, v):
        if v and v not in ["Installed", "Uninstalled"]:
            raise ValueError("Action должно быть 'Installed' или 'Uninstalled'")
        return v

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class Disk(BaseModel):
    device_id: Optional[str] = Field(None, alias="device_id", min_length=1)
    model: Optional[str] = Field(None, alias="model", min_length=1)
    total_space: int = Field(ge=0, alias="total_space")
    free_space: Optional[int] = Field(None, ge=0, alias="free_space")
    serial:  Optional[str] = None
    interface: Optional[NonEmptyStr] = None
    media_type: Optional[NonEmptyStr] = None
    volume_label: Optional[str] = None

    @property
    def total_space_gb(self) -> float:
        return self.total_space / (1024 ** 3) if self.total_space else 0.0

    @property
    def free_space_gb(self) -> Optional[float]:
        return self.free_space / (1024 ** 3) if self.free_space else None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class VideoCard(BaseModel):
    name: NonEmptyStr = Field(..., alias="name")
    driver_version: Optional[NonEmptyStr] = Field(None, alias="driver_version")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class Processor(BaseModel):
    name: NonEmptyStr = Field(..., alias="name")
    number_of_cores: int = Field(..., alias="number_of_cores")
    number_of_logical_processors: int = Field(..., alias="number_of_logical_processors")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class IPAddress(BaseModel):
    address: NonEmptyStr
    model_config = ConfigDict(from_attributes=True)

    @field_validator('address')
    @classmethod
    def validate_ip(cls, v):
        return validate_ip_address(cls, v, "IP address")

class MACAddress(BaseModel):
    address: NonEmptyStr
    model_config = ConfigDict(from_attributes=True)

    @field_validator('address')
    @classmethod
    def validate_mac(cls, v):
        return validate_mac_address(cls, v, "MAC address")

class ComputerBase(BaseModel):
    hostname: NonEmptyStr
    ip_addresses: List[IPAddress] = []
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    processors: Optional[List[Processor]] = None
    ram: Optional[int] = None
    mac_addresses: List[MACAddress] = []
    motherboard: Optional[str] = None
    last_boot: Optional[datetime] = None
    is_virtual: Optional[bool] = None
    check_status: Optional[CheckStatus] = None

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

    model_config = ConfigDict(from_attributes=True)

class ComputerList(ComputerBase):
    id: int
    last_updated: datetime
    disks: List[Disk] = []
    software: List[Software] = []
    roles: List[Role] = []
    video_cards: List[VideoCard] = []
    processors: List[Processor] = []
    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: lambda v: v.isoformat() if v else None})

class Computer(ComputerBase):
    id: int
    last_updated: datetime
    disks: List[Disk] = []
    roles: List[Role] = []
    software: List[Software] = []
    video_cards: List[VideoCard] = []
    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: lambda v: v.isoformat() if v else None})

class ComputerCreate(ComputerBase):
    roles: List[Role] = []
    software: List[Software] = []
    disks: List[Disk] = []
    video_cards: List[VideoCard] = []
    processors: List[Processor] = []
    model_config = ConfigDict(from_attributes=True)

class ComputerUpdateCheckStatus(BaseModel):
    hostname: NonEmptyStr
    check_status: CheckStatus
    model_config = ConfigDict(from_attributes=True)

class ChangeLog(BaseModel):
    id: int
    computer_id: int
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_at: datetime
    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: lambda v: v.isoformat() if v else None})

class ScanTask(BaseModel):
    id: NonEmptyStr
    status: ScanStatus
    created_at: datetime
    updated_at: datetime
    scanned_hosts: int
    successful_hosts: int
    error: Optional[str] = None
    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: lambda v: v.isoformat() if v else None})

class ComputersResponse(BaseModel):
    data: List[ComputerList]
    total: int
    model_config = ConfigDict(from_attributes=True)

class OsDistribution(BaseModel):
    category: str
    count: int
    model_config = ConfigDict(from_attributes=True)

class ServerDistribution(BaseModel):
    category: str
    count: int
    model_config = ConfigDict(from_attributes=True)

class DiskVolume(BaseModel):
    hostname: NonEmptyStr
    disk_id: NonEmptyStr
    total_space_gb: float
    free_space_gb: float
    model_config = ConfigDict(from_attributes=True)

class StatusStats(BaseModel):
    status: CheckStatus
    count: int
    model_config = ConfigDict(from_attributes=True)

class OsStats(BaseModel):
    client_os: List[OsDistribution]
    server_os: List[ServerDistribution]
    model_config = ConfigDict(from_attributes=True)

class DiskStats(BaseModel):
    low_disk_space: List[DiskVolume]
    model_config = ConfigDict(from_attributes=True)

class ScanStats(BaseModel):
    last_scan_time: Optional[datetime]
    status_stats: List[StatusStats]
    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: lambda v: v.isoformat() if v else None})

class DashboardStats(BaseModel):
    total_computers: Optional[int]
    os_stats: OsStats
    disk_stats: DiskStats
    scan_stats: ScanStats
    os_names: List[str] = []
    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: lambda v: v.isoformat() if v else None})

class ErrorResponse(BaseModel):
    error: NonEmptyStr
    detail: Optional[str] = None
    correlation_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class AppSettingUpdate(BaseModel):
    ad_server_url: Optional[str] = None
    domain: Optional[str] = None
    ad_username: Optional[NonEmptyStr] = None
    ad_password: Optional[NonEmptyStr] = None
    api_url: Optional[str] = None
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
    model_config = ConfigDict(from_attributes=True)