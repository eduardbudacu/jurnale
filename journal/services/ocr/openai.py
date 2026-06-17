import base64
import os
from pathlib import Path

from openai import OpenAI

from .base import OCRProvider

DEFAULT_MODEL = "gpt-4o"

SYSTEM_PROMPT = (
    "You are an OCR assistant specialized in reading handwritten text from journal pages. "
    "Transcribe the handwritten text in the image as accurately as possible. "
    "Preserve paragraph breaks. If text is illegible, indicate with [illegible]. "
    "Output only the transcribed text, nothing else."
)


class OpenAIOCR(OCRProvider):
    name = "openai"

    def __init__(self, model: str | None = None, **kwargs):
        self._model = model or os.environ.get("OCR_MODEL", DEFAULT_MODEL)
        self._client = OpenAI()

    @property
    def model_name(self) -> str:
        return self._model

    def ocr(self, image_path: Path) -> str:
        img_bytes = image_path.read_bytes()
        b64 = base64.b64encode(img_bytes).decode()
        mime = "image/png"

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
                        },
                    ],
                },
            ],
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""
