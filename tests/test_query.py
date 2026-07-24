from pathlib import Path
from types import SimpleNamespace

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from sparql_agent.artifacts import save_query_artifact
from sparql_agent.config import Settings
from sparql_agent.mcp_server.query import QueryService, QueryValidationError, classify_query
from sparql_agent.mcp_server.schema import SchemaService
from sparql_agent.mcp_server.server import create_server


def test_only_read_queries_are_accepted():
    assert classify_query("ASK { ?s ?p ?o }") == "ASK"
    assert classify_query("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }") == "CONSTRUCT"
    with pytest.raises(QueryValidationError):
        classify_query("INSERT DATA { <urn:s> <urn:p> <urn:o> }")
    with pytest.raises(QueryValidationError):
        classify_query("SELECT * WHERE { SERVICE <https://example.org/sparql> { ?s ?p ?o } }")


@pytest.mark.asyncio
async def test_demo_query_and_cached_schema():
    settings = Settings(sparql_endpoint=str((Path(__file__).parents[1] / "demo").resolve()))
    queries = QueryService(settings)
    result = await queries.execute("SELECT ?book WHERE { ?book a <https://schema.org/Book> } ORDER BY ?book")
    assert result["metadata"]["row_count"] == 2

    schemas = SchemaService(queries)
    first = await schemas.get_schema()
    second = await schemas.get_schema()
    assert first is second
    assert {item["class"] for item in first["classes"]} == {"https://schema.org/Book", "https://schema.org/Person"}
    assert first["connections"][0]["predicate"] == "https://schema.org/author"

    candidates = await schemas.search("Ursula")
    assert candidates["entities"] == [
        {"iri": "https://example.org/ursula", "label": "Ursula K. Le Guin", "type": "https://schema.org/Person"}
    ]
    relation_candidates = await schemas.search("author")
    assert relation_candidates["predicates"] == [
        {"iri": "https://schema.org/author", "label": "author"}
    ]


@pytest.mark.asyncio
async def test_schema_search_validates_and_safely_bounds_input():
    class RecordingQueryService:
        def __init__(self):
            self.queries = []

        async def execute(self, query):
            assert classify_query(query) == "SELECT"
            self.queries.append(query)
            return {"payload": '{"head": {"vars": []}, "results": {"bindings": []}}'}

    queries = RecordingQueryService()
    schemas = SchemaService(queries)
    result = await schemas.search('quote " and newline\n', limit=100)

    assert result["entities"] == []
    assert result["predicates"] == []
    assert len(queries.queries) == 2
    assert all(query.endswith("LIMIT 20") for query in queries.queries)
    with pytest.raises(ValueError, match="must not be empty"):
        await schemas.search("  ")


@pytest.mark.asyncio
async def test_mcp_exposes_search_without_adding_another_tool():
    settings = Settings(sparql_endpoint=str((Path(__file__).parents[1] / "demo").resolve()))
    server = create_server(settings)
    tools = {tool.name: tool for tool in server._tool_manager.list_tools()}

    assert set(tools) == {"schema", "sparql"}
    assert set(tools["schema"].parameters["properties"]) == {"search", "limit"}

    shape = await tools["schema"].fn()
    assert {item["label"] for item in shape["classes"]} == {"Book", "Person"}
    candidates = await tools["schema"].fn(search="Earthsea", limit=1)
    assert candidates["entities"][0]["iri"] == "https://example.org/book-2"
    with pytest.raises(ToolError, match="Search text must not be empty"):
        await tools["schema"].fn(search=" ")

    answer = await tools["sparql"].fn(query="ASK { ?s ?p ?o }")
    assert answer["preview"] == {"boolean": True}
    with pytest.raises(ToolError, match="read-only SPARQL query"):
        await tools["sparql"].fn(query="DELETE WHERE { ?s ?p ?o }")


@pytest.mark.asyncio
async def test_successful_query_saves_query_and_result_artifacts():
    class ArtifactContext:
        def __init__(self):
            self.saved = []

        async def save_artifact(self, filename, part, custom_metadata=None):
            self.saved.append((filename, part, custom_metadata))
            return len(self.saved) - 1

    context = ArtifactContext()
    response = {
        "ok": True,
        "query_form": "SELECT",
        "media_type": "application/sparql-results+json",
        "payload": '{"head": {}, "results": {"bindings": []}}',
        "payload_bytes": 43,
    }
    result = await save_query_artifact(
        SimpleNamespace(name="sparql"),
        {"query": "SELECT * WHERE { ?s ?p ?o }"},
        context,
        response,
    )

    assert [item[0] for item in context.saved] == ["sparql-query.rq", "sparql-results.json"]
    assert result["artifacts"] == [
        {"filename": "sparql-query.rq", "version": 0, "kind": "query"},
        {"filename": "sparql-results.json", "version": 1, "kind": "result"},
    ]
    assert "payload" not in result
