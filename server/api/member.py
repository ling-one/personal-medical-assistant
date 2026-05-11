"""家庭成员管理 API"""
from fastapi import APIRouter, HTTPException

from server.models.member import Member, MemberCreate, MemberUpdate
from server.models.profile import MedicalHistory, VitalSigns
from server.services.member_service import member_service
from server.services.group_service import group_service

router = APIRouter()


@router.post("/group/{group_id}", response_model=Member)
async def create_member(group_id: str, req: MemberCreate):
    """在家庭组中创建成员"""
    group = await group_service.get(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="家庭组不存在")

    member = await member_service.create(
        group_id=group_id,
        data=req.model_dump(),
    )
    # 同步到组
    await group_service.add_member(group_id, member.member_id)
    return member


@router.get("/group/{group_id}", response_model=list[Member])
async def get_group_members(group_id: str):
    """获取组的所有成员"""
    return await member_service.get_by_group(group_id)


@router.get("/{member_id}", response_model=Member)
async def get_member(member_id: str):
    """获取成员详情"""
    member = await member_service.get(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    return member


@router.put("/{member_id}", response_model=Member)
async def update_member(member_id: str, req: MemberUpdate):
    """更新成员信息"""
    member = await member_service.update(member_id, req.model_dump(exclude_none=True))
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    return member


@router.delete("/{member_id}")
async def delete_member(member_id: str):
    """删除成员"""
    member = await member_service.get(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    # 先从组移除
    await group_service.remove_member(member.group_id, member_id)
    # 再删除成员
    await member_service.delete(member_id)
    return {"message": "删除成功"}


@router.put("/{member_id}/medical-history", response_model=Member)
async def update_medical_history(member_id: str, history: MedicalHistory):
    """更新成员病史"""
    member = await member_service.update_medical_history(member_id, history)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    return member


@router.put("/{member_id}/vital-signs", response_model=Member)
async def update_vital_signs(member_id: str, vital_signs: VitalSigns):
    """更新成员生命体征"""
    member = await member_service.update_vital_signs(member_id, vital_signs)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    return member


@router.get("/{member_id}/summary")
async def get_member_summary(member_id: str):
    """获取成员健康摘要文本"""
    member = await member_service.get(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    return {"summary": member_service.to_summary_text(member)}
