from datetime import datetime


def extract_date(value: str) -> str:
    if not value:
        return ""

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return value[:10]