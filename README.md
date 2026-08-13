# AI Coding Agent — Phase 7: Database + Project Management

A FastAPI backend where a LangGraph workflow can answer questions about a
local codebase (`POST /api/chat`), modify it with a human-approval gate
(`POST /api/tasks`), semantically search it (Codebase RAG, Phase 6), and
now **persists every bit of that activity to PostgreSQL**: projects,
conversations, messages, and — the important part — a full record of each
agent execution as it actually happens (plan, every tool call, every code
change, every test result), not just the final answer saved after the
fact.

## Project structure

```
app/
├── main.py                    # FastAPI app instance, mounts the router
├── api/
│   ├── deps.py                  # get_current_user_id (mock-user dependency)
│   └── routes/                   # was one routes.py through Phase 6; split into a package
│       ├── chat.py                 # /health, /api/chat
│       ├── tasks.py                 # /api/tasks* (Phase 5's human-approval endpoints)
│       ├── indexing.py               # /api/projects/{project_id}/index (Phase 6 — string slug)
│       ├── projects.py                # /api/projects* (Phase 7 — DB-backed, UUID)
│       ├── conversations.py            # /api/projects/{id}/conversations, /api/conversations/*
│       └── executions.py                # /api/projects/{id}/executions, /api/executions/{id}
├── core/
│   ├── config.py                # Settings loaded from environment variables
│   ├── llm.py                    # Shared ChatAnthropic factory, used by every node
│   ├── workspace.py               # Workspace root resolution + path-traversal guard
│   ├── command_safety.py           # Allowlisted, validated, non-shell command execution
│   └── diff.py                      # Unified diff rendering for proposed file changes
├── models/
│   └── schemas.py                # Pydantic I/O models for chat/tasks/indexing (Phases 1–6,
│                                     unchanged) — separate from app/schemas/ below; see note
├── db/                            # PostgreSQL persistence (Phase 7)
│   ├── base.py                     # DeclarativeBase + naming convention + utcnow() helper
│   ├── database.py                  # async engine, session factory, get_db_session, session_scope
│   └── models/                       # SQLAlchemy 2.x models — one file per table
│       ├── user.py, project.py, conversation.py, message.py
│       └── execution.py, agent_plan.py, tool_call.py, code_change.py, test_result.py
├── schemas/                       # Pydantic I/O models for the DB-backed API (Phase 7)
│   ├── project.py, conversation.py, execution.py
├── repositories/                   # Data access only — no business rules (Phase 7)
│   ├── user_repository.py, project_repository.py
│   ├── conversation_repository.py, execution_repository.py
├── prompts/
│   └── agent_prompts.py          # One prompt per graph node
├── tools/
│   ├── list_files.py, read_file.py, search_code.py    # filesystem inspection
│   ├── semantic_code_search.py                          # meaning-based search (Phase 6)
│   ├── run_command.py, run_tests.py                       # validated command execution
│   └── create_file.py, write_file.py                        # the only write-capable tools
├── indexing/                     # Codebase RAG pipeline (Phase 6). Zero LangChain/
│   │                              # LangGraph imports anywhere in this package.
│   ├── languages.py, discovery.py, parsing.py, chunking.py
│   ├── embeddings.py, vector_store.py, indexer.py, retriever.py, factory.py
├── graph/
│   ├── state.py                  # GraphState — now carries project_id/conversation_id/execution_id
│   ├── nodes.py                    # Every node is async (Phase 7) — see "How LangGraph
│   │                                  talks to the database" below
│   └── graph.py                      # StateGraph wiring, incl. the human-approval interrupt
└── services/
    ├── agent_service.py          # Builds the graph, drives start/resume (now async),
    │                                 syncs executions.status as the run progresses
    ├── execution_recorder.py      # The ONLY bridge LangGraph nodes use to reach the DB
    ├── redaction.py                 # Scrubs secret-looking content before it's persisted
    ├── project_service.py, conversation_service.py, execution_service.py
    └── indexing_service.py        # Runs the indexing pipeline, translates errors for the route
alembic/                        # Migrations (Phase 7) — see "Alembic" below
├── env.py                        # Async-engine migration runner, driven by Settings.database_url
└── versions/2b783ae7a5ba_initial_schema.py   # The one migration: all 9 tables
alembic.ini
tests/
requirements.txt
pyproject.toml                 # pytest + pytest-asyncio config
.env.example
```

One naming note: `app/models/schemas.py` (Pydantic, Phases 1–6) and the
new `app/schemas/` (Pydantic, Phase 7) both hold request/response models
but for different endpoint families — kept separate rather than merged,
so Phase 7 doesn't touch working Phase 1–6 code for no functional reason.

## 1–2. Setup and environment variables

Same as before — create a venv, `pip install -r requirements.txt`, copy
`.env.example` to `.env` and fill in `ANTHROPIC_API_KEY`. Variables from
Phase 5:

| Variable | Default | Description |
|---|---|---|
| `TEST_COMMAND` | `pytest` | Command the `run_tests` tool executes. |
| `ALLOWED_COMMANDS` | `pytest,python,python3,npm,node,yarn,pnpm,go,cargo,make` | Comma-separated allowlist for `run_command`/`run_tests`. |
| `COMMAND_TIMEOUT_SECONDS` | `30` | Timeout for any single validated command. |
| `MAX_RETRIES` | `3` | How many times the fix-and-retest loop may retry after a failing test. |

