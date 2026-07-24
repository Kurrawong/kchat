"""Read-only SPARQL validation and local/remote execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import httpx
from pyoxigraph import QueryBoolean, QueryResultsFormat, QuerySolutions, QueryTriples, RdfFormat, Store
from pyparsing import ParseBaseException, ParseResults
from rdflib import Dataset, Graph
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue

from sparql_agent.config import Settings

QUERY_FORMS = {"SelectQuery": "SELECT", "AskQuery": "ASK", "ConstructQuery": "CONSTRUCT", "DescribeQuery": "DESCRIBE"}
RESULTS_MEDIA_TYPE = "application/sparql-results+json"
RDF_MEDIA_TYPE = "text/turtle"
RDF_SUFFIXES = {".ttl": "turtle", ".nt": "nt", ".rdf": "xml", ".xml": "xml", ".jsonld": "json-ld", ".json": "json-ld", ".n3": "n3"}
DATASET_SUFFIXES = {".trig": "trig", ".nq": "nquads"}


class SparqlError(RuntimeError):
    pass


class QueryValidationError(SparqlError):
    pass


class EndpointError(SparqlError):
    pass


class ResponseTooLargeError(EndpointError):
    pass


def _contains(value: Any, name: str) -> bool:
    if isinstance(value, CompValue):
        return value.name == name or any(_contains(item, name) for item in value.values())
    if isinstance(value, (ParseResults, list, tuple, dict)):
        values = value.values() if isinstance(value, dict) else value
        return any(_contains(item, name) for item in values)
    return False


def classify_query(query: str) -> str:
    if not query.strip():
        raise QueryValidationError("SPARQL query must not be empty")
    try:
        operation = parseQuery(query)[1]
    except (ParseBaseException, TypeError, ValueError) as error:
        raise QueryValidationError("Input is not a valid read-only SPARQL query") from error
    form = QUERY_FORMS.get(getattr(operation, "name", ""))
    if form is None:
        raise QueryValidationError("Only SELECT, ASK, CONSTRUCT, and DESCRIBE are allowed; SPARQL Update is disabled")
    if _contains(operation, "ServiceGraphPattern"):
        raise QueryValidationError("Federated SERVICE clauses are not allowed")
    return form


def load_store(directory: str) -> Store:
    """Parse mounted RDF with RDFLib and load normalized RDF into Oxigraph."""
    root = Path(directory)
    if not root.is_dir():
        raise EndpointError(f"Local RDF path is not a directory: {root}")
    store = Store()
    files = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        suffix = path.suffix.lower()
        try:
            if suffix in DATASET_SUFFIXES:
                graph = Dataset()
                graph.parse(path, format=DATASET_SUFFIXES[suffix], publicID=path.as_uri())
                store.load(graph.serialize(format="nquads"), format=RdfFormat.N_QUADS)
            elif suffix in RDF_SUFFIXES:
                graph = Graph()
                graph.parse(path, format=RDF_SUFFIXES[suffix], publicID=path.as_uri())
                store.load(graph.serialize(format="nt"), format=RdfFormat.N_TRIPLES)
            else:
                continue
        except Exception as error:
            raise EndpointError(f"Could not load RDF file {path}: {error}") from error
        files += 1
    if not files:
        raise EndpointError(f"No supported RDF files found under {root}")
    return store


@dataclass(slots=True)
class QueryService:
    settings: Settings
    client: httpx.AsyncClient | None = None
    _store: Store | None = field(default=None, init=False)
    _store_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def execute(self, query: str) -> dict[str, Any]:
        form = classify_query(query)
        media_type = RESULTS_MEDIA_TYPE if form in {"SELECT", "ASK"} else RDF_MEDIA_TYPE
        payload = await (self._local_request(query, form) if self.settings.is_local else self._remote_request(query, media_type))
        if len(payload) > self.settings.max_response_bytes:
            raise ResponseTooLargeError(f"SPARQL response exceeds the configured maximum of {self.settings.max_response_bytes} bytes")
        return build_result_envelope(form, media_type, payload, self.settings.preview_items)

    async def _get_store(self) -> Store:
        if self._store is None:
            async with self._store_lock:
                if self._store is None:
                    self._store = await asyncio.to_thread(load_store, self.settings.sparql_endpoint)
        return self._store

    async def _local_request(self, query: str, form: str) -> bytes:
        store = await self._get_store()
        def run() -> bytes:
            result = store.query(query, use_default_graph_as_union=True)
            if isinstance(result, (bool, QueryBoolean)):
                return json.dumps({"head": {}, "boolean": bool(result)}).encode()
            if isinstance(result, QuerySolutions):
                return bytes(result.serialize(format=QueryResultsFormat.JSON))
            if isinstance(result, QueryTriples):
                return bytes(result.serialize(format=RdfFormat.TURTLE))
            raise EndpointError(f"Unexpected Oxigraph result for {form}")
        try:
            return await asyncio.wait_for(asyncio.to_thread(run), self.settings.timeout_seconds)
        except TimeoutError as error:
            raise EndpointError(f"Local query timed out after {self.settings.timeout_seconds:g} seconds") from error
        except SparqlError:
            raise
        except Exception as error:
            raise EndpointError(f"Oxigraph could not execute query: {error}") from error

    async def _remote_request(self, query: str, media_type: str) -> bytes:
        owns_client = self.client is None
        auth = None
        headers = {"accept": media_type, "content-type": "application/sparql-query"}
        if self.settings.sparql_bearer_token:
            headers["authorization"] = f"Bearer {self.settings.sparql_bearer_token}"
        elif self.settings.sparql_username:
            auth = (self.settings.sparql_username, self.settings.sparql_password or "")
        client = self.client or httpx.AsyncClient(timeout=self.settings.timeout_seconds, auth=auth)
        try:
            async with client.stream("POST", self.settings.sparql_endpoint, content=query.encode(), headers=headers) as response:
                response.raise_for_status()
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > self.settings.max_response_bytes:
                        raise ResponseTooLargeError(f"SPARQL response exceeds the configured maximum of {self.settings.max_response_bytes} bytes")
                    chunks.append(chunk)
                return b"".join(chunks)
        except ResponseTooLargeError:
            raise
        except httpx.TimeoutException as error:
            raise EndpointError(f"SPARQL endpoint timed out after {self.settings.timeout_seconds:g} seconds") from error
        except httpx.HTTPStatusError as error:
            detail = (await error.response.aread()).decode(errors="replace")[:500]
            raise EndpointError(f"SPARQL endpoint returned HTTP {error.response.status_code}: {detail}") from error
        except httpx.HTTPError as error:
            raise EndpointError(f"Could not query SPARQL endpoint: {error}") from error
        finally:
            if owns_client:
                await client.aclose()


def build_result_envelope(form: str, media_type: str, payload: bytes, preview_items: int) -> dict[str, Any]:
    text = payload.decode("utf-8")
    if form in {"SELECT", "ASK"}:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as error:
            raise EndpointError("Endpoint returned invalid SPARQL Results JSON") from error
        if form == "ASK":
            value = bool(parsed.get("boolean")); preview = {"boolean": value}; metadata = {"boolean": value}; truncated = False
        else:
            variables = parsed.get("head", {}).get("vars", [])
            bindings = parsed.get("results", {}).get("bindings", [])
            preview = {"variables": variables, "bindings": bindings[:preview_items]}
            metadata = {"variables": variables, "row_count": len(bindings)}
            truncated = len(bindings) > preview_items
    else:
        graph = Graph()
        try:
            graph.parse(data=text, format="turtle")
        except Exception as error:
            raise EndpointError("Endpoint returned invalid Turtle RDF") from error
        triples = sorted(({"subject": s.n3(), "predicate": p.n3(), "object": o.n3()} for s, p, o in graph), key=lambda x: (x["subject"], x["predicate"], x["object"]))
        preview = {"triples": triples[:preview_items]}; metadata = {"triple_count": len(triples)}; truncated = len(triples) > preview_items
    return {"ok": True, "query_form": form, "media_type": media_type, "metadata": metadata, "preview": preview, "preview_truncated": truncated, "payload": text, "payload_bytes": len(payload)}
