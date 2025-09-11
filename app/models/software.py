from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Index, func
from pydantic import field_validator
import re
from app.utils.validators import NonEmptyStr
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .computer import Computer
    

class Software(SQLModel, table=True):
    __tablename__ = "software"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    computer_id: int = Field(foreign_key="computers.id", nullable=False)
    name: NonEmptyStr = Field(max_length=255, nullable=False)
    version: Optional[NonEmptyStr] = Field(default=None, max_length=255)
    install_date: Optional[datetime] = Field(default=None)
    detected_on: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    removed_on: Optional[datetime] = Field(default=None)

    
    computer: "Computer" = Relationship(back_populates="software")
    
    __table_args__ = (
        Index('idx_software_computer_id', 'computer_id', 'name', 'version', unique=True),
    )
    
    @field_validator('version')
    @classmethod
    def validate_version(cls, value: Optional[str]) -> Optional[str]:
        if value:
            # Перевірка формату семантичного версіювання (наприклад, 1.2.3 або 1.2.3-beta)
            if not re.match(r'^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$', value):
                raise ValueError("version must follow semantic versioning format (e.g., 1.2.3 or 1.2.3-beta)")
        return value

class Role(SQLModel, table=True):
    __tablename__ = "roles"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    computer_id: int = Field(foreign_key="computers.id", nullable=False)
    name: NonEmptyStr = Field(max_length=255, nullable=False)
    detected_on: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    removed_on: Optional[datetime] = Field(default=None)
    
    computer: "Computer" = Relationship(back_populates="roles")
    
    __table_args__ = (
        Index('idx_computer_role', 'computer_id', 'name', unique=True),
    )