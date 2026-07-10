from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


APP_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    environment: str = "development"
    app_name: str = "Market Impact Agent"
    app_version: str = "0.1.0"
    app_host: str = "127.0.0.1"
    app_port: int = 8010

    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    marketaux_api_key: str = ""
    marketaux_base_url: str = "https://api.marketaux.com/v1/news/all"
    marketaux_page_size: int = 20
    trace_dir: str = "traces"

    llm_base_url: str = "https://api.openai.com/v1/chat/completions"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 60
    llm_retry_attempts: int = 3
    llm_retry_backoff_seconds: float = 1.0

    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "text-embedding-3-small"

    company_feeds_path: str = "config/company_feeds.json"
    market_feeds_path: str = "config/market_feeds.json"
    enable_company_rss: bool = True
    enable_market_rss: bool = True
    rss_timeout_seconds: int = 15
    min_news_count: int = 10

    alpha_vantage_base_url: str = "https://www.alphavantage.co/query"
    alpha_vantage_api_key: str = ""

    jwt_secret: str = ""
    token_expire_days: int = 7

    cors_allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    enable_report_scheduler: bool = False
    daily_report_hour: int = 8
    daily_report_minute: int = 0
    report_job_scan_seconds: int = 60
    report_job_scan_interval_seconds: int = 5
    report_job_stale_seconds: int = 1800
    market_pulse_analysis_concurrency: int = 6
    market_pulse_analysis_timeout_seconds: int = 90
    # Max news kept after rank_news and sent to per-item LLM analysis.
    market_pulse_max_analyze: int = 50
    # RSS-first collection. Marketaux is an optional supplement that is OFF by
    # default because its free tier rate-limits quickly (each run fires ~21
    # queries) and can starve the candidate pool. Set true only with a paid tier.
    collect_enable_marketaux: bool = False

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context: object) -> None:
        """
        Auto-fallback from DeepSeek to OpenAI-compatible settings.

        If no standalone LLM key is provided but a DeepSeek key exists,
        reuses it. When llm_provider is "deepseek", auto-derives the
        chat completions URL from deepseek_base_url and uses the
        deepseek_model instead of the default gpt-4o-mini.
        """
        if _is_empty_or_placeholder(self.llm_api_key) and not _is_empty_or_placeholder(
            self.deepseek_api_key
        ):
            self.llm_api_key = self.deepseek_api_key

        if self.llm_provider.lower() == "deepseek":
            if self.llm_base_url == "https://api.openai.com/v1/chat/completions":
                self.llm_base_url = _deepseek_chat_url(self.deepseek_base_url)
            if self.llm_model in {"gpt-4o-mini", "deepseek-chat"}:
                self.llm_model = self.deepseek_model

def _is_empty_or_placeholder(value: str) -> bool:
    text = str(value or "").strip()
    return text == "" or text in {
        "your_key",
        "your_llm_api_key_here",
        "your_marketaux_key",
        "your_alpha_vantage_key",
    }


def _deepseek_chat_url(base_url: str) -> str:
    text = str(base_url or "https://api.deepseek.com").rstrip("/")
    if text.endswith("/chat/completions"):
        return text
    return text + "/chat/completions"


settings = Settings()
