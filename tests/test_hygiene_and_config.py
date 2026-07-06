import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_env_examples_do_not_contain_real_key_formats():
    paths = [ROOT / ".env.example", ROOT / "agent-python" / ".env.example"]
    patterns = [
        re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        re.compile(r"deepseek-[A-Za-z0-9_-]{20,}", re.IGNORECASE),
        re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            assert not pattern.search(text), f"possible real key in {path}"
        assert "your_" in text


def test_frontend_default_api_matches_readme_and_config():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    config = (ROOT / "agent-python" / "app" / "config.py").read_text(encoding="utf-8")
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    api_js = (ROOT / "frontend" / "js" / "api.js").read_text(encoding="utf-8")

    assert "8010" in readme
    assert "app_port: int = 8010" in config
    assert "http://127.0.0.1:8010" in index
    assert "http://127.0.0.1:8010" in api_js
    assert "/api/agent/market-pulse/langgraph" in index
    assert "/api/agent/market-pulse/langgraph" in api_js
