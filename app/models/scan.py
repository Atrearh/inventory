from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlalchemy import Index, func, Enum, Column
from pydantic import field_validator
import uuid
from app.models.enums import ScanStatus
from app.utils.validators import NonEmptyStr

class ScanTask(SQLModel, table=True):
    __tablename__ = "scan_tasks"
    
    id: str = Field(max_length=36, primary_key=True)
    status: ScanStatus = Field(default=ScanStatus.pending, sa_column=Column(Enum(ScanStatus), nullable=False))   
    scanned_hosts: int = Field(default=0)
    successful_hosts: int = Field(default=0)
    error: Optional[NonEmptyStr] = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()})
    
    __table_args__ = (
        Index('idx_scan_task_status', 'status'),
        Index('idx_scan_task_created_at', 'created_at'),
    )
    
    @field_validator('id')
    @classmethod
    def validate_id(cls, value: str) -> str:
        try:
            uuid.UUID(value)
        except ValueError:
            raise ValueError("id must be a valid UUID")
        return value
    
    @field_validator('scanned_hosts', 'successful_hosts')
    @classmethod
    def validate_hosts(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Number of hosts must be non-negative")
        return value