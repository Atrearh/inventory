# app/models.py
from sqlalchemy import Integer, String, Boolean, DateTime, Enum, ForeignKey, Index, func, BigInteger, Column
from sqlalchemy.orm import relationship, Mapped, mapped_column
import enum
from .database import Base
from typing import Optional, List

class CheckStatus(enum.Enum):
    success = "success"
    failed = "failed"
    unreachable = "unreachable"

class ScanStatus(enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"

class ADComputer(Base):
    __tablename__ = "ad_computers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    hostname: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    os_name: Mapped[Optional[str]] = mapped_column(String)
    object_guid: Mapped[Optional[str]] = mapped_column(String)
    when_created: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    when_changed: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    enabled: Mapped[Optional[bool]] = mapped_column(Boolean)
    last_updated: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

class Processor(Base):
    __tablename__ = "processors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    number_of_cores: Mapped[int] = mapped_column(Integer, nullable=False)
    number_of_logical_processors: Mapped[int] = mapped_column(Integer, nullable=False)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="processors")
    __table_args__ = (
        Index('idx_computer_processor', 'computer_id', 'name', unique=True),
    )

class IPAddress(Base):
    __tablename__ = "ip_addresses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    address: Mapped[str] = mapped_column(String(45), nullable=False)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="ip_addresses")
    __table_args__ = (
        Index('idx_computer_ip', 'computer_id', 'address', unique=True),
    )

class MACAddress(Base):
    __tablename__ = "mac_addresses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    address: Mapped[str] = mapped_column(String(17), nullable=False)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="mac_addresses")
    __table_args__ = (
        Index('idx_computer_mac', 'computer_id', 'address', unique=True),
    )

class Computer(Base):
    __tablename__ = "computers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    hostname: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    ip_addresses: Mapped[List["IPAddress"]] = relationship("IPAddress", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    mac_addresses: Mapped[List["MACAddress"]] = relationship("MACAddress", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    os_name: Mapped[Optional[str]] = mapped_column(String)
    os_version: Mapped[Optional[str]] = mapped_column(String)
    ram: Mapped[Optional[int]] = mapped_column(Integer)
    motherboard: Mapped[Optional[str]] = mapped_column(String)
    last_boot: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    last_updated: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    last_full_scan: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    is_virtual: Mapped[bool] = mapped_column(Boolean, default=False)
    check_status: Mapped[CheckStatus] = mapped_column(Enum(CheckStatus), default=CheckStatus.success, nullable=False)

    roles: Mapped[List["Role"]] = relationship("Role", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    software: Mapped[List["Software"]] = relationship("Software", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    disks: Mapped[List["Disk"]] = relationship("Disk", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    video_cards: Mapped[List["VideoCard"]] = relationship("VideoCard", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    processors: Mapped[List["Processor"]] = relationship("Processor", back_populates="computer", cascade="all, delete-orphan", lazy="raise")
    change_logs: Mapped[List["ChangeLog"]] = relationship("ChangeLog", back_populates="computer", cascade="all, delete-orphan", lazy="raise")

    __table_args__ = (
        Index('idx_computer_hostname', 'hostname'),
    )

class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="roles")
    __table_args__ = (
        Index('idx_computer_role', 'computer_id', 'name', unique=True),
    )

class Software(Base):
    __tablename__ = "software"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    install_date: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    action: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="software")
    __table_args__ = (
        Index('idx_computer_software', 'computer_id', 'name', 'version', unique=True),
        Index('idx_software_is_deleted', 'is_deleted'),
    )

class Disk(Base):
    __tablename__ = "disks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_space: Mapped[int] = mapped_column(BigInteger, nullable=False)
    free_space: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="disks")
    serial =  Column(String, nullable=True)
    interface = Column(String, nullable=True)
    media_type =  Column(String, nullable=True)
    volume_label =  Column(String, nullable=True)
    __table_args__ = (
        Index('idx_computer_disk', 'computer_id', 'device_id', unique=True),
    )

class VideoCard(Base):
    __tablename__ = "video_cards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    driver_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    computer: Mapped["Computer"] = relationship("Computer", back_populates="video_cards")
    __table_args__ = (
        Index('idx_computer_video_card', 'computer_id', 'name', unique=True),
    )

class ChangeLog(Base):
    __tablename__ = "change_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    computer_id: Mapped[int] = mapped_column(Integer, ForeignKey("computers.id"), nullable=False)
    field: Mapped[str] = mapped_column(String, nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(String(255))
    new_value: Mapped[Optional[str]] = mapped_column(String(255))
    changed_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    computer: Mapped["Computer"] = relationship("Computer", back_populates="change_logs")
    __table_args__ = (
        Index('idx_change_log_computer_id', 'computer_id'),
    )

class ScanTask(Base):
    __tablename__ = "scan_tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), default=ScanStatus.pending, nullable=False)
    scanned_hosts: Mapped[int] = mapped_column(Integer, default=0)
    successful_hosts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())