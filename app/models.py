# app/models.py
from sqlalchemy import Integer, String, Boolean, DateTime, Enum, ForeignKey, Index, func, BigInteger, Column, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
import enum
from app.database import Base 
from typing import Optional, List
from datetime import datetime
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
import logging
logger = logging.getLogger(__name__)

class CheckStatus(enum.Enum):
    success = "success"
    failed = "failed"
    unreachable = "unreachable"
    partially_successful = "partially_successful"

class ScanStatus(enum.Enum):
    pending = "pending"
    running = "running" 
    completed = "completed"
    failed = "failed"

ENCRYPTION_KEY = None  
cipher = None  

class Domain(Base):
    __tablename__ = "domains"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[str] = mapped_column(String(255), nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (
        Index('idx_domain_name', 'name'),
    )
    

class Processor(Base):
    __tablename__ = "processors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    number_of_cores: Mapped[int] = mapped_column(Integer, nullable=False)
    number_of_logical_processors: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_on: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    removed_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="processors")
    __table_args__ = (
        Index('idx_computer_processor', 'computer_id', 'name', unique=True),
    )

class IPAddress(Base):
    __tablename__ = "ip_addresses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    address: Mapped[str] = mapped_column(String(45), nullable=False)
    detected_on: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    removed_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="ip_addresses")
    __table_args__ = (
        Index('idx_computer_ip', 'computer_id', 'address', unique=True),
    )

class MACAddress(Base):
    __tablename__ = "mac_addresses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    address: Mapped[str] = mapped_column(String(17), nullable=False)
    detected_on: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    removed_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="mac_addresses")
    __table_args__ = (
        Index('idx_computer_mac', 'computer_id', 'address', unique=True),
    )

class Computer(Base):
    __tablename__ = "computers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)  # Видалено unique=True
    physical_disks: Mapped[List["PhysicalDisk"]] = relationship("PhysicalDisk", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    logical_disks: Mapped[List["LogicalDisk"]] = relationship("LogicalDisk", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    os_name: Mapped[Optional[str]] = mapped_column(String(255))
    os_version: Mapped[Optional[str]] = mapped_column(String(50))
    ram: Mapped[Optional[int]] = mapped_column(Integer)
    motherboard: Mapped[Optional[str]] = mapped_column(String(255))
    last_boot: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    last_updated: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    last_full_scan: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    is_virtual: Mapped[bool] = mapped_column(Boolean, default=False)
    check_status: Mapped[CheckStatus] = mapped_column(Enum(CheckStatus), default=CheckStatus.success, nullable=False)
    # Нові поля для AD
    object_guid: Mapped[Optional[str]] = mapped_column(String(36), unique=True)
    when_created: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    when_changed: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    enabled: Mapped[Optional[bool]] = mapped_column(Boolean)
    ad_notes: Mapped[Optional[str]] = mapped_column(Text)
    local_notes: Mapped[Optional[str]] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_addresses: Mapped[List["IPAddress"]] = relationship("IPAddress", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    mac_addresses: Mapped[List["MACAddress"]] = relationship("MACAddress", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    roles: Mapped[List["Role"]] = relationship("Role", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    software: Mapped[List["Software"]] = relationship("Software", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    video_cards: Mapped[List["VideoCard"]] = relationship("VideoCard", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    processors: Mapped[List["Processor"]] = relationship("Processor", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    __table_args__ = (
        Index('idx_object_guid', 'object_guid', unique=True),
        Index('idx_computers_last_updated', 'last_updated'),
        Index('idx_computers_filters', 'os_name', 'check_status', 'last_updated'),
    )

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="roles")
    detected_on: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    removed_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        Index('idx_computer_role', 'computer_id', 'name', unique=True),
    )

class Software(Base):
    __tablename__ = "software"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    install_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    detected_on: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    removed_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="software")
    __table_args__ = (
        Index('idx_software_computer_id', 'computer_id', 'name', 'version', unique=True),
    )

class PhysicalDisk(Base):
    __tablename__ = "physical_disks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    serial: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    interface: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    media_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    detected_on: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    removed_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="physical_disks")
    __table_args__ = (
        Index('idx_computer_physical_disk', 'computer_id', 'serial', unique=True),
    )

class LogicalDisk(Base):
    __tablename__ = "logical_disks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    physical_disk_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("physical_disks.id"), nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    volume_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_space: Mapped[int] = mapped_column(BigInteger, nullable=False)
    free_space: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    detected_on: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    removed_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="logical_disks")
    physical_disk: Mapped[Optional["PhysicalDisk"]] = relationship("PhysicalDisk")
    __table_args__ = (
        Index('idx_computer_logical_disk', 'computer_id', 'device_id', unique=True),
    )

class VideoCard(Base):
    __tablename__ = "video_cards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    driver_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    detected_on: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    removed_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="video_cards")
    __table_args__ = (
        Index('idx_computer_video_card', 'computer_id', 'name', unique=True),
    )

class ScanTask(Base):
    __tablename__ = "scan_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), default=ScanStatus.pending, nullable=False)
    scanned_hosts: Mapped[int] = mapped_column(Integer, default=0)
    successful_hosts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

class User(SQLAlchemyBaseUserTable[int], Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

class AppSetting(Base):
    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)