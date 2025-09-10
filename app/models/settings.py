from sqlalchemy import  Integer, String, Text
from sqlalchemy.orm import  Mapped, mapped_column

from app.base import Base

class AppSetting(Base):
    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)