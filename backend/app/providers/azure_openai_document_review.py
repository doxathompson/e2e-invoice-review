import base64
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.document_review.base import DocumentReviewer, DocumentReviewError
from app.document_review.schemas import LlmDocumentExtraction

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png"}

INSTRUCTIONS = """
You are an independent financial-document reviewer. First classify the source as invoice,
receipt, or unsupported. Then extract every requested value directly from the source without
using another model's output. For receipts, map the merchant to vendor_name, transaction date
to invoice_date, total to invoice_total and amount_due, and classify the expense as fuel,
meals, travel, supplies, or other. Return dates as YYYY-MM-DD and monetary values as plain
decimal strings without currency symbols. Use null when a value is absent or unreadable. The
summary must be one concise factual sentence. Do not decide whether the document should be
approved; deterministic application rules do that.
""".strip()


class AzureOpenAIDocumentReviewer(DocumentReviewer):
    def __init__(self, *, client: Any, deployment_name: str) -> None:
        self.client = client
        self.deployment_name = deployment_name

    def review(self, path: Path, content_type: str) -> LlmDocumentExtraction:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        if content_type == "application/pdf":
            document_part = {
                "type": "input_file",
                "filename": path.name,
                "file_data": f"data:application/pdf;base64,{encoded}",
            }
        elif content_type in SUPPORTED_IMAGE_TYPES:
            document_part = {
                "type": "input_image",
                "image_url": f"data:{content_type};base64,{encoded}",
                "detail": "high",
            }
        else:
            raise DocumentReviewError(
                "The independent LLM review supports PDF, PNG, or JPEG files. "
                "Document Intelligence and deterministic checks still completed."
            )

        schema = LlmDocumentExtraction.model_json_schema()
        try:
            response = self.client.responses.create(
                model=self.deployment_name,
                instructions=INSTRUCTIONS,
                input=[
                    {
                        "role": "user",
                        "content": [
                            document_part,
                            {
                                "type": "input_text",
                                "text": (
                                    "Classify, independently extract, and review this "
                                    "financial document."
                                ),
                            },
                        ],
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "financial_document_review",
                        "strict": True,
                        "schema": schema,
                    }
                },
            )
        except Exception as error:
            raise DocumentReviewError(
                "Azure OpenAI document review failed. The deterministic review can continue."
            ) from error

        try:
            return LlmDocumentExtraction.model_validate(json.loads(response.output_text))
        except (json.JSONDecodeError, ValidationError, TypeError) as error:
            raise DocumentReviewError(
                "Azure OpenAI did not return valid structured document-review output."
            ) from error
