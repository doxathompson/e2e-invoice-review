from __future__ import annotations

from pathlib import Path

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from pydantic_settings import BaseSettings, SettingsConfigDict

PREBUILT_INVOICE_MODEL = "prebuilt-invoice"
PREBUILT_RECEIPT_MODEL = "prebuilt-receipt"
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class DocumentIntelligenceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    azure_document_intelligence_endpoint: str
    azure_document_intelligence_key: str


class DocumentIntelligenceService:
    def __init__(self, settings: DocumentIntelligenceSettings | None = None) -> None:
        resolved_settings = settings or DocumentIntelligenceSettings()
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
