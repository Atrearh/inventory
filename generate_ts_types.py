# generate_ts_types.py
import os
import logging
import sys
from pydantic2ts import generate_typescript_defs
import importlib.util

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def generate_ts_types():
    """Генерирует TypeScript-типы из Pydantic-схем с использованием pydantic-to-typescript."""
    try:
        # Определяем корневую директорию проекта (C:\Users\semen\inv)
        project_root = os.path.dirname(os.path.abspath(__file__))
        
        # Добавляем корневую директорию в sys.path для импорта как пакета
        sys.path.insert(0, project_root)
        
        # Формируем путь к модулю schemas
        module_path = os.path.join(project_root, "app", "schemas.py")
        output_file = os.path.join(project_root, "front", "src", "types", "schemas.ts")
        
        logger.info(f"Генерация TypeScript-типов из {module_path} в {output_file}")
        
        # Создаем директорию для выходного файла
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Динамический импорт модуля
        spec = importlib.util.spec_from_file_location("app.schemas", module_path)
        if spec is None:
            raise ImportError(f"Не удалось найти модуль по пути: {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["app.schemas"] = module
        spec.loader.exec_module(module)
        
        # Генерируем TypeScript-типы
        generate_typescript_defs("app.schemas", output_file)
        
        logger.info(f"TypeScript-типы успешно сгенерированы в {output_file}")
        
    except Exception as e:
        logger.error(f"Ошибка при генерации TypeScript-типов: {str(e)}")
        raise

if __name__ == "__main__":
    generate_ts_types()