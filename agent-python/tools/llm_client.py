# Legacy compatibility module. New code should use clients.llm_client.

from clients.llm_client import chat_completion

__all__ = ["chat_completion"]
