from openai import OpenAI

from app.config import Settings, get_settings


def build_azure_openai_client(settings: Settings | None = None) -> OpenAI:
    resolved = settings or get_settings()
    return OpenAI(
        base_url=resolved.azure_openai_endpoint,
        api_key=resolved.azure_openai_api_key,
    )
