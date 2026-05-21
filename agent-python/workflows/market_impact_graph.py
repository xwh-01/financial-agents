import uuid
from typing import Any, TypedDict

# Legacy compatibility module. New code should use market_pulse/...

from langgraph.graph import END, START, StateGraph

from schemas.request import AnalyzeRequest
from schemas.workflow import WorkflowResult

from agents.entity_resolver import resolve_entities
from agents.event_analyzer import analyze_event
from agents.ticker_linker import link_tickers
from agents.market_analyzer import analyze_market
from agents.risk_checker import check_risk
from agents.report_generator import generate_report
from agents.compliance_checker import check_compliance


class MarketImpactGraphState(TypedDict, total=False):
    request: AnalyzeRequest
    entities: Any
    event: Any
    tickers: Any
    market: Any
    risk: Any
    report: Any
    result: WorkflowResult
    status: str
    error_message: str | None
    task_id: str


async def _resolve_entities_node(
    state: MarketImpactGraphState,
) -> MarketImpactGraphState:
    print("[graph] resolve_entities")
    return {"entities": await resolve_entities(state["request"])}


async def _analyze_event_node(state: MarketImpactGraphState) -> MarketImpactGraphState:
    print("[graph] analyze_event")
    return {
        "event": await analyze_event(
            state["request"],
            state["entities"],
        )
    }


def _link_tickers_node(state: MarketImpactGraphState) -> MarketImpactGraphState:
    print("[graph] link_tickers")
    return {"tickers": link_tickers(state["entities"], state["event"])}


async def _analyze_market_node(state: MarketImpactGraphState) -> MarketImpactGraphState:
    print("[graph] analyze_market")
    return {
        "market": await analyze_market(
            state["tickers"],
            state["request"].published_at,
        )
    }


def _check_risk_node(state: MarketImpactGraphState) -> MarketImpactGraphState:
    print("[graph] check_risk")
    return {
        "risk": check_risk(
            state["request"],
            state["event"],
            state["tickers"],
        )
    }


async def _generate_report_node(state: MarketImpactGraphState) -> MarketImpactGraphState:
    print("[graph] generate_report")
    return {
        "report": await generate_report(
            entity_result=state["entities"],
            event_result=state["event"],
            ticker_links=state["tickers"],
            market_metrics=state["market"],
            risk_result=state["risk"],
        )
    }


def _check_compliance_node(state: MarketImpactGraphState) -> MarketImpactGraphState:
    print("[graph] check_compliance")
    compliance_result = check_compliance(state["report"])
    status = (
        "completed"
        if compliance_result.passed
        else "completed_with_compliance_warning"
    )

    result = WorkflowResult(
        task_id=state["task_id"],
        status=status,
        entity_result=state["entities"],
        event_result=state["event"],
        ticker_links=state["tickers"],
        market_metrics=state["market"],
        risk_result=state["risk"],
        compliance_result=compliance_result,
        report=compliance_result.sanitized_report,
        error_message=None,
    )

    return {
        "result": result,
        "status": status,
        "error_message": None,
    }


def _build_market_impact_graph():
    graph = StateGraph(MarketImpactGraphState)

    graph.add_node("resolve_entities", _resolve_entities_node)
    graph.add_node("analyze_event", _analyze_event_node)
    graph.add_node("link_tickers", _link_tickers_node)
    graph.add_node("analyze_market", _analyze_market_node)
    graph.add_node("check_risk", _check_risk_node)
    graph.add_node("generate_report", _generate_report_node)
    graph.add_node("check_compliance", _check_compliance_node)

    graph.add_edge(START, "resolve_entities")
    graph.add_edge("resolve_entities", "analyze_event")
    graph.add_edge("analyze_event", "link_tickers")
    graph.add_edge("link_tickers", "analyze_market")
    graph.add_edge("analyze_market", "check_risk")
    graph.add_edge("check_risk", "generate_report")
    graph.add_edge("generate_report", "check_compliance")
    graph.add_edge("check_compliance", END)

    return graph.compile()


market_impact_graph = _build_market_impact_graph()


async def run_market_impact_graph(request: AnalyzeRequest) -> WorkflowResult:
    task_id = str(uuid.uuid4())

    try:
        final_state = await market_impact_graph.ainvoke(
            {
                "request": request,
                "task_id": task_id,
                "status": "running",
                "error_message": None,
            }
        )
        return final_state["result"]

    except Exception as exc:
        return WorkflowResult(
            task_id=task_id,
            status="failed",
            report="",
            error_message=str(exc),
        )
