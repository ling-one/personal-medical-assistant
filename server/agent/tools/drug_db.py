"""药品数据库工具"""
from langchain.tools import tool


# 常用药品基础数据 (实际应连接专业药品数据库)
DRUG_DATABASE = {
    "布洛芬": {
        "name": "布洛芬",
        "category": "解热镇痛药",
        "indications": "用于缓解轻至中度疼痛如头痛、关节痛、偏头痛、牙痛、肌肉痛、神经痛、痛经，也用于普通感冒或流感引起的发热。",
        "dosage": "成人一次0.2-0.4g，每4-6小时1次。每日最大剂量不超过1.2g。",
        "contraindications": "对其他NSAIDs过敏者、活动性消化性溃疡患者禁用。",
        "side_effects": "恶心、呕吐、腹泻、头晕等。",
        "notes": "饭后服用，减少胃肠道刺激。"
    },
    "对乙酰氨基酚": {
        "name": "对乙酰氨基酚",
        "category": "解热镇痛药",
        "indications": "用于普通感冒或流感引起的发热，也用于缓解轻至中度疼痛。",
        "dosage": "成人一次0.3-0.6g，每4-6小时1次。每日最大剂量不超过2g。",
        "contraindications": "严重肝肾功能不全者禁用。",
        "side_effects": "偶见恶心、呕吐、腹痛等。",
        "notes": "避免饮酒，可能增加肝损害风险。"
    },
    "阿莫西林": {
        "name": "阿莫西林",
        "category": "抗生素",
        "indications": "用于敏感菌引起的呼吸道感染、泌尿生殖道感染、皮肤软组织感染等。",
        "dosage": "成人一次0.5g，每6-8小时1次。",
        "contraindications": "青霉素过敏者禁用。",
        "side_effects": "恶心、腹泻、皮疹等。",
        "notes": "用药前需做皮试，完整疗程很重要。"
    }
}


@tool
def query_drug(drug_name: str) -> str:
    """
    查询药品信息。
    
    Args:
        drug_name: 药品名称
    
    Returns:
        药品详细信息
    """
    drug = DRUG_DATABASE.get(drug_name)
    
    if not drug:
        return f"未找到药品 '{drug_name}' 的详细信息。请咨询专业药师或医生。"
    
    return f"""
【{drug['name']}】

类别: {drug['category']}

适应症:
{drug['indications']}

用法用量:
{drug['dosage']}

禁忌:
{drug['contraindications']}

不良反应:
{drug['side_effects']}

注意事项:
{drug['notes']}

---
请遵医嘱用药，具体用法请咨询医生或药师。
"""


@tool
def check_drug_interaction(drug1: str, drug2: str) -> str:
    """
    检查两种药物的相互作用。
    
    Args:
        drug1: 第一种药品名称
        drug2: 第二种药品名称
    
    Returns:
        相互作用说明
    """
    # 简化的相互作用检查
    known_interactions = {
        ("布洛芬", "阿司匹林"): "两者都是NSAIDs，合用可能增加胃肠道出血风险。",
        ("布洛芬", "华法林"): "可能增强抗凝作用，需监测凝血功能。",
        ("阿莫西林", "甲硝唑"): "一般无明显相互作用，但需遵医嘱使用。",
    }
    
    key = (drug1, drug2)
    reverse_key = (drug2, drug1)
    
    if key in known_interactions:
        return known_interactions[key]
    elif reverse_key in known_interactions:
        return known_interactions[reverse_key]
    else:
        return "目前没有已知的这两种药物的相互作用信息。请咨询医生或药师获取专业建议。"


@tool
def get_drug_reminder(drug_name: str) -> str:
    """
    获取用药提醒。
    
    Args:
        drug_name: 药品名称
    
    Returns:
        用药提醒
    """
    drug = DRUG_DATABASE.get(drug_name, {})
    
    reminders = [
        "请按时服药，不要自行停药或改变剂量",
        "如果出现不适，请及时就医",
        "妥善保存药品，放在儿童接触不到的地方"
    ]
    
    if drug.get("notes"):
        reminders.insert(0, drug["notes"])
    
    return "\n".join([f"• {r}" for r in reminders])
