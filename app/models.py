from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, Index, func, BigInteger
from sqlalchemy.orm import relationship
from .database import Base
import enum
from pydantic import BaseModel, field_validator
from typing import Optional 
import ipaddress
from datetime import datetime       
from .settings import validate_non_empty_string 

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
    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, unique=True, nullable=False)
    os_name = Column(String)
    object_guid = Column(String)
    when_created = Column(DateTime)
    when_changed = Column(DateTime)
    enabled = Column(Boolean)
    last_updated = Column(DateTime, default=func.now())

class Computer(Base):
    __tablename__ = "computers"
    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, unique=True, nullable=False)
    ip = Column(String)
    os_name = Column(String)
    os_version = Column(String)
    cpu = Column(String)
    ram = Column(Integer)
    mac = Column(String)
    motherboard = Column(String)
    last_boot = Column(DateTime)
    last_updated = Column(DateTime, default=func.now())
    last_full_scan = Column(DateTime)
    is_virtual = Column(Boolean, default=False)
    check_status = Column(Enum(CheckStatus), default=CheckStatus.success, nullable=False)

    roles = relationship("Role", back_populates="computer", cascade="all, delete-orphan")
    software = relationship("Software", back_populates="computer", cascade="all, delete-orphan")
    disks = relationship("Disk", back_populates="computer", cascade="all, delete-orphan")
    change_logs = relationship("ChangeLog", back_populates="computer", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_computer_hostname', 'hostname'),
    )

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
    last_updated: Optional[datetime] = None
    last_full_scan: Optional[datetime] = None  # Новое поле
    is_virtual: Optional[bool] = False
    check_status: Optional[CheckStatus] = CheckStatus.success

    @field_validator('hostname')
    @classmethod
    def validate_hostname(cls, v):
        return validate_non_empty_string(cls, v, "Hostname")

    @field_validator('ip')
    @classmethod
    def validate_ip(cls, v):
        if v:
            try:
                ipaddress.ip_address(v)
            except ValueError:
                raise ValueError("Неверный формат IP-адреса")
        return v


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    computer_id = Column(Integer, ForeignKey("computers.id"), nullable=False)
    name = Column(String, nullable=False)
    computer = relationship("Computer", back_populates="roles")
    __table_args__ = (
        Index('idx_computer_role', 'computer_id', 'name', unique=True),
        Index('idx_role_computer_id', 'computer_id'),
    )

class Software(Base):
    __tablename__ = "software"
    id = Column(Integer, primary_key=True, index=True)
    computer_id = Column(Integer, ForeignKey("computers.id"), nullable=False)
    name = Column(String, nullable=False)
    version = Column(String, nullable=True)
    install_date = Column(DateTime, nullable=True)
    action = Column(String(20), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    computer = relationship("Computer", back_populates="software")
    __table_args__ = (
        Index('idx_computer_software', 'computer_id', 'name', 'version', unique=True),
        Index('idx_software_computer_id', 'computer_id'),
        Index('idx_software_is_deleted', 'is_deleted'),  # Новый индекс
    )

class Disk(Base):
    __tablename__ = "disks"
    id = Column(Integer, primary_key=True, index=True)
    computer_id = Column(Integer, ForeignKey("computers.id"), nullable=False)
    device_id = Column(String, nullable=False)
    total_space = Column(BigInteger, nullable=False)
    free_space = Column(BigInteger, nullable=False)
    computer = relationship("Computer", back_populates="disks")
    __table_args__ = (
        Index('idx_computer_disk', 'computer_id', 'device_id', unique=True),
        Index('idx_disk_computer_id', 'computer_id'),
    )

class ChangeLog(Base):
    __tablename__ = "change_log"
    id = Column(Integer, primary_key=True, index=True)
    computer_id = Column(Integer, ForeignKey("computers.id"), nullable=False)
    field = Column(String, nullable=False)
    old_value = Column(String(255))
    new_value = Column(String(255))
    changed_at = Column(DateTime, default=func.now())
    computer = relationship("Computer", back_populates="change_logs")
    __table_args__ = (
        Index('idx_change_log_computer_id', 'computer_id'),
    )

class ScanTask(Base):
    __tablename__ = "scan_tasks"
    id = Column(String, primary_key=True, index=True)
    status = Column(Enum(ScanStatus), default=ScanStatus.pending, nullable=False)
    scanned_hosts = Column(Integer, default=0)
    successful_hosts = Column(Integer, default=0)
    error = Column(String)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now())