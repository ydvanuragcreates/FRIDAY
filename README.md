# AI Coding Agent — Phase 4: Tool Calling

A FastAPI backend where Claude answers `POST /api/chat` using a LangGraph
workflow that can inspect the local codebase through three read-only tools
(`list_files`, `read_file`, `search_code`) before answering. Built
incrementally — no write/execute tools, no database, no auth, no MCP, no
Redis, no Docker yet.

## Project structure

```
app/
├── main.py                 # FastAPI app instance, mounts the router
├── api/
│   └── routes.py           # GET /health, POST /api/chat — stays thin
├── core/
│   ├── config.py           # Settings loaded from environment variables
│   ├── llm.py                # Shared ChatAnthropic factory, used by every node
│   └── workspace.py           # Workspace root resolution + path-traversal guard
├── models/
│   └── schemas.py          # Pydantic request/response models
├── prompts/
│   └── agent_prompts.py    # One prompt per node, incl. the tool-using agent's system prompt
├── tools/
│   ├── list_files.py        # Recursively list files under the workspace
│   ├── read_file.py          # Read one file's contents
│   └── search_code.py         # Grep-style text search across the workspace
├── graph/
│   ├── state.py             # GraphState — the typed dict that flows through the graph
│   ├── nodes.py              # planner, agent, tools, analyzer, responder node functions
│   └── graph.py                # StateGraph wiring, incl. the agent↔tools loop
└── services/
    └── agent_service.py     # Builds + invokes the compiled graph
tests/
├── test_agent_service.py   # Unit tests for the service (graph.invoke is mocked)
├── test_workspace.py        # Path-traversal-prevention tests
├── test_tools.py             # Tool behavior against a throwaway fixture workspace
└── test_graph_nodes.py        # Tool-execution node + conditional routing tests
requirements.txt
pyproject.toml              # pytest config
.env.example
```

## 1. Setup

Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Environment variables

Copy `.env.example` to `.env` and fill in your Anthropic API key:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key from https://console.anthropic.com/ |
| `ANTHROPIC_MODEL` | No | Model ID to use (defaults to `claude-opus-5`) |
| `WORKSPACE_ROOT` | No | Directory the agent's tools may read from (defaults to `.`, the current working directory). Tools cannot access anything outside this directory — see [Workspace safety](#workspace-safety). |

The app reads these via `pydantic-settings`, which loads `.env` automatically
— no need to `export` anything manually for local development.

## 3. Run the server

```bash
uvicorn app.main:app --reload
```

The API is now available at `http://127.0.0.1:8000`. Interactive docs (Swagger UI)
are auto-generated at `http://127.0.0.1:8000/docs`.

## 4. Test the endpoints

**Health check:**

```bash
curl http://127.0.0.1:8000/health
# {"status": "ok"}
```

**Chat (now with tool calling):**

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain how authentication works in this repository."}'
# {"response": "..."}
```

For a request like that, the agent will typically call `list_files` to see
what's in the project, `search_code` for terms like "auth"/"login", and
`read_file` on whatever looks relevant — then analyze what it found and
write an answer. You can also test interactively via the Swagger UI at
`/docs`.

## Workspace safety

Every tool call is resolved against `WORKSPACE_ROOT` and checked before any
filesystem access happens (`app/core/workspace.py`):

- Absolute paths are rejected outright.
- Every path is resolved to its canonical real path (`..` segments
  collapsed, symlinks followed) and must still land inside the workspace
  root — an escape attempt spelled any way (`../../etc/passwd`, a symlink
  planted inside the workspace, a drive-relative Windows path, etc.) fails
  this containment check and is rejected.
- Recursive walks (`list_files`, `search_code`) skip noise directories
  (`.git`, `node_modules`, `__pycache__`, `.venv`, etc.) and never follow
  symlinks while walking.
- Only `list_files`, `read_file`, and `search_code` exist — there is no
  write or shell-execution tool yet, so a compromised or misbehaving tool
  call can read but not modify anything.

## Error handling

If the graph fails anywhere (bad key, network issue, rate limit, a node
producing no output, etc.), `POST /api/chat` returns an HTTP `502` with a
JSON `detail` message instead of crashing the server. A failed individual
tool call (bad path, missing file) doesn't fail the request — it's reported
back to the agent as an error string so it can adjust and try again.

## 5. Run the tests

```bash
pytest
```

- `test_agent_service.py` mocks the compiled graph's `.invoke()`.
- `test_workspace.py` and `test_tools.py` exercise the real path-safety
  logic and real tool functions against a throwaway `tmp_path` fixture
  workspace — no API key or network access needed.
- `test_graph_nodes.py` exercises the tool-execution node and the
  agent/tools routing decision directly, without invoking the LLM.

## What's next (not in this phase)

`write_file`, shell/terminal execution, a database, authentication, MCP,
Redis, and Docker packaging are deliberately out of scope for this phase
and will be added incrementally in later phases.
