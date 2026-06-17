from abc import ABC, abstractmethod
from pathlib import Path


class OCRProvider(ABC):
    """Base class for OCR providers."""

    name: str = "base"

    @abstractmethod
    def ocr(self, image_path: Path) -> str:
        """Extract text from an image file. Returns the recognized text."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier used for this provider."""
        ...
