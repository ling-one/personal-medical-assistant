"""用户管理接口"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.services.user_service import user_service

router = APIRouter()


class CreateUserRequest(BaseModel):
    user_id: str | None = Field(None, description="自定义用户ID，不传则自动生成")


class UserResponse(BaseModel):
    user_id: str
    created_at: float
    last_active: float


class UserInfoResponse(BaseModel):
    user_id: str
    created_at: float
    last_active: float
    exists: bool


@router.post("/create", response_model=UserResponse)
async def create_user(request: CreateUserRequest | None = None):
    """创建新用户"""
    try:
        user_data = user_service.create_user(
            user_id=request.user_id if request else None
        )
        return UserResponse(**user_data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{user_id}", response_model=UserInfoResponse)
async def get_user(user_id: str):
    """获取用户信息"""
    user_data = user_service.get_user(user_id)
    if user_data is None:
        return UserInfoResponse(
            user_id=user_id,
            created_at=0,
            last_active=0,
            exists=False,
        )
    return UserInfoResponse(
        user_id=user_data["user_id"],
        created_at=user_data["created_at"],
        last_active=user_data["last_active"],
        exists=True,
    )
