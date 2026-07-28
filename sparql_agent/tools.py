"""Native Google ADK tools for RDF schema discovery and querying."""

from __future__ import annotations

from typing import Any

from google.adk.tools import FunctionTool

from sparql_agent.config import Settings
from sparql_agent.query import QueryService, SparqlError
from sparql_agent.schema import SchemaService


def create_tools(settings: Settings) -> list[FunctionTool]:
    """Create two in-process ADK function tools sharing query and schema state."""
    queries = QueryService(settings)
    schemas = SchemaService(queries)

    async def schema(search: str | None = None, limit: int = 8) -> dict[str, Any]:
        """Inspect the observed RDF graph.

        With no search text, return cached classes, predicates, datatypes, counts,
        and connections. With search text, link an entity or relation label to
        observed IRI candidates.
        """
        try:
            return await schemas.search(search, limit) if search is not None else await schemas.get_schema()
        except (SparqlError, ValueError) as error:
            return {"error": f"Could not inspect graph schema: {error}"}

    async def sparql(query: str) -> dict[str, Any]:
        """Execute one read-only SELECT, ASK, CONSTRUCT, or DESCRIBE query.

        SPARQL Update and SERVICE are rejected.
        """
        try:
            return await queries.execute(query)
        except SparqlError as error:
            return {"error": str(error)}

    return [FunctionTool(schema), FunctionTool(sparql)]
