from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    app_name: str = "Market Impact Agent"
    app_version: str = "0.1.0"
    app_host: str = "127.0.0.1"
    app_port: int = 8001

    llm_base_url: str = "https://api.openai.com/v1/chat/completions"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 60
    llm_retry_attempts: int = 3
    llm_retry_backoff_seconds: float = 1.0

    news_base_url: str = ""
    news_api_key: str = ""

    company_feeds_path: str = "config/company_feeds.json"
    market_feeds_path: str = "config/market_feeds.json"
    enable_company_rss: bool = True
    enable_market_rss: bool = True
    rss_timeout_seconds: int = 15
    min_news_count: int = 10

    market_base_url: str = ""
    market_api_key: str = ""

    jwt_secret: str = ""
    token_expire_days: int = 7

    cors_allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    enable_report_scheduler: bool = False
    daily_report_hour: int = 8
    daily_report_minute: int = 0
    report_job_scan_seconds: int = 60
    report_job_scan_interval_seconds: int = 5
    report_job_stale_seconds: int = 1800
    market_pulse_analysis_concurrency: int = 3
    market_pulse_analysis_timeout_seconds: int = 90

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
