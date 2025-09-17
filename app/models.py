import re
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4
from pydantic import field_validator
from sqlalchemy import Column, Enum, Index, UniqueConstraint, func
from sqlmodel import Field, Relationship, SQLModel
from app.utils.validators import (
    DomainNameStr,
    HostnameStr,
    NonEmptyStr,
    IPAddressStr,
    MACAddressStr,
)
from sqlalchemy.types import BigInteger
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTable
from app.schemas import ScanStatus, CheckStatus


class OperatingSystem(SQLModel, table=True):
    __tablename__ = "operating_systems"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: NonEmptyStr = Field(max_length=255)
    version: Optional[str] = Field(max_length=100, default=None)
    architecture: Optional[str] = Field(max_length=50, default=None)

    computers: List["Computer"] = Relationship(back_populates="os")

    __table_args__ = (
        UniqueConstraint("name", "version", "architecture", name="ux_os_unique"),
        Index("idx_os_name_version", "name", "version"),
    )


# Нова модель: Єдиний каталог програмного забезпечення
class SoftwareCatalog(SQLModel, table=True):
    __tablename__ = "software_catalog"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: NonEmptyStr = Field(max_length=255)
    version: Optional[str] = Field(max_length=255, default=None)
    publisher: Optional[str] = Field(max_length=255, default=None)

    installations: List["InstalledSoftware"] = Relationship(back_populates="software_details")

    __table_args__ = (
        UniqueConstraint("name", "version", "publisher", name="ux_software_unique"),
        Index("idx_software_name_version", "name", "version"),
    )


# Нова модель: Зв'язуюча таблиця для встановленого ПЗ
class InstalledSoftware(SQLModel, table=True):
    __tablename__ = "installed_software"

    id: Optional[int] = Field(default=None, primary_key=True)
    computer_id: int = Field(foreign_key="computers.id")
    software_id: int = Field(foreign_key="software_catalog.id")

    install_date: Optional[datetime] = Field(default=None)
    detected_on: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    removed_on: Optional[datetime] = Field(default=None)  # Для відстеження видаленого ПЗ

    computer: "Computer" = Relationship(back_populates="installed_software")
    software_details: "SoftwareCatalog" = Relationship(back_populates="installations")

    __table_args__ = (UniqueConstraint("computer_id", "software_id", name="ux_computer_software"),)


# Оновлена модель Computer
class Computer(SQLModel, table=True):
    __tablename__ = "computers"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    hostname: HostnameStr = Field(max_length=255, nullable=False)

    # --- Зміни тут ---
    os_id: Optional[int] = Field(default=None, foreign_key="operating_systems.id")
    os: Optional[OperatingSystem] = Relationship(back_populates="computers")
    # ------------------

    ram: Optional[int] = Field(default=None)
    motherboard: Optional[NonEmptyStr] = Field(default=None, max_length=255)
    last_boot: Optional[datetime] = Field(default=None)
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
    )
    last_full_scan: Optional[datetime] = Field(default=None)
    check_status: CheckStatus = Field(default=CheckStatus.success, sa_column=Column(Enum(CheckStatus), nullable=False))
    object_guid: Optional[str] = Field(default=None, max_length=36, unique=True)
    when_created: Optional[datetime] = Field(default=None)
    when_changed: Optional[datetime] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)
    ad_notes: Optional[NonEmptyStr] = Field(default=None)
    local_notes: Optional[NonEmptyStr] = Field(default=None)
    last_logon: Optional[datetime] = Field(default=None)
    domain_id: int = Field(foreign_key="domains.id")

    # --- Зміни у зв'язках ---
    installed_software: List["InstalledSoftware"] = Relationship(back_populates="computer")
    # -------------------------

    # Існуючі зв'язки залишаються
    ip_addresses: List["IPAddress"] = Relationship(back_populates="computer")
    mac_addresses: List["MACAddress"] = Relationship(back_populates="computer")
    processors: List["Processor"] = Relationship(back_populates="computer")
    video_cards: List["VideoCard"] = Relationship(back_populates="computer")
    physical_disks: List["PhysicalDisk"] = Relationship(back_populates="computer")
    logical_disks: List["LogicalDisk"] = Relationship(back_populates="computer")
    roles: List["Role"] = Relationship(back_populates="computer")
    domain: Optional["Domain"] = Relationship(back_populates="computers")

    __table_args__ = (
        Index("idx_computers_last_updated", "last_updated"),
        Index("idx_computers_filters", "check_status", "last_updated"),  # os_name видалено з індексу
        UniqueConstraint("object_guid", name="idx_object_guid"),
    )