New in Phase 6:

| Variable | Default | Description |
|---|---|---|
| `VOYAGE_API_KEY` | *(none)* | Required to actually index or semantically search — get one at https://www.voyageai.com/. Not required to run the server or use `/api/chat`/`/api/tasks` for non-search requests. |
| `EMBEDDING_MODEL` | `voyage-code-3` | Voyage model used for embeddings; trained specifically for code retrieval. |
| `QDRANT_URL` | *(none)* | Point at a real Qdrant deployment (e.g. Qdrant Cloud). If unset, Qdrant runs embedded, on disk — no server needed. |
| `QDRANT_API_KEY` | *(none)* | API key for `QDRANT_URL`, if it requires one. |
| `QDRANT_PATH` | `.qdrant_data` | On-disk directory for the embedded Qdrant instance, used when `QDRANT_URL` is unset. |
| `DEFAULT_PROJECT_ID` | `default` | The project the LangGraph agent's `semantic_code_search` tool searches — see "Project scope" below. |

New in Phase 7:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/ai_coding_agent` | PostgreSQL connection string. Format: `postgresql+asyncpg://user:password@host:port/database`. Never commit real credentials. |
| `DATABASE_ECHO` | `false` | Echo every SQL statement to stdout — useful for debugging, noisy otherwise. |

## 3. Run the server

```bash
uvicorn app.main:app --reload
```

## 4. The human-in-the-loop workflow

```
User request
 ↓
Planner                         (planner_node          -> plan)
 ↓
Repository analysis             (agent ⇄ tools loop, then analyzer_node -> analysis,
 ↓                                using read-only tools: list_files, read_file,
 ↓                                search_code, run_command, run_tests)
Implementation plan             (implementer_node       -> proposed_changes, with diffs)
 ↓
Human approval                  (graph pauses here — see "Pausing for approval" below)
 ↓
Code modification               (apply_changes_node     -> applied_changes)
 ↓
Run tests                       (run_tests_node         -> test_results)
 ↓
Test result
 ↓
 ┌───────────────┐
 │ Tests passed? │
 └───────┬───────┘
       Yes ↓ No
          ↓         Test failure
    Final response         ↓
  (responder_node)   Error analysis    (error_analysis_node -> diagnosis + new proposed_changes,
                            ↓            retry_count += 1)
                      Code fix         (code_fix_node -> applied_changes)
                            ↓
                      Run tests again  (loops back to run_tests_node)
```

If a request needs no code change at all (a pure question), `implementer`
proposes nothing and the graph skips straight to the final response — no
approval, no modification, no tests. If the human **rejects** the
proposed changes, `apply_changes` writes nothing and the graph also skips
straight to the final response. If tests keep failing after `MAX_RETRIES`
attempts, the loop stops and the final response reports the failure
instead of retrying forever.

### Pausing for approval

The graph is compiled with `interrupt_before=["apply_changes"]` and an
in-memory checkpointer (`MemorySaver`), keyed by a `thread_id` per task.
`POST /api/tasks` runs the graph up to that interrupt and returns the
plan, the repo analysis, and every `proposed_changes` entry (each with a
`diff` field) — nothing has touched disk yet. A human reviews that
response, then calls `POST /api/tasks/{thread_id}/decision` with
`{"approved": true|false}`, which resumes the graph from exactly where it
paused. `GET /api/tasks/{thread_id}` polls the current status without
submitting a decision.

```bash
# 1. Start a task
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"message": "Add a /api/version endpoint that returns the app version"}'
# -> {"thread_id": "...", "status": "awaiting_approval", "proposed_changes": [...], ...}

# 2. Review proposed_changes[*].diff, then approve or reject
curl -X POST http://127.0.0.1:8000/api/tasks/<thread_id>/decision \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
# -> {"status": "completed", "applied_changes": [...], "test_results": "...", "final_response": "..."}
```

`POST /api/chat` still works for pure Q&A (it runs the same graph and
returns `final_response` directly), but if a chat message turns out to
need a code change, it errors out pointing at the task endpoints instead
of silently modifying anything without approval.

## 5. Safety

- **Workspace containment.** Every tool — including the four new ones —
  resolves paths through `resolve_workspace_path` (`app/core/workspace.py`),
  which rejects absolute paths and anything that resolves outside
  `WORKSPACE_ROOT`, exactly as in Phase 4. `create_file`/`write_file` are
  bound by the same check before ever touching disk.
- **No arbitrary filesystem or command access.** `run_command`/`run_tests`
  never use a shell (`subprocess.run(..., shell=False)`); the executable
  must be on `ALLOWED_COMMANDS`, arguments are checked for shell
  metacharacters, absolute paths, and `..` traversal, and interpreters
  that accept inline-code flags (`python -c`, `node -e`, ...) have those
  flags blocked outright. See `app/core/command_safety.py`.
