import re
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4
from sqlalchemy import (
    Column, Enum, Index, UniqueConstraint, func, String, BigInteger, Integer, Boolean, Float, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from app.utils.validators import (DomainNameStr, HostnameStr, NonEmptyStr, IPAddressStr, MACAddressStr)
from app.schemas import ScanStatus, CheckStatus

class Base(DeclarativeBase):
    pass

# Mixin-клас для полів аудиту
class DetectionLifecycleMixin:
    detected_on: Mapped[datetime] = mapped_column(default=datetime.utcnow, server_default=func.now())
    removed_on: Mapped[Optional[datetime]] = mapped_column(default=None)

class OperatingSystem(Base):
    __tablename__ = "operating_systems"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[NonEmptyStr] = mapped_column(String(255))
    version: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    architecture: Mapped[Optional[str]] = mapped_column(String(50), default=None)

    computers: Mapped[List["Computer"]] = relationship(back_populates="os")

    __table_args__ = (
        UniqueConstraint("name", "version", "architecture", name="ux_os_unique"),
        Index("idx_os_name_version", "name", "version"),
    )

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    device_type: Mapped[str] = mapped_column(String(50))
    hostname: Mapped[HostnameStr] = mapped_column(String(255), nullable=False, index=True)

    ip_addresses: Mapped[List["IPAddress"]] = relationship(
        back_populates="device",
        primaryjoin="Device.id == foreign(IPAddress.device_id)"
    )
    mac_addresses: Mapped[List["MACAddress"]] = relationship(
        back_populates="device",
        primaryjoin="Device.id == foreign(MACAddress.device_id)"
    )

    __mapper_args__ = {
        "polymorphic_on": "device_type",
        "polymorphic_identity": "device",
    }

class Computer(Base):
    __tablename__ = "computers"
    id: Mapped[int] = mapped_column(ForeignKey("devices.id"), primary_key=True, index=True)
    os_id: Mapped[Optional[int]] = mapped_column(ForeignKey("operating_systems.id"))
    os: Mapped[Optional["OperatingSystem"]] = relationship(back_populates="computers")
    ram: Mapped[Optional[int]] = mapped_column(default=None)
    motherboard: Mapped[Optional[NonEmptyStr]] = mapped_column(String(255), default=None)
    last_boot: Mapped[Optional[datetime]] = mapped_column(default=None)
    last_updated: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_full_scan: Mapped[Optional[datetime]] = mapped_column(default=None)
    domain_id: Mapped[Optional[int]] = mapped_column(ForeignKey("domains.id"))
    domain: Mapped[Optional["Domain"]] = relationship(back_populates="computers")
    object_guid: Mapped[Optional[str]] = mapped_column(String(36), default=None)
    when_created: Mapped[Optional[datetime]] = mapped_column(default=None)
    when_changed: Mapped[Optional[datetime]] = mapped_column(default=None)
    enabled: Mapped[Optional[bool]] = mapped_column(default=None)
    ad_notes: Mapped[Optional[NonEmptyStr]] = mapped_column(String(1000), default=None)
    local_notes: Mapped[Optional[NonEmptyStr]] = mapped_column(String(1000), default=None)
    last_logon: Mapped[Optional[datetime]] = mapped_column(default=None)
    check_status: Mapped[Optional[CheckStatus]] = mapped_column(Enum(CheckStatus))
    is_virtual: Mapped[bool] = mapped_column(default=False)
    physical_disks: Mapped[List["PhysicalDisk"]] = relationship(back_populates="computer")
    logical_disks: Mapped[List["LogicalDisk"]] = relationship(back_populates="computer")
    processors: Mapped[List["Processor"]] = relationship(back_populates="computer")
    video_cards: Mapped[List["VideoCard"]] = relationship(back_populates="computer")
    installed_software: Mapped[List["InstalledSoftware"]] = relationship(back_populates="computer")
    roles: Mapped[List["Role"]] = relationship(back_populates="computer")

    __mapper_args__ = {
        "polymorphic_identity": "computer",
    }

class SoftwareCatalog(Base):
    __tablename__ = "software_catalog"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[NonEmptyStr] = mapped_column(String(255))
    version: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), default=None)

    installations: Mapped[List["InstalledSoftware"]] = relationship(back_populates="software_details")

    __table_args__ = (
        UniqueConstraint("name", "version", "publisher", name="ux_software_unique"),
        Index("idx_software_name_version", "name", "version"),
    )