class Domain(SQLModel, table=True):
    __tablename__ = "domains"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    name: DomainNameStr = Field(max_length=255, nullable=False, unique=True)
    username: NonEmptyStr = Field(max_length=255, nullable=False)
    encrypted_password: NonEmptyStr = Field(max_length=512, nullable=False)
    server_url: Optional[DomainNameStr] = Field(default=None, max_length=255)
    ad_base_dn: Optional[NonEmptyStr] = Field(default=None, max_length=255)
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
    )

    # Зв’язок із комп’ютерами
    computers: List["Computer"] = Relationship(back_populates="domain")

    # Індекси
    __table_args__ = (Index("idx_domain_name", "name"),)

    # Валідація для ad_base_dn
    @field_validator("ad_base_dn")
    @classmethod
    def validate_ad_base_dn(cls, value: Optional[str]) -> Optional[str]:
        if value:
            # Перевірка формату LDAP DN (наприклад, DC=example,DC=com)
            if not re.match(r"^(?:[A-Za-z]+=[^,]+,)+[A-Za-z]+=[^,]+$", value):
                raise ValueError("ad_base_dn must be a valid LDAP Distinguished Name")
        return value


class ScanTask(SQLModel, table=True):
    __tablename__ = "scan_tasks"

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        max_length=36,
        primary_key=True,
        index=True,
    )
    status: ScanStatus = Field(default=ScanStatus.pending, sa_column_kwargs={"nullable": False})
    scanned_hosts: int = Field(default=0, ge=0)
    successful_hosts: int = Field(default=0, ge=0)
    error: Optional[NonEmptyStr] = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
    )


class PhysicalDisk(SQLModel, table=True):
    __tablename__ = "physical_disks"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    computer_id: int = Field(foreign_key="computers.id", nullable=False)
    model: Optional[NonEmptyStr] = Field(default=None, max_length=255)
    serial: Optional[NonEmptyStr] = Field(default=None, max_length=255)
    interface: Optional[NonEmptyStr] = Field(default=None, max_length=255)
    media_type: Optional[NonEmptyStr] = Field(default=None, max_length=255)
    detected_on: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    removed_on: Optional[datetime] = Field(default=None)

    computer: "Computer" = Relationship(back_populates="physical_disks")
    logical_disks: List["LogicalDisk"] = Relationship(back_populates="physical_disk")

    __table_args__ = (Index("idx_computer_physical_disk", "computer_id", "serial", unique=True),)