- **Destructive commands require explicit human approval — enforced as
  "never allowed" rather than "ask each time."** `rm`, `del`, `chmod`,
  `shutdown`, `sudo`, and similar are on a hard denylist that
  `ALLOWED_COMMANDS` cannot override. There's no reliable way for a human
  to give meaningful per-invocation sign-off on a single shell string, so
  the safer bound is that a human has to edit the source/config to permit
  one at all — a much higher bar than a single approve click. File
  modifications get the finer-grained treatment instead (next point),
  since those come with an actual diff to review.
- **Diffs before writes.** `create_file`/`write_file` are bound to the
  LLM only to capture *proposed* tool calls — `implementer_node` never
  invokes them for real. It reads each proposal's `file_path`/`content`,
  reads whatever's currently on disk (empty string if the file doesn't
  exist), and renders a unified diff (`app/core/diff.py`). Only
  `apply_changes_node`, after approval, calls the real tool functions.
- **Human approval gate.** Enforced structurally, not just by convention:
  `apply_changes` is the interrupted node, so the process cannot reach a
  disk write without a `POST .../decision` in between. Rejecting a task
  skips modification and testing entirely.
- **Bounded retries.** The fix-and-retest loop is capped by
  `MAX_RETRIES` (`route_after_tests` in `app/graph/nodes.py`), so a
  persistently-failing fix can't loop forever — it reports failure
  instead. The automatic retries stay within the scope of the single task
  the human already approved and don't re-prompt for approval per retry;
  see the "Bounded retries, not re-approved" note in `error_analysis_node`.

## 6. Why LangGraph for this workflow

- **Explicit, typed state instead of implicit context passed between
  function calls.** `GraphState` (`app/graph/state.py`) is the single
  source of truth for `plan`, `files_inspected`, `proposed_changes`,
  `applied_changes`, `test_results`, `errors`, `retry_count`, and
  `final_response`. Every node declares exactly which keys it reads and
  returns; nothing is passed around as loose function arguments or hidden
  in a class's mutable attributes, which matters once the workflow branches
  and loops as much as this one does.
- **Native pause/resume across process boundaries via checkpointing.**
  This workflow can't be a single synchronous function call — it has to
  stop and wait for a human, potentially minutes or hours later, in a
  *different* HTTP request. LangGraph's `interrupt_before` + a
  checkpointer (`MemorySaver`, keyed by `thread_id`) persists the entire
  state at the pause point and resumes exactly there with
  `graph.invoke(None, config)` once `update_state` records the decision.
  Building that by hand means either serializing partial state and coordinating
  it in a database, or making everything else in the codebase aware of
  a bespoke "task" abstraction just to survive that gap.
- **Conditional edges make the branching logic legible and enforced.**
  "No changes needed → skip to final response," "rejected → skip tests,"
  "tests failed but retries remain → error_analysis," "retries exhausted →
  give up" are each one small routing function
  (`route_after_implementer`, `route_after_apply`, `route_after_tests`)
  returning a next-node name — not a tangle of nested `if`/`else` spread
  across a monolithic handler.
- **Cycles are first-class, with a built-in circuit breaker.** Both loops
  in this graph — `agent ⇄ tools` during repository analysis, and
  `run_tests → error_analysis → code_fix → run_tests` during the
  fix-and-retest phase — are just edges that point backward. LangGraph's
  own recursion limit is a second, independent backstop underneath the
  domain-level `MAX_RETRIES` check, so a bug in the retry-counting logic
  still can't produce an infinite loop.
- **Composable with what Phases 1–4 already built.** `planner_node`,
  `agent_node`, `tool_node`, `analyzer_node`, and `responder_node` are
  unchanged from Phase 4 — Phase 5 adds five more nodes and two more
  conditional edges onto the same `StateGraph`. None of the existing
  nodes needed to know about approval, diffs, or retries to keep working.

## 7. Codebase RAG

### The indexing pipeline

```
Repository
 ↓
File discovery        (discovery.py — reuses the same workspace walk as
 ↓                      list_files/search_code; filters to known source
 ↓                      extensions, skips files over 500KB)
Code parsing           (parsing.py — ast for Python, exact function/class/
 ↓                      method spans; regex + brace-counting for JS/TS/
 ↓                      Java/Go/Rust/C/C++/C#/PHP/Kotlin/Scala; nothing
 ↓                      for any other language, which just means no units)
Chunking               (chunking.py — one chunk per parsed unit, split
 ↓                      further if it's over ~4000 characters with a
 ↓                      10-line overlap between pieces; whatever lines
 ↓                      aren't inside any unit — imports, constants, or an
 ↓                      entire unparsed file — become fixed 60-line
 ↓                      fallback chunks)
Metadata extraction    (chunking.py — every CodeChunk carries file_path,
 ↓                      language, a derived module path, symbol/symbol_type
 ↓                      when it came from a parsed unit, and line range)
Embeddings             (embeddings.py — Voyage AI's voyage-code-3; each
 ↓                      chunk is embedded with a small header — file path
 ↓                      + symbol — prepended for extra context, see
 ↓                      indexer.py:_embedding_text)
Qdrant                 (vector_store.py — one collection per project,
 ↓                      point ID derived deterministically from the
 ↓                      chunk's identity so re-indexing overwrites rather
 ↓                      than duplicates)
Retriever              (retriever.py — embeds a query the same way and
                         runs a similarity search against the project's
                         collection)
```

