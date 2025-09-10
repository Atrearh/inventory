from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import  Integer, String, DateTime, Boolean, Text, Enum, ForeignKey, UniqueConstraint, Index, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from ..base import Base
from .enums import CheckStatus

if TYPE_CHECKING:
    from .domain import Domain
    from .hardware import IPAddress, MACAddress, Processor, VideoCard, PhysicalDisk, LogicalDisk
    from .software import Software, Role

class Computer(Base):
    __tablename__ = "computers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    os_name: Mapped[Optional[str]] = mapped_column(String(255))
    os_version: Mapped[Optional[str]] = mapped_column(String(50))
    ram: Mapped[Optional[int]] = mapped_column(Integer)
    motherboard: Mapped[Optional[str]] = mapped_column(String(255))
    last_boot: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    last_full_scan: Mapped[Optional[datetime]] = mapped_column(DateTime)
    check_status: Mapped[CheckStatus] = mapped_column(Enum(CheckStatus), nullable=False, server_default=CheckStatus.success.value)
    object_guid: Mapped[Optional[str]] = mapped_column(String(36), unique=True)  
    when_created: Mapped[Optional[datetime]] = mapped_column(DateTime)
    when_changed: Mapped[Optional[datetime]] = mapped_column(DateTime)
    enabled: Mapped[Optional[bool]] = mapped_column(Boolean)
    ad_notes: Mapped[Optional[str]] = mapped_column(Text)
    local_notes: Mapped[Optional[str]] = mapped_column(Text)
    last_logon: Mapped[Optional[datetime]] = mapped_column(DateTime)
    domain_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("domains.id"), nullable=True)

    ip_addresses: Mapped[List["IPAddress"]] = relationship("IPAddress", back_populates="computer")
    mac_addresses: Mapped[List["MACAddress"]] = relationship("MACAddress", back_populates="computer")
    processors: Mapped[List["Processor"]] = relationship("Processor", back_populates="computer")
    video_cards: Mapped[List["VideoCard"]] = relationship("VideoCard", back_populates="computer")
    physical_disks: Mapped[List["PhysicalDisk"]] = relationship("PhysicalDisk", back_populates="computer")
    logical_disks: Mapped[List["LogicalDisk"]] = relationship("LogicalDisk", back_populates="computer")
    software: Mapped[List["Software"]] = relationship("Software", back_populates="computer")
    roles: Mapped[List["Role"]] = relationship("Role", back_populates="computer")
    domain: Mapped[Optional["Domain"]] = relationship("Domain", back_populates="computers")

    __table_args__ = (
        Index('idx_computers_last_updated', 'last_updated'),
        Index('idx_computers_filters', 'os_name', 'check_status', 'last_updated'),
        UniqueConstraint('object_guid', name='idx_object_guid'),
    )