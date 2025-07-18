# File: generate_ts_types.py
import os
import logging
import sys
from pydantic2ts import generate_typescript_defs
import importlib.util

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def generate_ts_types():
    """Генерує TypeScript-типи з SQLModel моделей."""
    try:
        project_root = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, project_root)
        
        module_path = os.path.join(project_root, "app", "models.py")
        output_file = os.path.join(project_root, "front", "src", "types", "schemas.ts")
        
        logger.info(f"Генерація TypeScript-типів з {module_path} до {output_file}")
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        spec = importlib.util.spec_from_file_location("app.models", module_path)
        if spec is None:
            raise ImportError(f"Не вдалося знайти модуль за шляхом: {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["app.models"] = module
        spec.loader.exec_module(module)
        
        generate_typescript_defs("app.models", output_file)
        
        logger.info(f"TypeScript-типи успішно згенеровано в {output_file}")
        
    except Exception as e:
        logger.error(f"Помилка при генерації TypeScript-типів: {str(e)}")
        raise

if __name__ == "__main__":
    generate_ts_types()