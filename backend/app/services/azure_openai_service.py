from __future__ import annotations

from pathlib import Path

from openai import OpenAI
from openai.types.responses import Response
from pydantic_settings import BaseSettings, SettingsConfigDict

DEPLOYMENT_NAME = "gpt-5.6-terra"
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class AzureOpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    azure_openai_endpoint: str
    azure_openai_api_key: str


class AzureOpenAIService:
    def __init__(self, settings: AzureOpenAISettings | None = None) -> None:
        resolved_settings = settings or AzureOpenAISettings()
        self._client = OpenAI(
            base_url=resolved_settings.azure_openai_endpoint,
            api_key=resolved_settings.azure_openai_api_key,
        )

    def create_response(self, input: str) -> Response:
        return self._client.responses.create(
            model=DEPLOYMENT_NAME,
            input=input,
        )
