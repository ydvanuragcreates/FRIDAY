from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str
    anthropic_model: str = "claude-opus-5"

    # Directory the filesystem tools (list_files, read_file, search_code,
    # create_file, write_file) are allowed to touch. Defaults to the
    # current working directory.
    workspace_root: str = "."

    # Command run by the run_tests tool.
    test_command: str = "pytest"

    # Comma-separated allowlist of executables run_command/run_tests may
    # invoke. Anything not listed here is rejected — see
    # app/core/command_safety.py for the full validation story.
    allowed_commands: str = "pytest,python,python3,npm,node,yarn,pnpm,go,cargo,make"

    # Wall-clock ceiling for any single validated command.
    command_timeout_seconds: int = 30

    # How many times the fix-and-retest loop may retry after a test
    # failure before giving up and reporting failure to the user.
    max_retries: int = 3

    # Voyage AI powers embeddings for codebase RAG — Anthropic recommends
    # Voyage since Claude itself has no embeddings endpoint, and
    # voyage-code-3 is trained specifically for code retrieval. Only
    # required when indexing or semantic search is actually used.
    voyage_api_key: str | None = None
    embedding_model: str = "voyage-code-3"

    # Qdrant connection. If qdrant_url is unset, the vector store runs in
    # embedded/local mode against a directory on disk at qdrant_path — no
    # server required, so indexing works out of the box in dev and in
    # tests. Set qdrant_url (e.g. a Qdrant Cloud endpoint) for production.
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_path: str = ".qdrant_data"

    # The single-workspace agent (agent_service.py) always searches this
    # project's index — see README > "Project scope" for why project_id
    # is otherwise just an indexing-time namespace.
    default_project_id: str = "default"

    # PostgreSQL, via SQLAlchemy's async engine + asyncpg. Defaulted to a
    # plausible local value (not required) so importing Settings doesn't
    # blow up before a real database is configured — actual DB access
    # fails with a clear connection error at call time instead, same as
    # any other unset-integration case in this project.
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_coding_agent"

    # Echo SQL statements to stdout — useful for debugging, noisy otherwise.
    database_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance so the .env file is only parsed once."""
    return Settings()
