FROM python:3.14.6-alpine AS dependencies

WORKDIR /app
COPY pyproject.toml ./

# LiteLLM does not publish a musl wheel, so compile it in a disposable stage.
RUN apk add --no-cache build-base cargo \
    && python -c 'import subprocess, sys, tomllib; dependencies = tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]; subprocess.check_call([sys.executable, "-m", "pip", "install", "--prefix=/install", "--no-cache-dir", "--no-compile", *dependencies])' \
    && site_packages="$(find /install/lib -type d -name site-packages -print -quit)" \
    && find "$site_packages" -type d \( -name __pycache__ -o -name tests \) -prune -exec rm -rf '{}' +

FROM python:3.14.6-alpine

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LITELLM_LOCAL_MODEL_COST_MAP=true \
    SPARQL_ENDPOINT=/demo \
    AGENTS_DIR=/app

WORKDIR /app

COPY --from=dependencies /install /usr/local
COPY sparql_agent ./sparql_agent
COPY demo /demo

EXPOSE 8000
CMD ["uvicorn", "sparql_agent.web:app", "--host", "0.0.0.0", "--port", "8000"]
