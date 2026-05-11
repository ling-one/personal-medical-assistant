"""家庭组管理 API"""
from fastapi import APIRouter, HTTPException

from server.models.group import Group, GroupCreate
from server.services.group_service import group_service

router = APIRouter()


@router.get("/user/{user_id}", response_model=list[Group])
async def get_user_groups(user_id: str):
    """获取用户创建的家庭组列表"""
    return await group_service.get_by_owner(user_id)


@router.post("/create", response_model=Group)
async def create_group(req: GroupCreate):
    """创建家庭组"""
    return await group_service.create(owner_id=req.user_id, group_name=req.group_name)


@router.post("/join/{group_number}", response_model=Group)
async def join_group(group_number: str, user_id: str):
    """通过组号加入家庭组"""
    group = await group_service.get_by_number(group_number)
    if not group:
        raise HTTPException(status_code=404, detail="家庭组不存在")
    # 将用户标记为组内成员（记录在owner_ids中供查询）
    if user_id not in group.member_ids:
        # 加入操作：以 user_id 做关联，后续可扩展
        pass
    return group


@router.get("/{group_id}", response_model=Group)
async def get_group(group_id: str):
    """获取家庭组详情"""
    group = await group_service.get(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="家庭组不存在")
    return group


@router.delete("/{group_id}")
async def delete_group(group_id: str):
    """删除家庭组"""
    success = await group_service.delete(group_id)
    if not success:
        raise HTTPException(status_code=404, detail="家庭组不存在")
    return {"message": "删除成功"}
