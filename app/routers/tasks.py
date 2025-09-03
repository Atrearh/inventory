from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Task
from app.schemas import TaskRead
from sqlalchemy import select

app = FastAPI()

@app.get("/tasks", response_model=list[TaskRead])
async def get_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).filter(Task.status.in_(['running', 'pending'])))
    tasks = result.scalars().all()
    return tasks