"""Generic SPARQL Google ADK agent."""

import warnings

# Current Google GenAI/ADK releases emit these from their own internals on
# Python 3.14. Keep other dependency and application warnings visible.
warnings.filterwarnings(
    "ignore",
    message="'_UnionGenericAlias' is deprecated.*",
    category=DeprecationWarning,
    module=r"google\.genai\.types",
)
warnings.filterwarnings(
    "ignore",
    message="BaseAgentConfig is deprecated.*",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"\[EXPERIMENTAL\] feature FeatureName\.PLUGGABLE_AUTH is enabled\.",
    category=UserWarning,
    module=r"google\.adk\.features\._feature_decorator",
)
warnings.filterwarnings(
    "ignore",
    message=r"\[EXPERIMENTAL\] InMemoryCredentialService: This feature is experimental.*",
    category=UserWarning,
    module=r"google\.adk\.cli\.fast_api",
)
warnings.filterwarnings(
    "ignore",
    message=r"\[EXPERIMENTAL\] BaseCredentialService: This feature is experimental.*",
    category=UserWarning,
    module=r"google\.adk\.auth\.credential_service\.in_memory_credential_service",
)

from sparql_agent.agent import root_agent

__all__ = ["root_agent"]
