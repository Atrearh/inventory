from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Index, UniqueConstraint, func, Enum, Column
from pydantic import field_validator
import uuid
from app.models.enums import CheckStatus
from app.utils.validators import HostnameStr, NonEmptyStr 

if TYPE_CHECKING:
    from .domain import Domain
    from .hardware import IPAddress, MACAddress, Processor, VideoCard, PhysicalDisk, LogicalDisk
    from .software import Software, Role

class Computer(SQLModel, table=True):
    __tablename__ = "computers"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    hostname: HostnameStr = Field(max_length=255, nullable=False) 
    os_name: Optional[NonEmptyStr] = Field(default=None, max_length=255)  
    os_version: Optional[NonEmptyStr] = Field(default=None, max_length=50)  
    ram: Optional[int] = Field(default=None)
    motherboard: Optional[NonEmptyStr] = Field(default=None, max_length=255)  
    last_boot: Optional[datetime] = Field(default=None)
    last_updated: datetime = Field(default_factory=datetime.utcnow, nullable=False, sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()})
    last_full_scan: Optional[datetime] = Field(default=None)
    check_status: CheckStatus = Field(default=CheckStatus.success, sa_column=Column(Enum(CheckStatus), nullable=False))
    object_guid: Optional[str] = Field(default=None, max_length=36, unique=True)
    when_created: Optional[datetime] = Field(default=None)
    when_changed: Optional[datetime] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)
    ad_notes: Optional[NonEmptyStr] = Field(default=None) 
    local_notes: Optional[NonEmptyStr] = Field(default=None)  
    last_logon: Optional[datetime] = Field(default=None)
    domain_id: Optional[int] = Field(default=None, foreign_key="domains.id")

    # Relationships 
    ip_addresses: List["IPAddress"] = Relationship(back_populates="computer")
    mac_addresses: List["MACAddress"] = Relationship(back_populates="computer")
    processors: List["Processor"] = Relationship(back_populates="computer")
    video_cards: List["VideoCard"] = Relationship(back_populates="computer")
    physical_disks: List["PhysicalDisk"] = Relationship(back_populates="computer")
    logical_disks: List["LogicalDisk"] = Relationship(back_populates="computer")
    software: List["Software"] = Relationship(back_populates="computer")
    roles: List["Role"] = Relationship(back_populates="computer")
    domain: Optional["Domain"] = Relationship(back_populates="computers")

    # Індекси та обмеження 
    __table_args__ = (
        Index('idx_computers_last_updated', 'last_updated'),
        Index('idx_computers_filters', 'os_name', 'check_status', 'last_updated'),
        UniqueConstraint('object_guid', name='idx_object_guid'),
    )

    # Валідація для object_guid 
    @field_validator('object_guid')
    @classmethod
    def validate_object_guid(cls, value: Optional[str]) -> Optional[str]:
        if value:
            try:
                uuid.UUID(value)
            except ValueError:
                raise ValueError("object_guid must be a valid UUID")
        return value

    # Валідація для ram
    @field_validator('ram')
    @classmethod
    def validate_ram(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 0:
            raise ValueError("ram must be non-negative")
        return value