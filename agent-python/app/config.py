from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Market Impact Agent"
    app_version: str = "0.1.0"
    app_host: str = "127.0.0.1"
    app_port: int = 8001

    llm_base_url: str = "https://api.openai.com/v1/chat/completions"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    news_base_url: str = ""
    news_api_key: str = ""

    market_base_url: str = ""
    market_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()