`app/indexing/indexer.py` (`CodebaseIndexer.index_path`) drives discovery
through Qdrant; `app/indexing/retriever.py` (`CodeRetriever.search`) is the
read side. Both are plain Python — see "Keep the vector store separate
from LangGraph" below.

```bash
curl -X POST http://127.0.0.1:8000/api/projects/default/index \
  -H "Content-Type: application/json" \
  -d '{"path": "."}'
# -> {"project_id": "default", "collection_name": "code_default",
#     "files_indexed": 41, "chunks_indexed": 187, "errors": []}
```

`path` (optional, defaults to `.`) is resolved the same way `list_files`
resolves its `directory` argument — relative to `WORKSPACE_ROOT`, rejecting
anything that escapes it. `project_id` must match `^[a-zA-Z0-9_-]{1,64}$`
(enforced in `vector_store.py`, returned as an HTTP 400 otherwise) since
it's used directly to name the Qdrant collection. Per-file failures (a
file that can't be decoded as UTF-8, for instance) are collected into the
response's `errors` list rather than failing the whole request.

### Project scope

The single-workspace agent (`/api/chat`, `/api/tasks`) always searches
`DEFAULT_PROJECT_ID`'s collection (default: `"default"`) — consistent with
every other tool in this project, which operates against the one
configured `WORKSPACE_ROOT` rather than a multi-tenant abstraction. Index
under a different `project_id` and its collection still exists and is
queryable via `CodeRetriever.search(project_id, ...)` directly; it's just
not what the LangGraph agent's `semantic_code_search` tool reaches for
without further wiring. A real multi-project deployment would thread
`project_id` through `GraphState` and the `/api/chat`/`/api/tasks` request
bodies — left out here to keep this phase's surface area focused on the
indexing/retrieval pipeline itself.

### Choosing between filesystem tools, semantic search, and direct reading

The agent has three ways to learn about the codebase during repository
analysis, each suited to a different kind of question (this is also
spelled out in `AGENT_SYSTEM_PROMPT`, `app/prompts/agent_prompts.py`):

| Tool | Use when | Because |
|---|---|---|
| `list_files` / `search_code` | You know precise text to look for — a function name, an error string, an import — or need a directory overview. | Exact, literal, and always reflects the current files on disk; no index to build or go stale. |
| `semantic_code_search` | You have a concept or question but not the exact wording — "where are retries capped," "how does the workspace containment check work" — especially somewhere unfamiliar where you can't guess the right literal search term. | Embedding similarity finds conceptually related code even when the wording differs. Trade-off: needs the project indexed first, returns chunked excerpts rather than full files, and can be stale if the index wasn't rebuilt after the last edit. |
| `read_file` | You've identified a specific file via either search above and need to act on it — especially before proposing any change. | The only one of the three that's guaranteed complete and current. Search tools return partial, possibly-stale excerpts; `read_file` is ground truth. |

The intended pattern is roughly: `list_files` for an overview,
`semantic_code_search` or `search_code` (whichever matches what you're
looking for — a concept vs. exact text) to find candidates, `read_file` to
confirm before relying on or modifying anything.

### Keep the vector store separate from LangGraph

`app/indexing/` has no LangChain or LangGraph imports anywhere in it —
`vector_store.py` only imports `qdrant_client`, `embeddings.py` only
imports `voyageai`, and `indexer.py`/`retriever.py` compose those two with
`discovery.py`/`parsing.py`/`chunking.py`, all plain Python. Two things sit
on either side of that boundary and bridge it deliberately:

- `app/tools/semantic_code_search.py` — the only place an `@tool`
  wraps `CodeRetriever`, for the LangGraph agent.
- `app/services/indexing_service.py` — the only place a FastAPI route
  calls into `CodebaseIndexer`, mirroring how `agent_service.py` keeps
  graph-building details out of `routes.py`.

This means the indexing/retrieval stack is independently usable (and
independently testable — see below) without an agent, a graph, or an LLM
tool-calling loop anywhere in the picture; and if the agent framework
changes later, the RAG pipeline underneath doesn't need to.

## 8. Database + Project Management

### Entity relationship diagram

```
users
  id (uuid, pk) · email · name · created_at · updated_at
    │ 1
    ▼ N
projects
  id (uuid, pk) · user_id (fk) · name · description
  repository_path · repository_url (nullable) · created_at · updated_at
    │
    ├─ 1───N ──► conversations
    │              id (uuid, pk) · project_id (fk) · title · created_at · updated_at
    │                │ 1
    │                ▼ N
    │              messages
    │                id (uuid, pk) · conversation_id (fk)
    │                role (user|assistant|system|tool) · content · created_at
    │
    └─ 1───N ──► executions
                   id (uuid, pk) · project_id (fk) · conversation_id (fk, nullable)
                   user_request · status · started_at · completed_at
                   error_message · retry_count
                     │
                     ├─ 1───N ──► agent_plans   (execution_id fk)
                     ├─ 1───N ──► tool_calls     (execution_id fk)
                     ├─ 1───N ──► code_changes    (execution_id fk)
                     └─ 1───N ──► test_results     (execution_id fk)
```

