from pathlib import Path
from types import SimpleNamespace

import pytest

from sparql_agent.artifacts import save_query_artifact
from sparql_agent.config import Settings
from sparql_agent.mcp_server.query import QueryService, QueryValidationError, classify_query
from sparql_agent.mcp_server.schema import SchemaService


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
