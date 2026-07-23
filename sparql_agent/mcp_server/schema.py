"""Cached empirical schema discovery."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from typing import Any
from urllib.parse import urlsplit

from sparql_agent.mcp_server.query import QueryService

PREFIXES = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX schema: <https://schema.org/>
"""

SCHEMA_QUERIES = {
    "classes": PREFIXES + """SELECT ?class (SAMPLE(?candidateLabel) AS ?label) (COUNT(DISTINCT ?instance) AS ?count)
WHERE { ?instance rdf:type ?class . OPTIONAL { ?class (rdfs:label|skos:prefLabel|schema:name) ?candidateLabel . FILTER(LANG(?candidateLabel) = "" || LANGMATCHES(LANG(?candidateLabel), "en")) } }
GROUP BY ?class ORDER BY DESC(?count) ?class""",
    "predicates": PREFIXES + """SELECT ?class ?predicate ?kind ?datatype (COUNT(*) AS ?count)
WHERE { ?instance rdf:type ?class ; ?predicate ?value . FILTER(?predicate != rdf:type) BIND(IF(ISLITERAL(?value), "literal", "resource") AS ?kind) BIND(IF(ISLITERAL(?value), STR(DATATYPE(?value)), "") AS ?datatype) }
GROUP BY ?class ?predicate ?kind ?datatype ORDER BY ?class ?predicate""",
    "connections": PREFIXES + """SELECT ?source ?predicate ?target (COUNT(*) AS ?count)
WHERE { ?subject rdf:type ?source ; ?predicate ?object . ?object rdf:type ?target . FILTER(?predicate != rdf:type) }
GROUP BY ?source ?predicate ?target ORDER BY DESC(?count) ?source ?predicate ?target""",
}


def _rows(envelope: dict[str, Any]) -> list[dict[str, str]]:
    result = json.loads(envelope["payload"])
    return [{key: item.get("value", "") for key, item in binding.items()} for binding in result.get("results", {}).get("bindings", [])]


def _short(iri: str) -> str:
    split = urlsplit(iri)
    return split.fragment or split.path.rstrip("/").rsplit("/", 1)[-1] or iri


def assemble_schema(rows: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    classes: dict[str, dict[str, Any]] = {}
    for row in rows["classes"]:
        iri = row["class"]
        classes[iri] = {"class": iri, "label": row.get("label") or _short(iri), "instance_count": int(row["count"]), "predicates": []}
    for row in rows["predicates"]:
        if row["class"] not in classes:
            continue
        item: dict[str, Any] = {"predicate": row["predicate"], "object_kind": row["kind"], "statement_count": int(row["count"])}
        if row["kind"] == "literal":
            item["datatype"] = row.get("datatype") or None
        classes[row["class"]]["predicates"].append(item)
    connections = [{"source_class": row["source"], "predicate": row["predicate"], "target_class": row["target"], "statement_count": int(row["count"])} for row in rows["connections"] if row["source"] in classes and row["target"] in classes]
    ordered = sorted(classes.values(), key=lambda value: (-value["instance_count"], value["class"]))
    connections.sort(key=lambda value: (-value["statement_count"], value["source_class"], value["predicate"], value["target_class"]))
    leading_classes = ", ".join(f'{item["label"]} ({item["instance_count"]})' for item in ordered[:5]) or "none"
    leading_connections = "; ".join(f'{_short(item["source_class"])} --{_short(item["predicate"])}--> {_short(item["target_class"])} ({item["statement_count"]})' for item in connections[:5]) or "none observed"
    return {"description": "Observed data shape and counts, not ontology constraints.", "summary": f"Observed {len(ordered)} classes. Largest classes: {leading_classes}. Strongest connections: {leading_connections}.", "classes": ordered, "connections": connections}


@dataclass(slots=True)
class SchemaService:
    query_service: QueryService
    _cache: dict[str, Any] | None = field(default=None, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def get_schema(self) -> dict[str, Any]:
        if self._cache is None:
            async with self._lock:
                if self._cache is None:
                    rows = {name: _rows(await self.query_service.execute(query)) for name, query in SCHEMA_QUERIES.items()}
                    self._cache = assemble_schema(rows)
        return self._cache