class InstalledSoftware(DetectionLifecycleMixin, Base):
    __tablename__ = "installed_software"

    id: Mapped[int] = mapped_column(primary_key=True)
    computer_id: Mapped[int] = mapped_column(ForeignKey("computers.id"))
    software_id: Mapped[int] = mapped_column(ForeignKey("software_catalog.id"))
    install_date: Mapped[Optional[datetime]] = mapped_column(default=None)
    computer: Mapped["Computer"] = relationship(back_populates="installed_software")
    software_details: Mapped["SoftwareCatalog"] = relationship(back_populates="installations")

    __table_args__ = (UniqueConstraint("computer_id", "software_id", name="ux_computer_software"),)

class PhysicalDisk(DetectionLifecycleMixin, Base):
    __tablename__ = "physical_disks"

    id: Mapped[int] = mapped_column(primary_key=True)
    computer_id: Mapped[int] = mapped_column(ForeignKey("computers.id"))
    model: Mapped[Optional[NonEmptyStr]] = mapped_column(String(255), default=None)
    serial: Mapped[Optional[NonEmptyStr]] = mapped_column(String(100), default=None)
    interface: Mapped[Optional[NonEmptyStr]] = mapped_column(String(50), default=None)
    media_type: Mapped[Optional[NonEmptyStr]] = mapped_column(String(50), default=None)
    computer: Mapped["Computer"] = relationship(back_populates="physical_disks")

    __table_args__ = (
        Index("idx_physical_disk_computer_serial", "computer_id", "serial", unique=True),
    )

class LogicalDisk(DetectionLifecycleMixin, Base):
    __tablename__ = "logical_disks"

    id: Mapped[int] = mapped_column(primary_key=True)
    computer_id: Mapped[int] = mapped_column(ForeignKey("computers.id"))
    device_id: Mapped[Optional[NonEmptyStr]] = mapped_column(String(255), default=None)
    volume_label: Mapped[Optional[NonEmptyStr]] = mapped_column(String(255), default=None)
    total_space: Mapped[int] = mapped_column(BigInteger, nullable=False)
    physical_disk_id: Mapped[Optional[int]] = mapped_column(ForeignKey("physical_disks.id"))
    free_space: Mapped[Optional[int]] = mapped_column(BigInteger, default=None)
    computer: Mapped["Computer"] = relationship(back_populates="logical_disks")
    physical_disk: Mapped[Optional["PhysicalDisk"]] = relationship()

    __table_args__ = (
        Index("idx_logical_disk_computer_device_id", "computer_id", "device_id", unique=True),
    )

class Processor(DetectionLifecycleMixin, Base):
    __tablename__ = "processors"

    id: Mapped[int] = mapped_column(primary_key=True)
    computer_id: Mapped[int] = mapped_column(ForeignKey("computers.id"))
    name: Mapped[NonEmptyStr] = mapped_column(String(255))
    cores: Mapped[Optional[int]] = mapped_column(default=None)
    threads: Mapped[Optional[int]] = mapped_column(default=None)
    speed_ghz: Mapped[Optional[float]] = mapped_column(default=None)
    computer: Mapped["Computer"] = relationship(back_populates="processors")

    __table_args__ = (
        Index("idx_processor_computer_name", "computer_id", "name", unique=True),
    )

class VideoCard(DetectionLifecycleMixin, Base):
    __tablename__ = "video_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    computer_id: Mapped[int] = mapped_column(ForeignKey("computers.id"))
    name: Mapped[NonEmptyStr] = mapped_column(String(255))
    vram: Mapped[Optional[int]] = mapped_column(default=None)
    driver_version: Mapped[Optional[NonEmptyStr]] = mapped_column(String(50), default=None)
    computer: Mapped["Computer"] = relationship(back_populates="video_cards")

    __table_args__ = (
        Index("idx_video_card_computer_name", "computer_id", "name", unique=True),
    )

