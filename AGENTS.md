Financial Agents is a Market Intelligence Agentic Workflow portfolio project.

Project boundary:
- Do not turn this into an auto-trading, stock-picking, buy/sell recommendation, or portfolio advice system.
- Outputs should be market observations, risk observations, evidence summaries, and research references.
- Every user-facing report must keep a clear disclaimer that it is not investment advice.

Primary workflow:
- The recommended demo entry is the LangGraph Market Pulse path:
  `POST /api/agent/market-pulse/langgraph`.
- The workflow is `collect_news -> rank_news -> analyze_items -> risk_route -> risk_review -> generate_report`.
- Legacy endpoints may stay for compatibility, but do not make them the recommended demo path.

Change discipline:
- Keep README, API routes, frontend API calls, evals, and tests consistent when changing behavior.
- Prefer small, deterministic improvements over broad rewrites.
- Preserve existing auth, watchlist, report job, report history, Docker, and frontend functionality.
- Do not commit `.env` or real API keys. Example config files must contain placeholders only.
- Tests and evals should run offline or with mock data by default.
