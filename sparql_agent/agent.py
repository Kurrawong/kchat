"""Google ADK agent for natural-language RDF graph exploration."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

from sparql_agent.artifacts import save_query_artifact
from sparql_agent.config import Settings

DEFAULT_INSTRUCTION = """
Answer user questions by querying the configured RDF graph and summarizing the results.

- Use only schema and sparql for graph facts. Call schema before querying whenever the relevant data shape is not already known.
- Submit only read-only SELECT, ASK, CONSTRUCT, or DESCRIBE queries. Never use SPARQL Update or SERVICE.
- Include sensible LIMITs on exploratory and listing queries when this does not alter the requested aggregate.
- Base factual claims strictly on tool output. Say when no matching data was found; do not invent missing facts.
- Explain tool validation, timeout, endpoint, or size errors. You may retry with a safer, narrower query.
- Summarize successful output concisely. Mention that the executed query and complete result are attached as artifacts, and mention if the preview is truncated.
""".strip()


def create_toolset() -> McpToolset:
    project_root = Path(__file__).resolve().parent.parent
    return McpToolset(connection_params=StdioConnectionParams(server_params=StdioServerParameters(command=sys.executable, args=["-m", "sparql_agent.mcp_server"], cwd=project_root, env=dict(os.environ)), timeout=30), tool_filter=["schema", "sparql"])


def create_agent(settings: Settings | None = None, toolset=None) -> LlmAgent:
    active = settings or Settings.from_env()
    model_args = {"model": active.model}
    if active.api_key:
        model_args["api_key"] = active.api_key
    return LlmAgent(name="sparql_query_agent", description="Runs read-only SPARQL and summarizes RDF graph results.", model=LiteLlm(**model_args), instruction=active.system_prompt or DEFAULT_INSTRUCTION, tools=[toolset or create_toolset()], after_tool_callback=save_query_artifact)


root_agent = create_agent()
