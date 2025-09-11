from typing import Optional
from datetime import datetime, timedelta
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Index, func
from pydantic import field_validator
import re
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTable
from app.utils.validators import NonEmptyStr

class User(SQLModel, SQLAlchemyBaseUserTable[int], table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    username: NonEmptyStr = Field(max_length=50, nullable=False)
    email: NonEmptyStr = Field(max_length=255, nullable=False, unique=True)
    hashed_password: NonEmptyStr = Field(max_length=255, nullable=False)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    is_verified: bool = Field(default=False)
    
    refresh_tokens: list["RefreshToken"] = Relationship(back_populates="user")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            raise ValueError("email must be a valid email address (e.g., user@example.com)")
        return value

class RefreshToken(SQLModel, SQLAlchemyBaseAccessTokenTable[int], table=True):
    __tablename__ = "refresh_tokens"
    
    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    user_id: int = Field(foreign_key="users.id", nullable=False)
    token: NonEmptyStr = Field(max_length=255, nullable=False, unique=True)
    issued_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(seconds=604800), nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now()})
    revoked: bool = Field(default=False, nullable=False)
    
    user: "User" = Relationship(back_populates="refresh_tokens")
    
    __table_args__ = (
        Index('idx_user_token', 'user_id', 'token', unique=True),
        Index('idx_token_expires', 'token', 'expires_at'),
    )
    
    def __init__(self, **kwargs):
        # Встановлюємо значення за замовчуванням для expires_at, якщо не передано
        if "expires_at" not in kwargs or kwargs["expires_at"] is None:
            kwargs["expires_at"] = datetime.utcnow() + timedelta(seconds=604800)  # 7 днів
        super().__init__(**kwargs)