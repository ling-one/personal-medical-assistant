"""好大夫在线医疗对话数据解析工具"""
import re
from typing import Any, Generator


def parse_haodf_file(file_path: str) -> Generator[dict[str, Any], None, None]:
    """
    流式解析好大夫数据文件
    
    按 `id=` 分割记录，逐条 yield 返回，避免将 104MB 文件一次性加载到内存。
    
    Args:
        file_path: 医疗对话.txt 的路径
        
    Yields:
        每条记录字典，包含：
        - id: 记录编号 (int)
        - url: 医生主页链接 (str)
        - doctor_faculty: 医生科室 (str)
        - disease: 疾病描述 (str)
        - description: 病情描述 (str)
        - help_needed: 希望获得的帮助 (str)
        - pregnancy: 怀孕情况 (str|None)
        - duration: 患病多久 (str|None)
        - allergy: 过敏史 (str|None)
        - past_history: 既往病史 (str|None)
        - medication: 用药情况 (str|None)
        - dialogue: 医患对话 (str|None)
        - diagnosis: 诊断建议 (str|None)
        - content: 合并后的向量化文本 (str)
        - metadata: 原始字段字典 (dict)
    """
    current_record = None
    current_field = None
    buffer_lines = []
    
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            
            # 检测新记录开始: id=XXX
            id_match = re.match(r"^id=(\d+)$", line.strip())
            if id_match:
                # 保存上一条记录
                if current_record is not None:
                    _finalize_record(current_record, buffer_lines)
                    yield current_record
                    buffer_lines = []
                
                # 开始新记录
                current_record = {
                    "id": int(id_match.group(1)),
                    "url": "",
                    "doctor_faculty": "",
                    "disease": "",
                    "description": "",
                    "help_needed": "",
                    "pregnancy": None,
                    "duration": None,
                    "allergy": None,
                    "past_history": None,
                    "medication": None,
                    "dialogue": None,
                    "diagnosis": None,
                }
                current_field = None
                continue
            
            if current_record is None:
                continue
            
            # 检测 URL
            if line.strip().startswith("http"):
                current_record["url"] = line.strip()
                continue
            
            # 检测字段标题
            if line.strip() == "Doctor faculty":
                current_field = "doctor_faculty"
                continue
            elif line.strip() == "Description":
                current_field = "description"
                continue
            elif line.strip() == "Dialogue":
                current_field = "dialogue"
                continue
            elif line.strip() == "Diagnosis and suggestions":
                current_field = "diagnosis"
                continue
            
            # 处理字段内容
            if current_field == "doctor_faculty":
                if line.strip():
                    current_record["doctor_faculty"] = line.strip()
                    current_field = None
                continue
            
            elif current_field == "description":
                # Description 块内包含多个子字段
                if line.startswith("疾病："):
                    current_record["disease"] = line.replace("疾病：", "").strip()
                elif line.startswith("病情描述："):
                    current_record["description"] = line.replace("病情描述：", "").strip()
                elif line.startswith("希望获得的帮助："):
                    current_record["help_needed"] = line.replace("希望获得的帮助：", "").strip()
                elif line.startswith("怀孕情况："):
                    current_record["pregnancy"] = line.replace("怀孕情况：", "").strip()
                elif line.startswith("患病多久："):
                    current_record["duration"] = line.replace("患病多久：", "").strip()
                elif line.startswith("过敏史："):
                    current_record["allergy"] = line.replace("过敏史：", "").strip()
                elif line.startswith("既往病史："):
                    current_record["past_history"] = line.replace("既往病史：", "").strip()
                elif line.startswith("用药情况："):
                    current_record["medication"] = line.replace("用药情况：", "").strip()
                continue
            
            elif current_field == "dialogue":
                # 对话内容，累积多行
                if line.strip():
                    buffer_lines.append(line.strip())
                else:
                    if buffer_lines:
                        current_record["dialogue"] = "\n".join(buffer_lines)
                        buffer_lines = []
                    current_field = None
                continue
            
            elif current_field == "diagnosis":
                # 诊断建议，累积多行
                if line.strip() and not line.strip().startswith("医生已经通过语音"):
                    buffer_lines.append(line.strip())
                else:
                    if buffer_lines:
                        current_record["diagnosis"] = "\n".join(buffer_lines)
                        buffer_lines = []
                    current_field = None
                continue
        
        # 处理最后一条记录
        if current_record is not None:
            _finalize_record(current_record, buffer_lines)
            yield current_record


def _finalize_record(record: dict, buffer_lines: list) -> None:
    """完成记录的最后处理，生成 content 字段"""
    # 处理未完成的 buffer
    if buffer_lines:
        if record.get("dialogue") is None:
            record["dialogue"] = "\n".join(buffer_lines)
        elif record.get("diagnosis") is None:
            record["diagnosis"] = "\n".join(buffer_lines)
    
    # 生成用于向量化的文本内容
    content_parts = []
    
    if record.get("disease"):
        content_parts.append(f"疾病：{record['disease']}")
    
    if record.get("description"):
        content_parts.append(f"病情描述：{record['description']}")
    
    if record.get("help_needed"):
        content_parts.append(f"咨询问题：{record['help_needed']}")
    
    if record.get("doctor_faculty"):
        content_parts.append(f"科室：{record['doctor_faculty']}")
    
    if record.get("dialogue"):
        content_parts.append(f"对话：{record['dialogue']}")
    
    if record.get("diagnosis"):
        content_parts.append(f"诊断建议：{record['diagnosis']}")
    
    record["content"] = "\n".join(content_parts)
    
    # 生成 metadata
    record["metadata"] = {
        "source": "haodf",
        "record_id": record["id"],
        "url": record["url"],
        "doctor_faculty": record["doctor_faculty"],
        "pregnancy": record.get("pregnancy"),
        "duration": record.get("duration"),
        "allergy": record.get("allergy"),
        "past_history": record.get("past_history"),
    }


def count_records(file_path: str) -> int:
    """
    快速统计文件中的记录总数
    
    Args:
        file_path: 文件路径
        
    Returns:
        记录总数
    """
    count = 0
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if re.match(r"^id=\d+$", line.strip()):
                count += 1
    return count


def test_parser(file_path: str, max_records: int = 5) -> None:
    """
    测试解析器，打印前 N 条记录
    
    Args:
        file_path: 文件路径
        max_records: 最多打印的记录数
    """
    print(f"测试解析文件：{file_path}")
    print(f"预计记录数：{count_records(file_path)}\n")
    
    for i, record in enumerate(parse_haodf_file(file_path)):
        if i >= max_records:
            break
        print(f"=== 记录 {i+1} ===")
        print(f"ID: {record['id']}")
        print(f"科室: {record['doctor_faculty']}")
        print(f"疾病: {record['disease']}")
        print(f"内容预览: {record['content'][:100]}...")
        print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        max_records = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        test_parser(sys.argv[1], max_records)
    else:
        print("用法: python haodf_parser.py <文件路径> [最大记录数]")
