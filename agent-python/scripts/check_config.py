from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ENV_FILE, settings


def _mask(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return "<empty>"
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}***{text[-4:]}"


def main() -> None:
    print("Config file:")
    p = Path(ENV_FILE)
    print(f"- {p}: exists={p.exists()}")

    print("\nLLM:")
    print(f"- provider={settings.llm_provider}")
    print(f"- base_url={settings.llm_base_url}")
    print(f"- model={settings.llm_model}")
    print(f"- has_key={bool(settings.llm_api_key)} key={_mask(settings.llm_api_key)}")

    print("\nMarketaux:")
    print(f"- base_url={settings.marketaux_base_url}")
    print(
        f"- has_key={bool(settings.marketaux_api_key)} "
        f"key={_mask(settings.marketaux_api_key)}"
    )
    print(f"- page_size={settings.marketaux_page_size}")

    print("\nAlpha Vantage:")
    print(f"- base_url={settings.alpha_vantage_base_url}")
    print(
        f"- has_key={bool(settings.alpha_vantage_api_key)} "
        f"key={_mask(settings.alpha_vantage_api_key)}"
    )


if __name__ == "__main__":
    main()