Repository *files* are never stored here — only `repository_path` (a
string pointing at a directory on the configured filesystem). Indexing
(Phase 6) reads and embeds those files directly; nothing about that
pipeline changed in this phase.

### What the database does and doesn't store

Persisted: users, projects, conversations, messages, executions, agent
plans, tool calls, code changes, and test results — the full shape asked
for. Not persisted, on purpose: source file contents (stay on the
filesystem under `WORKSPACE_ROOT`), API keys or other secrets (see
"Redaction" below), and the Qdrant vector index (a separate store,
unrelated identifier space — see "Project scope" above).

### Async database sessions in FastAPI — why they matter here

A synchronous DB driver blocks the thread it runs on for the full round
trip to Postgres. In a synchronous web framework that's usually fine —
each request already has its own worker thread. FastAPI's request
handlers, though, run on a single event loop by default; a blocking DB
call inside an `async def` route would freeze that event loop for every
other concurrent request, DB-bound or not, for as long as the query takes.
`asyncpg` + SQLAlchemy's async engine let a route `await` the query
instead — the event loop is free to serve other requests while the
network round trip to Postgres is in flight, and only resumes this one
once the result is ready. In this app it matters twice over: ordinary
CRUD routes (`app/api/routes/projects.py` etc.) `await session.execute(...)`
without blocking anything else, and — the more interesting case — the
LangGraph nodes that persist execution data (`app/graph/nodes.py`) run
`await record_tool_call(...)` mid-graph without stalling the server while
an LLM call or a subprocess is *also* in flight for a different request.

### Alembic

**Why migrations at all, instead of `Base.metadata.create_all()`:**
`create_all()` only ever adds tables/columns that don't exist — it has no
way to express "rename this column," "add NOT NULL to an existing
column with data already in it," or "drop this table." A migration is an
explicit, ordered, reviewable script for exactly those changes, applied
the same way in every environment (a teammate's laptop, staging,
production) instead of relying on each environment's schema having
organically arrived at the same shape.

**`alembic revision --autogenerate -m "message"`** diffs the current
database against `Base.metadata` (every model imported in
`app/db/models/__init__.py`) and writes a new file under
`alembic/versions/` with the `upgrade()`/`downgrade()` operations needed
to close that gap. It's a draft, not a guarantee — always read the
generated file before committing it; autogenerate can't infer a rename
(it sees a drop + an add) and doesn't know about non-schema changes like
seed data.

**`alembic upgrade head`** runs every migration between the database's
current revision (tracked in its own `alembic_version` table) and the
newest one, in order. `alembic downgrade base` runs every `downgrade()`
in reverse, back to an empty schema — used here to verify the initial
migration is actually reversible (see "Tests" below), not something
you'd run against a database with real data in it.

**Why not hand-edit a production database:** a manual `ALTER TABLE` run
directly against production leaves no record anywhere else — not in
`alembic_version`, not in git, not on any other environment. The next
`alembic upgrade head` elsewhere won't know that change happened, so
environments silently diverge; the next person to touch the schema has
no history to reconstruct what's actually there or why. A migration file
is that record: reviewable in the same PR as the model change, run
identically everywhere, and reversible.

The one migration in this repo (`alembic/versions/2b783ae7a5ba_initial_schema.py`)
was generated against a temporary SQLite database (this environment has no
Postgres server — see "Testing" below) and then verified with a real
`upgrade`/`downgrade` round trip. Its operations (`op.create_table`,
`sa.Enum(..., native_enum=False)`, `sa.JSON()`, ...) are dialect-agnostic
Alembic/SQLAlchemy calls, not SQLite-specific SQL, so it applies cleanly
to Postgres too.

### Project Management API

```bash
# Create a project (no auth yet — every project belongs to a fixed mock
# user, get-or-created on first use; see app/api/deps.py)
curl -X POST http://127.0.0.1:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "My FastAPI App", "description": "Backend project", "repository_path": "/workspace/my-fastapi-app"}'

curl http://127.0.0.1:8000/api/projects
curl http://127.0.0.1:8000/api/projects/<project_id>

curl -X PATCH http://127.0.0.1:8000/api/projects/<project_id> \
  -H "Content-Type: application/json" \
  -d '{"description": "updated description"}'

curl -X DELETE http://127.0.0.1:8000/api/projects/<project_id>
```

### Conversation API and the message-send request lifecycle

The spec's endpoint list (`POST`/`GET .../conversations`,
`GET /api/conversations/{id}`, `GET .../messages`) doesn't include a
"send a message" route, but the four numbered steps right after it
describe exactly one — so `POST /api/conversations/{conversation_id}/messages`
is added as the natural REST completion of that resource:

```bash
curl -X POST http://127.0.0.1:8000/api/projects/<project_id>/conversations \
  -H "Content-Type: application/json" -d '{"title": "Add JWT auth"}'

curl -X POST http://127.0.0.1:8000/api/conversations/<conversation_id>/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Add JWT authentication to this project"}'
# -> {"conversation_id": "...", "execution_id": "...", "status": "completed" | "awaiting_approval",
#     "user_message": {...}, "assistant_message": {...} | null}
```

Full lifecycle:

