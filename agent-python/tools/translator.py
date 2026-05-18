from tools.llm_client import chat_completion


TRANSLATE_SYSTEM_PROMPT = """
你是一个专业财经新闻翻译助手。
请把用户提供的英文财经新闻翻译成简体中文。
要求：
1. 保留公司名、人名、股票代码。
2. 不要添加原文没有的信息。
3. 不要输出解释。
4. 只输出翻译结果。
"""


async def translate_to_chinese(text: str) -> str:
    if not text or not text.strip():
        return ""

    user_prompt = f"""
请翻译以下财经新闻文本为简体中文：

{text}
"""

    result = await chat_completion(TRANSLATE_SYSTEM_PROMPT, user_prompt)
    return result.strip()