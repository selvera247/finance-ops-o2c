"""Deterministic PDF/text remittance extract + pluggable OCR provider.

CI-safe: no GPU / tesseract required. Optional tesseract binary when present.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from finance_ops.copilot.remittance.types import RemittanceDocument
from finance_ops.lib.paths import REPO_ROOT

_DEFAULT_DIR = REPO_ROOT / "data" / "copilot" / "remittance"

_INV_RE = re.compile(r"\b(INV-[\w-]+)\b", re.IGNORECASE)
_PAY_RE = re.compile(r"\b(PAY-[\w-]+)\b", re.IGNORECASE)
_PO_RE = re.compile(r"\b(PO-[\w-]+)\b", re.IGNORECASE)
_CUST_RE = re.compile(r"\b(C-\d+)\b", re.IGNORECASE)
_AMT_RE = re.compile(
    r"(?i)(?:amount|total)\s*[:=]?\s*\$?\s*"
    r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?)"
    r"(?:\s*USD)?"
)
_AMT_BARE = re.compile(r"\b([0-9]+(?:,[0-9]{3})*\.[0-9]{2})\b")
_THIN_RE = re.compile(
    r"\bno invoice\b|\bmissing remittance\b|\bunknown\b|\bn/?a\b|\bunclear\b|\?\?\?\?",
    re.IGNORECASE,
)
_PDF_LITERAL = re.compile(r"\((?:\\.|[^\\)])*\)\s*Tj")


def is_thin_remittance_text(text: str | None) -> bool:
    """Shared thin-remittance detector for extractors + investigate fallback."""
    if not text:
        return False
    return bool(_THIN_RE.search(text))


class OcrProvider(ABC):
    """Optional OCR backend. Stub used in CI."""

    name: str = "base"

    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def ocr_image_or_pdf(self, path: Path) -> tuple[str, float]:
        """Return (text, confidence 0..1)."""
        raise NotImplementedError


class StubOcrProvider(OcrProvider):
    """Fixture OCR: reads sibling .txt / .ocr.txt when present; else empty."""

    name = "stub"

    def available(self) -> bool:
        return True

    def ocr_image_or_pdf(self, path: Path) -> tuple[str, float]:
        for candidate in (
            path.with_suffix(".ocr.txt"),
            path.with_suffix(".txt"),
        ):
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8", errors="replace")
                # Low confidence when thin markers present.
                conf = 0.35 if _THIN_RE.search(text) else 0.55
                return text, conf
        return "", 0.0


class TesseractOcrProvider(OcrProvider):
    """Optional system tesseract. Skipped when binary missing."""

    name = "tesseract"

    def available(self) -> bool:
        if (os.getenv("COPILOT_OCR_PROVIDER") or "").strip().lower() == "stub":
            return False
        return shutil.which("tesseract") is not None

    def ocr_image_or_pdf(self, path: Path) -> tuple[str, float]:
        if not self.available():
            return "", 0.0
        # Tesseract wants images; for PDF we fall back to stub sibling text.
        if path.suffix.lower() == ".pdf":
            stub = StubOcrProvider().ocr_image_or_pdf(path)
            if stub[0]:
                return stub[0], min(stub[1], 0.5)
            return "", 0.0
        try:
            proc = subprocess.run(
                ["tesseract", str(path), "stdout"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            text = (proc.stdout or "").strip()
            if not text:
                return "", 0.0
            conf = 0.4 if _THIN_RE.search(text) else 0.65
            return text, conf
        except Exception:
            return "", 0.0


def _pdf_text_extract(path: Path) -> str:
    """Extract text from simple PDF content streams without third-party deps.

    Also tries optional ``pypdf`` when installed.
    """
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        chunks: list[str] = []
        for page in reader.pages:
            chunks.append(page.extract_text() or "")
        joined = "\n".join(chunks).strip()
        if joined:
            return joined
    except Exception:
        pass

    raw = path.read_bytes().decode("latin-1", errors="replace")
    parts: list[str] = []
    for m in _PDF_LITERAL.finditer(raw):
        lit = m.group(0)
        # strip trailing Tj and outer parens
        inner = lit.rsplit("Tj", 1)[0].strip()
        if inner.startswith("(") and inner.endswith(")"):
            inner = inner[1:-1]
        inner = (
            inner.replace("\\n", "\n")
            .replace("\\(", "(")
            .replace("\\)", ")")
            .replace("\\\\", "\\")
        )
        if inner.strip():
            parts.append(inner)
    if parts:
        return "\n".join(parts)
    # Last resort: expose readable ASCII runs (still useful for our fixtures).
    return "\n".join(
        line
        for line in raw.splitlines()
        if re.search(r"[A-Za-z]{3,}", line) and "endobj" not in line
    )


def parse_remittance_fields(text: str) -> dict[str, Any]:
    invoice_ids = list(dict.fromkeys(m.group(1).upper() for m in _INV_RE.finditer(text)))
    payment_ids = list(dict.fromkeys(m.group(1).upper() for m in _PAY_RE.finditer(text)))
    po_numbers = list(dict.fromkeys(m.group(1).upper() for m in _PO_RE.finditer(text)))
    customers = list(dict.fromkeys(m.group(1).upper() for m in _CUST_RE.finditer(text)))
    amount = None
    m = _AMT_RE.search(text) or _AMT_BARE.search(text)
    if m:
        try:
            amount = float(m.group(1).replace(",", ""))
        except ValueError:
            amount = None
    currency = "USD" if re.search(r"\bUSD\b|\$", text, re.IGNORECASE) else None
    return {
        "invoice_ids": invoice_ids,
        "payment_id": payment_ids[0] if payment_ids else None,
        "payment_ids": payment_ids,
        "po_numbers": po_numbers,
        "customer_id": customers[0] if customers else None,
        "amount": amount,
        "currency": currency,
        "raw_reference": (text or "").strip()[:500],
    }


def score_extraction_confidence(
    text: str,
    fields: dict[str, Any],
    *,
    method: str,
    base: float | None = None,
) -> tuple[float, bool]:
    """Return (confidence, thin_evidence)."""
    if not (text or "").strip():
        return 0.0, True
    if _THIN_RE.search(text) and not fields.get("invoice_ids"):
        return min(base or 0.25, 0.3), True
    score = 0.2 if base is None else float(base)
    if fields.get("invoice_ids"):
        score += 0.35
    if fields.get("payment_id"):
        score += 0.15
    if fields.get("amount") is not None:
        score += 0.15
    if fields.get("po_numbers"):
        score += 0.1
    if fields.get("customer_id"):
        score += 0.05
    if method == "pdf_text":
        score += 0.05
    elif method == "ocr":
        score -= 0.05
    score = max(0.0, min(1.0, score))
    thin = score < 0.45 or not fields.get("invoice_ids")
    return score, thin


class RemittanceExtractor:
    """Pluggable extractor: PDF text first, OCR hook as fallback."""

    def __init__(self, ocr: OcrProvider | None = None) -> None:
        self.ocr = ocr or _select_ocr_provider()

    def extract_path(
        self,
        path: Path,
        *,
        document_id: str | None = None,
        customer_id: str | None = None,
        payment_id: str | None = None,
    ) -> RemittanceDocument:
        path = Path(path)
        doc_id = document_id or path.stem
        suffix = path.suffix.lower()
        text = ""
        method: str = "none"
        ocr_conf: float | None = None

        if suffix == ".json":
            meta = json.loads(path.read_text(encoding="utf-8"))
            # Prefer linked txt/pdf beside the json fixture.
            sibling_pdf = path.with_suffix(".pdf")
            sibling_txt = path.with_suffix(".txt")
            if sibling_pdf.is_file():
                return self.extract_path(
                    sibling_pdf,
                    document_id=str(meta.get("document_id") or doc_id),
                    customer_id=customer_id or meta.get("customer_id"),
                    payment_id=payment_id or meta.get("payment_id"),
                )
            if sibling_txt.is_file():
                return self.extract_path(
                    sibling_txt,
                    document_id=str(meta.get("document_id") or doc_id),
                    customer_id=customer_id or meta.get("customer_id"),
                    payment_id=payment_id or meta.get("payment_id"),
                )
            fields = dict(meta.get("expected_fields") or {})
            conf = float(meta.get("min_confidence") or 0.0)
            thin = bool(meta.get("expect_thin")) or conf < 0.45
            return RemittanceDocument(
                document_id=str(meta.get("document_id") or doc_id),
                customer_id=customer_id or meta.get("customer_id"),
                payment_id=payment_id or meta.get("payment_id"),
                source_path=str(path),
                method="json_fixture",
                text=json.dumps(fields),
                extracted_fields=fields,
                confidence=conf,
                thin_evidence=thin,
                notes="json fixture without sibling text/pdf",
            )

        if suffix in {".txt", ".csv", ".edi"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            method = "plain_text"
        elif suffix == ".pdf":
            text = _pdf_text_extract(path)
            method = "pdf_text"
            # If PDF text is empty / thin markers dominate, try OCR hook.
            if not text.strip() or (
                _THIN_RE.search(text) and not _INV_RE.search(text)
            ):
                ocr_text, ocr_conf = self.ocr.ocr_image_or_pdf(path)
                if ocr_text.strip() and (
                    not text.strip() or len(ocr_text) >= len(text)
                ):
                    text = ocr_text
                    method = "ocr"
        else:
            # Images etc. → OCR only
            text, ocr_conf = self.ocr.ocr_image_or_pdf(path)
            method = "ocr" if text else "none"

        fields = parse_remittance_fields(text)
        if customer_id and not fields.get("customer_id"):
            fields["customer_id"] = customer_id
        if payment_id and not fields.get("payment_id"):
            fields["payment_id"] = payment_id
        conf, thin = score_extraction_confidence(
            text, fields, method=method, base=ocr_conf
        )
        return RemittanceDocument(
            document_id=doc_id,
            customer_id=fields.get("customer_id") or customer_id,
            payment_id=fields.get("payment_id") or payment_id,
            source_path=str(path),
            method=method,  # type: ignore[arg-type]
            text=text,
            extracted_fields=fields,
            confidence=conf,
            thin_evidence=thin,
            notes=f"extractor={method};ocr={self.ocr.name}",
        )

    def extract_text(
        self,
        text: str,
        *,
        document_id: str,
        customer_id: str | None = None,
        payment_id: str | None = None,
    ) -> RemittanceDocument:
        fields = parse_remittance_fields(text)
        if customer_id and not fields.get("customer_id"):
            fields["customer_id"] = customer_id
        if payment_id and not fields.get("payment_id"):
            fields["payment_id"] = payment_id
        conf, thin = score_extraction_confidence(text, fields, method="plain_text")
        return RemittanceDocument(
            document_id=document_id,
            customer_id=fields.get("customer_id") or customer_id,
            payment_id=fields.get("payment_id") or payment_id,
            source_path=None,
            method="plain_text",
            text=text,
            extracted_fields=fields,
            confidence=conf,
            thin_evidence=thin,
        )


def _select_ocr_provider() -> OcrProvider:
    pref = (os.getenv("COPILOT_OCR_PROVIDER") or "auto").strip().lower()
    if pref == "tesseract":
        tess = TesseractOcrProvider()
        return tess if tess.available() else StubOcrProvider()
    if pref == "stub":
        return StubOcrProvider()
    tess = TesseractOcrProvider()
    if tess.available():
        return tess
    return StubOcrProvider()


def get_default_extractor() -> RemittanceExtractor:
    return RemittanceExtractor(ocr=_select_ocr_provider())


def remittance_dir() -> Path:
    override = (os.getenv("COPILOT_REMITTANCE_DIR") or "").strip()
    return Path(override) if override else _DEFAULT_DIR


def find_remittance_path(payment_id: str) -> Path | None:
    """Locate fixture remittance for a payment id (pdf/txt/json)."""
    base = remittance_dir()
    if not base.is_dir():
        return None
    pid = payment_id.strip().upper()
    candidates = [
        base / f"REM-{pid}.pdf",
        base / f"REM-{pid}.txt",
        base / f"REM-{pid}.json",
        base / f"{pid}.pdf",
        base / f"{pid}.txt",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def extract_remittance_document(
    *,
    payment_id: str,
    customer_id: str | None = None,
    path: Path | None = None,
    reference_text: str | None = None,
    extractor: RemittanceExtractor | None = None,
) -> RemittanceDocument | None:
    """Resolve remittance for a payment — file fixture preferred, else reference text."""
    ext = extractor or get_default_extractor()
    resolved = path or find_remittance_path(payment_id)
    if resolved is not None:
        return ext.extract_path(
            resolved,
            document_id=f"REM-{payment_id}",
            customer_id=customer_id,
            payment_id=payment_id,
        )
    if reference_text:
        return ext.extract_text(
            reference_text,
            document_id=f"REM-{payment_id}",
            customer_id=customer_id,
            payment_id=payment_id,
        )
    return None
