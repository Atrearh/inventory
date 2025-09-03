import logging
import ipaddress
from datetime import datetime
from typing import Optional, List, Union, Any
from pydantic import BaseModel, field_validator, Field, ConfigDict, EmailStr, HttpUrl, computed_field
from fastapi_users import schemas
from app.utils.validators import NonEmptyStr, HostnameStr, MACAddressStr, IPAddressStr, DomainNameStr, validate_ip_address_format, validate_mac_address_format
from app.models import CheckStatus, ScanStatus
from hashlib import md5

logger = logging.getLogger(__name__)

# --- Базові класи та Enums ---

class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )

class TrackableComponent(BaseSchema):
    detected_on: Optional[datetime] = None
    removed_on: Optional[datetime] = None

# --- Схеми компонентів комп'ютера ---

class Role(TrackableComponent):
    name: NonEmptyStr = Field(..., alias="Name")

    @classmethod
    def from_raw_data(cls, raw_data: Any, hostname: str) -> List['Role']:
        """Перетворює сирі дані ролей у список Pydantic-схем."""
        if not isinstance(raw_data, (list, str)):
            logger.warning(f"Некоректні дані ролей: {raw_data}", extra={"hostname": hostname})
            return []
        data_list = [raw_data] if isinstance(raw_data, str) else raw_data
        seen_identifiers = set()
        result = []

        for item in data_list:
            try:
                name = item.strip() if isinstance(item, str) else item.get("name", "").strip()
                if not name or name in seen_identifiers:
                    continue
                seen_identifiers.add(name)
                result.append(cls(name=name))
            except Exception as e:
                logger.warning(f"Помилка обробки ролі: {str(e)}", extra={"data": item, "hostname": hostname})
        return result

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
            logger.warning(f"Некоректний формат install_date: {v}, повертаємо None")
            return None

    @classmethod
    def from_raw_data(cls, raw_data: Any, hostname: str) -> List['Software']:
        """Перетворює сирі дані програмного забезпечення у список Pydantic-схем."""
        if not isinstance(raw_data, list):
            raw_data = [raw_data] if raw_data else []
        seen_identifiers = set()
        result = []

        for item in raw_data:
            if not isinstance(item, dict):
                logger.warning(f"Некоректні дані ПЗ: {item}", extra={"hostname": hostname})
                continue
            try:
                name = item.get("DisplayName", item.get("name", "")).strip()
                if not name or name in seen_identifiers:
                    continue
                seen_identifiers.add(name)
                result.append(cls(
                    name=name,
                    version=item.get("version", "Unknown"),
                    install_date=item.get("install_date")
                ))
            except Exception as e:
                logger.warning(f"Помилка обробки ПЗ: {str(e)}", extra={"data": item, "hostname": hostname})
        return result

class PhysicalDisk(TrackableComponent):
    id: Optional[int] = None
    computer_id: Optional[int] = None
    model: Optional[NonEmptyStr] = Field(None, alias="model", max_length=255)
    serial: NonEmptyStr = Field(..., alias="serial", max_length=100)
    interface: Optional[NonEmptyStr] = Field(None, alias="interface", max_length=50)
    media_type: Optional[NonEmptyStr] = Field(None, alias="media_type", max_length=50)

    @classmethod
    def from_raw_data(cls, raw_data: Any, hostname: str) -> List['PhysicalDisk']:
        """Перетворює сирі дані фізичних дисків у список Pydantic-схем."""
        if not isinstance(raw_data, list):
            raw_data = [raw_data] if raw_data else []
        seen_identifiers = set()
        result = []

        for item in raw_data:
            if not isinstance(item, dict):
                logger.warning(f"Некоректні дані диска: {item}", extra={"hostname": hostname})
                continue
            try:
                serial = item.get("serial", "").strip()
                if not serial:
                    model = item.get("model", "")
                    serial = md5(f"{model}_{item.get('size', '')}_{hostname}".encode()).hexdigest()[:100]
                if serial in seen_identifiers:
                    continue
                seen_identifiers.add(serial)
                result.append(cls(
                    model=item.get("model"),
                    serial=serial,
                    interface=item.get("interface"),
                    media_type=item.get("media_type")
                ))
            except Exception as e:
                logger.warning(f"Помилка обробки диска: {str(e)}", extra={"data": item, "hostname": hostname})
        return result

