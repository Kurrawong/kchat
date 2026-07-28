# kchat: natural-language chat for SPARQL

kchat is a bolt-on SPARQL agent. Point it at any SPARQL endpoint to add natural-language search and chat without changing the endpoint or the data behind it. People can ask questions in plain English, and kchat explores the graph, writes a read-only SPARQL query, runs it, and explains the results.

It runs as a single container with a ready-to-use web chat and an API for connecting your own application, interface, or embedded widget. It can also load local RDF files, so you can try it without running a separate SPARQL service.

The agent uses two focused tools:

- `schema` learns how the graph is structured and matches names in a question to classes, properties, and resources in the data.
- `sparql` runs safe, read-only `SELECT`, `ASK`, `CONSTRUCT`, and `DESCRIBE` queries. It blocks updates and federated `SERVICE` queries.

Every generated query and its complete result are saved as downloadable artifacts, while the chat response gives a readable summary. If a query fails or returns nothing, the agent can inspect the feedback and try one correction.

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

Open `http://localhost:8000/` for the bundled kchat UI or `http://localhost:8000/docs` for interactive API documentation.

The bottom-right chat widget renders Markdown, reports input/output/context token usage, and shows the executed SPARQL query and returned JSON or Turtle result as inline pills. Click a pill to inspect or download its complete contents in a movable window.

## How it fits into an application

kchat is a standalone backend service with an optional interface. The service manages conversations, runs the SPARQL agent, streams responses, and stores the generated queries and results. Applications communicate with it over HTTP, so they do not need to include the agent code or connect to its internal tools.

The bundled chat widget is a working example rather than a required part of the service. It can be replaced with a full-page application, embedded widget, command-line client, or another service. A custom client follows the same basic flow:

1. create or resume a conversation;
2. submit a message and render the streamed response;
3. read usage information if token reporting is useful; and
4. list and retrieve query and result artifacts for inspection or download.

The app name is `sparql_agent`. Custom clients use this name when creating sessions and submitting runs through the session, `/run` or `/run_sse`, and artifact routes.

### Runtime configuration for custom interfaces

`GET /kchat-config` is the small piece of server-side integration provided for chat interfaces. It gives a browser or other client non-secret, display-ready information about the running kchat instance:

```json
{
  "model": "mistral/mistral-small-latest",
  "contextWindowTokens": 128000,
  "sparqlEndpoint": "https://example.com/sparql",
  "sparqlEndpointType": "Remote SPARQL endpoint"
}
```

- `model` identifies the configured language model.
- `contextWindowTokens` is the configured or detected context limit and may be `null` when it is unknown.
- `sparqlEndpoint` identifies the graph being queried.
- `sparqlEndpointType` is either `Remote SPARQL endpoint` or `Local RDF directory`.

This lets a reusable widget discover what it is connected to instead of hard-coding deployment details. The bundled interface uses it to show the endpoint and calculate context-window usage. It deliberately excludes API keys, graph credentials, and the system prompt. Custom widgets can consume the same route even when the bundled interface is not used.

The only other web integration is serving the bundled static interface at `/`. API and documentation routes take precedence, so mounting the example interface does not hide them. See [`sparql_agent/web.py`](sparql_agent/web.py) for the configuration route and static mount, and [`sparql_agent/ui/app.js`](sparql_agent/ui/app.js) for a complete browser client example.

## Technology stack

- **Agent and API:** Google Agent Development Kit (ADK) for conversations, streaming runs, usage metadata, and artifacts.
- **Web server:** Python and FastAPI.
- **Model access:** LiteLLM, allowing kchat to use supported models from different providers.
- **Graph tools:** native in-process ADK function tools for schema discovery and read-only querying.
- **Local RDF:** RDFLib for parsing and Oxigraph for the in-memory graph store.
- **Demo interface:** plain HTML, CSS, and JavaScript with no frontend framework.
- **Deployment:** a single Docker image; uv and Docker Compose are included in the development workflow.

## Docker Compose development

Put configuration in `.env` (Compose reads it automatically), then build and run:

```bash
docker compose up --build
```

For live development, use Compose Watch:

```bash
docker compose watch
```

Changes under `sparql_agent/` are synchronized into the running container and reloaded automatically. Demo RDF changes restart the service so the in-memory store is rebuilt; dependency or Dockerfile changes rebuild the image.

## Use mounted RDF

```bash
docker run --rm -p 8000:8000 \
  -v "$PWD/rdf:/rdf:ro" \
  -e SPARQL_ENDPOINT=/rdf \
  -e LLM_MODEL=anthropic/claude-sonnet-4-5 \
  -e LLM_API_KEY="$ANTHROPIC_API_KEY" \
  ghcr.io/kurrawong/kchat:latest
```

The directory is searched recursively for Turtle, N-Triples, RDF/XML, JSON-LD, N3, TriG, and N-Quads, then loaded into an in-memory graph. If `SPARQL_ENDPOINT` is omitted, the included `/demo` graph is used.

## Use a remote endpoint

Set `SPARQL_ENDPOINT` to an HTTP(S) query endpoint. Basic authentication uses `SPARQL_USERNAME` and `SPARQL_PASSWORD`; bearer authentication uses `SPARQL_BEARER_TOKEN` and takes precedence.

See [`environment.example`](environment.example) for all settings. `SYSTEM_PROMPT`, when set, replaces the built-in instruction. LiteLLM model identifiers are accepted in `LLM_MODEL`; `LLM_API_KEY` is passed directly to LiteLLM.

## Persist sessions

By default, kchat preserves the existing ADK behavior: sessions use ADK's local per-agent SQLite storage. This survives process restarts when the application directory is persistent, but container filesystem contents are lost when a container is replaced.

Set `SESSION_DATABASE_URL` to use ADK's database session service instead. kchat includes async drivers and validates connection strings for these schemes:

- `sqlite:////data/kchat-sessions.db` or `sqlite+aiosqlite:////data/kchat-sessions.db`
- `postgresql+asyncpg://user:password@database.example/kchat`
- `mysql+aiomysql://user:password@database.example/kchat`

For file-based SQLite in a container, mount the database's parent directory on persistent storage:

```bash
docker run --rm -p 8000:8000 \
  -v kchat-data:/data \
  -e SESSION_DATABASE_URL=sqlite:////data/kchat-sessions.db \
  -e LLM_API_KEY="$MISTRAL_API_KEY" \
  ghcr.io/kurrawong/kchat:latest
```

For multi-instance deployments, use PostgreSQL or MySQL rather than SQLite. The database account must be able to create and update ADK's session tables. Keep the connection string server-side because it commonly contains credentials; it is not returned by `/kchat-config`. This setting changes conversation/session storage only—query artifacts continue to use ADK's local artifact storage.

## Research attribution

The agent workflow is an independent, lightweight adaptation of ideas from Perevalov and Both's mKGQAgent paper. No mKGQAgent software is included or used. See [`NOTICE.md`](NOTICE.md) for the full citation and scope of the attribution.

## Local development

```bash
cp environment.example .env  # edit values
uv sync
uv run uvicorn sparql_agent.web:app --host 0.0.0.0 --port 8000 --reload --env-file .env
```
