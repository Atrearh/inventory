# models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, Index, func, BigInteger
from sqlalchemy.orm import relationship
from .database import Base
import enum

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
    hostname = Column(String(255), unique=True, nullable=False)
    os_name = Column(String(255), nullable=True)
    object_guid = Column(String(36), nullable=True)
    when_created = Column(DateTime, nullable=True)
    when_changed = Column(DateTime, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Computer(Base):
    __tablename__ = "computers"
    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String(255), unique=True, nullable=False)
    ip = Column(String(255), nullable=True)
    os_name = Column(String(255), nullable=True)
    os_version = Column(String(255), nullable=True)
    cpu = Column(String(255), nullable=True)
    ram = Column(Integer, nullable=True)
    mac = Column(String(255))
    motherboard = Column(String(255))
    last_boot = Column(String(255))
    is_virtual = Column(Boolean)
    check_status = Column(Enum(CheckStatus), default=CheckStatus.unreachable, nullable=False)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
    roles = relationship("Role", back_populates="computer", cascade="all, delete-orphan")
    disks = relationship("Disk", back_populates="computer", cascade="all, delete-orphan", lazy="selectin")  # Изменено на selectin
    software = relationship("Software", back_populates="computer", cascade="all, delete-orphan")
    change_logs = relationship("ChangeLog", back_populates="computer", cascade="all, delete-orphan")

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    computer_id = Column(Integer, ForeignKey("computers.id"), nullable=False)
    name = Column(String(255))
    computer = relationship("Computer", back_populates="roles")

class Disk(Base):
    __tablename__ = "disks"
    id = Column(Integer, primary_key=True, index=True)
    computer_id = Column(Integer, ForeignKey("computers.id"), nullable=True)
    device_id = Column(String(255), nullable=True)
    total_space = Column(BigInteger, nullable=True)
    free_space = Column(BigInteger, nullable=True)
    computer = relationship("Computer", back_populates="disks", lazy="selectin")  # Изменено на selectin

class Software(Base):
    __tablename__ = "software"
    id = Column(Integer, primary_key=True, index=True)
    computer_id = Column(Integer, ForeignKey("computers.id"), nullable=False)
    name = Column(String, nullable=False)
    version = Column(String, nullable=True)
    install_date = Column(DateTime, nullable=True)
    computer = relationship("Computer", back_populates="software")
    __table_args__ = (
        Index('idx_computer_software', 'computer_id', 'name', 'version', unique=True),
    )

class ChangeLog(Base):
    __tablename__ = "change_log"
    id = Column(Integer, primary_key=True, index=True)
    computer_id = Column(Integer, ForeignKey("computers.id"), nullable=False)
    field = Column(String(255), nullable=False)
    old_value = Column(String(255))
    new_value = Column(String(255))
    changed_at = Column(DateTime, server_default=func.now())
    computer = relationship("Computer", back_populates="change_logs")

class ScanTask(Base):
    __tablename__ = "scan_tasks"
    id = Column(String(36), primary_key=True)
    status = Column(Enum(ScanStatus), default=ScanStatus.pending, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    scanned_hosts = Column(Integer, default=0)
    successful_hosts = Column(Integer, default=0)
    error = Column(String(255), nullable=True)