class LogicalDisk(TrackableComponent):
    device_id: Optional[NonEmptyStr] = Field(None, alias="device_id", max_length=255)
    volume_label: Optional[str] = Field(None, alias="volume_label", max_length=255)
    total_space: int = Field(ge=0, alias="total_space")
    free_space: Optional[int] = Field(None, ge=0, alias="free_space")
    parent_disk_serial: Optional[NonEmptyStr] = Field(None, alias="parent_disk_serial", max_length=100)

    @field_validator('volume_label')
    @classmethod
    def normalize_volume_label(cls, v):
        return None if v == "" else v

    @computed_field(return_type=float)
    @property
    def total_space_gb(self) -> float:
        return self.total_space / (1024 ** 3) if self.total_space else 0.0

    @computed_field(return_type=Optional[float])
    @property
    def free_space_gb(self) -> Optional[float]:
        return self.free_space / (1024 ** 3) if self.free_space is not None else None

    @classmethod
    def from_raw_data(cls, raw_data: Any, hostname: str) -> List['LogicalDisk']:
        """Перетворює сирі дані логічних дисків у список Pydantic-схем."""
        if not isinstance(raw_data, list):
            raw_data = [raw_data] if raw_data else []
        seen_identifiers = set()
        result = []

        for item in raw_data:
            if not isinstance(item, dict):
                logger.warning(f"Некоректні дані логічного диска: {item}", extra={"hostname": hostname})
                continue
            try:
                device_id = item.get("device_id", "").strip()
                if not device_id or device_id in seen_identifiers:
                    continue
                seen_identifiers.add(device_id)
                result.append(cls(
                    device_id=device_id,
                    volume_label=item.get("volume_label"),
                    total_space=item.get("total_space", 0),
                    free_space=item.get("free_space"),
                    parent_disk_serial=item.get("parent_disk_serial")
                ))
            except Exception as e:
                logger.warning(f"Помилка обробки логічного диска: {str(e)}", extra={"data": item, "hostname": hostname})
        return result

class VideoCard(TrackableComponent):
    id: Optional[int] = None
    name: NonEmptyStr = Field(..., alias="name")
    driver_version: Optional[NonEmptyStr] = Field(None, alias="driver_version")

    @classmethod
    def from_raw_data(cls, raw_data: Any, hostname: str) -> List['VideoCard']:
        """Перетворює сирі дані відеокарт у список Pydantic-схем."""
        if not isinstance(raw_data, list):
            raw_data = [raw_data] if raw_data else []
        seen_identifiers = set()
        result = []

        for item in raw_data:
            if not isinstance(item, dict):
                logger.warning(f"Некоректні дані відеокарти: {item}", extra={"hostname": hostname})
                continue
            try:
                name = item.get("name", "").strip()
                if not name or name in seen_identifiers:
                    continue
                seen_identifiers.add(name)
                result.append(cls(
                    name=name,
                    driver_version=item.get("driver_version")
                ))
            except Exception as e:
                logger.warning(f"Помилка обробки відеокарти: {str(e)}", extra={"data": item, "hostname": hostname})
        return result

class Processor(TrackableComponent):
    name: NonEmptyStr = Field(..., alias="name")
    number_of_cores: int = Field(..., alias="number_of_cores")
    number_of_logical_processors: int = Field(..., alias="number_of_logical_processors")

    @classmethod
    def from_raw_data(cls, raw_data: Any, hostname: str) -> List['Processor']:
        """Перетворює сирі дані процесорів у список Pydantic-схем."""
        if not isinstance(raw_data, list):
            raw_data = [raw_data] if raw_data else []
        seen_identifiers = set()
        result = []

        for item in raw_data:
            if not isinstance(item, dict):
                logger.warning(f"Некоректні дані процесора: {item}", extra={"hostname": hostname})
                continue
            try:
                name = item.get("name", "").strip()
                if not name or name in seen_identifiers:
                    continue
                seen_identifiers.add(name)
                result.append(cls(
                    name=name,
                    number_of_cores=item.get("number_of_cores", 0),
                    number_of_logical_processors=item.get("number_of_logical_processors", 0)
                ))
            except Exception as e:
                logger.warning(f"Помилка обробки процесора: {str(e)}", extra={"data": item, "hostname": hostname})
        return result

class IPAddress(TrackableComponent):
    address: IPAddressStr

    @classmethod
    def from_raw_data(cls, raw_data: Any, hostname: str) -> List['IPAddress']:
        """Перетворює сирі дані IP-адрес у список Pydantic-схем."""
        if not isinstance(raw_data, (list, str)):
            logger.warning(f"Некоректні дані IP: {raw_data}", extra={"hostname": hostname})
            return []
        data_list = [raw_data] if isinstance(raw_data, str) else raw_data
        seen_identifiers = set()
        result = []

        for item in data_list:
            try:
                address = item.strip() if isinstance(item, str) else item.get("address", "").strip()
                if not address or not validate_ip_address_format(address) or address in seen_identifiers:
                    continue
                seen_identifiers.add(address)
                result.append(cls(address=address))
            except Exception as e:
                logger.warning(f"Помилка обробки IP: {str(e)}", extra={"data": item, "hostname": hostname})
        return result

