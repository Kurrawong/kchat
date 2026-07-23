"""Keep complete query results in ADK artifacts, not model context."""

from __future__ import annotations

import json
from typing import Any

from google.adk.agents.context import Context
from google.adk.tools import BaseTool
from google.genai import types


async def save_query_artifact(tool: BaseTool, args: dict[str, Any], tool_context: Context, tool_response: dict[str, Any]) -> dict[str, Any] | None:
    if tool.name != "sparql":
        return None
    wrapped = isinstance(tool_response.get("structuredContent"), dict)
    result = tool_response["structuredContent"] if wrapped else tool_response
    if not result.get("ok") or not isinstance(result.get("payload"), str):
        return None
    media_type = result.get("media_type")
    extension = "json" if media_type == "application/sparql-results+json" else "ttl"
    result_filename = f"sparql-results.{extension}"
    query_filename = "sparql-query.rq"
    query = str(args.get("query") or "")

    query_version = await tool_context.save_artifact(
        query_filename,
        types.Part.from_bytes(data=query.encode(), mime_type="application/sparql-query"),
        custom_metadata={"query_form": result.get("query_form")},
    )
    result_version = await tool_context.save_artifact(
        result_filename,
        types.Part.from_bytes(data=result["payload"].encode(), mime_type=media_type),
        custom_metadata={"query": query, "query_form": result.get("query_form"), "payload_bytes": result.get("payload_bytes")},
    )
    artifacts = [
        {"filename": query_filename, "version": query_version, "kind": "query"},
        {"filename": result_filename, "version": result_version, "kind": "result"},
    ]
    model_result = {key: value for key, value in result.items() if key != "payload"}
    model_result["artifacts"] = artifacts
    # Retain the singular field for clients that only understand the result artifact.
    model_result["artifact"] = artifacts[1]
    if not wrapped:
        return model_result
    response = dict(tool_response)
    response["structuredContent"] = model_result
    response["content"] = [{"type": "text", "text": json.dumps(model_result, indent=2)}]
    return response