class LogicalDisk(SQLModel, table=True):
    __tablename__ = "logical_disks"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    computer_id: int = Field(foreign_key="computers.id", nullable=False)
    physical_disk_id: Optional[int] = Field(default=None, foreign_key="physical_disks.id")
    device_id: Optional[NonEmptyStr] = Field(default=None, max_length=255)
    volume_label: Optional[NonEmptyStr] = Field(default=None, max_length=255)
    total_space: int = Field(sa_type=BigInteger, nullable=False)
    free_space: Optional[int] = Field(default=None, sa_type=BigInteger)
    detected_on: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    removed_on: Optional[datetime] = Field(default=None)

    computer: "Computer" = Relationship(back_populates="logical_disks")
    physical_disk: Optional["PhysicalDisk"] = Relationship(back_populates="logical_disks")

    __table_args__ = (Index("idx_computer_logical_disk", "computer_id", "device_id", unique=True),)

    @field_validator("total_space", "free_space")
    @classmethod
    def validate_space(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 0:
            raise ValueError("Disk space must be non-negative")
        return value


class VideoCard(SQLModel, table=True):
    __tablename__ = "video_cards"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    computer_id: int = Field(foreign_key="computers.id", nullable=False)
    name: NonEmptyStr = Field(max_length=255, nullable=False)
    driver_version: Optional[NonEmptyStr] = Field(default=None, max_length=50)
    detected_on: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    removed_on: Optional[datetime] = Field(default=None)

    computer: "Computer" = Relationship(back_populates="video_cards")

    __table_args__ = (Index("idx_computer_video_card", "computer_id", "name", unique=True),)


class Processor(SQLModel, table=True):
    __tablename__ = "processors"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    computer_id: int = Field(foreign_key="computers.id", nullable=False)
    name: NonEmptyStr = Field(max_length=255, nullable=False)
    number_of_cores: int = Field(nullable=False)
    number_of_logical_processors: int = Field(nullable=False)
    detected_on: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    removed_on: Optional[datetime] = Field(default=None)

    computer: "Computer" = Relationship(back_populates="processors")

    __table_args__ = (Index("idx_computer_processor", "computer_id", "name", unique=True),)

    @field_validator("number_of_cores", "number_of_logical_processors")
    @classmethod
    def validate_cores(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Number of cores/processors must be positive")
        return value


class IPAddress(SQLModel, table=True):
    __tablename__ = "ip_addresses"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    computer_id: int = Field(foreign_key="computers.id", nullable=False)
    address: IPAddressStr = Field(max_length=45, nullable=False)  # Використовуємо IPAddressStr
    detected_on: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    removed_on: Optional[datetime] = Field(default=None)

    computer: "Computer" = Relationship(back_populates="ip_addresses")

    __table_args__ = (Index("idx_computer_ip", "computer_id", "address", unique=True),)


class MACAddress(SQLModel, table=True):
    __tablename__ = "mac_addresses"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    computer_id: int = Field(foreign_key="computers.id", nullable=False)
    address: MACAddressStr = Field(max_length=17, nullable=False)  # Використовуємо MACAddressStr
    detected_on: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    removed_on: Optional[datetime] = Field(default=None)

    computer: "Computer" = Relationship(back_populates="mac_addresses")

    __table_args__ = (Index("idx_computer_mac", "computer_id", "address", unique=True),)


class AppSetting(SQLModel, table=True):
    """
    Модель для збереження налаштувань додатку
    SQLModel автоматично створює SQLAlchemy таблицю з Pydantic валідацією
    """

    __tablename__ = "app_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(max_length=50, unique=True, index=True)
    value: str = Field()


class Role(SQLModel, table=True):
    __tablename__ = "roles"

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    computer_id: int = Field(foreign_key="computers.id", nullable=False)
    name: NonEmptyStr = Field(max_length=255, nullable=False)
    detected_on: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    removed_on: Optional[datetime] = Field(default=None)

    computer: "Computer" = Relationship(back_populates="roles")

    __table_args__ = (Index("idx_computer_role", "computer_id", "name", unique=True),)


class User(SQLModel, SQLAlchemyBaseUserTable, table=True):  # <--- Змінено: прибрали [int]
    __tablename__ = "users"

    # --- Поля, які тепер визначені явно ---
    id: Optional[int] = Field(default=None, primary_key=True)  # <--- Додано
    email: str = Field(max_length=320, unique=True, index=True, nullable=False)  # <--- Додано
    hashed_password: str = Field(max_length=1024, nullable=False)  # <--- Додано
    is_active: bool = Field(default=True, nullable=False)  # <--- Додано
    is_superuser: bool = Field(default=False, nullable=False)  # <--- Додано
    is_verified: bool = Field(default=False, nullable=False)  # <--- Додано

    # --- Ваші кастомні поля залишаються ---
    username: NonEmptyStr = Field(max_length=50, nullable=False)
    refresh_tokens: List["RefreshToken"] = Relationship(back_populates="user")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value):
            raise ValueError("email must be a valid email address (e.g., user@example.com)")
        return value


class RefreshToken(SQLModel, SQLAlchemyBaseAccessTokenTable, table=True):  # <--- Змінено: прибрали [int]
    __tablename__ = "refresh_tokens"

    # --- Поля, які тепер визначені явно ---
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(index=True, unique=True, nullable=False)
    user_id: int = Field(foreign_key="users.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    expires_at: datetime = Field(nullable=False)  # Це поле тепер визначено явно

    # --- Ваші кастомні поля ---
    revoked: bool = Field(default=False, nullable=False)
    user: "User" = Relationship(back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_user_token", "user_id", "token", unique=True),
        Index("idx_token_expires", "token", "expires_at"),
    )

    # Метод __init__ залишається без змін. Він буде працювати з полем expires_at.
    def __init__(self, **kwargs):
        if "expires_at" not in kwargs or kwargs["expires_at"] is None:
            kwargs["expires_at"] = datetime.utcnow() + timedelta(seconds=604800)
        super().__init__(**kwargs)
