from sqlmodel import SQLModel

# SQLModel вже має вбудований Base клас
# Тому просто експортуємо SQLModel як Base для сумісності
Base = SQLModel
