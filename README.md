# Generic SPARQL ADK agent

kchat is an API-first example of serving a Google Agent Development Kit (ADK) agent and building a custom chat experience on top of the standard ADK API. Its primary purpose is to provide a reusable SPARQL agent service that can be called by the bundled web client, another application, or any custom interface that implements the ADK session and run flow.

The single container combines the ADK API application, a Google ADK agent, and a stdio MCP server. The agent has exactly two graph tools:

- `schema`: discovers and caches observed classes, predicates, datatypes, counts, and connections; optional label search resolves entities and relations to observed IRIs.
- `sparql`: executes validated read-only `SELECT`, `ASK`, `CONSTRUCT`, and `DESCRIBE` queries. Updates and federated `SERVICE` are rejected.

Results are summarized from a bounded preview; each executed SPARQL query and its complete accepted JSON or Turtle result are saved as ADK artifacts. The agent uses a compact plan–link–query workflow inspired by mKGQAgent: it resolves mentioned labels before composing SPARQL and may make one feedback-driven correction after an error or unexpectedly empty result. This keeps the quality benefits without a multi-agent pipeline or vector database.

## Purpose and architecture

The ADK API is the core application boundary. kchat starts ADK's FastAPI application with its normal session, execution, artifact, app-discovery, and OpenAPI routes intact. This makes the agent usable as a backend independently of the included interface; clients are not required to import the Python agent package or communicate with the MCP server directly.

The bundled interface is a reference implementation of a custom ADK client. It is plain HTML, CSS, and JavaScript mounted at `/` after the ADK routes so it does not replace or hide them. The browser:

1. creates or resumes a conversation through the ADK session endpoint;
2. sends messages to `/run_sse` and renders streamed response events;
3. reads ADK usage metadata to display input, output, and context-window token usage;
4. lists and retrieves ADK artifacts to expose the exact SPARQL and complete query result; and
5. reads non-secret model and graph information from the small `/kchat-config` endpoint.

This separation is intentional: the SPARQL agent and its artifacts form the reusable service, while the chat widget demonstrates how a product-specific interface can be layered over ADK. The UI can be replaced by a full-page application, embedded widget, command-line client, or another service while retaining the same agent API and behavior.

## Screenshots

### Ask questions in natural language

![kchat answering a natural-language question about an RDF graph](docs/images/kchat-query.png)

### Inspect the generated SPARQL

![kchat's artifact viewer showing the generated SPARQL query](docs/images/kchat-artifact.png)

## Run the demo

The published image is available from the [GitHub Container Registry](https://github.com/Kurrawong/kchat/pkgs/container/kchat).

```bash
docker pull ghcr.io/kurrawong/kchat:latest
docker run --rm -p 8000:8000 \
  -e LLM_MODEL=mistral/mistral-small-latest \
  -e LLM_API_KEY="$MISTRAL_API_KEY" \
  ghcr.io/kurrawong/kchat:latest
```

Open `http://localhost:8000/` for the bundled kchat UI or `http://localhost:8000/docs` for the interactive ADK API documentation. Standard ADK `/list-apps`, `/run`, `/run_sse`, session, and artifact routes remain available. The ADK app name is `sparql_agent`; custom clients must use that name when creating sessions and submitting runs.

The bottom-right chat widget renders Markdown, reports input/output/context token usage, and shows the executed SPARQL query and returned JSON or Turtle result as inline pills. Click a pill to inspect or download its complete contents in a movable window. Browser client behavior is implemented in [`sparql_agent/ui/app.js`](sparql_agent/ui/app.js), and the small amount of server-side integration is in [`sparql_agent/web.py`](sparql_agent/web.py).

## Docker Compose development

Put configuration in `.env` (Compose reads it automatically), then build and run:

```bash
docker compose up --build
```

For live development, use Compose Watch:

```bash
docker compose watch
```

Changes under `sparql_agent/` are synchronized into the running container and reloaded by ADK. Demo RDF changes restart the service so the in-memory store is rebuilt; dependency or Dockerfile changes rebuild the image.

## Use mounted RDF

```bash
docker run --rm -p 8000:8000 \
  -v "$PWD/rdf:/rdf:ro" \
  -e SPARQL_ENDPOINT=/rdf \
  -e LLM_MODEL=anthropic/claude-sonnet-4-5 \
  -e LLM_API_KEY="$ANTHROPIC_API_KEY" \
  ghcr.io/kurrawong/kchat:latest
```

The directory is searched recursively for Turtle, N-Triples, RDF/XML, JSON-LD, N3, TriG, and N-Quads. RDFLib parses and normalizes the files into a process-local, in-memory Oxigraph store. If `SPARQL_ENDPOINT` is omitted, the included `/demo` graph is used.

## Use a remote endpoint

Set `SPARQL_ENDPOINT` to an HTTP(S) query endpoint. Basic authentication uses `SPARQL_USERNAME` and `SPARQL_PASSWORD`; bearer authentication uses `SPARQL_BEARER_TOKEN` and takes precedence.

See [`environment.example`](environment.example) for all settings. `SYSTEM_PROMPT`, when set, replaces the built-in instruction. LiteLLM model identifiers are accepted in `LLM_MODEL`; `LLM_API_KEY` is passed directly to LiteLLM.

## Research attribution

The agent workflow is an independent, lightweight adaptation of ideas from Perevalov and Both's mKGQAgent paper. No mKGQAgent software is included or used. See [`NOTICE.md`](NOTICE.md) for the full citation and scope of the attribution.

## Local development

```bash
cp environment.example .env  # edit values
uv sync
uv run uvicorn sparql_agent.web:app --host 0.0.0.0 --port 8000 --reload --env-file .env
```