```
User → POST /api/conversations/{id}/messages
  │
  ▼
routes/conversations.py            (route — no queries here)
  │
  ▼
ConversationService.send_message
  │  1. verify the conversation exists (404 if not)
  │  2. save the user message
  │  3. create an execution row (status=pending), COMMIT now — see
  │     "Transactions" below for why this commit can't wait
  │
  ▼
AgentService.start_task(execution_id=...)     execution_id doubles as the
  │                                            LangGraph checkpointer thread_id
  ▼
graph.ainvoke(...)
  │
  ├─ planner_node        ─────► record_plan            (own DB session, commits)
  ├─ agent ⇄ tools loop   ────► record_tool_call × N     (own session per call)
  ├─ analyzer / implementer   (unchanged from Phase 5, no DB writes)
  │
  ├─[proposes changes]──► INTERRUPT before apply_changes
  │                        AgentService: executions.status = waiting_for_approval
  │                        → response: "approve via POST /api/tasks/{execution_id}/decision"
  │                                                    (Phase 5's endpoint, reused as-is)
  │
  └─[no changes needed, OR approved + resumed]
       ├─ apply_changes_node ─► record_code_change × N
       ├─ run_tests_node      ─► record_test_result + record_tool_call
       └─ responder_node        (final_response text, no DB write itself)
  │
  ▼
ConversationService (start_task has returned)
  │  4. if completed: save the assistant message
  │  5. AgentService already updated executions.status/completed_at
  │
  ▼
Response → User
```

If the message needs a code change, `assistant_message` comes back
`null` and `status` is `"awaiting_approval"` — call
`POST /api/tasks/{execution_id}/decision` (`{"approved": true|false}`,
same endpoint Phase 5 introduced) to resume it. **That resume path saves
the assistant's reply itself** (`execution_recorder.record_assistant_message`),
since it's reached directly and has no `ConversationService` call above
it to do that saving the way the non-paused path does.

### How LangGraph talks to the database

Three decisions matter more than the code:

1. **Every node in `app/graph/nodes.py` is `async def`, calling
   `.ainvoke()`.** Persisting mid-run means a node has to `await` a DB
   call, which requires the node itself to be a coroutine. Nodes with
   nothing to persist (`agent_node`, `analyzer_node`, `responder_node`)
   were converted too, uniformly, rather than leaving a confusing mix of
   blocking and non-blocking nodes in the same graph — see "Async
   database sessions" above for why a blocking node is a real problem
   now that a real connection pool shares the event loop. Tool
   implementations (`app/tools/*.py`) are untouched:
   `BaseTool.ainvoke()` runs a sync tool function in a thread
   automatically.
2. **All persistence goes through `app/services/execution_recorder.py`
   — never raw SQLAlchemy inside `nodes.py`.** `record_plan`,
   `record_tool_call`, `record_code_change`, `record_test_result`, and
   `update_execution_status` each open their own short-lived session,
   write, and commit. A node calls `await record_tool_call(execution_id, ...)`
   and never imports anything from `app.db`.
3. **`execution_id` doubles as the LangGraph checkpointer's `thread_id`.**
   Phase 5's approval pause already keys a run by `thread_id` in
   `MemorySaver`. Reusing the execution's own id as that key means the
   *existing* `/api/tasks/{thread_id}/decision` endpoint resumes a
   DB-tracked execution for free, with no second approval mechanism to
   build or keep in sync. `project_id`/`conversation_id`/`execution_id`
   are all `None` for the plain `/api/chat`/`/api/tasks` entry points
   (Phases 4/5) — every `record_*` call checks `execution_id` first and
   is a no-op when it's `None`, so those endpoints are completely
   unaffected by any of this.

One deliberate simplification: `code_changes` rows are written once, in
`apply_changes_node`/`code_fix_node`, at the point `diff`, `approved`, and
`applied` are all simultaneously known — not as an INSERT at proposal
time (`implementer_node`) followed by an UPDATE at apply time. Two-phase
would need a way to match a later "was it applied" row back to its
earlier "here's the diff" row for no real benefit, since nothing reads
the in-between "proposed, undecided" state from the database.

### Redaction

`execution_recorder.record_tool_call` runs every tool call's args/output
through `app/services/redaction.py` before it's persisted — a
`read_file` call on a `.env` file is the realistic way a real secret
would otherwise land verbatim in `tool_calls.output`. Filenames that look
like secrets (`.env`, `.pem`, `.key`, ...) get their whole output
replaced outright; everything else is scanned for known token shapes
(`sk-ant-...`, `AKIA...`, `ghp_...`, ...) and `KEY=value`-style lines
whose key name suggests a secret. Best-effort, not a guarantee — stated
plainly in the module's own docstring.

### Transactions

Two different patterns, for two different reasons:

- **Ordinary CRUD** (`app/api/routes/projects.py`, `conversations.py`,
  `executions.py`) uses one request-scoped session
  (`get_db_session` in `app/db/database.py`): commits automatically if
  the route handler returns normally, rolls back if anything raises.
  Standard FastAPI-with-SQLAlchemy pattern.
