from sqlmodel import SQLModel, Field
from typing import Optional

class AppSetting(SQLModel, table=True):
    """
    Модель для збереження налаштувань додатку
    SQLModel автоматично створює SQLAlchemy таблицю з Pydantic валідацією
    """
    __tablename__ = "app_settings"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(max_length=50, unique=True, index=True)
    value: str = Field()