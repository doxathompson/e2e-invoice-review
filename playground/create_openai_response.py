"""Send a prompt to Azure OpenAI through the backend service.

Run from this folder:

    uv run --project ../backend --locked --no-sync python create_openai_response.py

Pass a custom prompt:

    uv run --project ../backend --locked --no-sync python create_openai_response.py "Summarize this in one sentence."
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"

sys.path.insert(0, str(BACKEND_ROOT))

from app.services.azure_openai_service import AzureOpenAIService  # noqa: E402


def main() -> None:
    prompt = "What is the capital of France?"
    service = AzureOpenAIService()
    response = service.create_response(prompt)
    # print(json.dumps(response.model_dump(), indent=2, default=str))
    print(response.output[0].content[0].text)


if __name__ == "__main__":
    main()