class MACAddress(TrackableComponent):
    address: MACAddressStr

    @classmethod
    def from_raw_data(cls, raw_data: Any, hostname: str) -> List['MACAddress']:
        """Перетворює сирі дані MAC-адрес у список Pydantic-схем."""
        if not isinstance(raw_data, (list, str)):
            logger.warning(f"Некоректні дані MAC: {raw_data}", extra={"hostname": hostname})
            return []
        data_list = [raw_data] if isinstance(raw_data, str) else raw_data
        seen_identifiers = set()
        result = []

        for item in data_list:
            try:
                address = item.strip() if isinstance(item, str) else item.get("address", "").strip()
                if not validate_mac_address_format(address) or address in seen_identifiers:
                    continue
                seen_identifiers.add(address)
                result.append(cls(address=address))
            except Exception as e:
                logger.warning(f"Помилка обробки MAC: {str(e)}", extra={"data": item, "hostname": hostname})
        return result

# --- Схеми комп'ютера ---

class ComputerBase(BaseSchema):
    hostname: HostnameStr 
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
    last_logon: Optional[datetime] = None
    object_guid: Optional[NonEmptyStr] = None
    when_created: Optional[datetime] = None
    when_changed: Optional[datetime] = None
    enabled: Optional[bool] = None
    ad_notes: Optional[NonEmptyStr] = None
    local_notes: Optional[NonEmptyStr] = None
    domain_id: Optional[int] = None

    @field_validator('os_name')
    @classmethod
    def normalize_os_name(cls, v):
        if not v or not v.strip():
            return 'Unknown'
        return v.replace('Майкрософт ', '').replace('Microsoft ', '')

    @field_validator('ram')
    @classmethod
    def normalize_ram(cls, v):
        if v is None:
            return None
        if not isinstance(v, (int, float)):
            logger.warning(f"Некоректний тип RAM: {type(v)}, очікується int або float")
            return None
        if v > 4294967295:
            logger.warning(f"Значення RAM ({v} МБ) перевищує допустимий діапазон, обрізається до 4294967295")
            return 4294967295
        return int(v)

class ComputerList(ComputerBase):
    id: int
    last_updated: Optional[datetime] = None
    last_full_scan: Optional[datetime] = None



class ComputerListItem(ComputerBase):
    id: int
    last_updated: datetime
    last_full_scan: Optional[datetime] = None

class Computer(ComputerBase):
    id: int
    last_updated: datetime

class ComputerCreate(ComputerBase):
    pass

class ComputerUpdateCheckStatus(BaseSchema):
    hostname: HostnameStr 
    check_status: CheckStatus

# --- Схеми для API відповідей та статистики ---

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

class DiskVolume(BaseSchema):
    id: int
    hostname: HostnameStr 
    disk_id: NonEmptyStr = Field(..., alias="disk_id", max_length=255)
    volume_label: Optional[NonEmptyStr] = Field(None, alias="volume_label", max_length=255)
    total_space_gb: float = Field(ge=0.0)
    free_space_gb: float = Field(ge=0.0)

class DiskStats(BaseSchema):
    low_disk_space: List[DiskVolume]

class ScanStats(BaseSchema):
    last_scan_time: Optional[datetime]
    status_stats: List[StatusStats]

class ComponentChangeStats(BaseSchema):
    component_type: str
    changes_count: int

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
    detail: Optional[str] = None
    correlation_id: Optional[str] = None

# --- Схеми налаштувань та історії ---

class AppSettingUpdate(BaseSchema):
    ad_server_url: Optional[NonEmptyStr] = None
    domain: Optional[NonEmptyStr] = None
    ad_username: Optional[NonEmptyStr] = None
    ad_password: Optional[NonEmptyStr] = None
    api_url: Optional[HttpUrl] = None 
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
    cors_allow_origins: Optional[str] = None
    allowed_ips: Optional[str] = None
    encryption_key: Optional[NonEmptyStr] = None
    timezone: Optional[NonEmptyStr] = None

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

# --- Схеми користувачів ---

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


class TaskRead(BaseModel):
    id: str
    name: str
    status: str
    created_at: str

