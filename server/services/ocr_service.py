"""OCR 服务 - 基于千问 Qwen-VL-OCR 模型"""
import base64
import logging

from openai import OpenAI

from server.config import settings

logger = logging.getLogger(__name__)


class OCRService:
    """OCR 服务，封装千问 OCR API (OpenAI 兼容模式)"""

    def __init__(self):
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.ocr_api_key,
                base_url=settings.ocr_api_base,
            )
        return self._client

    async def extract_text(self, image_bytes: bytes, filename: str = "image.jpg") -> str:
        """从图片字节流提取文字

        Args:
            image_bytes: 图片二进制数据
            filename: 原始文件名（用于判断格式）

        Returns:
            识别出的文字内容
        """
        # 将图片转为 base64
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # 根据后缀判断 MIME 类型
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "jpg"
        mime_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "bmp": "image/bmp",
        }
        mime = mime_map.get(ext, "image/jpeg")
        data_url = f"data:{mime};base64,{image_base64}"

        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": "请完整识别这张体检报告中的所有文字内容，包括数值、单位和结论。"},
                    ],
                }
            ]

            response = self.client.chat.completions.create(
                model=settings.ocr_model,
                messages=messages,  # pyright: ignore[reportArgumentType]
                max_tokens=4096,
            )

            text = response.choices[0].message.content or ""
            logger.info("OCR 识别成功，长度=%d 字符", len(text))
            return text

        except Exception as e:
            logger.error("OCR 识别失败: %s", e)
            raise


ocr_service = OCRService()
