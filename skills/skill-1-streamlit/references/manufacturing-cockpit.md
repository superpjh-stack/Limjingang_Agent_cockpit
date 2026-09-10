# Manufacturing cockpit reference

## Suggested document set

Use ten starter documents: full process flow, estimating and cost, drawing-change control, incoming inspection, material shortage and substitution approval, laser-cutting standard, forming quality cases, welding/assembly inspection, FAT checklist, and delay-response cases.

Each document is a Markdown file whose header lists document number, revision, scope, owner, effective date, status, and search keywords, followed by purpose, procedure, and a "DB 연결 예시" section that names the concrete project, LOT, PO, or operation IDs the document explains. The file stem prefix (for example `KGT-KB-005`) becomes the document ID, so rules can reference documents by that ID. Mark sample documents as unapproved examples in both the header and the status column.

## Suggested rule set

Start with seven or more rules covering material shortage, expected purchase delay, drawing approval pending, delayed operation, plan-hours overrun, FAT failure, and incoming-inspection hold. Each rule should link to its source document and state owner plus next action. Keep rules in a `rules.json` beside the documents with fields `rule_id`, `name`, `source_table`, `condition`, `owner`, `action`, `source_document`, `revision`, `status`; a test should assert every `source_document` matches a stored document ID.

## Data backend and migration conventions

Prefer local PostgreSQL with the `vector` extension for the operational backend. Keep a whitelist of browseable table names. Never interpolate an arbitrary user-provided table name into SQL. Validate page size and offset, use deterministic ordering, and return dictionaries for UI tables. Use parameterized SQL and backend adapters so the same read-only tools can run against PostgreSQL or SQLite.

Implement the PostgreSQL repository as a subclass of the SQLite repository with a thin connection adapter that rewrites `?` placeholders and `INSERT OR IGNORE` into `%s` and `ON CONFLICT DO NOTHING`, returns dictionary rows that also accept integer indexing, and commits or rolls back on context exit. Select the backend from `DATABASE_URL` (or `POSTGRES_URL`) in one factory function so the app and tests share the same entry point.

Initialization order on PostgreSQL matters: open a connection without registering the pgvector adapter, run `CREATE EXTENSION IF NOT EXISTS vector`, commit, then run the shared schema and seed, then add the `embedding vector(1536)` and `embedding_model` columns and the HNSW cosine index. Close the raw connection if adapter registration raises. The fresh-database regression test reads `TEST_POSTGRES_ADMIN_URL`, creates a uniquely named database, asserts the `vector` type is absent before initialization and usable after, checks the index exists, checks a saved setting survives reopening, and drops the database in a `finally` block. It skips when the admin URL is unset so the default test run stays offline.

For SQLite → PostgreSQL migration, initialize the target schema first, then import projects, designs, materials, inspections, operations, equipment readings, quote predictions, purchase orders, FAT tests, claims, rules, knowledge documents, and settings. A replacement migration should clear target rows before loading the source so seed data and tables without unique constraints do not duplicate. Keep an append mode only when the caller explicitly wants to preserve target rows. Store optional 1536-dimensional document embeddings in `knowledge_documents.embedding`, register the pgvector adapter, and use cosine distance for nearest-neighbor search; retain lexical search as the no-embedding fallback.

Lexical search should tolerate Korean particles and spacing: tokenize on Hangul/alphanumeric runs, add character bigrams, drop terms shorter than two characters, score by term hits over filename plus body, and return the top five with document ID, filename, full text, and source label.

## Agent loop conventions

- Tool definitions are strict-schema function tools. Optional string parameters use `["string", "null"]` types and remain in `required`, so the model must pass `null` explicitly for "all".
- The registry maps tool names to repository methods. `execute` returns a JSON string: `{"status": "ok", "demo_data": true, "result": ...}` on success and `{"error": ..., "tool": ...}` on unknown tools or bad arguments. Never raise into the UI.
- The agent builds one tool list per question: registry tools plus a `file_search` tool when a vector store ID exists (include `file_search_call.results` so snippets are returned). Refuse to run when neither source is connected.
- Loop: create a response, merge cited filenames and search snippets from every round, execute all `function_call` items, send `function_call_output` items with `previous_response_id`, and stop when no calls remain. After the round cap, set `tool_choice` to `none` on the follow-up. Local `search_knowledge` results are merged into the same evidence list as File Search hits.
- The answer dataclass carries text, sources, evidence, response ID, invoked tool names, `searched_documents`, `tool_rounds`, and `knowledge_base_connected`. The UI stores these per message and renders an evidence expander plus a warning when no document search happened.
- Tests use fake `responses.create` objects built from `SimpleNamespace` to cover: a single function-call round, empty-question rejection, evidence retained from an earlier round, `searched_documents` false when File Search was not used, the round cap forcing a text answer, and local knowledge search populating evidence from a real SQLite repository.

## Session and settings conventions

Initialize session state once with the message list (welcome message), vector store ID loaded from persisted settings, uploaded file names, the Responses chain ID, `pending_question`, the active recommendation group, voice draft and digest, and an `agent_settings` dictionary (`api_key`, `model`, `max_results`) seeded from the server environment. The sidebar reads and writes only `agent_settings`. Use `st.form` with `clear_on_submit` for the override so a submitted key never lingers in the widget. Build the OpenAI client from the current settings on every run with the request timeout and retry bounds.

## Conversation surface conventions

Treat the chat as an operational console, not a generic panel. On desktop, separate it from tables with a charcoal or graphite surface, one warm accent line, a compact status header, and asymmetric message bubbles: the user's question is visually distinct from the assistant's evidence-backed response. Keep the assistant response surface light enough for Korean text and preserve an obvious disclosure for sources and Data Hub tools.

At mobile widths, prioritize the reading loop: message history, loading/error state, and the composer. Hide KPI, recommendation, knowledge-table, and secondary voice surfaces when they make the conversation hard to scan. Use a single radius scale, touch-sized controls, safe-area padding, and `min-height`/`100dvh` patterns that do not jump when the browser chrome changes. Target Streamlit's `st-key-*` container classes from CSS so layout rules survive widget re-renders; between roughly 640px and 1100px stack the three columns with the conversation first and add a sticky three-link jump navigation.

## Deployment conventions

- `Dockerfile`: `python:3.11-slim`, headless Streamlit on `0.0.0.0:8501`, install from `requirements.txt`, copy `app.py`, `assets/`, the agent package, `sample_docs/`, `scripts/`, and the demo SQLite file only.
- `docker-compose.yml`: `postgres` service from `pgvector/pgvector:pg17` with `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?...}`, a `pg_isready` healthcheck, and a named volume; `app` service built from the Dockerfile with `depends_on` on the healthy database, `DATABASE_URL` pointing at the `postgres` service, and `OPENAI_API_KEY`/`OPENAI_MODEL` from the host environment.
- Local development can run PostgreSQL 17 plus pgvector from Homebrew on a non-default port (the reference uses 55432) with `initdb` under `data/postgres`; keep that directory and its log out of git and the image.
- README must state: keys come from environment only, `.env` is never committed or baked into the image, how to rotate the server key on the host, and that the migration script is the way to move the SQLite demo into PostgreSQL.

## OpenAI audio boundary

Speech-to-text uses the configured OpenAI audio transcription client with Korean language context (a short domain prompt with company and process vocabulary improves recognition); text-to-speech uses the configured speech client and returns MP3 bytes for Streamlit audio playback. Reject empty or oversized recordings and empty or overlong answer text before calling the API. Keep OpenAI calls behind a small service class so the UI can be tested with a fake client.