- **Execution persistence** (`execution_recorder.py`) deliberately does
  *not* share that session. A code-modifying execution can sit paused at
  the human-approval interrupt for minutes or hours, spanning two
  separate HTTP requests — holding one DB transaction open across that
  gap would mean an idle connection (and any locks it holds) checked out
  for an unbounded time, a real anti-pattern. So every persistence call
  is its own short transaction: open a session, write, commit, close.
  This is also why `ConversationService.send_message` explicitly commits
  right after creating the execution row, *before* calling
  `agent_service.start_task(...)` — the graph's independent sessions
  need that row to already be committed (visible outside the
  request-scoped session/transaction) the moment they start writing
  against it via its foreign key.

### Execution History API

```bash
curl http://127.0.0.1:8000/api/projects/<project_id>/executions
curl http://127.0.0.1:8000/api/executions/<execution_id>
# -> {"id": "...", "status": "completed", "user_request": "...",
#     "agent_plans": [...], "tool_calls": [...], "code_changes": [...], "test_results": [...]}
```

### Error handling

- **Invalid project/conversation/execution id:** a malformed UUID in the
  path is rejected by FastAPI's own type coercion (`422`) before the
  route body runs at all; a well-formed but nonexistent id raises a
  `*NotFoundError` from the relevant service, mapped to `404`.
- **LangGraph / tool / test execution failures:** unchanged from Phase 5
  — `tool_node` catches a tool exception and reports it back to the model
  as an error string rather than crashing the graph; `run_tests_node`
  always returns a result either way. Now additionally persisted: a
  failing tool call becomes a `tool_calls` row with `status=error`, a
  failing test run becomes a `test_results` row with `passed=false`.
- **The graph itself raising** (an actual infrastructure failure — the
  Anthropic API erroring, a bug escaping a node): `AgentService` catches
  it, sets `executions.status = "failed"` with `error_message` and
  `completed_at`, and re-raises as `AgentServiceError` → HTTP `502`.
  Nothing is silently swallowed — see
  `tests/test_execution_lifecycle.py::test_graph_failure_marks_execution_failed_with_error_message`.

## 9. Testing without a local Postgres server

This development environment has no PostgreSQL server (and no Docker),
so `tests/conftest.py`'s `db_engine` fixture points `DATABASE_URL` at a
fresh SQLite file (via `aiosqlite`) per test instead. The models avoid
Postgres-only types specifically so this substitution is meaningful, not
just convenient: `sqlalchemy.Uuid`, `JSON`, and `Enum(..., native_enum=False)`
all compile to equivalent, working DDL on both dialects. Run the suite
against a real Postgres before deploying — the SQL SQLAlchemy generates
for both dialects is close but not identical (e.g. `RETURNING` behavior,
`JSON` vs `JSONB` operators if that's ever adopted).

## 10. Run the tests

```bash
pytest
```

New in Phase 5:
- `test_command_safety.py` — allowlist/denylist/shell-metacharacter/
  traversal validation, plus one real subprocess execution.
- `test_diff.py` — unified diff rendering.
- `test_tools.py` — extended with `create_file`, `write_file`,
  `run_command`, `run_tests` against a throwaway `tmp_path` workspace.
- `test_graph_nodes.py` — extended with the implementer, apply_changes,
  run_tests, and code_fix nodes, plus every new conditional edge,
  including the retry-limit boundary. LLM calls are stubbed with a
  minimal `Runnable` fake so no network access is needed.
- `test_agent_service.py` — the `start_task` / `submit_decision` /
  `get_task_status` interface, mocking the compiled graph's
  `aget_state`/`aupdate_state`/`ainvoke` (Phase 7: these became async —
  see "How LangGraph talks to the database").

New in Phase 6:
- `test_indexing_languages.py`, `test_indexing_parsing.py`,
  `test_indexing_chunking.py`, `test_indexing_discovery.py` — the
  pipeline stages that are pure text/AST/regex logic, no external
  services involved.
- `test_vector_store.py` — real `qdrant_client` calls against an
  embedded `:memory:` instance: collection lifecycle, upsert idempotency
  (re-upserting a chunk overwrites its point rather than duplicating),
  language-filtered search, project-id validation.
- `test_embeddings.py` — `VoyageEmbeddingProvider`'s own logic (missing
  API key, model-to-dimension mapping); never calls the real Voyage API.
- `test_indexing_pipeline.py` — `CodebaseIndexer`/`CodeRetriever`
  end-to-end against a `tmp_path` workspace and the in-memory vector
  store, using a small deterministic hash-based `FakeEmbeddingProvider`
  in place of Voyage.
- `test_semantic_code_search_tool.py` — the tool's result formatting and
  its `ProjectNotIndexedError`/`EmbeddingProviderError` handling, with
  `get_retriever` monkeypatched to a fake.
- `test_routes_indexing.py` — `POST /api/projects/{project_id}/index` via
  FastAPI's `TestClient`, with `get_indexing_service` overridden through
  `app.dependency_overrides`.

