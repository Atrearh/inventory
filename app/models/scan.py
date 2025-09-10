from sqlalchemy import  Integer, String, DateTime, func
from sqlalchemy.orm import  Mapped, mapped_column
from typing import Optional
from app.base import Base
from .enums import ScanStatus
from sqlalchemy import Enum

from sqlalchemy.orm import relationship

class ScanTask(Base):
    __tablename__ = "scan_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), default=ScanStatus.pending, nullable=False)
    scanned_hosts: Mapped[int] = mapped_column(Integer, default=0)
    successful_hosts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

