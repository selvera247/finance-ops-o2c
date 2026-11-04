"""Remittance document with extracted fields + confidence."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ExtractionMethod = Literal["pdf_text", "plain_text", "ocr", "json_fixture", "none"]


class RemittanceDocument(BaseModel):
    document_id: str
    customer_id: str | None = None
    payment_id: str | None = None
    source_path: str | None = None
    method: ExtractionMethod = "none"
    text: str = ""
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    thin_evidence: bool = True
    notes: str | None = None

    def to_evidence_fields(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "customer_id": self.customer_id,
            "payment_id": self.payment_id,
            "source_path": self.source_path,
            "method": self.method,
            "text": self.text[:2000],
            "extracted_fields": dict(self.extracted_fields),
            "confidence": self.confidence,
            "thin_evidence": self.thin_evidence,
            "notes": self.notes,
        }
