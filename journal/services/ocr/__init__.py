from .base import OCRProvider
from .openai import OpenAIOCR

PROVIDERS: dict[str, type[OCRProvider]] = {
    "openai": OpenAIOCR,
}


def get_provider(name: str, **kwargs) -> OCRProvider:
    cls = PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown OCR provider: {name}. Available: {list(PROVIDERS)}")
    return cls(**kwargs)
