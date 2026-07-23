import json
from typing import Any

from pydantic import ValidationError

from app.correction_email.base import CorrectionEmailDrafter, CorrectionEmailDraftingError
from app.correction_email.schemas import CorrectionEmailDraft
from app.documents.schemas import ReviewData, ValidationIssue

INSTRUCTIONS = """
Draft a concise, professional correction-request email from a finance administrator to the
supplier or merchant. Mention only the supplied business issues and document facts. Do not
mention AI, extraction confidence, internal systems, or invent an email address. Ask for a
corrected document or clarification. Use a neutral greeting and sign off as Maya, Finance
Administration, Northstar Facilities B.V.
""".strip()


class AzureOpenAICorrectionEmailDrafter(CorrectionEmailDrafter):
    def __init__(self, *, client: Any, deployment_name: str) -> None:
        self.client = client
        self.deployment_name = deployment_name

    def draft(
        self, data: ReviewData, issues: list[ValidationIssue]
    ) -> CorrectionEmailDraft:
        payload = json.dumps(
            {
                "document": data.model_dump(mode="json"),
                "issues": [issue.model_dump(mode="json") for issue in issues],
            }
        )
        try:
            response = self.client.responses.create(
                model=self.deployment_name,
                instructions=INSTRUCTIONS,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": payload,
                            }
                        ],
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "correction_email_draft",
                        "strict": True,
                        "schema": CorrectionEmailDraft.model_json_schema(),
                    }
                },
            )
        except Exception as error:
            raise CorrectionEmailDraftingError(
                "Azure OpenAI could not draft the correction email."
            ) from error

        try:
            return CorrectionEmailDraft.model_validate(json.loads(response.output_text))
        except (json.JSONDecodeError, ValidationError, TypeError) as error:
            raise CorrectionEmailDraftingError(
                "Azure OpenAI returned an invalid correction-email draft."
            ) from error
