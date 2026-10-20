"""Google ADK agent for natural-language RDF graph exploration."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import BaseTool

from sparql_agent.artifacts import save_query_artifact
from sparql_agent.config import Settings
from sparql_agent.tools import create_tools

DEFAULT_INSTRUCTION = """
Answer user questions by querying the configured RDF graph and summarizing the results. Follow this compact workflow internally; do not narrate the plan unless asked.

1. Understand the question. For non-English input, reason from a faithful English semantic paraphrase while answering in the user's language.
2. Inspect the data shape with schema when it is not already known. Use schema with search text to resolve user-mentioned entity and relation labels to observed IRIs; never guess an IRI.
3. Compose the smallest read-only query that answers the question and execute it with sparql.
4. Treat validation errors and unexpectedly empty results as feedback. Check IRIs, predicates, direction, filters, and language tags, then make at most one corrected query. Do not retry an empty result when it plausibly means there are no matches.

- Use only schema and sparql for graph facts.
- Submit only read-only SELECT, ASK, CONSTRUCT, or DESCRIBE queries. Never use SPARQL Update or SERVICE.
- Include sensible LIMITs on exploratory and listing queries when this does not alter the requested aggregate.
- Base factual claims strictly on tool output. Say when no matching data was found; do not invent missing facts.
- Explain tool validation, timeout, endpoint, or size errors when they remain after the one correction.
- Summarize successful output concisely.
""".strip()


def system_instruction(settings: Settings) -> str:
    """Build the agent instruction with explicit connection context."""
    endpoint_kind = "local RDF directory" if settings.is_local else "remote HTTP SPARQL endpoint"
    endpoint_context = (
        f"Configured graph connection: {settings.sparql_endpoint!r} ({endpoint_kind}). "
        "This is the endpoint used by the graph tools; do not attempt to access it except through schema and sparql."
    )
    instruction = f"{settings.system_prompt or DEFAULT_INSTRUCTION}\n\n{endpoint_context}"
    if settings.extra_instructions:
        instruction = f"{instruction}\n\nAdditional operator instructions:\n{settings.extra_instructions}"
    return instruction


def create_agent(settings: Settings | None = None, tools: list[BaseTool] | None = None) -> LlmAgent:
    active = settings or Settings.from_env()
    model_args = {"model": active.model}
    if active.api_key:
        model_args["api_key"] = active.api_key
    return LlmAgent(name="sparql_query_agent", description="Runs read-only SPARQL and summarizes RDF graph results.", model=LiteLlm(**model_args), instruction=system_instruction(active), tools=tools or create_tools(active), after_tool_callback=save_query_artifact)


root_agent = create_agent()
