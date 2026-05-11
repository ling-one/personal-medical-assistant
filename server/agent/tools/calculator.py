"""健康计算工具"""
from langchain.tools import tool


@tool
def calculate_bmi(height_cm: float, weight_kg: float) -> str:
    """
    计算 BMI (身体质量指数)。
    
    Args:
        height_cm: 身高（厘米）
        weight_kg: 体重（公斤）
    
    Returns:
        BMI值及健康评估
    """
    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)
    bmi = round(bmi, 1)
    
    # BMI 分类标准
    if bmi < 18.5:
        category = "偏瘦"
        suggestion = "建议适当增加营养摄入，保持均衡饮食。"
    elif bmi < 24:
        category = "正常"
        suggestion = "继续保持健康的生活方式！"
    elif bmi < 28:
        category = "超重"
        suggestion = "建议适当增加运动，控制饮食。"
    else:
        category = "肥胖"
        suggestion = "建议咨询医生，制定科学的减重计划。"
    
    return f"""
【BMI 计算结果】
BMI = {bmi}

分类: {category}

{suggestion}

BMI参考标准:
• < 18.5: 偏瘦
• 18.5-24: 正常
• 24-28: 超重
• ≥ 28: 肥胖

注: BMI 是通用指标，不能完全反映身体 composition。"""


@tool
def calculate_bmr(age: int, gender: str, height_cm: float, weight_kg: float) -> str:
    """
    计算基础代谢率 (BMR)。
    
    Args:
        age: 年龄
        gender: 性别 (男/女)
        height_cm: 身高（厘米）
        weight_kg: 体重（公斤）
    
    Returns:
        BMR值及每日热量需求
    """
    if gender in ["男", "male", "m"]:
        # Mifflin-St Jeor 公式
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    
    bmr = int(bmr)
    
    # 活动水平估算
    daily_calories = {
        "久坐": bmr * 1.2,
        "轻度活动": bmr * 1.375,
        "中度活动": bmr * 1.55,
        "重度活动": bmr * 1.725,
        "极重活动": bmr * 1.9
    }
    
    result = f"""
【基础代谢率 (BMR)】
BMR = {bmr} 千卡/天

【每日热量需求估算】
"""
    for level, cal in daily_calories.items():
        result += f"• {level}: {int(cal)} 千卡\n"
    
    return result


@tool
def calculate_water_intake(weight_kg: float) -> str:
    """
    计算每日建议饮水量。
    
    Args:
        weight_kg: 体重（公斤）
    
    Returns:
        每日饮水建议
    """
    # 通用建议: 30-40ml/kg
    min_water = weight_kg * 30
    max_water = weight_kg * 40
    
    return f"""
【每日饮水建议】

基础建议: {int(min_water)}-{int(max_water)} 毫升

分次饮水建议:
• 早起后: 1杯 (约200ml)
• 早餐: 1-2杯
• 上午: 2-3杯
• 午餐: 1-2杯
• 下午: 2-3杯
• 晚餐: 1-2杯
• 睡前: 半杯

提示:
• 运动后需额外补充水分
• 发热、腹泻时需增加饮水量
• 肾功能异常者需遵医嘱"""


@tool
def calculate_heart_rate_zones(age: int, max_hr: int | None = None) -> str:
    """
    计算运动心率区间。
    
    Args:
        age: 年龄
        max_hr: 最大心率（如果不提供则用220-age估算）
    
    Returns:
        心率区间
    """
    if max_hr is None:
        max_hr = 220 - age
    
    zones = {
        "热身/恢复区": (0.5, 0.6),
        "脂肪燃烧区": (0.6, 0.7),
        "有氧耐力区": (0.7, 0.8),
        "无氧运动区": (0.8, 0.9),
        "极限运动区": (0.9, 1.0)
    }
    
    result = f"""
【运动心率区间】(最大心率: {max_hr} bpm)

"""
    for name, (low, high) in zones.items():
        low_hr = int(max_hr * low)
        high_hr = int(max_hr * high)
        result += f"• {name}: {low_hr}-{high_hr} bpm\n"
    
    result += """
建议:
• 普通人以脂肪燃烧区和有氧耐力区为主
• 运动新手从低强度开始
• 每周运动3-5次，每次30-60分钟"""
    
    return result