New in Phase 7 (all run against SQLite via the `db_engine`/`db_session`/
`client` fixtures in `tests/conftest.py` — see "Testing without a local
Postgres server" above):
- `test_repositories.py` — CRUD + relationship loading for every
  repository directly against the ORM.
- `test_redaction.py` — token-shape and `.env`-style pattern matching,
  and the "whole output replaced" path for secret-looking filenames.
- `test_execution_recorder.py` — every `record_*`/`update_execution_status`
  function against a real (SQLite) database, including that
  `record_tool_call` actually redacts before the row is written.
- `test_api_projects.py` — the full project CRUD surface via FastAPI's
  `TestClient`: create/list/get/patch/delete, 404s, and the 422 FastAPI
  produces for a malformed UUID before any route code runs.
- `test_api_conversations.py` — conversation/message CRUD plus a full
  `POST .../messages` round trip through the real (async, now-persisting)
  graph, with the LLM stubbed via the same `Runnable`-fake pattern Phase 5
  established — the fake instance is constructed *once* and shared across
  the whole graph run (a per-node-call fresh instance would reset the
  response queue every time; see the comment in the test for the exact
  failure mode this caused during development).
- `test_execution_lifecycle.py` — the scenario Phase 7 is really about:
  a code-modifying message pauses for approval with the plan already
  persisted and nothing written to disk yet; approving resumes, writes
  the file, runs tests, and persists all of it; rejecting persists the
  rejection without writing or testing; and a simulated graph failure
  ends with `executions.status = "failed"` and a real `error_message`,
  never silently dropped.

No API key, no network access, and no local Postgres/Qdrant/Voyage
service is needed for any of the tests — the real LLM is stubbed, Qdrant
runs embedded, embeddings are faked, and Postgres is substituted with
SQLite for this environment (see "Testing without a local Postgres
server").

## 11. Quick reference

**1. Installation**

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in ANTHROPIC_API_KEY and DATABASE_URL
```

**2. PostgreSQL setup** (any of these — pick what's available)

```bash
# Local install (Debian/Ubuntu example)
sudo apt install postgresql
sudo -u postgres createuser --superuser $(whoami)
createdb ai_coding_agent

# Or Docker, if you have it (this project doesn't require it elsewhere)
docker run --name ai-coding-agent-db -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=ai_coding_agent -p 5432:5432 -d postgres:16
```

Then point `DATABASE_URL` in `.env` at it — the placeholder default
already matches the Docker example above.

**3. Environment variables** — see the tables under "Setup and
environment variables" and "Database + Project Management" further up;
`ANTHROPIC_API_KEY` and `DATABASE_URL` are the two you need before
anything will run.

**4. Alembic commands**

```bash
alembic upgrade head              # apply all migrations — run this after setup
alembic downgrade base            # roll back to an empty schema
alembic revision --autogenerate -m "description"   # generate a new migration
                                                     # after changing app/db/models/
alembic current                   # show the database's current revision
alembic history                   # list all migrations in order
```

**5. Start FastAPI**

```bash
uvicorn app.main:app --reload
```

**6. API examples** — see the `curl` blocks under "Project Management
API," "Conversation API," and "Execution History API" above for the full
set; the shortest end-to-end path is: create a project, create a
conversation on it, `POST` a message, then `GET` the execution it
returned to see everything that got persisted.

**7. Tests**

```bash
pytest              # everything — no Postgres, no API keys, no network needed
pytest tests/test_execution_lifecycle.py -v   # just the Phase 7 integration tests
```

**8. Common errors and how to debug them**

| Symptom | Cause | Fix |
|---|---|---|
| `pydantic_core.ValidationError: anthropic_api_key Field required` | `.env` missing or `ANTHROPIC_API_KEY` unset | Copy `.env.example` to `.env` and fill it in. |
| `sqlalchemy.exc.OperationalError: connection refused` (or similar, on `alembic upgrade head` / server start) | Postgres isn't running, or `DATABASE_URL` points at the wrong host/port | Confirm Postgres is up (`pg_isready`) and `DATABASE_URL` matches how you started it. |
| `MissingGreenlet: greenlet_spawn has not been called` | A model attribute populated only by a DB-server default (`server_default`) was read after the session already returned, with `expire_on_commit=False` in effect | Already fixed at the model level (`app/db/base.py:utcnow`, applied to every timestamp column) — if you add a new server-defaulted column, give it a matching Python-side `default=`/`onupdate=` too, or `await session.refresh(obj)` before returning it. |
| `alembic.util.exc.CommandError: Target database is not up to date` | Migrations exist that haven't been applied yet | `alembic upgrade head`. |
| A `POST /api/conversations/{id}/messages` for a code change never returns an `assistant_message` | Expected — it paused for approval (`status: "awaiting_approval"`) | `POST /api/tasks/{execution_id}/decision` with `{"approved": true}` (or `false`) to resume it. |
| `HTTPException 502` from `/api/chat` mentioning "needs human approval" | `/api/chat` has no approval step of its own; the request proposed a code change | Use `POST /api/tasks` (or the conversation flow) instead of `/api/chat` for anything that might modify files — see Phase 5's README section. |
| Tests fail with an SQLite-specific error after changing a model | A new column uses a Postgres-only type (e.g. `JSONB`, `ARRAY`) | Either stick to portable types (`JSON`, `Uuid`, `Enum(native_enum=False)`, as every existing column does) or accept that the automated suite here can't exercise that column — see "Testing without a local Postgres server." |
