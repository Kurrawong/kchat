FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SPARQL_ENDPOINT=/demo \
    AGENTS_DIR=/app

WORKDIR /app

# Keep third-party dependencies in a layer that application and documentation
# changes do not invalidate.
COPY pyproject.toml ./
RUN python -c 'import subprocess, sys, tomllib; dependencies = tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]; subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", *dependencies])'

# The application runs directly from /app, so installing the local package is
# unnecessary. Source changes now only invalidate these inexpensive copy layers.
COPY sparql_agent ./sparql_agent
COPY demo /demo

EXPOSE 8000
CMD ["uvicorn", "sparql_agent.web:app", "--host", "0.0.0.0", "--port", "8000"]
