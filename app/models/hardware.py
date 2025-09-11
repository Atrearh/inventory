from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Index, func
from pydantic import field_validator
from app.utils.validators import NonEmptyStr, IPAddressStr, MACAddressStr
from sqlalchemy.types import BigInteger
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .computer import Computer

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
    
    __table_args__ = (
        Index('idx_computer_physical_disk', 'computer_id', 'serial', unique=True),
    )

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
    
    __table_args__ = (
        Index('idx_computer_logical_disk', 'computer_id', 'device_id', unique=True),
    )
    
    @field_validator('total_space', 'free_space')
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
    
    __table_args__ = (
        Index('idx_computer_video_card', 'computer_id', 'name', unique=True),
    )

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
    
    __table_args__ = (
        Index('idx_computer_processor', 'computer_id', 'name', unique=True),
    )
    
    @field_validator('number_of_cores', 'number_of_logical_processors')
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
    
    __table_args__ = (
        Index('idx_computer_ip', 'computer_id', 'address', unique=True),
    )

class MACAddress(SQLModel, table=True):
    __tablename__ = "mac_addresses"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    computer_id: int = Field(foreign_key="computers.id", nullable=False)
    address: MACAddressStr = Field(max_length=17, nullable=False)  # Використовуємо MACAddressStr
    detected_on: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    removed_on: Optional[datetime] = Field(default=None)
    
    computer: "Computer" = Relationship(back_populates="mac_addresses")
    
    __table_args__ = (
        Index('idx_computer_mac', 'computer_id', 'address', unique=True),
    )