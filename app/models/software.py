from sqlalchemy import  Integer, String, DateTime, ForeignKey,  Index, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional
from app.base import Base
from app.models.computer import Computer

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