from market_pulse.schemas import AnalyzeRequest, EntityResult
from clients.llm_client import chat_completion
from tools.json_util import parse_llm_json, as_float, as_str_list
from prompts.entity_prompt import ENTITY_SYSTEM_PROMPT, build_entity_user_prompt


async def resolve_entities(request: AnalyzeRequest) -> EntityResult:
    user_prompt = build_entity_user_prompt(request.title, request.content)
    raw = await chat_completion(ENTITY_SYSTEM_PROMPT, user_prompt)
    data = parse_llm_json(raw)

    return EntityResult(
        persons=as_str_list(data.get("persons")),
        companies=as_str_list(data.get("companies")),
        tickers=[ticker.upper() for ticker in as_str_list(data.get("tickers"))],
        topics=as_str_list(data.get("topics")),
        confidence=as_float(data.get("confidence"), default=0.0),
    )
