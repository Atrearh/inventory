from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Index, func
from app.utils.validators import DomainNameStr, NonEmptyStr 
from pydantic import field_validator
import re
from typing import Optional, List, TYPE_CHECKING
if TYPE_CHECKING:
    from .computer import Computer

class Domain(SQLModel, table=True):
    __tablename__ = "domains"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    name: DomainNameStr = Field(max_length=255, nullable=False, unique=True) 
    username: NonEmptyStr = Field(max_length=255, nullable=False)  
    encrypted_password: NonEmptyStr = Field(max_length=512, nullable=False)  
    server_url: Optional[DomainNameStr] = Field(default=None, max_length=255)  
    ad_base_dn: Optional[NonEmptyStr] = Field(default=None, max_length=255)  
    last_updated: datetime = Field(default_factory=datetime.utcnow, nullable=False, sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()})
    
    # Зв’язок із комп’ютерами
    computers: List["Computer"] = Relationship(back_populates="domain")
    
    # Індекси
    __table_args__ = (
        Index('idx_domain_name', 'name'),
    )
    
    # Валідація для ad_base_dn 
    @field_validator('ad_base_dn')
    @classmethod
    def validate_ad_base_dn(cls, value: Optional[str]) -> Optional[str]:
        if value:
            # Перевірка формату LDAP DN (наприклад, DC=example,DC=com)
            if not re.match(r'^(?:[A-Za-z]+=[^,]+,)+[A-Za-z]+=[^,]+$', value):
                raise ValueError("ad_base_dn must be a valid LDAP Distinguished Name")
        return value