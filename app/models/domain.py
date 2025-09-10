from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import  Integer, String, DateTime, Index, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from ..base import Base

if TYPE_CHECKING:
    from .computer import Computer

class Domain(Base):
    __tablename__ = "domains"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[str] = mapped_column(String(512), nullable=False)
    server_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  
    ad_base_dn: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    computers: Mapped[List["Computer"]] = relationship("Computer", back_populates="domain")
    __table_args__ = (
        Index('idx_domain_name', 'name'),
    )