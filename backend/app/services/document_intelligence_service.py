from __future__ import annotations

from pathlib import Path

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, AnalyzeResult
from azure.core.credentials import AzureKeyCredential

from app.config import Settings, get_settings

PREBUILT_INVOICE_MODEL = "prebuilt-invoice"
PREBUILT_RECEIPT_MODEL = "prebuilt-receipt"

# Backwards-compatible alias for playground scripts.
DocumentIntelligenceSettings = Settings


class DocumentIntelligenceService:
    def __init__(self, settings: Settings | None = None) -> None:
        resolved_settings = settings or get_settings()
        self._client = DocumentIntelligenceClient(
            endpoint=resolved_settings.azure_document_intelligence_endpoint,
            credential=AzureKeyCredential(resolved_settings.azure_document_intelligence_key),
        )

    def analyze_invoice(self, document_path: Path) -> AnalyzeResult:
        poller = self._client.begin_analyze_document(
            PREBUILT_INVOICE_MODEL,
            AnalyzeDocumentRequest(bytes_source=document_path.read_bytes()),
        )
        return poller.result()

    def analyze_receipt(self, document_path: Path) -> AnalyzeResult:
        poller = self._client.begin_analyze_document(
            PREBUILT_RECEIPT_MODEL,
            AnalyzeDocumentRequest(bytes_source=document_path.read_bytes()),
        )
        return poller.result()

    @staticmethod
    def to_dict(result: AnalyzeResult) -> dict:
        return result.as_dict()
