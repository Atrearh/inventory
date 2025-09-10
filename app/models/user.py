from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTable
from datetime import datetime, timedelta
from sqlalchemy import ForeignKey, Boolean, Index , Column, DateTime
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from ..base import Base
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import  Mapped, mapped_column
from sqlalchemy import func
from datetime import datetime, timedelta
from sqlalchemy.orm import relationship

class User(SQLAlchemyBaseUserTable[int], Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

class RefreshToken(Base, SQLAlchemyBaseAccessTokenTable):
    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user: Mapped["User"] = relationship("User", backref="refresh_tokens")
    __table_args__ = (
        Index('idx_user_token', 'user_id', 'token', unique=True),
        Index('idx_token_expires', 'token', 'expires_at'),
    )

    def __init__(self, **kwargs):
        # Встановлюємо значення за замовчуванням для expires_at, якщо не передано
        if "expires_at" not in kwargs or kwargs["expires_at"] is None:
            kwargs["expires_at"] = datetime.utcnow() + timedelta(seconds=604800)  # 7 днів
        super().__init__(**kwargs)