"""MCP server exposing exactly two RDF tools."""

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from sparql_agent.config import Settings
from sparql_agent.mcp_server.query import QueryService, SparqlError
from sparql_agent.mcp_server.schema import SchemaService


def create_server(settings: Settings | None = None) -> FastMCP:
    active = settings or Settings.from_env()
    queries = QueryService(active)
    schemas = SchemaService(queries)
    server = FastMCP("Generic read-only SPARQL", instructions="Inspect the observed graph with schema, then query it with read-only SPARQL.")

    @server.tool(name="schema", description="Inspect the observed RDF graph. With no search text, return cached classes, predicates, datatypes, counts, and connections. With search text, link an entity or relation label to observed IRI candidates.")
    async def schema_tool(search: str | None = None, limit: int = 8) -> dict[str, Any]:
        try:
            return await schemas.search(search, limit) if search is not None else await schemas.get_schema()
        except (SparqlError, ValueError) as error:
            raise ToolError(f"Could not inspect graph schema: {error}") from error

    @server.tool(name="sparql", description="Execute one read-only SELECT, ASK, CONSTRUCT, or DESCRIBE query. SPARQL Update and SERVICE are rejected.")
    async def sparql_tool(query: str) -> dict[str, Any]:
        try:
            return await queries.execute(query)
        except SparqlError as error:
            raise ToolError(str(error)) from error

    return server


mcp = create_server()
