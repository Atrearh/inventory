# app/routers/sessions.py
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..database import get_db
from ..models import User, RefreshToken
from ..schemas import SessionRead
from .auth import fastapi_users

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["sessions"])
get_current_active_user = fastapi_users.current_user(active=True)

@router.get("/", response_model=List[SessionRead])
async def get_user_sessions(
    user: User = Depends(get_current_active_user),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """Получает список активных сессий (refresh-токенов) для текущего пользователя."""
    current_token_cookie = request.cookies.get("auth_token")

    query = (
        select(RefreshToken)
        .where(RefreshToken.user_id == user.id)
        .where(RefreshToken.revoked == False)
    )
    result = await db.execute(query)
    tokens = result.scalars().all()

    sessions = []
    for token in tokens:
        session_data = SessionRead(
            id=token.id,
            issued_at=token.issued_at,
            expires_at=token.expires_at,
            is_current=(token.token == current_token_cookie) # Проверяем, является ли сессия текущей
        )
        sessions.append(session_data)
        
    return sorted(sessions, key=lambda s: s.issued_at, reverse=True)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    token_id: int,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Отзывает конкретную сессию (refresh-токен) по её ID."""
    token_query = await db.execute(
        select(RefreshToken).where(RefreshToken.id == token_id)
    )
    token = token_query.scalar_one_or_none()

    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена")

    # Важнейшая проверка безопасности: убеждаемся, что пользователь отзывает свою сессию
    if token.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

    token.revoked = True
    await db.commit()
    return None

@router.post("/revoke-all-others", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_other_sessions(
    user: User = Depends(get_current_active_user),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """Отзывает все сессии пользователя, кроме текущей."""
    current_token_cookie = request.cookies.get("auth_token")
    if not current_token_cookie:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Текущая сессия не определена")

    stmt = (
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id)
        .where(RefreshToken.token != current_token_cookie)
        .values(revoked=True)
    )
    await db.execute(stmt)
    await db.commit()
    return None