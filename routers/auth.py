from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth_utils import create_access_token, hash_password, verify_password
from database import get_async_session
from dependencies import get_current_user
from models import User, UserRole
from schemas_auth import ChangePassword, Token, UserCreate, UserResponse


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_async_session)) -> UserResponse:
    existing = await db.scalar(
        select(User).where(or_(User.email == user_data.email, User.nickname == user_data.nickname))
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email или никнейм уже используется")
    user = User(
        nickname=user_data.nickname,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        role=UserRole.USER,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email или никнейм уже используется") from None
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_async_session),
) -> Token:
    user = await db.scalar(select(User).where(User.email == form_data.username))
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/change-password")
async def change_password(
    data: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный текущий пароль")
    current_user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return {"message": "Пароль изменен"}
