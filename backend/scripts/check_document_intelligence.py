from pathlib import Path

from app.documents.projection import project_extraction
from app.schemas.invoice.mapping import map_invoice_result
from app.services.document_intelligence_service import DocumentIntelligenceService


def main() -> None:
    sample = Path(__file__).parents[2] / "samples" / "sample-invoice.pdf"
    if not sample.exists():
        sample = Path(__file__).parents[2] / "samples" / "generated" / "01-en-happy-classic.pdf"
    service = DocumentIntelligenceService()
    result = service.analyze_invoice(sample)
    review_data = project_extraction(map_invoice_result(service.to_dict(result)))
    print(review_data.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
