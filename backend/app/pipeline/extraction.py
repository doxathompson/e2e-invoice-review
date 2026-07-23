from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.pipeline.classification import DocumentKind
from app.schemas.invoice.mapping import map_invoice_result
from app.schemas.receipt.mapping import map_receipt_result
from app.services.document_intelligence_service import (
    PREBUILT_INVOICE_MODEL,
    PREBUILT_RECEIPT_MODEL,
    DocumentIntelligenceService,
)

if TYPE_CHECKING:
    from app.pipeline.base import PipelineContext

logger = logging.getLogger(__name__)


class ExtractionStep:
    """Route to prebuilt-invoice or prebuilt-receipt and map into domain models."""

    name = "extraction"

    def __init__(self, service: DocumentIntelligenceService | None = None) -> None:
        self._service = service or DocumentIntelligenceService()

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.classification is None:
            raise ValueError("ExtractionStep requires ctx.classification from ClassificationStep.")

        document_path = ctx.document_path
        if ctx.classification.document_kind == DocumentKind.invoice:
            logger.info("Extracting with Document Intelligence model %s", PREBUILT_INVOICE_MODEL)
            result = self._service.analyze_invoice(document_path)
            extraction = map_invoice_result(self._service.to_dict(result))
        else:
            logger.info("Extracting with Document Intelligence model %s", PREBUILT_RECEIPT_MODEL)
            result = self._service.analyze_receipt(document_path)
            extraction = map_receipt_result(self._service.to_dict(result))

        logger.info(
            "Mapped extraction (%s) with %d line item(s)",
            extraction.document_type,
            len(extraction.items),
        )
        return ctx.model_copy(update={"extraction": extraction})
