# app/schemas.py
from pydantic import BaseModel, field_validator, Field, ConfigDict
from typing import Optional, List, Union
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
    detected_on: Optional[datetime] = None
    removed_on: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator('install_date', mode='before')
    @classmethod
    def validate_install_date(cls, v):
        if v is None or v == '':
            return None
        try:
            # Спробуємо розпарсити дату у форматі ISO 8601 або інших поширених форматах
            if isinstance(v, str):
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            logger.warning(f"Некоректний формат install_date: {v}, повертаємо None")
            return None


class PhysicalDisk(BaseModel):
    id: Optional[int] = None
    computer_id: Optional[int] = None
    model: Optional[NonEmptyStr] = Field(None, alias="model", min_length=1, max_length=255)
    serial: Optional[NonEmptyStr] = Field(None, alias="serial", max_length=100)
    interface: Optional[NonEmptyStr] = Field(None, alias="interface", max_length=50)
    media_type: Optional[NonEmptyStr] = Field(None, alias="media_type", max_length=50)
    detected_on: Optional[datetime] = None
    removed_on: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator('model')
    @classmethod
    def validate_model(cls, v):
        if v and len(v.strip()) == 0:
            raise ValueError("Model не может быть пустой строкой")
        return v

    @field_validator('serial')
    @classmethod
    def validate_serial(cls, v):
        if v and len(v.strip()) == 0:
            raise ValueError("Serial не может быть пустой строкой")
        return v

    @field_validator('interface')
    @classmethod
    def validate_interface(cls, v):
        if v and len(v.strip()) == 0:
            raise ValueError("Interface не может быть пустой строкой")
        return v

    @field_validator('media_type')
    @classmethod
    def validate_media_type(cls, v):
        if v and len(v.strip()) == 0:
            raise ValueError("Media type не может быть пустой строкой")
        return v

class LogicalDisk(BaseModel):
    device_id: Optional[NonEmptyStr] = Field(None, alias="device_id", min_length=1, max_length=255)
    volume_label: Optional[NonEmptyStr] = Field(None, alias="volume_label", max_length=255)
    total_space: int = Field(ge=0, alias="total_space")
    free_space: Optional[int] = Field(None, ge=0, alias="free_space")
    physical_disk_id: Optional[int] = None
    detected_on: Optional[datetime] = None
    removed_on: Optional[datetime] = None
    @property
    def total_space_gb(self) -> float:
        return self.total_space / (1024 ** 3) if self.total_space else 0.0
    @property
    def free_space_gb(self) -> Optional[float]:
        return self.free_space / (1024 ** 3) if self.free_space else None
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator('device_id')
    @classmethod
    def validate_device_id(cls, v):
        if v and len(v.strip()) == 0:
            raise ValueError("Device ID не может быть пустой строкой")
        return v

    @field_validator('volume_label')
    @classmethod
    def validate_volume_label(cls, v):
        if v and len(v.strip()) == 0:
            raise ValueError("Volume label не может быть пустой строкой")
        return v

class DiskVolume(BaseModel):
    id: int
    hostname: NonEmptyStr
    disk_id: NonEmptyStr = Field(..., alias="disk_id", min_length=1, max_length=255)
    volume_label: Optional[NonEmptyStr] = Field(None, alias="volume_label", max_length=255)
    total_space_gb: float = Field(ge=0.0)
    free_space_gb: float = Field(ge=0.0)
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator('disk_id')
    @classmethod 
    def validate_disk_id(cls, v):
        if len(v.strip()) == 0: 
            raise ValueError("Disk ID не может быть пустой строкой")
        return v

    @field_validator('volume_label')
    @classmethod
    def validate_volume_label(cls, v):
        if v and len(v.strip()) == 0:
            raise ValueError("Volume label не может быть пустой строкой")
        return v

class VideoCard(BaseModel):
    name: NonEmptyStr = Field(..., alias="name")
    driver_version: Optional[NonEmptyStr] = Field(None, alias="driver_version")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    detected_on: Optional[datetime] = None
    removed_on: Optional[datetime] = None

class Processor(BaseModel):
    name: NonEmptyStr = Field(..., alias="name")
    number_of_cores: int = Field(..., alias="number_of_cores")
    number_of_logical_processors: int = Field(..., alias="number_of_logical_processors")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    detected_on: Optional[datetime] = None
    removed_on: Optional[datetime] = None

class IPAddress(BaseModel):
    address: NonEmptyStr
    model_config = ConfigDict(from_attributes=True)
    detected_on: Optional[datetime] = None
    removed_on: Optional[datetime] = None

    @field_validator('address')
    @classmethod
    def validate_ip(cls, v):
        return validate_ip_address(cls, v, "IP address")

class MACAddress(BaseModel):
    address: NonEmptyStr
    model_config = ConfigDict(from_attributes=True)
    detected_on: Optional[datetime] = None
    removed_on: Optional[datetime] = None

    @field_validator('address')
    @classmethod
    def validate_mac(cls, v):
        return validate_mac_address(cls, v, "MAC address")

class ComputerBase(BaseModel):
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
    physical_disks: List[PhysicalDisk] = []
    logical_disks: List[LogicalDisk] = []
    software: List[Software] = []
    roles: List[Role] = []
    video_cards: List[VideoCard] = []
    processors: List[Processor] = []
    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: lambda v: v.isoformat() if v else None})

class Computer(ComputerBase):
    id: int
    last_updated: datetime
    physical_disks: List[PhysicalDisk] = []
    logical_disks: List[LogicalDisk] = []
    roles: List[Role] = []
    software: List[Software] = []
    video_cards: List[VideoCard] = []
    model_config = ConfigDict(from_attributes=True, json_encoders={datetime: lambda v: v.isoformat() if v else None})

class ComputerCreate(ComputerBase):
    roles: List[Role] = []
    software: List[Software] = []
    physical_disks: List[PhysicalDisk] = []
    logical_disks: List[LogicalDisk] = []
    video_cards: List[VideoCard] = []
    processors: List[Processor] = []
    model_config = ConfigDict(from_attributes=True)

class ComputerUpdateCheckStatus(BaseModel):
    hostname: NonEmptyStr
    check_status: CheckStatus
    model_config = ConfigDict(from_attributes=True)

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

class ComponentChangeStats(BaseModel):
    component_type: str
    changes_count: int

class DashboardStats(BaseModel):
    total_computers: Optional[int] = None  # Изменено с int | None на Optional[int]
    os_stats: OsStats
    disk_stats: DiskStats
    scan_stats: ScanStats
    component_changes: List[ComponentChangeStats] = []

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

class ComponentHistory(BaseModel):
    component_type: str
    data: Union[PhysicalDisk, LogicalDisk, Processor, VideoCard, IPAddress, MACAddress, Software]
    detected_on: Optional[str] = None
    removed_on: Optional[str] = None