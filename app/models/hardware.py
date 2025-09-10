from sqlalchemy import  Integer, String, DateTime, ForeignKey,  Index, func, BigInteger
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional
from app.base import Base
from app.models.computer import Computer

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
    logical_disks = relationship("LogicalDisk", back_populates="physical_disk")
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