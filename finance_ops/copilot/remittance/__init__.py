"""Pluggable remittance extractors — PDF text + optional OCR hook."""

from __future__ import annotations

from finance_ops.copilot.remittance.extractors import (
    OcrProvider,
    RemittanceExtractor,
    StubOcrProvider,
    TesseractOcrProvider,
    extract_remittance_document,
    get_default_extractor,
)
from finance_ops.copilot.remittance.types import RemittanceDocument

__all__ = [
    "OcrProvider",
    "RemittanceDocument",
    "RemittanceExtractor",
    "StubOcrProvider",
    "TesseractOcrProvider",
    "extract_remittance_document",
    "get_default_extractor",
]
