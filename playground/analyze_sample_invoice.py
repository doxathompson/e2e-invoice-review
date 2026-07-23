"""Analyze the sample invoice with Azure Document Intelligence.

Run from this folder:

    uv run --project ../backend --locked --no-sync python analyze_sample_invoice.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
SAMPLE_INVOICE = REPO_ROOT / "samples" / "sample-invoice.pdf"

sys.path.insert(0, str(BACKEND_ROOT))

from app.services.document_intelligence_service import DocumentIntelligenceService  # noqa: E402


def main() -> None:
    service = DocumentIntelligenceService()
    result = service.analyze_invoice(SAMPLE_INVOICE)
    print(json.dumps(service.to_dict(result), indent=2, default=str))
    result.content
    


if __name__ == "__main__":
    main()
