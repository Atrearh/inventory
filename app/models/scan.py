from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlalchemy import func
from uuid import uuid4
from app.models.enums import ScanStatus
from app.utils.validators import NonEmptyStr

class ScanTask(SQLModel, table=True):
    __tablename__ = "scan_tasks"
    
    id: str = Field(default_factory=lambda: str(uuid4()), max_length=36, primary_key=True, index=True)
    status: ScanStatus = Field(default=ScanStatus.pending, sa_column_kwargs={"nullable": False})
    scanned_hosts: int = Field(default=0, ge=0)
    successful_hosts: int = Field(default=0, ge=0)
    error: Optional[NonEmptyStr] = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()})