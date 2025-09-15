import os
import logging
import sys
import inspect
import tempfile
from pydantic2ts import generate_typescript_defs
import importlib.util
from sqlmodel import SQLModel
from pydantic import BaseModel
from enum import Enum

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, filename="generate_ts_types.log", filemode="w")

def find_model_modules(root_dir: str, base_modules: list[str] = ["app"]) -> list[str]:
    """Знаходить усі модулі з Pydantic/SQLModel-схемами у вказаних директоріях."""

    return( "app.schemas", "app.models")

def is_pydantic_or_sqlmodel(cls) -> bool:
    """Перевіряє, чи є клас Pydantic або SQLModel моделлю."""
    return inspect.isclass(cls) and (issubclass(cls, BaseModel) or issubclass(cls, SQLModel)) and cls not in (BaseModel, SQLModel)

def is_enum(cls) -> bool:
    """Перевіряє, чи є клас перелічуваним типом (Enum)."""
    return inspect.isclass(cls) and issubclass(cls, Enum)

def generate_ts_types():
    """Генерує TypeScript-типи з Pydantic/SQLModel-схем."""
    try:
        project_root = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, project_root)
        
        output_file = os.path.join(project_root, "front", "src", "types", "schemas.ts")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Знаходимо модулі
        model_modules = find_model_modules(project_root, base_modules=["app"])
        if not model_modules:
            logger.error("Не знайдено модулів з Pydantic/SQLModel-схемами")
            raise ValueError("Не знайдено модулів з Pydantic/SQLModel-схемами")

        logger.info(f"Знайдено модулі: {model_modules}")
        
        # Зберігаємо унікальні перелічувані типи
        processed_enums = set()
        
        # Створюємо тимчасові файли для кожного модуля
        temp_files = []
        for module_name in model_modules:
            logger.info(f"Обробка модуля: {module_name}")
            try:
                spec = importlib.util.spec_from_file_location(module_name, os.path.join(project_root, module_name.replace(".", os.sep) + ".py"))
                if spec is None:
                    logger.error(f"Не вдалося знайти модуль: {module_name}")
                    continue
                
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # Перевіряємо Pydantic/SQLModel-моделі
                model_classes = [
                    name for name, obj in inspect.getmembers(module, is_pydantic_or_sqlmodel)
                ]
                
                # Перевіряємо перелічувані типи (Enum)
                enum_classes = [
                    name for name, obj in inspect.getmembers(module, is_enum)
                    if name not in processed_enums
                ]
                
                if not model_classes and not enum_classes:
                    logger.info(f"У модулі {module_name} немає Pydantic/SQLModel-моделей або Enum")
                    continue
                
                logger.info(f"Знайдено класи в модулі {module_name}: {model_classes}")
                logger.info(f"Знайдено перелічувані типи в модулі {module_name}: {enum_classes}")
                
                # Оновлюємо набір оброблених enum
                processed_enums.update(enum_classes)
                
                # Генеруємо тимчасовий файл для модуля
                with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".ts", encoding="utf-8") as temp_file:
                    generate_typescript_defs(module_name, temp_file.name)
                    temp_files.append(temp_file.name)
                
            except ImportError as e:
                logger.error(f"Помилка імпорту модуля {module_name}: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"Помилка обробки модуля {module_name}: {str(e)}")
                continue
        
        # Об’єднуємо всі тимчасові файли в один
        with open(output_file, "w", encoding="utf-8") as final_file:
            final_file.write("// Auto-generated TypeScript types\n\n")
            for temp_file in temp_files:
                with open(temp_file, "r", encoding="utf-8") as tf:
                    content = tf.read()
                    # Фільтруємо дубльовані enum (якщо залишилися)
                    lines = content.splitlines()
                    filtered_lines = [
                        line for line in lines
                        if not any(enum_name in line for enum_name in processed_enums)
                        or module_name == "app.models"  # Зберігаємо enum лише з app.models
                    ]
                    final_file.write("\n".join(filtered_lines) + "\n")
                os.unlink(temp_file)
        
        if not temp_files:
            logger.warning("Жоден модуль не створив TypeScript-типів")
        
        logger.info(f"TypeScript-типи успішно сгенеровано в {output_file}")
        
    except Exception as e:
        logger.error(f"Помилка при генерації TypeScript-типів: {str(e)}")
        raise

if __name__ == "__main__":
    generate_ts_types()