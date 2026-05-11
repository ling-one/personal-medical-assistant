"""体检报告上传与 OCR 识别 API"""
import json
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from server.config import settings
from server.models.report import ReportRecord
from server.services.ocr_service import ocr_service
from server.services.member_service import member_service
from server.services.llm_service import llm_service
from server.models.profile import MedicalHistory, VitalSigns

router = APIRouter()

# 允许的图片格式
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _ensure_report_dir(member_id: str) -> str:
    """确保成员报告目录存在"""
    dir_path = os.path.join(settings.report_data_dir, member_id)
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


REPORT_ANALYSIS_PROMPT = """你是一个专业的体检报告分析专家。请分析以下体检报告内容，提取关键信息并以 JSON 格式返回。

报告内容：
{ocr_text}

请提取以下信息（如无相关数据则留空），仅返回 JSON：
{{
    "summary": "体检报告总体概要和结论（一段话）",
    "abnormal_items": ["异常指标1", "异常指标2"],
    "vital_signs": {{
        "blood_pressure_systolic": 收缩压数值或null,
        "blood_pressure_diastolic": 舒张压数值或null,
        "heart_rate": 心率数值或null,
        "temperature": 体温数值或null,
        "respiratory_rate": 呼吸频率数值或null,
        "oxygen_saturation": 血氧饱和度数值或null
    }},
    "medical_history": {{
        "chronic_diseases": ["慢性病列表"],
        "allergies": ["过敏史"],
        "medications": ["当前用药"]
    }},
    "suggestions": ["健康建议1", "健康建议2"]
}}

注意：只输出 JSON，不要包含其他文字。数值提取时不要带单位。"""


@router.post("/upload")
async def upload_report(
    file: UploadFile = File(...),
    member_id: str = Form(...),
):
    """上传体检报告图片，OCR 识别并返回文字内容"""
    # 验证文件格式
    ext = os.path.splitext(file.filename or "image.jpg")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 验证成员存在
    member = await member_service.get(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")

    # 读取文件
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="文件内容为空")

    # OCR 识别
    try:
        ocr_text = await ocr_service.extract_text(image_bytes, file.filename or "image.jpg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR 识别失败: {str(e)}")

    if not ocr_text.strip():
        raise HTTPException(status_code=500, detail="OCR 未能识别出文字，请检查图片清晰度")

    # 保存报告记录
    report_id = str(uuid.uuid4())
    report_dir = _ensure_report_dir(member_id)
    report_file = os.path.join(report_dir, f"{report_id}.json")

    record = ReportRecord(
        report_id=report_id,
        member_id=member_id,
        filename=file.filename or "unknown",
        ocr_text=ocr_text,
        created_at=datetime.now(),
    )

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(record.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

    # 同时保存 latest 方便快速读取
    latest_file = os.path.join(report_dir, "latest.txt")
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(ocr_text)

    return {
        "report_id": report_id,
        "member_id": member_id,
        "ocr_text": ocr_text,
        "length": len(ocr_text),
        "message": "OCR 识别成功",
    }


@router.post("/analyze")
async def analyze_report(
    file: UploadFile = File(...),
    member_id: str = Form(...),
):
    """上传体检报告 → OCR 识别 → LLM 分析 → 自动更新成员健康档案"""
    # 验证文件格式
    ext = os.path.splitext(file.filename or "image.jpg")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 验证成员存在
    member = await member_service.get(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")

    # 读取文件 + OCR
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="文件内容为空")

    try:
        ocr_text = await ocr_service.extract_text(image_bytes, file.filename or "image.jpg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR 识别失败: {str(e)}")

    if not ocr_text.strip():
        raise HTTPException(status_code=500, detail="OCR 未能识别出文字")

    # LLM 分析
    try:
        analysis_prompt = llm_service.format_prompt(
            "report_analysis_prompt", REPORT_ANALYSIS_PROMPT,
            ocr_text=ocr_text,
        )
        analysis_json = await llm_service.chat(
            messages=[{"role": "user", "content": analysis_prompt}],
            system="你是一个专业的体检报告分析专家，擅长提取结构化数据。",
        )

        # 解析 JSON
        import json as json_parser

        # 尝试提取 JSON
        start = analysis_json.index("{")
        end = analysis_json.rindex("}")
        analysis_data = json_parser.loads(analysis_json[start:end + 1])
    except Exception:
        analysis_data = {"summary": ocr_text[:500], "abnormal_items": [], "suggestions": []}

    # 自动更新成员健康档案
    try:
        # 更新生命体征
        vs_data = analysis_data.get("vital_signs", {})
        if any(vs_data.values()):
            vital_signs = VitalSigns(
                blood_pressure_systolic=vs_data.get("blood_pressure_systolic"),
                blood_pressure_diastolic=vs_data.get("blood_pressure_diastolic"),
                heart_rate=vs_data.get("heart_rate"),
                temperature=vs_data.get("temperature"),
                respiratory_rate=vs_data.get("respiratory_rate"),
                oxygen_saturation=vs_data.get("oxygen_saturation"),
            )
            # 合并现有体征
            if member.vital_signs:
                for field in vital_signs.model_fields:
                    new_val = getattr(vital_signs, field)
                    if new_val is not None:
                        setattr(member.vital_signs, field, new_val)
            else:
                member.vital_signs = vital_signs
            await member_service.update_vital_signs(member_id, member.vital_signs)

        # 更新病史
        mh_data = analysis_data.get("medical_history", {})
        if any(mh_data.values()):
            new_allergies = mh_data.get("allergies", [])
            new_chronic = mh_data.get("chronic_diseases", [])
            new_meds = mh_data.get("medications", [])
            if new_allergies or new_chronic or new_meds:
                # 合并去重
                existing_allergies = set(member.medical_history.allergies)
                existing_allergies.update(new_allergies)
                existing_chronic = set(member.medical_history.chronic_diseases)
                existing_chronic.update(new_chronic)
                existing_meds = set(member.medical_history.medications)
                existing_meds.update(new_meds)

                medical_history = MedicalHistory(
                    allergies=list(existing_allergies),
                    chronic_diseases=list(existing_chronic),
                    surgeries=member.medical_history.surgeries,
                    family_history=member.medical_history.family_history,
                    medications=list(existing_meds),
                )
                await member_service.update_medical_history(member_id, medical_history)
    except Exception as e:
        # 档案更新失败不阻塞主流程
        pass

    # 保存报告记录
    report_id = str(uuid.uuid4())
    report_dir = _ensure_report_dir(member_id)
    report_file = os.path.join(report_dir, f"{report_id}.json")

    record = ReportRecord(
        report_id=report_id,
        member_id=member_id,
        filename=file.filename or "unknown",
        ocr_text=ocr_text,
        analysis=analysis_data.get("summary", ""),
        created_at=datetime.now(),
    )

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(record.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

    # 保存最新 OCR 文本
    latest_file = os.path.join(report_dir, "latest.txt")
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(ocr_text)

    return {
        "report_id": report_id,
        "member_id": member_id,
        "ocr_text": ocr_text,
        "analysis": analysis_data,
        "vital_signs_updated": bool(any(vs_data.values())),
        "medical_history_updated": bool(any(mh_data.values())),
        "message": "报告分析完成，健康档案已更新",
    }
