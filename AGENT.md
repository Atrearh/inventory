# AGENT.md - Project Configuration

## Build/Test Commands
- **Start development**: `start.bat` (Windows) or manually run backend + frontend
- **Backend start**: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` (from root dir)
- **Frontend start**: `cd front && npm run dev -- --host`
- **Generate TypeScript types**: `cd front && npm run generate:ts` or `python generate_ts_types.py`
- **Build frontend**: `cd front && npm run build`
- **Install dependencies**: Backend: `pip install -r requirements.txt`, Frontend: `cd front && npm install`

## Architecture
- **Backend (app/)**: FastAPI + SQLAlchemy + async MySQL, WinRM for Windows inventory collection
- **Frontend (front/)**: React + TypeScript + Vite + Ant Design + React Query
- **Database**: MySQL with SQLAlchemy models, async operations
- **Key modules**: data_collector.py (WinRM scripts), models.py (DB schemas), repositories/ (data access), services/ (business logic)
- **Authentication**: FastAPI-Users based auth system
- **Type generation**: Python models → TypeScript types via generate_ts_types.py

## Code Style
- **Python**: Relative imports (`from .module`), async/await patterns, SQLAlchemy Mapped types, logging with structured messages
- **Naming**: snake_case (Python), camelCase (TypeScript), descriptive variable names, enum classes for statuses
- **Error handling**: Custom exceptions module, global exception handler, proper HTTP status codes
- **Type hints**: Required in Python, strict TypeScript with proper interfaces
- **Comments**: Russian language for business logic comments, minimal code comments, docstrings for public methods