class IPAddress(DetectionLifecycleMixin, Base):
    __tablename__ = "ip_addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False)
    address: Mapped[IPAddressStr] = mapped_column(String(45))
    device: Mapped[Optional["Device"]] = relationship(
        back_populates="ip_addresses",
        primaryjoin="Device.id == foreign(IPAddress.device_id)"
    )

    __table_args__ = (
        Index("idx_ip_address_device_address", "device_id", "address", unique=True),
    )

class MACAddress(DetectionLifecycleMixin, Base):
    __tablename__ = "mac_addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    address: Mapped[MACAddressStr] = mapped_column(String(17))
    device: Mapped[Optional["Device"]] = relationship(
        back_populates="mac_addresses",
        primaryjoin="Device.id == foreign(MACAddress.device_id)"
    )

    __table_args__ = (
        Index("idx_mac_address_device_address", "device_id", "address", unique=True),
    )

class Role(DetectionLifecycleMixin, Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(ForeignKey("computers.id"), nullable=False)
    name: Mapped[NonEmptyStr] = mapped_column(String(255), nullable=False)
    computer: Mapped["Computer"] = relationship(back_populates="roles")

    __table_args__ = (Index("idx_computer_role", "computer_id", "name", unique=True),)

class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[DomainNameStr] = mapped_column(String(255), unique=True)
    username: Mapped[NonEmptyStr] = mapped_column(String(255))
    encrypted_password: Mapped[NonEmptyStr] = mapped_column(String(512), nullable=False)
    server_url: Mapped[DomainNameStr] = mapped_column(String(255))
    ad_base_dn: Mapped[NonEmptyStr] = mapped_column(String(255))
    last_updated: Mapped[Optional[datetime]] = mapped_column(default=None)

    computers: Mapped[List["Computer"]] = relationship(back_populates="domain")

    __table_args__ = (
        Index("idx_domain_name", "name"),
    )

class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()), primary_key=True, index=True)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), nullable=False)
    scanned_hosts: Mapped[int] = mapped_column(default=0)
    successful_hosts: Mapped[int] = mapped_column(default=0)
    error: Mapped[Optional[NonEmptyStr]] = mapped_column(String(1000), default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=func.now(), onupdate=func.now()
    )
    name: Mapped[Optional[NonEmptyStr]] = mapped_column(String(255), default=None)

class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    value: Mapped[str] = mapped_column()

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    username: Mapped[NonEmptyStr] = mapped_column(String(50), nullable=False)
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(back_populates="user")

    @classmethod
    def validate_email(cls, value: str) -> str:
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value):
            raise ValueError("email must be a valid email address (e.g., user@example.com)")
        return value

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(index=True, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow() + timedelta(seconds=604800), nullable=False
    )
    revoked: Mapped[bool] = mapped_column(default=False, nullable=False)
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_user_token", "user_id", "token", unique=True),
        Index("idx_token_expires", "token", "expires_at"),
    )

class DahuaDVR(Device):
    __tablename__ = "dahua_dvrs"

    name: Mapped[NonEmptyStr] = mapped_column(String(255), nullable=False, unique=True)
    port: Mapped[int] = mapped_column(Integer, default=37777, nullable=False)
    users: Mapped[List["DahuaDVRUser"]] = relationship(back_populates="dvr")

    __mapper_args__ = {
        "polymorphic_identity": "dahua_dvr",
    }

class DahuaDVRUser(Base):
    __tablename__ = "dahua_dvr_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    dvr_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    username: Mapped[NonEmptyStr] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[NonEmptyStr] = mapped_column(String(512), nullable=False)

    dvr: Mapped["DahuaDVR"] = relationship(back_populates="users")

    __table_args__ = (UniqueConstraint("dvr_id", "username", name="ux_dvr_user"),)

class ScanTask(Base):
    __tablename__ = "scan_tasks"

    id: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()), primary_key=True, index=True)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), default=ScanStatus.pending, nullable=False)
    scanned_hosts: Mapped[int] = mapped_column(default=0)
    successful_hosts: Mapped[int] = mapped_column(default=0)
    error: Mapped[Optional[NonEmptyStr]] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=func.now(), onupdate=func.now()
    )