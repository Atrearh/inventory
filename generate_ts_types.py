# generate_ts_types.py
import os
import logging
import sys
from pydantic2ts import generate_typescript_defs

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def generate_ts_types():
    """Генерирует TypeScript-типы из Pydantic-схем с использованием pydantic-to-typescript."""
    try:
       
        # Определяем корневую директорию проекта (C:\Users\semen\inv)
        project_root = os.path.dirname(os.path.abspath(__file__))
        
        # Добавляем корневую директорию в sys.path для импорта app.schemas
        sys.path.append(project_root)
        
        # Формируем пути
        module_path = "app.schemas"  # Путь к модулю в формате Python
        output_file = os.path.join(project_root, "front", "src", "types", "schemas.ts")
        
        logger.info(f"Генерация TypeScript-типов из {module_path} в {output_file}")
        
        # Создаем директорию для выходного файла
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Генерируем TypeScript-типы
        generate_typescript_defs(module_path, output_file)
        
        logger.info(f"TypeScript-типы успешно сгенерированы в {output_file}")
        
    except Exception as e:
        logger.error(f"Ошибка при генерации TypeScript-типов: {str(e)}")
        raise

if __name__ == "__main__":
    generate_ts_types()