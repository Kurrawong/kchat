# Generic SPARQL ADK agent

A single container combining a Google ADK agent and a stdio MCP server. The agent has exactly two graph tools:

- `schema`: discovers and caches observed classes, predicates, datatypes, counts, and connections; optional label search resolves entities and relations to observed IRIs.
- `sparql`: executes validated read-only `SELECT`, `ASK`, `CONSTRUCT`, and `DESCRIBE` queries. Updates and federated `SERVICE` are rejected.

Results are summarized from a bounded preview; each executed SPARQL query and its complete accepted JSON or Turtle result are saved as ADK artifacts. The agent uses a compact plan–link–query workflow inspired by mKGQAgent: it resolves mentioned labels before composing SPARQL and may make one feedback-driven correction after an error or unexpectedly empty result. This keeps the quality benefits without a multi-agent pipeline or vector database.

## Run the demo

The published image is available from the [GitHub Container Registry](https://github.com/Kurrawong/kchat/pkgs/container/kchat).

```bash
docker pull ghcr.io/kurrawong/kchat:latest
docker run --rm -p 8000:8000 \
  -e LLM_MODEL=mistral/mistral-small-latest \
  -e LLM_API_KEY="$MISTRAL_API_KEY" \
  ghcr.io/kurrawong/kchat:latest
```

Open `http://localhost:8000/` for the bundled kchat UI or `http://localhost:8000/docs` for the ADK API. Standard ADK `/list-apps`, `/run`, and `/run_sse` routes remain available. The ADK app name is `sparql_agent`.

The bottom-right chat widget renders Markdown, reports input/output/context token usage, and shows the executed SPARQL query and returned JSON or Turtle result as inline pills. Click a pill to inspect or download its complete contents in a movable window.

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
